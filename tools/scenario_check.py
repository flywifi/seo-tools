#!/usr/bin/env python3
"""Realistic-scenario suite runner (P24).

Runs the cross-lane scenario contract in skills/creator-core/evals/scenarios.json against the
repo as it exists TODAY. Each scenario is a realistic creator utterance ("what's the email for
that guy from my Hearthline account?") pinned to (a) routing assertions against the live hub
routing table, (b) deterministic legs executed through the real product code (obligations date
math, transcript parsing, chapter fan-out, quality-gate arithmetic) on fictional fixtures, and
(c) a gap ledger of missing capabilities, each with a repo-state probe.

Findings-as-contract: the run FAILS if a leg assertion breaks, if a routing assertion breaks in
EITHER direction (a declared-absent classification appearing is as loud as a declared-present one
vanishing), or if a gap probe stops observing its gap. Closing a gap therefore forces a deliberate
update to scenarios.json and docs/SCENARIOS.md, never a silent drift.

Stdlib only. Deterministic (pinned clock in scenarios.json; override with --today/--year, which
demotes date-exact assertions to structural ones). Reads fixtures and product modules; writes
NOTHING anywhere. Evidence legs (evidence_for) are computed by this runner to demonstrate a gap's
raw material exists; they are labeled evidence, not product capability.

CLI:
  python3 tools/scenario_check.py [--json] [--scenario ID] [--today YYYY-MM-DD] [--year N]
  python3 tools/scenario_check.py --list
  python3 tools/scenario_check.py --selftest
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_PATH = ROOT / "skills" / "creator-core" / "evals" / "scenarios.json"
FIXTURES_DIR = ROOT / "skills" / "creator-core" / "evals" / "fixtures"
HUB_SKILL = ROOT / "skills" / "creator-core" / "SKILL.md"

sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "videoedit"))
sys.path.insert(0, str(ROOT / "shared" / "docintel"))
import obligations  # noqa: E402
import accounts  # noqa: E402
import chapters  # noqa: E402
import transcripts  # noqa: E402
import tasks as tasks_mod  # noqa: E402
import shipments as shipments_mod  # noqa: E402
import coverage_verify as coverage_mod  # noqa: E402
import finance as finance_mod  # noqa: E402
import doctemplates as doct_mod  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "qr_score", ROOT / "skills" / "quality-review" / "scripts" / "score.py"
)
qr_score = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qr_score)


# --------------------------------------------------------------------------- routing table

ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|[^|]*\|\s*`?([^`|]*?)`?\s*\|")


def parse_routing_table() -> dict:
    """{classification: spoke} from the hub's '### Classification routing table' section."""
    text = HUB_SKILL.read_text(encoding="utf-8")
    m = re.search(r"### Classification routing table\n(.*?)(?:\n### |\n## )", text, re.S)
    if not m:
        return {}
    table = {}
    for line in m.group(1).splitlines():
        row = ROW_RE.match(line.strip())
        if row and row.group(1).lower() != "classification":
            table[row.group(1).strip()] = row.group(2).strip()
    return table


def check_routing(routing: dict, table: dict) -> list:
    failures = []
    for pair in routing.get("present", []):
        cls, spoke = pair["classification"], pair["spoke"]
        if cls not in table:
            failures.append(f"routing: `{cls}` declared present but missing from the hub table")
        elif table[cls] != spoke:
            failures.append(f"routing: `{cls}` routes to `{table[cls]}`, expected `{spoke}`")
    for cls in routing.get("absent_classifications", []):
        if cls in table:
            failures.append(
                f"routing: `{cls}` declared ABSENT now appears in the hub table "
                f"(routes to `{table[cls]}`); update scenarios.json + docs/SCENARIOS.md deliberately"
            )
    return failures


# --------------------------------------------------------------------------- assert engine

