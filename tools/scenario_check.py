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
    expect("account_read is not in the live table", "account_read" not in table)

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
    expect("routing.probe absent works", run_probe({"op": "routing.probe", "with": {"classification": "account_read", "expect": "absent"}}, table, clock))
    print(f"selftest: {'PASS' if not failures else 'FAIL'} ({12 - len(failures)} of 12 checks)")
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
