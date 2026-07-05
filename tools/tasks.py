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


# ── scheduling: DAG forward/backward pass, reverse-plan, feasibility (CPM) ────
def _apply_offset(d: date, days: int, basis: str) -> date:
    return add_business_days(d, days) if basis == "business" else d + timedelta(days=days)


def _dag(tasks):
    """Predecessor map from blocked_by (finish-to-start) + trigger.after_task (a task predecessor)."""
    by_id = {t["id"]: t for t in tasks}
    preds = {tid: set() for tid in by_id}
    for t in tasks:
        tid = t["id"]
        for b in t.get("blocked_by") or []:
            if b in by_id:
                preds[tid].add(b)
        trg = t.get("trigger") or {}
        if trg.get("type") == "after_task" and trg.get("event_key") in by_id:
            preds[tid].add(trg["event_key"])
    return by_id, preds


def _topo(by_id, preds):
    from collections import deque
    indeg = {tid: len(preds[tid]) for tid in by_id}
    succ = {tid: [] for tid in by_id}
    for tid, ps in preds.items():
        for p in ps:
            succ[p].append(tid)
    q = deque([tid for tid in by_id if indeg[tid] == 0])
    order = []
    while q:
        n = q.popleft()
        order.append(n)
        for s in succ[n]:
            indeg[s] -= 1
            if indeg[s] == 0:
                q.append(s)
    if len(order) != len(by_id):
        raise ValueError("cycle in task dependency graph")
    return order, succ


def forward_schedule(tasks, events=None) -> dict:
    """Forward pass: earliest due for each task from its trigger (fixed | after_event | after_task) plus the
    finish-to-start constraint (not before any blocker's due). events maps event_key -> ISO date. Unresolved
    triggers leave the due null and add a gap, never a guessed date."""
    events = events or {}
    by_id, preds = _dag(tasks)
    order, _ = _topo(by_id, preds)
    due, gaps = {}, []
    for tid in order:
        t = by_id[tid]
        trg = t.get("trigger") or {}
        ttype = trg.get("type")
        base = None
        if ttype in (None, "fixed"):
            base = _ob._parse_date(t.get("due_date"))
        elif ttype == "after_event":
            evd = _ob._parse_date(events.get(trg.get("event_key")))
            if evd is not None:
                base = _apply_offset(evd, trg.get("offset_days") or 0, trg.get("offset_basis") or "calendar")
            else:
                gaps.append(f"{tid}: event '{trg.get('event_key')}' unresolved; due unknown")
        elif ttype == "after_task":
            pd = due.get(trg.get("event_key"))
            if pd is not None:
                base = _apply_offset(pd, trg.get("offset_days") or 0, trg.get("offset_basis") or "calendar")
            else:
                gaps.append(f"{tid}: predecessor '{trg.get('event_key')}' has no due yet")
        cand = [d for d in [base] + [due[b] for b in preds[tid] if due.get(b)] if d]
        due[tid] = max(cand) if cand else None
    return {"due": {k: (v.isoformat() if v else None) for k, v in due.items()}, "gaps": gaps}


def reverse_plan(tasks, deadline_task, deadline_date) -> dict:
    """Backward pass from a hard deadline on one task: the latest each upstream task must FINISH to hit it
    ('when must the product ship for a fixed publish date'). Propagates the per-edge lag backward."""
    by_id, preds = _dag(tasks)
    order, _ = _topo(by_id, preds)
    dd = _ob._parse_date(deadline_date)
    if dd is None or deadline_task not in by_id:
        return {"must_finish_by": {}, "gaps": [f"deadline task '{deadline_task}' or date invalid"]}
    must = {deadline_task: dd}
    for tid in reversed(order):
        my_latest = must.get(tid)
        if my_latest is None:
            continue
        trg = by_id[tid].get("trigger") or {}
        lag_pred = trg.get("event_key") if trg.get("type") == "after_task" else None
        lag, basis = trg.get("offset_days") or 0, trg.get("offset_basis") or "calendar"
        for p in preds[tid]:
            latest_p = _apply_offset(my_latest, -lag, basis) if p == lag_pred and lag else my_latest
            if p not in must or latest_p < must[p]:
                must[p] = latest_p
    return {"must_finish_by": {k: v.isoformat() for k, v in must.items()}, "gaps": []}