def resolve_path(obj, path: str):
    """Dotted path with [i] indexing. Returns (found, value, parent, final_key)."""
    parent, key = None, None
    cur = obj
    if path == "":
        return True, cur, parent, key
    for part in path.split("."):
        m = re.match(r"^([^\[\]]*)((?:\[\d+\])*)$", part)
        if not m:
            return False, None, None, None
        name, indexes = m.group(1), m.group(2)
        if name:
            if not isinstance(cur, dict) or name not in cur:
                return False, None, cur, name
            parent, key = cur, name
            cur = cur[name]
        for idx in re.findall(r"\[(\d+)\]", indexes):
            i = int(idx)
            if not isinstance(cur, list) or i >= len(cur):
                return False, None, cur, i
            parent, key = cur, i
            cur = cur[i]
    return True, cur, parent, key


def check_assert(result, a: dict) -> str | None:
    """Returns a failure string, or None on pass."""
    path, check, value = a["path"], a["check"], a.get("value")
    found, actual, _, _ = resolve_path(result, path)
    if check == "absent_key":
        return None if not found else f"{path}: expected key absent, found {actual!r}"
    if not found:
        return f"{path}: path not found"
    if check == "eq":
        return None if actual == value else f"{path}: {actual!r} != {value!r}"
    if check == "ne":
        return None if actual != value else f"{path}: unexpectedly equals {value!r}"
    if check == "null":
        return None if actual is None else f"{path}: expected null, got {actual!r}"
    if check == "not_null":
        return None if actual is not None else f"{path}: expected non-null"
    if check == "contains":
        ok = (value in actual) if isinstance(actual, (list, str)) else (str(value) in str(actual))
        return None if ok else f"{path}: {value!r} not in {actual!r}"
    if check == "len_eq":
        return None if len(actual) == value else f"{path}: len {len(actual)} != {value}"
    if check == "len_gte":
        return None if len(actual) >= value else f"{path}: len {len(actual)} < {value}"
    if check == "gte":
        return None if actual >= value else f"{path}: {actual!r} < {value!r}"
    if check == "in":
        return None if actual in value else f"{path}: {actual!r} not in {value!r}"
    if check == "matches":
        return None if re.search(value, str(actual)) else f"{path}: {actual!r} !~ /{value}/"
    if check == "not_matches":
        return None if not re.search(value, str(actual)) else \
            f"{path}: unexpectedly matches /{value}/"
    return f"{path}: unknown check {check!r}"


# --------------------------------------------------------------------------- ops

def _fixture_path(name: str) -> Path:
    if name.startswith("repo:"):
        return ROOT / name[len("repo:"):]
    return FIXTURES_DIR / name


def _substitute_year(obj, year: int):
    if isinstance(obj, str):
        return obj.replace("{YEAR}", str(year))
    if isinstance(obj, list):
        return [_substitute_year(x, year) for x in obj]
    if isinstance(obj, dict):
        return {k: _substitute_year(v, year) for k, v in obj.items()}
    return obj


def _load_fixture(withp: dict, clock: dict):
    p = _fixture_path(withp["fixture"])
    if p.suffix == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        if withp.get("substitute_year"):
            data = _substitute_year(data, clock["year"])
        return data
    return str(p)


def op_json_load(withp, clock, prior):
    return _load_fixture(withp, clock)


def op_build_register(withp, clock, prior):
    data = _load_fixture(withp, clock)
    return obligations.build_register(data, clock["today"], clock["lead_days"])


def op_scan(withp, clock, prior):
    data = _load_fixture(withp, clock)
    return obligations.scan(data, clock["today"], clock["lead_days"])


def op_transcripts_parse(withp, clock, prior):
    return transcripts.parse(str(_fixture_path(withp["fixture"])))


def op_gap_metrics(withp, clock, prior):
    """Delegates to the product capability shared/docintel/transcripts.gap_metrics (P28)."""
    parsed = withp["parsed"]
    segs = parsed.get("segments", [])
    min_gap = float(withp.get("min_gap_seconds", 5.0))
    result = transcripts.gap_metrics(segs, min_gap)
    result["computed_by"] = "shared/docintel/transcripts.gap_metrics"
    return result


