#!/usr/bin/env python3
"""ci_history.py -- green/red transitions of this branch's GitHub Actions runs (P81 G-10 / RC-3).

The P80 records said "CI had been red since 2026-08-16"; the Actions history showed the last green
run on 2026-07-19 and TWO causes, not one. A claim about CI in a record must cite this tool's
output, not memory. Modes:

  * live:        paginate /repos/<owner>/<repo>/actions/runs?branch=<b>&per_page=100 (reads
                 GITHUB_TOKEN if set; honors the env proxy + CA bundle via dependency_currency's
                 _http_get_json). api.github.com is proxy-blocked from some sandboxes; the tool then
                 reports blocked, never guesses.
  * --from-file: parse one or more saved API payload files (offline, reproducible).
  * --selftest:  the transition logic against a fixture.

Output: one line per green<->red boundary (run number, date, sha, conclusion), then the current
state and streak. Stdlib only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

OWNER_REPO = "flywifi/seo-tools"
BRANCH = "claude/repo-access-confirm-wxe50a"


def transitions(runs):
    """runs: [{run_number, conclusion, head_sha, created_at}] in ANY order. Returns
    (ordered_runs, boundary_list, current_state, streak). A boundary is the FIRST run of a new
    state: (run_number, date, sha7, 'green'|'red')."""
    ordered = sorted((r for r in runs if r.get("conclusion") in ("success", "failure")),
                     key=lambda r: r["run_number"])
    bounds, prev = [], None
    for r in ordered:
        state = "green" if r["conclusion"] == "success" else "red"
        if state != prev:
            bounds.append((r["run_number"], str(r.get("created_at", ""))[:10],
                           str(r.get("head_sha", ""))[:7], state))
            prev = state
    streak = 0
    for r in reversed(ordered):
        state = "green" if r["conclusion"] == "success" else "red"
        if state == prev:
            streak += 1
        else:
            break
    return ordered, bounds, prev, streak


def _report(runs) -> int:
    ordered, bounds, state, streak = transitions(runs)
    if not ordered:
        print("ci_history: no completed runs in the input")
        return 1
    print(f"ci_history: {len(ordered)} completed run(s), {ordered[0]['run_number']}..{ordered[-1]['run_number']}")
    for num, date, sha, st in bounds:
        print(f"  run {num:>4}  {date}  {sha}  -> {st}")
    print(f"current: {state} (streak {streak})")
    return 0


def fetch_live(branch: str = BRANCH):
    from dependency_currency import _http_get_json
    runs, page = [], 1
    while True:
        url = (f"https://api.github.com/repos/{OWNER_REPO}/actions/runs"
               f"?branch={branch}&per_page=100&page={page}")
        data = _http_get_json(url)
        if not data or "workflow_runs" not in data:
            return runs, (None if runs else "blocked or empty response from the Actions API")
        batch = data["workflow_runs"]
        runs.extend(batch)
        if len(batch) < 100:
            return runs, None
        page += 1


def selftest() -> int:
    failures = []

    def ok(name, cond):
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    def mk(n, c, d="2026-07-19T19:00:00Z"):
        return {"run_number": n, "conclusion": c, "head_sha": f"sha{n:04d}aaa", "created_at": d}

    fx = [mk(227, "success"), mk(228, "failure"), mk(240, "failure"), mk(289, "failure"),
          mk(290, "success"), mk(292, "success"), mk(293, "failure"), mk(294, "success"),
          mk(230, None), mk(231, "cancelled")]
    ordered, bounds, state, streak = transitions(fx)
    ok("non-terminal runs excluded", len(ordered) == 8)
    ok("boundaries are the FIRST run of each state",
       [(b[0], b[3]) for b in bounds] == [(227, "green"), (228, "red"), (290, "green"),
                                          (293, "red"), (294, "green")])
    ok("current state green, streak 1", state == "green" and streak == 1)
    ok("input order does not matter", transitions(list(reversed(fx)))[1] == bounds)
    ok("empty input handled", transitions([]) == ([], [], None, 0))
    ok("all-red history has one boundary",
       [(b[0], b[3]) for b in transitions([mk(1, "failure"), mk(2, "failure")])[1]] == [(1, "red")])
    print(f"ci_history selftest: {'PASS' if not failures else 'FAIL'} ({len(failures)} failure(s))")
    return 1 if failures else 0


def main(argv) -> int:
    if "--selftest" in argv:
        return selftest()
    if "--from-file" in argv:
        runs = []
        for f in argv[argv.index("--from-file") + 1:]:
            data = json.loads(Path(f).read_text(encoding="utf-8"))
            runs.extend(data.get("workflow_runs", data if isinstance(data, list) else []))
        return _report(runs)
    runs, err = fetch_live()
    if err:
        print(f"ci_history: LIVE FETCH FAILED ({err}). From a machine that reaches api.github.com, "
              f"run this tool again, or save the API pages and use --from-file.")
        return 2
    return _report(runs)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