def feasibility(tasks, events, deadline_task, deadline_date) -> dict:
    """Compare earliest-possible (forward) against latest-allowed (backward). Any task whose earliest due is
    later than its must-finish-by has negative slack: the chain cannot fit the deadline. Surfaced, never
    silently dropped."""
    fwd = forward_schedule(tasks, events)["due"]
    rev = reverse_plan(tasks, deadline_task, deadline_date)["must_finish_by"]
    conflicts = []
    for tid, latest in rev.items():
        earliest = fwd.get(tid)
        if earliest and _ob._parse_date(earliest) > _ob._parse_date(latest):
            conflicts.append({
                "task": tid, "earliest_possible": earliest, "must_finish_by": latest,
                "slack_days": (_ob._parse_date(latest) - _ob._parse_date(earliest)).days,
            })
    return {"feasible": not conflicts, "conflicts": conflicts, "forward": fwd, "reverse": rev,
            "boundary": BOUNDARY}


# ── recurrence (RRULE subset; materialize on demand, never spawn-on-complete) ─
def _add_months(d: date, n: int) -> date:
    import calendar
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _add_freq(d: date, freq: str, interval: int) -> date:
    if freq == "DAILY":
        return d + timedelta(days=interval)
    if freq == "WEEKLY":
        return d + timedelta(weeks=interval)
    if freq == "MONTHLY":
        return _add_months(d, interval)
    return _add_months(d, 12 * interval)  # YEARLY


def rrule_dates(rule, cap=500):
    """Expand an RRULE-subset rule to concrete dates. FREQ/INTERVAL/COUNT-xor-UNTIL in stdlib; BYDAY defers
    to python-dateutil when present, else returns a gap (never guesses). Returns (dates, gaps)."""
    freq = rule.get("freq")
    interval = rule.get("interval") or 1
    count, until = rule.get("count"), _ob._parse_date(rule.get("until"))
    anchor = _ob._parse_date(rule.get("anchor_date"))
    if count and rule.get("until"):
        raise ValueError("RRULE count and until are mutually exclusive")
    if anchor is None or freq not in {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}:
        return [], ["recurrence rule needs a valid anchor_date and freq"]
    if rule.get("byday"):
        try:
            from dateutil import rrule as _rr  # optional
            FR = {"DAILY": _rr.DAILY, "WEEKLY": _rr.WEEKLY, "MONTHLY": _rr.MONTHLY, "YEARLY": _rr.YEARLY}
            wd = {"MO": _rr.MO, "TU": _rr.TU, "WE": _rr.WE, "TH": _rr.TH, "FR": _rr.FR, "SA": _rr.SA, "SU": _rr.SU}
            from datetime import datetime
            kwargs = {"interval": interval, "dtstart": datetime(anchor.year, anchor.month, anchor.day),
                      "byweekday": [wd[b] for b in rule["byday"] if b in wd]}
            if count:
                kwargs["count"] = count
            elif until:
                kwargs["until"] = datetime(until.year, until.month, until.day)
            else:
                kwargs["count"] = cap
            return [dt.date() for dt in _rr.rrule(FR[freq], **kwargs)], []
        except ImportError:
            return [], ["BYDAY recurrence needs python-dateutil; install it or drop byday"]
    out, d, i = [], anchor, 0
    while len(out) < (count or cap):
        if until and d > until:
            break
        out.append(d)
        d = _add_freq(d, freq, interval)
        i += 1
        if i > cap:
            break
    return out, []