def op_fan_out(withp, clock, prior):
    return chapters.fan_out(_load_fixture(withp, clock))


def op_validate(withp, clock, prior):
    data = _load_fixture(withp, clock)
    ch = data.get("chapters", data) if isinstance(data, dict) else data
    return {"violations": chapters.validate(ch)}


def op_quality(withp, clock, prior):
    data = _load_fixture(withp, clock)
    scores = data[withp["key"]] if "key" in withp else data
    return qr_score.evaluate(scores)


def op_accounts_resolve(withp, clock, prior):
    """Delegates to the product capability tools/accounts.resolve (P32). Fixture-driven: the
    roster comes from a fixture so the runner never touches the local account store."""
    roster = _load_fixture({"fixture": withp["fixture"]}, clock)
    return accounts.resolve(withp["query"], accounts=roster)


def op_accounts_contacts(withp, clock, prior):
    roster = _load_fixture({"fixture": withp["fixture"]}, clock)
    return accounts.contacts(withp["query"], person=withp.get("person"), accounts=roster)


def op_accounts_deal_status(withp, clock, prior):
    roster = _load_fixture({"fixture": withp["fixture"]}, clock)
    deals = _load_fixture({"fixture": withp["deals"]}, clock)
    return accounts.deal_status(query=withp.get("query"), deal_id=withp.get("deal_id"),
                                deals=deals, accounts=roster)


def op_tasks_scan(withp, clock, prior):
    """Delegates to the product capability tools/tasks.scan (P35): the waiting-on vs I-owe split plus
    overdue/due-soon, computed offline from a fictional task register on the pinned clock."""
    register = _load_fixture({"fixture": withp["fixture"]}, clock)
    out = tasks_mod.scan(register, clock["today"])
    out["computed_by"] = "tools/tasks.py.scan"
    return out


def op_tasks_ping_pong(withp, clock, prior):
    """Delegates to tools/tasks.advance_ping_pong + apply_deliverable_event (P35). Runs one full
    two-party approval loop (creator submits, brand requests changes, creator resubmits, brand approves)
    and fires the deliverable-approval event that flips the payment milestone to billable-ready. Returns
    the folded end state plus the newly-billable, citation-carrying finance proposal."""
    fx = _load_fixture({"fixture": withp["fixture"]}, clock)
    task = fx["task"]
    schedule = fx["schedule"]
    at = fx.get("at", clock["today"].isoformat())
    tasks_mod.advance_ping_pong(task, "submit", at)
    tasks_mod.advance_ping_pong(task, "request_changes", at)
    tasks_mod.advance_ping_pong(task, "resubmit", at)
    folded = tasks_mod.advance_ping_pong(task, "approve", at)
    newly = tasks_mod.apply_deliverable_event(schedule, fx["deliverable_id"], "approval", at)
    bill = newly[0] if newly else {}
    return {
        "final_status": folded.get("status"),
        "final_responsible_party": folded.get("responsible_party"),
        "iteration": (task.get("ping_pong") or {}).get("iteration"),
        "billable_count": len(newly),
        "billable_task_id": bill.get("id"),
        "billable_source_kind": (bill.get("source") or {}).get("kind"),
        "billable_amount": (bill.get("_billing") or {}).get("amount"),
        "human_review_required": True,
        "computed_by": "tools/tasks.py.advance_ping_pong+apply_deliverable_event",
    }


def op_shipment_manual(withp, clock, prior):
    """Delegates to tools/shipments.manual_shipment + planning_anchor (P35): a manually-entered delivered
    shipment yields the immutable delivered_at backwards-planning anchor (not a provisional estimate)."""
    ship = shipments_mod.manual_shipment(
        tracking_number=withp.get("tracking_number"), carrier=withp.get("carrier"),
        status=withp.get("status", "delivered"), delivered_at=withp.get("delivered_at"),
        est_delivery=withp.get("est_delivery"), note=withp.get("note"),
        source_ref=withp.get("source_ref"), deal_id=withp.get("deal_id"))
    anchor = shipments_mod.planning_anchor(ship)
    return {"shipment": ship, "anchor": anchor, "computed_by": "tools/shipments.py.planning_anchor"}


