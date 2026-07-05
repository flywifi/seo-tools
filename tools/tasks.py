#!/usr/bin/env python3
"""
Creator OS project task and obligation tracker (offline compute lane).

Deterministic, stdlib-only records + state machine + scheduling for the tasks a brand deal generates. The
model never spends tokens on this math. Every task cites a real source (anti-phantom rule); history[] is an
append-only event log and status is a fold over it; nothing is sent or invoiced automatically. Reuses the
business-day date math in tools/obligations.py. See shared/tasks-engine.md.

This module is built in chunks: core records + state machine + store adapter (here), scheduling, recurrence
+ waiting-on + billable, and .ics export are added by later sections.

Usage:
  python3 tools/tasks.py --selftest
  python3 tools/tasks.py scan [--register PATH] [--today YYYY-MM-DD]
  python3 tools/tasks.py manifest
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obligations as _ob  # type: ignore  # reuse business-day date math

ROOT = Path(os.environ.get("CREATOR_OS_ROOT", str(Path(__file__).resolve().parent.parent)))
CONFIG_PATH = ROOT / "creator-os-config.json"
CONFIG_LOCAL_PATH = ROOT / "creator-os-config.local.json"
REGISTER_PATH = ROOT / "pipeline" / "user-context" / "task-register.local.json"
MANIFEST_PATH = ROOT / "tasks-bucket.manifest.json"

BOUNDARY = (
    "ORGANIZATIONAL TRACKING, NOT LEGAL, FINANCIAL, OR COMPLIANCE ADVICE. Verify dates and tasks against "
    "the contract and counterparty. Nothing is sent, filed, invoiced, or posted automatically."
)

# ── enums (validated against frozensets; no schema library needed) ────────────
OPEN_STATES = frozenset({"not_started", "in_progress", "waiting_external", "blocked", "deferred"})
CLOSED_STATES = frozenset({"done", "cancelled"})
STATES = OPEN_STATES | CLOSED_STATES
TASK_KINDS = frozenset({"next_action", "waiting_on", "agenda", "milestone"})
PARTIES = frozenset({"creator", "brand", "agency", "platform", "other"})
PRIORITIES = frozenset({"H", "M", "L"})
SOURCE_KINDS = frozenset({"document", "event_derived", "user_stated"})
DUE_SOON_BUSINESS_DAYS = 3

ALLOWED_TRANSITIONS = {
    "not_started": {"in_progress", "waiting_external", "blocked", "deferred", "cancelled"},
    "in_progress": {"waiting_external", "blocked", "done", "deferred", "cancelled"},
    "waiting_external": {"in_progress", "blocked", "done", "cancelled"},
    "blocked": {"not_started", "in_progress", "cancelled"},
    "deferred": {"not_started", "cancelled"},
    "done": set(),       # terminal; reopen is an explicit logged action (reopen())
    "cancelled": set(),
}


# ── config / flag gate (repo pattern) ─────────────────────────────────────────
def load_config() -> dict:
    base: dict = {}
    try:
        base = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    if CONFIG_LOCAL_PATH.exists():
        try:
            local = json.loads(CONFIG_LOCAL_PATH.read_text(encoding="utf-8"))
            for k, v in local.get("capabilities", {}).items():
                base.setdefault("capabilities", {})[k] = v
        except (OSError, json.JSONDecodeError):
            pass
    return base


def flag_enabled(config: dict, name: str) -> bool:
    caps = config.get("capabilities", {}) if isinstance(config, dict) else {}
    meta = caps.get(name)
    if isinstance(meta, dict):
        return bool(meta.get("enabled", False))
    return bool(meta)


# ── business-day helpers (reuse obligations holidays; numpy busday roll semantics) ──
def _roll(d: date, forward: bool) -> date:
    step = timedelta(days=1 if forward else -1)
    while not _ob.is_business_day(d):
        d += step
    return d


def add_business_days(d: date, n: int) -> date:
    """Add n business days (negative = subtract). Rolls the input to a valid day first, then steps."""
    forward = n >= 0
    d = _roll(d, forward)
    step = timedelta(days=1 if forward else -1)
    remaining = abs(n)
    while remaining > 0:
        d += step
        while not _ob.is_business_day(d):
            d += step
        remaining -= 1
    return d


def subtract_business_days(d: date, n: int) -> date:
    return add_business_days(d, -n)


def business_days_between(start: date, end: date) -> int:
    """Signed count of business days in the half-open interval, like numpy busday_count."""
    if start == end:
        return 0
    lo, hi, sign = (start, end, 1) if start < end else (end, start, -1)
    d, c = lo, 0
    while d < hi:
        if _ob.is_business_day(d):
            c += 1
        d += timedelta(days=1)
    return c * sign


# ── source validation (the anti-phantom rule) ─────────────────────────────────
def validate_source(source) -> list:
    """Return a list of problems; empty list means the source is well-formed for its kind."""
    if not isinstance(source, dict) or not source.get("kind"):
        return ["source missing or has no kind"]
    kind = source.get("kind")
    if kind not in SOURCE_KINDS:
        return [f"source.kind '{kind}' not one of {sorted(SOURCE_KINDS)}"]
    problems = []
    if kind == "document":
        ref = source.get("ref") or {}
        has_locator = bool(ref.get("contract_id") and ref.get("section")) or bool(ref.get("message_id"))
        if not has_locator:
            problems.append("document source needs ref.{contract_id+section} or ref.message_id")
        if not ref.get("quote"):
            problems.append("document source needs ref.quote (a verbatim excerpt)")
    elif kind == "event_derived":
        rule = source.get("rule") or {}
        if not rule.get("rule_id"):
            problems.append("event_derived source needs rule.rule_id")
        if not (rule.get("defined_in") or {}):
            problems.append("event_derived source needs rule.defined_in (a human artifact the rule traces to)")
        if not (source.get("anchor_event") or {}).get("value"):
            problems.append("event_derived source needs anchor_event.value")
    elif kind == "user_stated":
        if not source.get("statement"):
            problems.append("user_stated source needs a statement")
        if not source.get("stated_by"):
            problems.append("user_stated source needs stated_by")
    return problems


def validate_task(task) -> list:
    """Structural validation; returns a list of problems (empty = valid). Enforces the anti-phantom rule."""
    problems = []
    if not isinstance(task, dict):
        return ["task is not an object"]
    if not task.get("id"):
        problems.append("task has no id")
    if task.get("status") not in STATES:
        problems.append(f"status '{task.get('status')}' not one of {sorted(STATES)}")
    if task.get("task_kind") not in TASK_KINDS:
        problems.append(f"task_kind '{task.get('task_kind')}' invalid")
    if task.get("responsible_party") not in PARTIES:
        problems.append(f"responsible_party '{task.get('responsible_party')}' invalid")
    if task.get("priority") not in PRIORITIES:
        problems.append(f"priority '{task.get('priority')}' invalid")
    if task.get("status") in {"waiting_external", "blocked", "cancelled", "deferred"} and not task.get("status_reason"):
        problems.append(f"status '{task.get('status')}' requires a status_reason")
    problems += [f"source: {p}" for p in validate_source(task.get("source"))]
    if not task.get("history"):
        problems.append("task has no history (append-only event log is the source of truth)")
    return problems


# ── event log + folds ─────────────────────────────────────────────────────────
def _next_seq(history) -> int:
    return 1 + max((e.get("seq", 0) for e in history), default=0)


def make_event(history, event, actor, at, **fields) -> dict:
    ev = {"seq": _next_seq(history), "at": at, "actor": actor, "event": event}
    ev.update({k: v for k, v in fields.items() if v is not None})
    return ev


def fold_task(task) -> dict:
    """Recompute the projected fields (status, responsible_party, timestamps) from history[] (event log =
    source of truth). Idempotent; used after a union-merge of two divergent copies."""
    history = sorted(task.get("history", []), key=lambda e: e.get("seq", 0))
    status = None
    responsible = task.get("responsible_party")
    started = completed = updated = None
    for e in history:
        updated = e.get("at", updated)
        if e.get("to_status"):
            status = e["to_status"]
            if status == "in_progress" and not started:
                started = e.get("at")
            if status in CLOSED_STATES:
                completed = e.get("at")
            elif status not in CLOSED_STATES:
                completed = None  # reopened
        if e.get("responsible_party"):
            responsible = e["responsible_party"]
    if status is not None:
        task["status"] = status
    if responsible is not None:
        task["responsible_party"] = responsible
    task["started_at"] = started
    task["completed_at"] = completed
    task["updated_at"] = updated or task.get("updated_at")
    return task


def transition(task, to_status, by, at, note=None, source_ref=None) -> dict:
    """Append a state-changing event and re-fold. Validates the allowed-transition table. Raises ValueError
    on an illegal transition. The done-with-open-blockers guard lives in apply_transition (register-level)."""
    frm = task.get("status")
    if to_status not in STATES:
        raise ValueError(f"unknown status '{to_status}'")
    if to_status not in ALLOWED_TRANSITIONS.get(frm, set()):
        raise ValueError(f"illegal transition {frm} -> {to_status}")
    ev = make_event(task["history"], "transition", by, at,
                    from_status=frm, to_status=to_status, note=note, source_ref=source_ref)
    task["history"].append(ev)
    return fold_task(task)


def reopen(task, by, at, note=None) -> dict:
    """Explicit, logged reopen of a closed task -> in_progress (the only path out of a terminal state)."""
    if task.get("status") not in CLOSED_STATES:
        raise ValueError("reopen only applies to done/cancelled tasks")
    ev = make_event(task["history"], "reopen", by, at,
                    from_status=task["status"], to_status="in_progress", note=note)
    task["history"].append(ev)
    return fold_task(task)


# ── derived flags (never stored) ──────────────────────────────────────────────
def derived_flags(task, today: date) -> dict:
    status = task.get("status")
    is_closed = status in CLOSED_STATES
    due = _ob._parse_date(task.get("due_date"))
    defer = _ob._parse_date(task.get("defer_until"))
    blocked_open = bool(task.get("blocked_by"))  # register-level check refines this
    actionable = (status in {"not_started", "in_progress"}
                  and (defer is None or defer <= today)
                  and not blocked_open)
    flags = {
        "is_closed": is_closed,
        "is_overdue": bool(due and not is_closed and due < today),
        "is_due_soon": bool(due and not is_closed and 0 <= business_days_between(today, due) <= DUE_SOON_BUSINESS_DAYS),
        "is_actionable": actionable,
        "is_aging_wait": False,
        "urgency_band": _ob.urgency_band(due, today) if due else "unknown",
    }
    if status == "waiting_external":
        handoff = task.get("handoff") or {}
        rdue = _ob._parse_date(handoff.get("response_due_at"))
        flags["is_aging_wait"] = bool(rdue and rdue < today)
    return flags


# ── store adapter ─────────────────────────────────────────────────────────────
STORE_BACKENDS = frozenset({"local_fs", "google_drive", "remote_mcp"})


def _empty_register(deal_id=None, contract_ref=None) -> dict:
    return {
        "_boundary": BOUNDARY, "schema_version": "0.1.0",
        "deal_id": deal_id, "contract_ref": contract_ref,
        "computed_as_of": None, "task_count": 0, "status_counts": {},
        "tasks": [], "human_review_required": True,
        "generated_by": "tools/tasks.py", "last_computed": None,
    }


def load_register(backend="local_fs", path=None) -> dict:
    """Load the register through the selected store backend. Only local_fs is implemented here; the
    google_drive and remote_mcp backends are wired in later chunks (shared/integrations-engine.md)."""
    if backend == "local_fs":
        p = Path(path) if path else REGISTER_PATH
        if not p.exists():
            return _empty_register()
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"could not read task register: {exc}")
    if backend in STORE_BACKENDS:
        raise NotImplementedError(f"store backend '{backend}' is configured in a later chunk; use local_fs")
    raise ValueError(f"unknown store backend '{backend}'")


def save_register(register, backend="local_fs", path=None) -> str:
    if backend != "local_fs":
        raise NotImplementedError(f"store backend '{backend}' write is wired in a later chunk")
    p = Path(path) if path else REGISTER_PATH
    register["task_count"] = len(register.get("tasks", []))
    register["status_counts"] = _status_counts(register.get("tasks", []))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(register, indent=2) + "\n", encoding="utf-8")
    return str(p)


def _status_counts(tasks) -> dict:
    counts: dict = {}
    for t in tasks:
        counts[t.get("status")] = counts.get(t.get("status"), 0) + 1
    return counts


def merge_tasks(task_a, task_b) -> dict:
    """Union two divergent copies of the same task by event (seq, at, event, actor) and re-fold. This is
    why concurrent surfaces editing the shared store never clobber: history is append-only, so the merge is
    the union of events followed by a deterministic re-projection."""
    base = dict(task_a)
    seen = set()
    merged_events = []
    for e in list(task_a.get("history", [])) + list(task_b.get("history", [])):
        key = (e.get("seq"), e.get("at"), e.get("event"), e.get("actor"))
        if key in seen:
            continue
        seen.add(key)
        merged_events.append(e)
    merged_events.sort(key=lambda e: (e.get("seq", 0), str(e.get("at") or "")))
    # renumber seq densely to keep the log monotonic after a union of two independently-numbered logs
    for i, e in enumerate(merged_events, start=1):
        e["seq"] = i
    base["history"] = merged_events
    return fold_task(base)


def reconcile(register_a, register_b) -> dict:
    """Union-merge two register copies (e.g. Desktop and web edits of the same Drive store). Tasks present
    in both are event-merged; tasks unique to either are kept. Deterministic and idempotent."""
    by_id = {t.get("id"): t for t in register_a.get("tasks", [])}
    for t in register_b.get("tasks", []):
        tid = t.get("id")
        by_id[tid] = merge_tasks(by_id[tid], t) if tid in by_id else fold_task(dict(t))
    out = dict(register_a)
    out["tasks"] = list(by_id.values())
    out["task_count"] = len(out["tasks"])
    out["status_counts"] = _status_counts(out["tasks"])
    return out


# ── manifest / verify (sha256 bucket, mirrors obligations.py) ─────────────────
def manifest(path=None) -> dict:
    p = Path(path) if path else REGISTER_PATH
    entries = {}
    if p.exists():
        entries[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"tool": "tools/tasks.py", "bucket": "tasks", "entries": entries}


def verify(manifest_path) -> dict:
    try:
        m = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}
    current = manifest()
    ok = m.get("entries") == current.get("entries")
    return {"ok": ok, "expected": m.get("entries"), "actual": current.get("entries")}


# ── read-only scan ────────────────────────────────────────────────────────────
def scan(register, today: date) -> dict:
    tasks = register.get("tasks", [])
    open_ids = {t.get("id") for t in tasks if t.get("status") in OPEN_STATES}
    rows = []
    for t in tasks:
        f = derived_flags(t, today)
        # refine actionable with real blocker state (a blocker is "open" if still in the open bucket)
        if t.get("blocked_by"):
            f["is_actionable"] = f["is_actionable"] and not any(b in open_ids for b in t["blocked_by"])
        rows.append({
            "id": t.get("id"), "title": t.get("title"), "status": t.get("status"),
            "responsible_party": t.get("responsible_party"), "due_date": t.get("due_date"),
            **f,
        })
    return {
        "boundary": BOUNDARY,
        "as_of": today.isoformat(),
        "task_count": len(tasks),
        "status_counts": _status_counts(tasks),
        "waiting_on_counterparty": [r for r in rows if r["status"] == "waiting_external"],
        "i_owe": [r for r in rows if r["status"] in {"not_started", "in_progress", "blocked"}],
        "overdue": [r for r in rows if r["is_overdue"]],
        "due_soon": [r for r in rows if r["is_due_soon"]],
        "human_review_required": True,
    }


# ── task construction (used by later chunks + selftest) ───────────────────────
def make_task(id, title, source, project_id=None, contract_id=None, task_kind="next_action",
              responsible_party="creator", priority="M", at=None, by="user:creator", **extra) -> dict:
    at = at or date.today().isoformat()
    task = {
        "id": id, "schema_version": 1, "title": title,
        "project_id": project_id, "contract_id": contract_id, "obligation_id": None,
        "parent_id": None, "deliverable_ref": None, "task_kind": task_kind,
        "responsible_party": responsible_party, "party_ref": None, "accountable_party": None,
        "waiting_on_party": None, "status": "not_started", "status_reason": None,
        "blocked_by": [], "defer_until": None, "scheduled_date": None, "due_date": None,
        "expires_at": None, "trigger": None, "priority": priority, "tags": [],
        "recurrence_id": None, "occurrence_index": None, "handoff": None, "ping_pong": None,
        "source": source, "created_at": at, "updated_at": at, "started_at": None, "completed_at": None,
        "history": [],
    }
    task.update(extra)
    task["history"].append(make_event(task["history"], "task_created", by, at,
                                      to_status="not_started", source_ref=source))
    return fold_task(task)


# ── selftest ──────────────────────────────────────────────────────────────────
def selftest() -> int:
    failures = []

    def check(name, cond):
        if not cond:
            failures.append(name)

    doc_src = {"kind": "document", "ref": {"contract_id": "ctr1", "section": "4.2",
                                           "quote": "Creator delivers a draft within 7 business days of receipt."}}
    t = make_task("task_1", "Deliver draft", doc_src, project_id="deal_1", contract_id="ctr1")
    check("valid-task", validate_task(t) == [])
    check("initial-status", t["status"] == "not_started")

    # anti-phantom: a task with no source is rejected
    bad = make_task("task_x", "No source", {"kind": "document"}, project_id="deal_1")
    check("anti-phantom", any(p.startswith("source:") for p in validate_task(bad)))
    check("event-derived-needs-anchor", validate_source(
        {"kind": "event_derived", "rule": {"rule_id": "r1", "defined_in": {"contract_id": "c"}}}) != [])
    check("event-derived-ok", validate_source(
        {"kind": "event_derived", "rule": {"rule_id": "r1", "defined_in": {"contract_id": "c"}},
         "anchor_event": {"value": "2026-08-01"}}) == [])
    check("user-stated-ok", validate_source(
        {"kind": "user_stated", "statement": "client asked for an extra story", "stated_by": "user:creator"}) == [])

    # state machine
    transition(t, "in_progress", "user:creator", "2026-07-06")
    check("to-in-progress", t["status"] == "in_progress" and t["started_at"] == "2026-07-06")
    transition(t, "waiting_external", "user:creator", "2026-07-07", note="sent to brand",
               source_ref=doc_src)
    check("to-waiting", t["status"] == "waiting_external")
    try:
        transition(t, "done", "user:creator", "2026-07-08")  # legal from waiting_external
        check("waiting-to-done", t["status"] == "done" and t["completed_at"] == "2026-07-08")
    except ValueError:
        failures.append("waiting-to-done-raised")
    try:
        transition(t, "in_progress", "user:creator", "2026-07-09")  # illegal from done
        failures.append("illegal-transition-allowed")
    except ValueError:
        pass
    reopen(t, "user:creator", "2026-07-10", note="brand reversed")
    check("reopen", t["status"] == "in_progress" and t["completed_at"] is None)

    # business-day math
    check("add-bd", add_business_days(date(2026, 7, 13), 1) == date(2026, 7, 14))  # Mon +1 -> Tue
    check("sub-bd", subtract_business_days(date(2026, 7, 17), 1) == date(2026, 7, 16))  # Fri -1 -> Thu
    check("between-bd", business_days_between(date(2026, 7, 13), date(2026, 7, 20)) == 5)  # Mon..Fri
    check("bd-rolls-holiday", add_business_days(date(2026, 7, 2), 1) == date(2026, 7, 6))  # Thu +1 over Jul 3-5

    # derived flags
    t2 = make_task("task_2", "Overdue thing", doc_src, project_id="deal_1")
    t2["due_date"] = "2026-07-01"
    f = derived_flags(t2, date(2026, 7, 15))
    check("overdue-flag", f["is_overdue"] is True and f["is_closed"] is False)

    # event-log union-merge (concurrency safety): two divergent copies re-fold identically
    import copy
    a = copy.deepcopy(t2); b = copy.deepcopy(t2)
    transition(a, "in_progress", "user:web", "2026-07-11")
    transition(b, "in_progress", "user:desktop", "2026-07-11")
    merged = merge_tasks(a, b)
    check("merge-idempotent", merge_tasks(merged, merged)["history"] == merged["history"])
    check("merge-folds", merged["status"] == "in_progress")

    # reconcile two registers
    ra = {"tasks": [copy.deepcopy(t)]}; rb = {"tasks": [copy.deepcopy(t2)]}
    rec = reconcile(ra, rb)
    check("reconcile-union", rec["task_count"] == 2)

    n = 18
    print(f"selftest: {'PASS' if not failures else 'FAIL'} ({n - len(failures)} of {n} checks)")
    if failures:
        print("failed:", ", ".join(failures))
        return 1
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS offline task tracker")
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("scan"); p.add_argument("--register"); p.add_argument("--today")
    sub.add_parser("manifest")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.cmd == "scan":
        reg = load_register("local_fs", args.register)
        today = _ob._parse_date(args.today) or date.today()
        print(json.dumps(scan(reg, today), indent=2))
        return 0
    if args.cmd == "manifest":
        print(json.dumps(manifest(), indent=2))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