def materialize_occurrences(rule_record, horizon_date, by="system:recurrence", now=None):
    """Create the concrete occurrence tasks due on or before horizon_date that have not been generated yet.
    Idempotent on (recurrence_id, occurrence_index) via the generation ledger; each occurrence inherits the
    template source (anti-phantom). Skips are handled by cancelling the occurrence, not by advancing here."""
    now = now or date.today().isoformat()
    rule = rule_record.get("rule", {})
    tmpl = rule_record.get("template", {})
    horizon = _ob._parse_date(horizon_date)
    dates, gaps = rrule_dates(rule)
    gen = rule_record.setdefault("generation", {"lookahead": 1, "last_generated_index": 0, "next_anchor": None})
    last = gen.get("last_generated_index", 0)
    off = tmpl.get("due_offset") or {}
    made = []
    for idx, d in enumerate(dates):
        if idx < last:
            continue
        if horizon and d > horizon:
            break
        due = _apply_offset(d, off.get("days") or 0, off.get("basis") or "calendar")
        src = dict(tmpl.get("source") or {"kind": "user_stated", "statement": "recurring duty",
                                          "stated_by": by})
        occ = make_task(f"{rule_record.get('id')}#{idx}", tmpl.get("title") or "Recurring task", src,
                        project_id=rule_record.get("project_id"), contract_id=rule_record.get("contract_id"),
                        task_kind=tmpl.get("task_kind") or "next_action",
                        responsible_party=tmpl.get("responsible_party") or "creator",
                        at=now, by=by,
                        recurrence_id=rule_record.get("id"), occurrence_index=idx,
                        obligation_id=rule_record.get("obligation_id"))
        occ["due_date"] = due.isoformat()
        made.append(occ)
        gen["last_generated_index"] = idx + 1
        nxt = dates[idx + 1] if idx + 1 < len(dates) else None
        gen["next_anchor"] = nxt.isoformat() if nxt else None
    return made, gaps