def op_coverage_verify(withp, clock, prior):
    """Delegates to tools/coverage_verify.reconcile + verify_coverage (P35): reconcile N fictional media
    transcripts to a canonical truth, then verify the required talking points against it with an extractive
    citation per satisfied point, abstaining rather than inferring. Conflicts surface as a minority_report."""
    fx = _load_fixture({"fixture": withp["fixture"]}, clock)
    recon = coverage_mod.reconcile(fx["sources"])
    result = coverage_mod.verify_coverage(recon.get("canonical_text", ""), fx["required_points"],
                                          reconciliation=recon)
    result["reconciliation_conflicts"] = len(recon.get("conflicts", []))
    result["computed_by"] = "tools/coverage_verify.py.verify_coverage"
    return result


def _fixture_rate_card(withp):
    """Optional in-memory stand-in for the gitignored rate-card.local.json: a committed fictional
    fixture (never a tracked .local. file). Nothing is written anywhere."""
    if not withp.get("rate_card_fixture"):
        return None
    return json.loads(_fixture_path(withp["rate_card_fixture"]).read_text(encoding="utf-8"))


def op_finance_price(withp, clock, prior):
    """Delegates to tools/finance.proposal_price, mirroring the --price CLI handler (P40): rate-card
    format resolution, rate_floor_source provenance, and tier gaps."""
    p = _load_fixture(withp, clock) if "fixture" in withp else withp["payload"]
    card = _fixture_rate_card(withp)
    rate_floor = p.get("rate_floor")
    rate_floor_source = "payload" if rate_floor is not None else None
    extra_gaps = []
    if card is None and (rate_floor is None and p.get("format") or p.get("benchmark_range")):
        card, _src = finance_mod.load_rate_card()
    if rate_floor is None and p.get("format"):
        rate_floor, rc_gap = finance_mod.rate_floor_for(card, p["format"])
        if rate_floor is not None:
            rate_floor_source = "rate_card"
        elif rc_gap:
            extra_gaps.append(rc_gap)
    res = finance_mod.proposal_price(p.get("cost_total"), p.get("margin_percent"),
                                     rate_floor, p.get("benchmark_range"))
    res["rate_floor_source"] = rate_floor_source
    res["gaps"] = res.get("gaps", []) + extra_gaps + finance_mod._tier_gaps(
        card, p.get("benchmark_range"), p.get("benchmark_tier"))
    res["computed_by"] = "tools/finance.py.proposal_price"
    return res


def op_finance_price_package(withp, clock, prior):
    """Delegates to tools/finance.price_package (P40). With rate_card_fixture, the fictional card
    stands in for rate-card.local.json in memory only (restored in finally; no writes)."""
    p = _load_fixture(withp, clock) if "fixture" in withp else withp["payload"]
    card = _fixture_rate_card(withp)
    if card is not None:
        orig = finance_mod.load_rate_card
        finance_mod.load_rate_card = lambda root=None: (card, "local")
        try:
            return finance_mod.price_package(p)
        finally:
            finance_mod.load_rate_card = orig
    return finance_mod.price_package(p)


def op_doctemplates_validate(withp, clock, prior):
    """Delegates to tools/doctemplates.validate_template (P42). Fixture-driven; the filename
    argument controls starter-purity rules (fixtures use a .local.json name)."""
    tpl = _load_fixture(withp, clock)
    errors, warnings = doct_mod.validate_template(tpl, withp.get("as_filename", "fixture.local.json"))
    return {"errors": errors, "warnings": warnings, "computed_by": "tools/doctemplates.py.validate"}


