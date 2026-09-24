#!/usr/bin/env python3
"""battery.py -- the ONE gate runner (P81 M-8 / RC-8).

P80 pushed a red commit because an ad-hoc shell gate piped hash_audit through `tail -1`, masking its
exit code, and pushed another with a stale Mac surface because `git add -A` ran after the reconcile.
This runner closes the class:

  * every gate is a subprocess whose RAW exit code decides; nothing is piped or filtered;
  * it REFUSES to run while tracked files carry unstaged edits (the mac-surface and package manifests
    derive from the INDEX, so reconciling with a dirty worktree blesses bytes a commit will not carry);
  * `--py <interpreter>` reruns the battery under a second interpreter (the repo floor rule);
  * `--list` prints the gate roster; `--check-parity` asserts a BLOCKING CI step runs each gate's
    exact command (P94: the old parity step printed the roster under a name that promised a
    comparison; P95: a disabled, advisory or wrong-subcommand step no longer counts).

Outside a git checkout the unstaged check prints a loud DID-NOT-RUN advisory instead of silently
passing (the repo's fail-closed idiom). Stdlib only.
"""
from __future__ import annotations

import shlex
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

    # P95: parity branches, pinned on a fixture workflow so none can regress silently.
    saved_gates, saved_notes = list(GATES), dict(CI_PARITY_NOTES)
    try:
        GATES[:] = [("alpha", ["tools/alpha.py", "check"]), ("beta", ["tools/beta.py"]),
                    ("gamma", ["tools/gamma.py"]), ("delta", ["tools/delta.py"]),
                    ("epsilon", ["tools/epsilon.py"]), ("zeta", ["tools/zeta.py"])]
        CI_PARITY_NOTES.clear()
        CI_PARITY_NOTES.update({"gamma": "covered by a superset step, fixture reason"})
        wf = ("jobs:\n  guard:\n    runs-on: x\n    steps:\n"
              "      - name: A\n        run: python3 tools/alpha.py check\n"
              "      - name: B\n        if: false\n        run: python3 tools/beta.py\n"
              "      - name: D\n        continue-on-error: true\n        run: python3 tools/delta.py\n"
              "      - name: E\n        run: |\n          set +e\n          python3 tools/epsilon.py\n"
              "      - name: V\n        run: python3 tools/version.py --check\n")
        nightly = ("  nightly:\n    if: github.event_name == 'schedule'\n    runs-on: x\n    steps:\n"
                   "      - name: Z\n        run: python3 tools/zeta.py\n")
        direct_gamma = "      - name: G\n        run: python3 tools/gamma.py\n"
        wf_all = wf + nightly
        missing, noted, stale, ci_only, cond = parity_report(wf_all)
        ok("parity: a blocking step running the exact command covers its gate",
           not any("alpha" in m for m in missing))
        ok("parity: an `if: false` step is not coverage", any("beta" in m for m in missing))
        ok("parity: a continue-on-error step is not coverage", any("delta" in m for m in missing))
        ok("parity: a gate inside a multi-command block (set +e) is not coverage",
           any("epsilon" in m for m in missing))
        ok("parity: a noted gate is reported as covered differently", noted == ["gamma"])
        ok("parity: a CI-only command is reported", ci_only == ["python3 tools/version.py --check"])
        ok("parity: a step in a job with an `if:` guard is not coverage",
           any("zeta" in m for m in missing))
        ok("parity: conditional steps are listed as not counted", cond == ["B", "D", "Z"])
        missing, _, _, _, _ = parity_report(wf_all.replace("alpha.py check", "alpha.py reconcile"))
        ok("parity: a different subcommand does not cover the gate",
           any("alpha" in m for m in missing))
        _, _, stale, _, _ = parity_report(wf + direct_gamma + nightly)
        ok("parity: a note whose gate CI now runs directly is flagged stale",
           any("BOTH noted and run directly" in x for x in stale))
        CI_PARITY_NOTES["retired"] = "a gate that no longer exists, fixture reason"
        _, _, stale, _, _ = parity_report(wf_all)
        ok("parity: a note naming no battery gate is flagged stale",
           any("names no battery gate" in x for x in stale))
    finally:
        GATES[:] = saved_gates
        CI_PARITY_NOTES.clear()
        CI_PARITY_NOTES.update(saved_notes)
    print(f"battery selftest: {'PASS' if not failures else 'FAIL'} ({len(failures)} failure(s))")
    return 1 if failures else 0