# ── waiting-on / nudge / approval ping-pong ───────────────────────────────────
def compute_handoff(handed_off_at, n_business_days):
    """Nudge at 80% of the response window, escalate at 50% past due (business-day aware)."""
    h = _ob._parse_date(handed_off_at)
    if h is None or not n_business_days:
        return {}
    response_due = add_business_days(h, n_business_days)
    window = business_days_between(h, response_due)
    return {
        "handed_off_at": handed_off_at,
        "expected_response_business_days": n_business_days,
        "response_due_at": response_due.isoformat(),
        "nudge_at": add_business_days(h, max(1, int(0.8 * window))).isoformat(),
        "escalate_at": add_business_days(response_due, max(1, (window + 1) // 2)).isoformat(),
        "nudge_count": 0,
    }


_PP_MAP = {  # event -> (target status, responsible party, stage, iteration delta)
    "submit": ("waiting_external", "brand", "awaiting_human_review", 0),
    "resubmit": ("waiting_external", "brand", "awaiting_human_review", 0),
    "request_changes": ("in_progress", "creator", "revision_queue", 1),
    "approve": ("done", "creator", "done", 0),
}


def advance_ping_pong(task, event, at, by="user:creator", handoff=None):
    """One hand-off in an approval/revision loop: flip responsible_party, count iterations, and move the
    status. Beyond max_iterations the cycle escalates. The party who owes the next move is responsible_party."""
    if event not in _PP_MAP:
        raise ValueError(f"unknown ping-pong event '{event}'")
    to_status, party, stage, delta = _PP_MAP[event]
    pp = task.get("ping_pong") or {"cycle_id": task.get("id"), "iteration": 0, "max_iterations": 5, "stage": "draft"}
    pp["iteration"] += delta
    pp["stage"] = "escalated" if pp["iteration"] > pp.get("max_iterations", 5) else stage
    task["ping_pong"] = pp
    if event in ("submit", "resubmit"):
        task["waiting_on_party"] = "brand"
        task["status_reason"] = "awaiting brand review"
        task["handoff"] = handoff or task.get("handoff")
    # move status through the validated transition, carrying the responsible-party flip on the event
    frm = task.get("status")
    if to_status in ALLOWED_TRANSITIONS.get(frm, set()):
        ev = make_event(task["history"], f"pingpong:{event}", by, at,
                        from_status=frm, to_status=to_status, responsible_party=party,
                        note=f"iteration {pp['iteration']}")
        task["history"].append(ev)
    else:
        task["history"].append(make_event(task["history"], f"pingpong:{event}", by, at, responsible_party=party))
    return fold_task(task)


# ── payment milestones -> billable readiness -> finance lane ──────────────────
def _billable_task(schedule, ms, at, by="system:billable"):
    trg = ms.get("trigger") or {}
    defined_in = (ms.get("source") or {}).get("ref") or {"contract_id": schedule.get("contract_ref")}
    src = {"kind": "event_derived",
           "rule": {"rule_id": f"bill_on_{trg.get('event') or trg.get('type')}", "defined_in": defined_in},
           "anchor_event": {"type": "deliverable_event", "value": at, "deliverable_id": trg.get("deliverable_id")}}
    task = make_task(f"bill_{ms.get('milestone_id')}", f"Invoice ready: {ms.get('label')}", src,
                     project_id=schedule.get("deal_id"), contract_id=schedule.get("contract_ref"),
                     task_kind="milestone", responsible_party="creator", at=at, by=by,
                     tags=["billable"], deliverable_ref=trg.get("deliverable_id"))
    task["_billing"] = {"amount": ms.get("amount"), "pct_of_total": ms.get("pct_of_total"),
                        "milestone_id": ms.get("milestone_id"), "net_terms_days": schedule.get("net_terms_days")}
    return task


def apply_deliverable_event(schedule, deliverable_id, event, at):
    """When a deliverable event fires (delivery/approval/publish), flip billable_ready on matching milestones
    and return the newly-billable milestones as citation-carrying billable tasks (proposals for the finance
    lane; nothing is invoiced or sent here). acceptance_required milestones only fire on 'approval'."""
    newly = []
    for ms in schedule.get("milestones", []):
        trg = ms.get("trigger") or {}
        if (trg.get("type") == "on_deliverable_event" and trg.get("deliverable_id") == deliverable_id
                and trg.get("event") == event):
            if ms.get("acceptance_required") and event != "approval":
                continue
            if not ms.get("billable_ready"):
                ms["billable_ready"] = True
                newly.append(_billable_task(schedule, ms, at))
    return newly


def billable_scan(schedule):
    ready = [ms for ms in schedule.get("milestones", []) if ms.get("billable_ready") and not ms.get("billed_invoice_id")]
    return {"boundary": BOUNDARY, "ready_to_bill": ready, "human_review_required": True}


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

    # scheduling: draft (7 cal days after product receipt) -> brand review (3 business days) -> post
    def trg(ttype, key, days, basis):
        return {"type": ttype, "event_key": key, "offset_days": days, "offset_basis": basis,
                "resolved": False, "source": doc_src}
    draft = make_task("draft", "Draft", doc_src, project_id="d", trigger=trg("after_event", "product_received", 7, "calendar"))
    review = make_task("review", "Review", doc_src, project_id="d", responsible_party="brand", trigger=trg("after_task", "draft", 3, "business"))
    post = make_task("post", "Post", doc_src, project_id="d", trigger=trg("after_task", "review", 0, "calendar"))
    chain = [draft, review, post]
    fwd = forward_schedule(chain, {"product_received": "2026-08-03"})["due"]
    check("fwd-draft", fwd["draft"] == "2026-08-10")     # Aug 3 + 7 calendar
    check("fwd-review", fwd["review"] == "2026-08-13")   # Aug 10 + 3 business
    rev = reverse_plan(chain, "post", "2026-08-14")["must_finish_by"]
    check("rev-draft", rev["draft"] == "2026-08-11")     # Aug 14 - 3 business
    check("feasible", feasibility(chain, {"product_received": "2026-08-03"}, "post", "2026-08-14")["feasible"] is True)
    bad = feasibility(chain, {"product_received": "2026-08-03"}, "post", "2026-08-11")
    check("infeasible", bad["feasible"] is False and any(c["task"] == "draft" for c in bad["conflicts"]))

    # recurrence: monthly, 3 occurrences, materialize-on-demand, idempotent, source inherited
    rr = {"id": "recur1", "project_id": "deal_1", "contract_id": "ctr1",
          "template": {"title": "Monthly report", "task_kind": "next_action", "responsible_party": "creator",
                       "due_offset": {"anchor": "period_start", "days": 5, "basis": "business"}, "source": doc_src},
          "rule": {"freq": "MONTHLY", "interval": 1, "count": 3, "until": None, "byday": None,
                   "anchor_date": "2026-07-01"},
          "generation": {"lookahead": 1, "last_generated_index": 0, "next_anchor": None}, "status": "active"}
    rdates, _ = rrule_dates(rr["rule"])
    check("rrule-monthly", [d.isoformat() for d in rdates] == ["2026-07-01", "2026-08-01", "2026-09-01"])
    try:
        rrule_dates({"freq": "MONTHLY", "count": 2, "until": "2026-12-01", "anchor_date": "2026-07-01"})
        failures.append("count-until-allowed")
    except ValueError:
        pass
    occ, _ = materialize_occurrences(rr, "2026-12-31", now="2026-07-01")
    check("materialize-3", len(occ) == 3 and occ[0]["occurrence_index"] == 0)
    check("occ-source-inherit", occ[0]["source"] == doc_src)
    check("occ-due-set", occ[2]["due_date"] is not None)
    occ2, _ = materialize_occurrences(rr, "2026-12-31", now="2026-07-01")
    check("materialize-idempotent", len(occ2) == 0)

    # waiting-on nudge/escalate math
    ho = compute_handoff("2026-08-03", 3)
    check("handoff-due", ho["response_due_at"] == "2026-08-06")
    check("handoff-nudge", ho["nudge_at"] == "2026-08-05")
    check("handoff-escalate", ho["escalate_at"] == "2026-08-10")

    # approval ping-pong: responsible_party flips, iteration counts
    wt = make_task("wt", "Reel approval", doc_src, project_id="deal_1")
    transition(wt, "in_progress", "user:creator", "2026-08-01")
    advance_ping_pong(wt, "submit", "2026-08-02", handoff=ho)
    check("pp-submit", wt["status"] == "waiting_external" and wt["responsible_party"] == "brand")
    advance_ping_pong(wt, "request_changes", "2026-08-05")
    check("pp-changes", wt["status"] == "in_progress" and wt["responsible_party"] == "creator" and wt["ping_pong"]["iteration"] == 1)
    advance_ping_pong(wt, "resubmit", "2026-08-06")
    advance_ping_pong(wt, "approve", "2026-08-08")
    check("pp-approve", wt["status"] == "done")

    # billable readiness on a deliverable approval
    sched = {"deal_id": "deal_1", "contract_ref": "ctr1", "net_terms_days": 30,
             "milestones": [{"milestone_id": "ms_final", "label": "Final approval", "amount": None,
                             "pct_of_total": 50, "acceptance_required": True, "billable_ready": False,
                             "trigger": {"type": "on_deliverable_event", "deliverable_id": "del_final", "event": "approval"},
                             "source": doc_src}]}
    check("billable-gated", apply_deliverable_event(sched, "del_final", "delivery", "2026-09-01") == []
          and sched["milestones"][0]["billable_ready"] is False)
    fired = apply_deliverable_event(sched, "del_final", "approval", "2026-09-01")
    check("billable-fires", len(fired) == 1 and sched["milestones"][0]["billable_ready"] is True)
    check("billable-source", validate_source(fired[0]["source"]) == [])

    n = 37
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
    p = sub.add_parser("plan")
    p.add_argument("--register"); p.add_argument("--events", help="JSON file mapping event_key -> ISO date")
    p.add_argument("--deadline-task"); p.add_argument("--deadline")
    sub.add_parser("manifest")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.cmd == "scan":
        reg = load_register("local_fs", args.register)
        today = _ob._parse_date(args.today) or date.today()
        print(json.dumps(scan(reg, today), indent=2))
        return 0
    if args.cmd == "plan":
        reg = load_register("local_fs", args.register)
        tasks = reg.get("tasks", [])
        events = {}
        if args.events:
            try:
                events = json.loads(Path(args.events).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(json.dumps({"error": f"could not read events file: {exc}"})); return 1
        if args.deadline_task and args.deadline:
            print(json.dumps(feasibility(tasks, events, args.deadline_task, args.deadline), indent=2))
        else:
            print(json.dumps(forward_schedule(tasks, events), indent=2))
        return 0
    if args.cmd == "manifest":
        print(json.dumps(manifest(), indent=2))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