def op_doctemplates_assemble(withp, clock, prior):
    """Delegates to tools/doctemplates.assemble (P42): structural selection resolution + bracket
    fills, all from committed fictional fixtures (profile via profile_fixture; nothing on-disk is
    read or written)."""
    tpl = _load_fixture(withp, clock)
    sources = {}
    if withp.get("profile_fixture"):
        sources["profile"] = _load_fixture({"fixture": withp["profile_fixture"]}, clock)
    return doct_mod.assemble(tpl, withp.get("selections") or {}, sources=sources,
                             fills=withp.get("fills") or {})


def op_content_import_analyze(withp, clock, prior):
    """Delegates to the P45 content-import lane end to end on fictional fixtures, writing nothing to
    disk (an in-memory SQLite store). Parses a YouTube Studio CSV (the ONLY revenue source) via
    tools/import_parse.parse_youtube_studio_csv and an Instagram DYI export via parse_instagram_dyi,
    attaches a synthetic YouTube retention array (representing the Analytics API leg) to the first YT
    record, normalizes + upserts through tools/video_library, then runs analyze(). Returns compact
    facts the scenario pins: most_watched derived from retention, tags surfaced, IG retention
    null-flagged, and revenue present ONLY from the CSV."""
    import import_parse as ip
    import video_library as vl

    # The Studio CSV content is embedded in a JSON fixture (no committed .csv per the data-at-rest policy).
    yt_fixture = json.loads(_fixture_path(withp["youtube_studio_csv"]).read_text(encoding="utf-8"))
    yt_records = ip.parse_youtube_studio_csv(yt_fixture["csv_text"])
    ig_records = ip.parse_instagram_dyi(_fixture_path(withp["instagram_dyi"]))

    # A synthetic retention curve (the Analytics API leg): a clear front peak and a mid cliff.
    retention = [{"elapsed_ratio": round(i / 100, 2),
                  "watch_ratio": (1.4 if i < 10 else (0.4 if i >= 60 else 0.9))}
                 for i in range(0, 100, 2)]

    con = vl._open_db(":memory:")  # in-memory: writes nothing to disk
    yt_key = None
    for idx, r in enumerate(yt_records):
        r = dict(r)
        r.setdefault("tags", ["armoire", "diy"] if idx == 0 else ["wainscoting", "diy"])
        if idx == 0:
            r["retention"] = retention  # only the first YT video carries a retention curve
        rec = vl.normalize_record(r, platform="youtube", source_mode="export_bundle",
                                  source_citation="studio_csv")
        vl._upsert(con, rec)
        if idx == 0:
            yt_key = rec["video_key"]
    ig_key = None
    for r in ig_records:
        r = dict(r)
        r["tags"] = ["armoire"]
        rec = vl.normalize_record(r, platform="instagram", source_mode="export_bundle")
        vl._upsert(con, rec)
        ig_key = rec["video_key"]

    yt_rec = vl.get_record(con, yt_key)
    ig_rec = vl.get_record(con, ig_key) if ig_key else None
    analysis = vl.analyze(con)
    con.close()

    top_tag_names = [t["tag"] for t in analysis["top_tags"]]
    return {
        "youtube_key": yt_key,
        "instagram_key": ig_key,
        "youtube_most_watched_count": len(yt_rec.get("most_watched_segments") or []),
        "youtube_has_peak": any(s.get("label") == "peak" for s in (yt_rec.get("most_watched_segments") or [])),
        "youtube_revenue_present": bool(yt_rec.get("revenue")),
        "instagram_revenue_present": bool(ig_rec and ig_rec.get("revenue")),
        "instagram_retention_null": bool(ig_rec and ig_rec.get("retention") is None),
        "instagram_most_watched_count": len((ig_rec or {}).get("most_watched_segments") or []),
        "top_tags": top_tag_names,
        "retention_unavailable": analysis["retention_insights"]["retention_unavailable"],
    }


