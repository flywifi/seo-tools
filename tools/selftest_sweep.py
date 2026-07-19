#!/usr/bin/env python3
"""Creator OS behavioral selftest sweep (P66).

The P65 audit found that CI ran only three --selftest invocations while the tree carries dozens
of behavioral selftests: a selftest regression could merge green (F-CI-COVERAGE). This runner
DISCOVERS every Python CLI under tools/ and shared/ that exposes a selftest (an argparse
`--selftest` flag or a `selftest` subcommand) and runs each in a subprocess. Discovery is
scripted, never a hand-list, so the CI battery cannot drift from the tree. All selftests are
offline by repo convention; tools with optional dependencies degrade honestly and still exit 0.

Modes:
  python3 tools/selftest_sweep.py            # run every discovered selftest; exit 1 on any failure
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
    return 0 if not failed else 1


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
