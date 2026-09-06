#!/usr/bin/env python3
"""Creator OS behavioral selftest sweep (P66).

The P65 audit found that CI ran only three --selftest invocations while the tree carries dozens
of behavioral selftests: a selftest regression could merge green (F-CI-COVERAGE). This runner
DISCOVERS every Python CLI under tools/ and shared/ that exposes a selftest (an argparse
`--selftest` flag or a `selftest` subcommand) and runs each in a subprocess. Discovery is
scripted, never a hand-list, so the CI battery cannot drift from the tree. All selftests are
offline by repo convention; tools with optional dependencies degrade honestly and still exit 0.

Enrolment (P74, re-landed P79): discovery alone lets a tool ship with NO selftest and nothing
notice. After the run, every tracked tools/**/*.py and shared/**/*.py must either be in the
discovered set or appear in tools/selftest-exemption.json with a reviewable reason; a stale
exemption (file gained a selftest, or is no longer tracked) fails too. The sweep exits 1 on any
selftest failure OR any enrolment problem.

Modes:
  python3 tools/selftest_sweep.py            # run every discovered selftest + the enrolment gate; exit 1 on any failure
  python3 tools/selftest_sweep.py --list     # print the discovered set and how each is invoked
  python3 tools/selftest_sweep.py --selftest # the sweep's own selftest (discovery sanity)
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Three ways the tree exposes a selftest: an argparse flag, a manual argv probe
# (preflight_push style), or a `selftest` subcommand.
FLAG_RE = re.compile(r"add_argument\(\s*['\"]--selftest['\"]"
                     r"|['\"]--selftest['\"]\s+in\s+(?:argv|sys\.argv)")
SUB_RE = re.compile(r"add_parser\(\s*['\"]selftest['\"]")
PER_TOOL_TIMEOUT = 300


def discover():
    """(path, argv-suffix) for every CLI under tools/ and shared/ exposing a selftest.

    Package __main__.py entries (tools/publishing) need `python -m` with the package parent on
    sys.path, not file invocation; the sweep runs them per their documented module form via the
    PACKAGE_ENTRIES table below rather than skipping them silently."""
    found = []
    for base in ("tools", "shared"):
        root = ROOT / base
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.py")):
            if ".venv" in p.parts or p.name == Path(__file__).name:
                continue
            if p.name == "__main__.py":
                continue  # covered by PACKAGE_ENTRIES with the correct -m invocation
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if FLAG_RE.search(text):
                found.append((p, ["--selftest"]))
            elif SUB_RE.search(text):
                found.append((p, ["selftest"]))
    return found


# Package selftests that must run as `python -m` with tools/ on sys.path (label, argv).
PACKAGE_ENTRIES = [
    ("tools/publishing (-m)", ["-m", "publishing", "--selftest"]),
]


EXEMPTION_PATH = ROOT / "tools" / "selftest-exemption.json"
MIN_REASON_CHARS = 25


def _tracked_python():
    """Tracked .py files under tools/ and shared/, or None outside a git checkout."""
    try:
        out = subprocess.run(["git", "ls-files", "tools", "shared"], cwd=str(ROOT),
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return [f for f in out.stdout.split() if f.endswith(".py")]


def _enrolment_problems_for(tracked, discovered, exempt, self_rel):
    """Pure core of the enrolment gate (no git, no filesystem) so its four branches are asserted
    permanently in selftest() rather than red-teamed once by hand."""
    problems = []
    for rel in sorted(tracked):
        if rel in discovered or rel.endswith("__main__.py"):
            continue
        if rel == self_rel:
            continue
        reason = exempt.get(rel)
        if not reason:
            problems.append(
                f"selftest-enrolment: {rel} has no --selftest and no exemption. Either wire a "
                f"selftest the sweep can discover, or add it to tools/selftest-exemption.json "
                f"with a written reason.")
        elif len(reason.strip()) < MIN_REASON_CHARS:
            problems.append(
                f"selftest-enrolment: {rel} is exempt with a reason too short to review "
                f"({reason.strip()!r}); say why a selftest is not the right coverage for it.")
    for rel in sorted(exempt):
        if rel in discovered:
            problems.append(
                f"selftest-enrolment: {rel} is BOTH exempt and covered; drop the stale exemption.")
        elif rel not in tracked:
            problems.append(
                f"selftest-enrolment: {rel} is exempt but no longer tracked; drop the entry.")
    return problems


def enrolment_problems():
    """Every tracked tool must expose a selftest OR be exempt in writing.

    P74 WP4 (re-landed P79 WP-C): discovery was scripted but ENROLMENT was not, so a tool could
    ship with no selftest and nothing noticed -- which is how the OG-extractor defect survived in
    a module nothing ever executed. A file is enrolled by having a --selftest the sweep can find,
    or by appearing in tools/selftest-exemption.json with a reason a reviewer can argue with.
    Returns [] when clean; outside a git checkout it returns a single DID-NOT-RUN line (never a
    silent pass).
    """
    import json
    tracked = _tracked_python()
    if tracked is None:
        return ["selftest-enrolment: not a git checkout; enrolment DID NOT RUN"]
    try:
        exempt = json.loads(EXEMPTION_PATH.read_text(encoding="utf-8")).get("exempt", {})
    except (OSError, ValueError) as exc:
        return [f"selftest-enrolment: {EXEMPTION_PATH.name} unreadable ({exc}); refusing to pass"]
    discovered = {str(p.relative_to(ROOT)) for p, _ in discover()}
    return _enrolment_problems_for(tracked, discovered, exempt,
                                   str(Path(__file__).resolve().relative_to(ROOT)))


def run_sweep():
    import os
    targets = [(str(p.relative_to(ROOT)), [str(p)] + args) for p, args in discover()]
    targets.extend(PACKAGE_ENTRIES)
    failed = []
    for rel, argv in targets:
        env = dict(os.environ)
        if argv and argv[0] == "-m":
            env["PYTHONPATH"] = str(ROOT / "tools")
        try:
            out = subprocess.run([sys.executable] + argv, cwd=str(ROOT), env=env,
                                 capture_output=True, text=True, timeout=PER_TOOL_TIMEOUT)
        except subprocess.TimeoutExpired:
            print(f"  [FAIL] {rel} (timeout after {PER_TOOL_TIMEOUT}s)")
            failed.append(str(rel))
            continue
        ok = out.returncode == 0
        print(f"  [{'ok' if ok else 'FAIL'}] {rel} (exit {out.returncode})")
        if not ok:
            tail = (out.stdout + out.stderr).strip().splitlines()[-8:]
            for line in tail:
                print(f"         {line}")
            failed.append(str(rel))
    print(f"selftest-sweep: {'PASS' if not failed else 'FAIL'} "
          f"({len(targets) - len(failed)} of {len(targets)} selftests)")
    enrol = enrolment_problems()
    for e in enrol:
        print(f"  [FAIL] {e}")
    if enrol:
        print(f"selftest-enrolment: FAIL ({len(enrol)} unenrolled or stale entr(ies))")
    else:
        print("selftest-enrolment: clean (every tracked tool is discovered or exempt in writing)")
    return 0 if not failed and not enrol else 1


def selftest():
    failures = []
    ran = [0]

    def check(label, cond):
        ran[0] += 1
        print(f"  [{'ok' if cond else 'FAIL'}] {label}")
        if not cond:
            failures.append(label)

    targets = dict((str(p.relative_to(ROOT)), args) for p, args in discover())
    check("discovery finds a known --selftest tool (secret_scan)",
          targets.get("tools/secret_scan.py") == ["--selftest"])
    check("discovery finds a known selftest-subcommand tool (source_currency)",
          targets.get("tools/source_currency.py") == ["selftest"])
    check("discovery finds the drift-guard siblings (preflight_push)",
          "tools/preflight_push.py" in targets)
    check("the sweep never discovers itself (no recursion)",
          "tools/selftest_sweep.py" not in targets)
    check("discovery is non-trivial (a dozen or more selftests in the tree)",
          len(targets) >= 12)
    # enrolment gate, pure core (the three P74 red-teams made permanent, plus the fourth branch)
    me = "tools/selftest_sweep.py"
    disc = {"tools/a.py"}
    ok_ex = {"tools/b.py": "a runner; executing it in the battery is the assertion itself"}
    check("enrolment: clean when every tracked file is discovered or exempt",
          _enrolment_problems_for(["tools/a.py", "tools/b.py", me, "tools/pkg/__main__.py"],
                                  disc, ok_ex, me) == [])
    r = _enrolment_problems_for(["tools/a.py", "tools/new_thing.py"], disc, {}, me)
    check("enrolment: an unenrolled tracked tool fails and is named",
          len(r) == 1 and "tools/new_thing.py has no --selftest and no exemption" in r[0])
    r = _enrolment_problems_for(["tools/c.py"], disc, {"tools/c.py": "no network"}, me)
    check("enrolment: a reason too short to review fails",
          len(r) == 1 and "too short to review" in r[0])
    r = _enrolment_problems_for(["tools/a.py"], disc,
                                {"tools/a.py": "a long enough reason that is now stale x"}, me)
    check("enrolment: exempt AND covered fails (stale exemption)",
          len(r) == 1 and "BOTH exempt and covered" in r[0])
    r = _enrolment_problems_for(["tools/a.py"], disc,
                                {"tools/gone.py": "a long enough reason for a deleted file"}, me)
    check("enrolment: exempt but no longer tracked fails",
          len(r) == 1 and "no longer tracked" in r[0])
    live = enrolment_problems()
    check("enrolment: the live tree is clean (or honestly DID-NOT-RUN outside git)",
          live == [] or (len(live) == 1 and "DID NOT RUN" in live[0]))
    n = ran[0]
    print(f"selftest: {'PASS' if not failures else 'FAIL'} ({n - len(failures)} of {n} checks)")
    return 0 if not failures else 1


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS behavioral selftest sweep")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.list:
        for p, args in discover():
            print(f"{p.relative_to(ROOT)} {' '.join(args)}")
        return 0
    return run_sweep()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