def op_inbox_scan(withp, clock, prior):
    """Runs the REAL offline drop-folder scan (tools/handoff/inbox.py, P60) on a temp hub built
    from files declared in the scenario. The committed rules table (shared/docintel/inbox_rules.json)
    is the routing authority; the ledger is passed empty so the leg is hermetic. Writes only to a
    temp dir; the repo and the real inbox ledger are untouched."""
    import tempfile

    from handoff import inbox

    hub = Path(tempfile.mkdtemp(prefix="s10-hub-"))
    (hub / "Inbox").mkdir(parents=True)
    for name, content in withp["files"].items():
        (hub / "Inbox" / name).write_bytes(content.encode("utf-8"))
    return inbox.scan(hub, ledger={})


def op_text_probe(withp, clock, prior):
    p = ROOT / withp["file"]
    if not p.exists():
        return {"present": False, "file_exists": False}
    found = re.search(withp["pattern"], p.read_text(encoding="utf-8")) is not None
    return {"present": found, "file_exists": True}


def op_path_probe(withp, clock, prior):
    return {"present": (ROOT / withp["path"]).exists()}


OPS = {
    "json.load": op_json_load,
    "obligations.build_register": op_build_register,
    "obligations.scan": op_scan,
    "transcripts.parse": op_transcripts_parse,
    "transcripts.gap_metrics": op_gap_metrics,
    "chapters.fan_out": op_fan_out,
    "chapters.validate": op_validate,
    "quality.evaluate": op_quality,
    "accounts.resolve": op_accounts_resolve,
    "accounts.contacts": op_accounts_contacts,
    "accounts.deal_status": op_accounts_deal_status,
    "tasks.scan": op_tasks_scan,
    "tasks.ping_pong": op_tasks_ping_pong,
    "shipments.manual": op_shipment_manual,
    "coverage.verify": op_coverage_verify,
    "finance.price": op_finance_price,
    "finance.price_package": op_finance_price_package,
    "doctemplates.validate": op_doctemplates_validate,
    "doctemplates.assemble": op_doctemplates_assemble,
    "content_import.analyze": op_content_import_analyze,
    "inbox.scan": op_inbox_scan,
    "text.probe": op_text_probe,
    "path.probe": op_path_probe,
}


def _resolve_from(withp: dict, prior: dict) -> dict:
    out = {}
    for k, v in withp.items():
        if isinstance(v, dict) and "$from" in v:
            leg_id = v["$from"]
            if leg_id not in prior:
                raise KeyError(f"$from references unknown leg {leg_id!r}")
            out[k] = prior[leg_id]
        else:
            out[k] = v
    return out


# --------------------------------------------------------------------------- probes

def run_probe(probe, table: dict, clock: dict) -> bool:
    """A gap probe passes when the gap is CURRENTLY observable in the repo."""
    probes = probe if isinstance(probe, list) else [probe]
    for p in probes:
        op = p["op"]
        if op == "routing.probe":
            cls = p["with"]["classification"]
            present = cls in table
            want_present = p["with"].get("expect", "absent") == "present"
            if present != want_present:
                return False
        elif op == "json.probe":
            data = json.loads((ROOT / p["with"]["file"]).read_text(encoding="utf-8"))
            for a in p.get("assert", []):
                if check_assert(data, a) is not None:
                    return False
        elif op in ("text.probe", "path.probe"):
            res = OPS[op](p["with"], clock, {})
            want_present = p["with"].get("expect", "absent") == "present"
            if res["present"] != want_present:
                return False
        else:
            raise ValueError(f"unknown probe op {op!r}")
    return True


# --------------------------------------------------------------------------- scenario evaluation