def ci_parity(workflow=None) -> int:
    """P94: assert CI actually ENFORCES every battery gate, instead of printing a roster under a
    step name that promises a comparison. P95: a gate counts only when a BLOCKING CI step (no
    `if:` guard on it or its job beyond always()/success(), no continue-on-error) runs exactly the
    gate's command as its whole step. P94 matched the script path in the step text, so a step
    disabled with `if: false`, or `source_sync.py reconcile` standing in for `source_sync.py
    check`, still counted. Gates CI covers by a different route are declared in CI_PARITY_NOTES
    with a reason; a note whose gate CI now runs directly fails as stale; and commands CI runs
    that are not battery gates are printed, so the two rosters' differences stay visible."""
    wf = Path(workflow) if workflow else ROOT / ".github" / "workflows" / "ci.yml"
    if not wf.exists():
        print(f"battery parity: {wf} not found", file=sys.stderr)
        return 1
    missing, noted, stale, ci_only, conditional = parity_report(wf.read_text(encoding="utf-8"))
    for name in sorted(noted):
        print(f"battery parity: {name} is covered differently in CI: {CI_PARITY_NOTES[name]}")
    for cmd in ci_only:
        print(f"battery parity: CI also runs {cmd!r}, which is not a battery gate")
    if conditional:
        print(f"battery parity: {len(conditional)} conditional or advisory CI step(s) are not "
              f"counted as coverage: {', '.join(conditional)}")
    for line in missing + stale:
        print(f"battery parity: {line}", file=sys.stderr)
    if missing or stale:
        return 1
    print(f"battery parity: CI enforces {len(GATES) - len(noted)} of {len(GATES)} battery gates "
          f"directly; {len(noted)} covered differently (listed above)")
    return 0


def parity_report(text):
    """(missing, noted, stale, ci_only, conditional) for a workflow's text. Pure (no filesystem)
    so each branch is asserted permanently in selftest() rather than red-teamed once by hand."""
    steps = _ci_steps(text)
    commands = [(st, _step_command(st)) for st in steps if not st["gates"]]
    wanted = {name: CI_EQUIVALENT.get(name, argv) for name, argv in GATES}
    covered, missing, noted, stale = set(), [], [], []
    for name, want in wanted.items():
        if any(cmd == want for _, cmd in commands):
            covered.add(name)
        elif name in CI_PARITY_NOTES:
            noted.append(name)
        else:
            near = next((st for st in steps if any(want[0] in ln for ln in st["run"])), None)
            why = ""
            if near is not None and near["gates"]:
                why = f"; step {near['name']!r} does not enforce it ({', '.join(near['gates'])})"
            elif near is not None:
                why = (f"; step {near['name']!r} runs {' / '.join(near['run'])!r}, not exactly "
                       f"the gate's command as its whole step")
            missing.append(f"CI does not enforce the {name} gate (needs a blocking step running "
                           f"exactly: {' '.join(want)}){why}")
    for name in sorted(CI_PARITY_NOTES):
        if name not in wanted:
            stale.append(f"{name!r} is noted but names no battery gate; drop the note")
        elif name in covered:
            stale.append(f"{name!r} is BOTH noted and run directly by CI; drop the stale note")
    ci_only = sorted({" ".join(st["run"][0].split()) for st, cmd in commands
                      if cmd and cmd not in wanted.values()
                      and (cmd[0].startswith("tools/") or cmd[0] == "bash")})
    conditional = [st["name"] or st["run"][0] for st in steps if st["gates"] and st["run"]]
    return missing, noted, stale, ci_only, conditional


