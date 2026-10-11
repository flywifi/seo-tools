#!/usr/bin/env python3
"""Creator OS behavioral selftest sweep (P66).

CI once ran only three --selftest invocations while the tree carries dozens of behavioral
selftests, so a selftest regression could merge green. This runner
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
# Longer caps, each with its reason; a key names a discovered target. The surface workflow suite's
# --selftest runs its committed mutants one after another and took 246 to 287 s on a Windows
# computer (P102), close to the default cap, and a hosted Windows runner can be slower.
# tools/file_hash.py --selftest runs the committed mutation rows, which grow with each change:
# on a 4-CPU Linux computer it took 165 s alone at 482 rows and 415 s at 1,022 rows (P102,
# Push 4b), where a GitHub Windows runner went past 900 s. 1800 s stays inside the Windows CI
# job's 45 minutes with the other gates.
TOOL_TIMEOUTS = {"tools/surface_workflow_check.py": 900,
                 "tools/file_hash.py": 1800}
# file_hash's 1800 s were set from runs with four of its children at a time (GitHub's Windows and
# Linux runners have four CPUs for a public repository). Where file_hash.mutant_jobs() is lower (a
# computer whose os.cpu_count() is below four, or CREATOR_OS_FILE_HASH_JOBS set lower for a
# computer with little memory) the same rows take longer in proportion, so its cap grows in that
# proportion.
FILE_HASH_REF_JOBS = 4


def _file_hash_jobs() -> int:
    """How many children file_hash's selftest runs at a time here: file_hash.mutant_jobs(), which
    reads CREATOR_OS_FILE_HASH_JOBS and os.cpu_count() as the child the sweep starts does (the sweep
    passes the child its environment, not its interpreter options). FILE_HASH_REF_JOBS when
    file_hash does not import or has no mutant_jobs, so the sweep still runs and reports its target."""
    try:
        try:
            import file_hash
        except ImportError:  # loaded by file path with tools/ not on sys.path
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import file_hash
        return file_hash.mutant_jobs()
    except Exception:  # noqa: BLE001 -- a file_hash that does not import fails its own target
        return FILE_HASH_REF_JOBS


def _tool_timeout(rel, jobs=None) -> int:
    """The seconds the sweep gives one target: its TOOL_TIMEOUTS entry, else PER_TOOL_TIMEOUT. For
    tools/file_hash.py, when its mutation run uses fewer than FILE_HASH_REF_JOBS children at a time
    (jobs, else _file_hash_jobs()), the entry is multiplied by FILE_HASH_REF_JOBS over that count."""
    limit = TOOL_TIMEOUTS.get(rel, PER_TOOL_TIMEOUT)
    if rel == "tools/file_hash.py":
        jobs = _file_hash_jobs() if jobs is None else jobs
        if jobs < FILE_HASH_REF_JOBS:
            limit = limit * FILE_HASH_REF_JOBS // max(1, jobs)
    return limit


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
    # P101: git lists tracked files and the exemption file names them with POSIX separators, so the
    # discovered set is keyed the same way on a Windows checkout.
    discovered = {p.relative_to(ROOT).as_posix() for p, _ in discover()}
    return _enrolment_problems_for(tracked, discovered, exempt,
                                   Path(__file__).resolve().relative_to(ROOT).as_posix())


def run_sweep():
    import os
    targets = [(p.relative_to(ROOT).as_posix(), [str(p)] + args) for p, args in discover()]
    targets.extend(PACKAGE_ENTRIES)
    failed = []
    for rel, argv in targets:
        env = dict(os.environ)
        if argv and argv[0] == "-m":
            env["PYTHONPATH"] = str(ROOT / "tools")
        limit = _tool_timeout(rel)
        try:
            out = subprocess.run([sys.executable] + argv, cwd=str(ROOT), env=env,
                                 capture_output=True, text=True, timeout=limit)
        except subprocess.TimeoutExpired:
            print(f"  [FAIL] {rel} (timeout after {limit}s)")
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

    targets = dict((p.relative_to(ROOT).as_posix(), args) for p, args in discover())
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
    in_git = _tracked_python() is not None
    check("enrolment: the live tree is clean (or honestly DID-NOT-RUN outside git)",
          live == [] if in_git else (len(live) == 1 and "DID NOT RUN" in live[0]))
    # P101: on Windows relative_to yields backslash paths, while git and the exemption file use
    # POSIX ones; the live gate keys the discovered set the same way, so it stays clean.
    try:
        import file_hash
    except ImportError:  # loaded by file path with tools/ not on sys.path
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import file_hash
    with file_hash.windows_paths():
        win_sim = "\\" in str((ROOT / "tools" / "x.py").relative_to(ROOT))
        live_w = enrolment_problems()
    check("enrolment: Windows-form paths give the same result as POSIX paths (P101)",
          win_sim and live_w == live)
    # P102: a per-tool cap names a discovered target, exceeds the default, and reaches the run.
    names = set(targets) | {rel for rel, _ in PACKAGE_ENTRIES}
    check("each TOOL_TIMEOUTS key names a discovered target and exceeds the default cap",
          bool(TOOL_TIMEOUTS) and all(k in names and v > PER_TOOL_TIMEOUT for k, v in TOOL_TIMEOUTS.items()))
    import contextlib
    import io
    seen = []
    real_run, real_discover, real_pkgs = subprocess.run, globals()["discover"], list(PACKAGE_ENTRIES)
    probe = {"tools/surface_workflow_check.py": ["--selftest"], "tools/file_hash.py": ["--selftest"],
             "tools/secret_scan.py": ["--selftest"]}

    def fake_run(argv, **kw):
        rel = next((r for r in probe if len(argv) > 1 and str(argv[1]).endswith(Path(r).name)), None)
        if rel is None:
            return real_run(argv, **kw)
        seen.append((rel, kw.get("timeout")))
        return subprocess.CompletedProcess(argv, 0, "", "")
    import os
    saved_jobs = os.environ.get("CREATOR_OS_FILE_HASH_JOBS")
    runs = {}
    try:
        subprocess.run = fake_run
        globals()["discover"] = lambda: [(ROOT / r, a) for r, a in probe.items()]
        PACKAGE_ENTRIES[:] = []
        for jobs in ("4", "2"):  # file_hash's worker count, as CREATOR_OS_FILE_HASH_JOBS sets it
            os.environ["CREATOR_OS_FILE_HASH_JOBS"] = jobs
            del seen[:]
            with contextlib.redirect_stdout(io.StringIO()):
                run_sweep()
            runs[jobs] = sorted(seen)
    finally:
        subprocess.run, globals()["discover"] = real_run, real_discover
        PACKAGE_ENTRIES[:] = real_pkgs
        if saved_jobs is None:
            os.environ.pop("CREATOR_OS_FILE_HASH_JOBS", None)
        else:
            os.environ["CREATOR_OS_FILE_HASH_JOBS"] = saved_jobs
    check("the sweep runs each target with its own cap (the suite 900 s, file_hash 1800 s with four "
          "workers and 3600 s with two, another tool the default)",
          runs == {"4": [("tools/file_hash.py", 1800), ("tools/secret_scan.py", PER_TOOL_TIMEOUT),
                         ("tools/surface_workflow_check.py", 900)],
                   "2": [("tools/file_hash.py", 3600), ("tools/secret_scan.py", PER_TOOL_TIMEOUT),
                         ("tools/surface_workflow_check.py", 900)]})
    caps = {j: _tool_timeout("tools/file_hash.py", jobs=j) for j in (1, 2, 3, 4, 8)}
    check("file_hash's cap is 1800 s with four or more workers and grows in proportion with fewer",
          caps == {1: 7200, 2: 3600, 3: 2400, 4: 1800, 8: 1800})
    check("another tool's cap does not follow file_hash's worker count",
          _tool_timeout("tools/surface_workflow_check.py", jobs=1) == 900
          and _tool_timeout("tools/secret_scan.py", jobs=1) == PER_TOOL_TIMEOUT)
    # With no override the count follows os.cpu_count(); a file_hash that does not import, or does
    # not parse, gives the reference count; with tools/ off sys.path the lookup still imports it.
    tools_dir = Path(__file__).resolve().parent

    def _is_tools(entry):
        try:
            return Path(entry or ".").resolve() == tools_dir
        except OSError:
            return False

    class _NoParse:
        def find_spec(self, name, path=None, target=None):
            if name == "file_hash":
                raise SyntaxError("a stand-in for a file_hash.py that does not parse")
            return None

    saved_path, saved_mod = list(sys.path), sys.modules.get("file_hash")
    saved_jobs, real_cpu = os.environ.get("CREATOR_OS_FILE_HASH_JOBS"), os.cpu_count
    got, finder = {}, _NoParse()
    try:
        os.environ.pop("CREATOR_OS_FILE_HASH_JOBS", None)
        os.cpu_count = lambda: 2
        got["two CPUs"] = _tool_timeout("tools/file_hash.py")
        os.cpu_count = real_cpu
        os.environ["CREATOR_OS_FILE_HASH_JOBS"] = "2"
        sys.modules["file_hash"] = None  # `import file_hash` raises ImportError
        got["no import"] = _file_hash_jobs()
        del sys.modules["file_hash"]
        sys.meta_path.insert(0, finder)
        got["no parse"] = _file_hash_jobs()
        sys.meta_path.remove(finder)
        sys.path[:] = [e for e in sys.path if not _is_tools(e)]
        got["by path"] = _file_hash_jobs()
    finally:
        os.cpu_count = real_cpu
        if finder in sys.meta_path:
            sys.meta_path.remove(finder)
        sys.path[:] = saved_path
        if saved_mod is None:
            sys.modules.pop("file_hash", None)
        else:
            sys.modules["file_hash"] = saved_mod
        if saved_jobs is None:
            os.environ.pop("CREATOR_OS_FILE_HASH_JOBS", None)
        else:
            os.environ["CREATOR_OS_FILE_HASH_JOBS"] = saved_jobs
    check("file_hash's worker count follows os.cpu_count() with no override, a file_hash that does not "
          "import or parse gives the four-worker cap, and the lookup imports it by path",
          got == {"two CPUs": 3600, "no import": FILE_HASH_REF_JOBS, "no parse": FILE_HASH_REF_JOBS,
                  "by path": 2})
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