def evaluate_scenario(sc: dict, table: dict, clock: dict) -> dict:
    routing_failures = check_routing(sc.get("routing", {}), table)
    prior: dict = {}
    legs_out = []
    for leg in sc.get("legs", []):
        entry = {"id": leg["id"], "op": leg["op"], "failures": []}
        if leg.get("evidence_for"):
            entry["evidence_for"] = leg["evidence_for"]
        try:
            withp = _resolve_from(leg.get("with", {}), prior)
            result = OPS[leg["op"]](withp, clock, prior)
            prior[leg["id"]] = result
            for a in leg.get("assert", []):
                if a.get("pinned_today_only") and not clock["pinned"]:
                    continue
                failure = check_assert(result, a)
                if failure:
                    entry["failures"].append(failure)
        except Exception as exc:  # noqa: BLE001
            entry["failures"].append(f"leg raised: {type(exc).__name__}: {exc}")
        entry["status"] = "pass" if not entry["failures"] else "fail"
        legs_out.append(entry)
    ok = not routing_failures and all(l["status"] == "pass" for l in legs_out)
    return {
        "scenario_id": sc["id"],
        "utterance": sc.get("utterance"),
        "routing_mode": sc.get("routing", {}).get("mode"),
        "routing_failures": routing_failures,
        "legs": legs_out,
        "declared_gaps": sc.get("known_gaps", []),
        "status": "pass" if ok else "fail",
    }


# --------------------------------------------------------------------------- selftest

def selftest() -> int:
    failures = []

    def expect(name, cond):
        if not cond:
            failures.append(name)
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    table = parse_routing_table()
    expect("routing table parses with 25 or more rows", len(table) >= 25)
    expect("seasonal_planning routes to seasonal-trends", table.get("seasonal_planning") == "seasonal-trends")
    expect("crm_query is not in the live table", "crm_query" not in table)

    obj = {"a": {"b": [{"c": 5}]}, "s": "hello world", "l": [1, 2, 3]}
    expect("path a.b[0].c resolves", resolve_path(obj, "a.b[0].c")[1] == 5)
    expect("eq passes", check_assert(obj, {"path": "a.b[0].c", "check": "eq", "value": 5}) is None)
    expect("eq fails loudly", check_assert(obj, {"path": "a.b[0].c", "check": "eq", "value": 6}) is not None)
    expect("absent_key passes on missing", check_assert(obj, {"path": "zz", "check": "absent_key"}) is None)
    expect("absent_key fails on present", check_assert(obj, {"path": "s", "check": "absent_key"}) is not None)
    expect("contains on string", check_assert(obj, {"path": "s", "check": "contains", "value": "world"}) is None)
    expect("len_eq on list", check_assert(obj, {"path": "l", "check": "len_eq", "value": 3}) is None)

    parsed = {"segments": [{"start": 0.0, "end": 5.0}, {"start": 15.0, "end": 20.0}, {"start": 21.0, "end": 25.0}]}
    gm = op_gap_metrics({"parsed": parsed, "min_gap_seconds": 8.0}, {}, {})
    expect("gap_metrics finds the one 10s silence", len(gm["silences"]) == 1 and gm["silences"][0]["gap_seconds"] == 10.0)

    declared, observed = {"G1", "G2"}, {"G1"}
    expect("gap-diff logic detects a silently closed gap", declared != observed)

    clock = {"today": date(2026, 9, 15), "year": 2026, "lead_days": 3, "pinned": True}
    expect("routing.probe absent works", run_probe({"op": "routing.probe", "with": {"classification": "crm_query", "expect": "absent"}}, table, clock))

    scan = op_inbox_scan({"files": {"a.srt": "1\n00:00:01,000 --> 00:00:02,000\nx\n", "b.pdf": "%PDF-1.4 stub"}}, clock, {})
    expect("inbox.scan op routes the srt by format and holds the pdf for review",
           len(scan["proposals"]) == 1 and scan["proposals"][0]["route_to"]["handler"] == "transcript-import"
           and len(scan["needs_review"]) == 1 and scan["needs_review"][0]["classified_as"] is None)
    print(f"selftest: {'PASS' if not failures else 'FAIL'} ({13 - len(failures)} of 13 checks)")
    return 1 if failures else 0


# --------------------------------------------------------------------------- CLI