def _yaml_value(text):
    """A scalar value with its trailing comment and surrounding quotes removed."""
    val = text.split(" #", 1)[0].strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
        val = val[1:-1]
    return val


def _ci_steps(text):
    """Every step of every job as {job, name, run: [command lines], gates: [why not blocking]}.
    Comments are dropped, so a commented-out step does not exist. A step is BLOCKING (empty
    `gates`) when it runs on every trigger and its failure fails the job. Line-based on purpose:
    the battery is stdlib only, and the workflow is plain block YAML."""
    steps, job, job_gates, cur = [], None, [], None
    in_jobs, block_indent = False, None
    for raw in text.splitlines():
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if block_indent is not None:
            if not stripped or indent > block_indent:
                if stripped and not stripped.startswith("#"):
                    cur["run"].append(stripped.split(" #", 1)[0].rstrip())
                continue
            block_indent = None
        if not stripped or stripped.startswith("#"):
            continue
        if indent == 0:
            in_jobs, job, cur = stripped == "jobs:", None, None
            continue
        if not in_jobs:
            continue
        if indent == 2 and stripped.endswith(":"):
            job, job_gates, cur = stripped[:-1], [], None
            continue
        if job is None:
            continue
        key_indent = indent
        if stripped.startswith("- ") and indent >= 6:
            cur = {"job": job, "name": "", "run": [], "gates": list(job_gates), "indent": indent + 2}
            steps.append(cur)
            stripped, key_indent = stripped[2:].strip(), indent + 2
        key, sep, val = stripped.partition(":")
        key, val = key.strip(), _yaml_value(val)
        if not sep:
            continue
        if cur is None:
            if indent == 4 and key == "if" and val not in _ALWAYS_RUNS:
                job_gates.append(f"job if: {val}")
            elif indent == 4 and key == "continue-on-error" and val != "false":
                job_gates.append(f"job continue-on-error: {val}")
            continue
        if key_indent != cur["indent"]:
            continue                        # a nested mapping (`with:` inputs), not a step key
        if key == "name":
            cur["name"] = val
        elif key == "if" and val not in _ALWAYS_RUNS:
            cur["gates"].append(f"if: {val}")
        elif key == "continue-on-error" and val != "false":
            cur["gates"].append(f"continue-on-error: {val}")
        elif key == "run":
            if val in ("|", ">", "|-", ">-", "|+", ">+"):
                block_indent = key_indent
            elif val:
                cur["run"].append(val)
    return steps


def _step_command(step):
    """A step's single command as shell words, python interpreter dropped; None when the step runs
    anything else as well. A gate must be the WHOLE step: `x || true`, `set +e` earlier in a
    block, or a trailing `; exit 0` would each mask its exit code."""
    if len(step["run"]) != 1:
        return None
    try:
        words = shlex.split(step["run"][0])
    except ValueError:
        return None
    if words and (words[0] in ("python", "python3") or words[0].startswith("python3.")):
        words = words[1:]
    return words


# Gates CI covers by a different route than running the gate's own command, each with its reason.
CI_PARITY_NOTES = {
    "staged secret scan": "CI scans ALL tracked content (secret_scan.py --tracked), a superset of "
                          "the staged scan, because a CI checkout has nothing staged",
    "preflight push": "checks the LOCAL working tree before a push (unstaged edits, branch state); "
                      "a CI checkout is clean by construction, so there is nothing for it to find",
}
# The shell words CI runs for a gate whose battery argv is not a plain script call.
CI_EQUIVALENT = {"launcher syntax": ["bash", "-n", "Start Creator OS Setup.command"]}
# `if:` values that cannot be false on a push, so they do not make a step conditional.
_ALWAYS_RUNS = {"always()", "success()", "true", "${{ always() }}", "${{ success() }}",
                "${{ true }}"}


def main(argv) -> int:
    if "--selftest" in argv:
        return selftest()
    if "--check-parity" in argv:
        return ci_parity()
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
