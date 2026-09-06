#!/usr/bin/env python3
"""battery.py -- the ONE gate runner (P81 M-8 / RC-8).

P80 pushed a red commit because an ad-hoc shell gate piped hash_audit through `tail -1`, masking its
exit code, and pushed another with a stale Mac surface because `git add -A` ran after the reconcile.
This runner closes the class:

  * every gate is a subprocess whose RAW exit code decides; nothing is piped or filtered;
  * it REFUSES to run while tracked files carry unstaged edits (the mac-surface and package manifests
    derive from the INDEX, so reconciling with a dirty worktree blesses bytes a commit will not carry);
  * `--py <interpreter>` reruns the battery under a second interpreter (the repo floor rule);
  * `--list` prints the gate roster (CI's parity step asserts the roster is importable and non-empty).

Outside a git checkout the unstaged check prints a loud DID-NOT-RUN advisory instead of silently
passing (the repo's fail-closed idiom). Stdlib only.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (name, argv-after-interpreter). Raw exit code decides; order mirrors CLAUDE.md's battery block.
GATES = [
    ("drift guard", ["tools/sync_check.py"]),
    ("scenarios", ["tools/scenario_check.py"]),
    ("selftest sweep", ["tools/selftest_sweep.py"]),
    ("doc freshness", ["tools/doc_freshness.py", "--check"]),
    ("projections", ["tools/projection_manifest.py", "--check"]),
    ("count truth", ["tools/count_truth.py"]),
    ("hash audit", ["tools/hash_audit.py"]),
    ("source sync", ["tools/source_sync.py", "check"]),
    ("package manifest", ["tools/package_skill.py", "--check-manifest"]),
    ("eval lint", ["tools/eval_lint.py"]),
    ("preflight push", ["tools/preflight_push.py"]),
    ("staged secret scan", ["tools/secret_scan.py", "--staged"]),
    ("launcher syntax", ["-c", "import subprocess,sys; sys.exit(subprocess.run(['bash','-n','Start Creator OS Setup.command']).returncode)"]),
]


def unstaged_tracked(root: Path = ROOT):
    """Relative paths of tracked files with unstaged edits, or None outside git."""
    try:
        r = subprocess.run(["git", "diff", "--name-only"], cwd=str(root),
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return [x for x in r.stdout.splitlines() if x.strip()]


def run(py: str = sys.executable, root: Path = ROOT) -> int:
    dirty = unstaged_tracked(root)
    if dirty is None:
        print("battery: ADVISORY -- unstaged-edit check DID NOT RUN (not a git checkout)")
    elif dirty:
        print("battery: REFUSING to run -- stage first (git add -A): the mac-surface and package "
              "manifests derive from the INDEX, and these tracked files carry unstaged edits:")
        for f in dirty:
            print(f"  {f}")
        return 3
    failed = []
    for name, argv in GATES:
        r = subprocess.run([py] + argv, cwd=str(root), capture_output=True, text=True)
        verdict = "PASS" if r.returncode == 0 else f"FAIL (exit {r.returncode})"
        print(f"  [{'ok' if r.returncode == 0 else 'FAIL'}] {name}: {verdict}")
        if r.returncode != 0:
            failed.append(name)
            tail = (r.stdout + r.stderr).strip().splitlines()[-8:]
            for line in tail:
                print(f"       {line}")
    print(f"battery: {'PASS' if not failed else 'FAIL'} ({len(GATES) - len(failed)} of {len(GATES)} gates)"
          + (f"; failed: {', '.join(failed)}" if failed else "") + f" [interpreter {py}]")
    return 0 if not failed else 1


def selftest() -> int:
    import tempfile
    failures = []

    def ok(name, cond):
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        subprocess.run(["git", "init", "-q", td], check=True)
        (d / "f.txt").write_text("one\n")
        subprocess.run(["git", "-C", td, "add", "-A"], check=True)
        ok("clean tree: no unstaged edits", unstaged_tracked(d) == [])
        (d / "f.txt").write_text("two\n")
        ok("an unstaged tracked edit is detected", unstaged_tracked(d) == ["f.txt"])
        # refusal path: run() with a fake gate list is overkill; assert the exit code contract directly
        saved = list(GATES)
        try:
            GATES[:] = [("true gate", ["-c", "import sys; sys.exit(0)"]),
                        ("exit-3 gate", ["-c", "import sys; sys.exit(3)"])]
            rc_refuse = run(root=d)
            ok("dirty tree refuses with exit 3 before any gate runs", rc_refuse == 3)
            subprocess.run(["git", "-C", td, "add", "-A"], check=True)
            rc = run(root=d)
            ok("raw exit codes decide: one failing gate fails the battery", rc == 1)
            GATES[:] = [("true gate", ["-c", "import sys; sys.exit(0)"])]
            ok("all-green battery exits 0", run(root=d) == 0)
        finally:
            GATES[:] = saved
    with tempfile.TemporaryDirectory() as td2:
        ok("outside git the unstaged check returns None (loud advisory path)",
           unstaged_tracked(Path(td2)) is None)
    print(f"battery selftest: {'PASS' if not failures else 'FAIL'} ({len(failures)} failure(s))")
    return 1 if failures else 0


def main(argv) -> int:
    if "--selftest" in argv:
        return selftest()
    if "--list" in argv:
        for name, gate_argv in GATES:
            print(f"{name}: python3 {' '.join(gate_argv)}")
        return 0
    py = sys.executable
    if "--py" in argv:
        py = argv[argv.index("--py") + 1]
    return run(py=py)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