def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Run the realistic-scenario suite against the live repo.")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--scenario", metavar="ID", help="run one scenario by id")
    ap.add_argument("--today", metavar="YYYY-MM-DD", help="override the pinned clock (demotes date-exact asserts)")
    ap.add_argument("--year", type=int, help="override the fixture {YEAR} (demotes date-exact asserts)")
    ap.add_argument("--list", action="store_true", help="list scenarios and gaps")
    ap.add_argument("--selftest", action="store_true", help="micro-tests of the runner itself")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()

    try:
        contract = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": f"scenarios.json unreadable: {exc}"}))
        return 2

    pinned_today = date.fromisoformat(contract["pinned_today"])
    pinned = a.today is None and a.year is None
    today = date.fromisoformat(a.today) if a.today else pinned_today
    clock = {
        "today": today,
        "year": a.year if a.year else today.year,
        "lead_days": contract.get("defaults", {}).get("lead_days", 3),
        "pinned": pinned,
    }

    if a.list:
        for sc in contract["scenarios"]:
            print(f"  {sc['id']}: {sc['utterance']}")
        for g in contract["gap_ledger"]:
            print(f"  {g['id']}: {g['title']}")
        return 0

    table = parse_routing_table()
    scenarios = contract["scenarios"]
    if a.scenario:
        scenarios = [s for s in scenarios if s["id"] == a.scenario]
        if not scenarios:
            print(json.dumps({"error": f"unknown scenario {a.scenario!r}"}))
            return 2

    results = [evaluate_scenario(sc, table, clock) for sc in scenarios]

    gap_findings = []
    observed, declared = set(), set()
    if not a.scenario:  # gap contract is suite-wide; skip when running a single scenario
        for g in contract["gap_ledger"]:
            declared.add(g["id"])
            try:
                seen = run_probe(g["probe"], table, clock)
            except Exception as exc:  # noqa: BLE001
                seen = False
                gap_findings.append({"id": g["id"], "error": f"probe raised: {exc}"})
            if seen:
                observed.add(g["id"])
            gap_findings.append({"id": g["id"], "title": g["title"], "observed": seen})

    contract_violations = []
    if not a.scenario and observed != declared:
        closed = sorted(declared - observed)
        if closed:
            contract_violations.append(
                f"gaps no longer observed (silently closed?): {closed}; "
                f"update scenarios.json + docs/SCENARIOS.md deliberately"
            )

    all_pass = all(r["status"] == "pass" for r in results) and not contract_violations
    report = {
        "suite": contract["suite"],
        "clock": {"today": today.isoformat(), "year": clock["year"], "pinned": pinned},
        "scenarios": results,
        "gap_findings": [g for g in gap_findings if "title" in g],
        "contract_violations": contract_violations,
        "summary": {
            "scenarios_passed": sum(1 for r in results if r["status"] == "pass"),
            "scenarios_total": len(results),
            "gaps_observed": len(observed),
            "gaps_declared": len(declared),
        },
        "status": "pass" if all_pass else "fail",
    }

    if a.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"scenario suite: {report['suite']} (today={today.isoformat()}, pinned={pinned})")
        for r in results:
            print(f"\n  {r['scenario_id']} [{r['routing_mode']}]: {r['status'].upper()}")
            print(f"    \"{r['utterance']}\"")
            for f in r["routing_failures"]:
                print(f"    ROUTING FAIL: {f}")
            for leg in r["legs"]:
                tag = " (evidence)" if leg.get("evidence_for") else ""
                print(f"    [{'ok' if leg['status'] == 'pass' else 'FAIL'}] {leg['id']}{tag}")
                for f in leg["failures"]:
                    print(f"        {f}")
        if not a.scenario:
            print(f"\n  gaps: {len(observed)} of {len(declared)} declared gaps observed")
            for v in contract_violations:
                print(f"  CONTRACT VIOLATION: {v}")
        s = report["summary"]
        print(f"\nRESULT: {s['scenarios_passed']}/{s['scenarios_total']} scenarios pass; "
              f"{s['gaps_observed']}/{s['gaps_declared']} gaps observed -> {report['status'].upper()}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
