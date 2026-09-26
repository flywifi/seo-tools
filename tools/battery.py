#!/usr/bin/env python3
"""battery.py -- the ONE gate runner (P81).

P80 pushed a red commit because an ad-hoc shell gate piped hash_audit through `tail -1`, masking its
exit code, and pushed another with a stale Mac surface because `git add -A` ran after the reconcile.
This runner closes the class:

  * every gate is a subprocess whose RAW exit code decides; nothing is piped or filtered;
  * it REFUSES to run while tracked files carry unstaged edits (the mac-surface and package manifests
    derive from the INDEX, so reconciling with a dirty worktree blesses bytes a commit will not carry);
  * `--py <interpreter>` reruns the battery under a second interpreter (the repo floor rule);
  * `--list` prints the gate roster; `--check-parity` compares it with the CI workflow: a gate
    counts when a step that _ci_steps reads as blocking runs exactly the gate's command as the
    whole step (ci_parity lists the limits of that reading).

Drift invariant 61 (tools/sync_check.py::check_ci_parity) runs the same parity report over
.github/workflows/ci.yml, so the comparison also runs wherever the drift guard gate runs.

Outside a git checkout the unstaged check prints a loud DID-NOT-RUN advisory instead of silently
passing (the repo's fail-closed idiom). Stdlib only.
"""
from __future__ import annotations

import re
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
    ("version consistency", ["tools/version.py", "--check"]),
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


def _selftest_roster(ok):
    """The roster keeps the version check that CI runs as its own step."""
    ok("roster: the battery runs `tools/version.py --check`",
       ("version consistency", ["tools/version.py", "--check"]) in GATES)


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
    _selftest_roster(ok)

    _selftest_reader(ok)
    _selftest_parity(ok)
    print(f"battery selftest: {'PASS' if not failures else 'FAIL'} ({len(failures)} failure(s))")
    return 1 if failures else 0


def _same(a, b):
    """Equal, with equal types all the way down (True is not 1, 1.0 is not 1)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return list(a) == list(b) and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _selftest_reader(ok):
    """What _yaml_subset returns for each form it reads, and the forms it refuses. Each expected
    value is what a YAML 1.2 core-schema parser returns for the snippet; a refused snippet is
    invalid YAML or a form outside the subset."""
    no = WorkflowSyntaxError
    cases = [
        ("block mapping and list", "a: 1\nb:\n  - x\n  - y\n", {"a": 1, "b": ["x", "y"]}),
        ("empty values are null", "a:\nb: ~\nc: null\n", {"a": None, "b": None, "c": None}),
        ("YAML 1.2 booleans only; on and yes stay text", "on: push\nyes: no\nt: true\nf: False\n",
         {"on": "push", "yes": "no", "t": True, "f": False}),
        ("numbers", "a: 3.10\nb: 012\nc: 0o17\nd: 0x1F\ne: -2\nf: 1e3\n",
         {"a": 3.1, "b": 12, "c": 15, "d": 31, "e": -2, "f": 1000.0}),
        ("text that only looks special", "a: 1.2.3\nb: 2024-01-01\nc: ${{ always() }}\nd: x:y\n",
         {"a": "1.2.3", "b": "2024-01-01", "c": "${{ always() }}", "d": "x:y"}),
        ("flow list and mapping on one line", "a: [\"**\", x, 'y', 3]\nb: {k: v, n: [1]}\nc: [x,]\nd: []\n",
         {"a": ["**", "x", "y", 3], "b": {"k": "v", "n": [1]}, "c": ["x"], "d": []}),
        ("literal block: clip, strip and keep", "a: |\n  x\n  y # z\nb: |-\n  x\n\nc: |+\n  x\n\nd: 1\n",
         {"a": "x\ny # z\n", "b": "x", "c": "x\n\n", "d": 1}),
        ("indentation indicator", "a: |2\n   x\n  y\n", {"a": " x\ny\n"}),
        ("a comment line inside a block is text", "a: |\n  x\n  # y\n# z\nb: 1\n", {"a": "x\n# y\n", "b": 1}),
        ("document start, CRLF, no final newline", "---\r\na: 1\r\nb: |\r\n  x", {"a": 1, "b": "x"}),
        ("a document of comments is empty", "# only a comment\n", None),
        ("a plain value continued onto more lines folds", "a: python3 x.py\n  || true\nb: c\n\n  d\n",
         {"a": "python3 x.py || true", "b": "c\nd"}),
        ("a dash inside a continuation is text", "a: x\n  - y\n", {"a": "x - y"}),
        ("refused: a plain value continued after a comment", "a: b # c\n  d\n", no),
        ("mapping items, wider dash spacing", "- name: A\n  with:\n    k: v\n-   run: x\n    if: false\n",
         [{"name": "A", "with": {"k": "v"}}, {"run": "x", "if": False}]),
        ("quoted keys and values", "'if': 'it''s # x'\n\"run\": \"x\\ty\\u00e9\"\n",
         {"if": "it's # x", "run": "x\tyé"}),
        ("a list written at its key's indentation", "k:\n- a\n- b\nc: 3\n", {"k": ["a", "b"], "c": 3}),
        ("comments after keys and values", "jobs:   # all\n  g:   # main\n    x: b   # c\n    y: b#c\n",
         {"jobs": {"g": {"x": "b", "y": "b#c"}}}),
        ("a value on the line after its key", "a:\n  python3 x.py\n", {"a": "python3 x.py"}),
        ("a flow-mapping step", "- {name: A, run: python3 x.py}\n", [{"name": "A", "run": "python3 x.py"}]),
        ("folded block with a more-indented line", "a: >\n  x\n  y\n\n  z\nb: >-\n  x\n    y\n  z\n",
         {"a": "x y\nz\n", "b": "x\n  y\nz"}),
        ("refused: anchor", "a: &x 1\n", no),
        ("refused: alias", "a: *x\n", no),
        ("refused: tag", "a: !!str 1\n", no),
        ("refused: merge key", "b:\n  <<: {x: 1}\n", no),
        ("refused: duplicate key", "a: 1\na: 2\n", no),
        ("refused: complex key", "? a\n: b\n", no),
        ("refused: quoted value spanning lines", "a: 'x\n  y'\n", no),
        ("refused: flow value spanning lines", "a: [x,\n  y]\n", no),
        ("refused: tab indentation", "a:\n\tb: 1\n", no),
        ("refused: nested dash on one line", "- - x\n", no),
        ("refused: `: ` inside a plain value", "a: b: c\n", no),
        ("refused: a second document", "a: 1\n---\nb: 2\n", no),
        ("refused: a directive", "%YAML 1.2\n---\na: 1\n", no),
        ("refused: a pair inside a flow list", "a: [k: v]\n", no),
        ("refused: text after a quoted value", "a: 'x' y\n", no),
        ("refused: an empty block scalar", "a: |\nb: 1\n", no),
        ("refused: an unknown escape", "a: \"\\q\"\n", no),
        ("refused: unexpected indentation", "a: 1\n  b: 2\n", no),
        ("refused: a list item where a key belongs", "a: 1\n- b\n", no),
        ("refused: a document that is only text", "just text\n", no),
        ("refused: a control character", "a: \x07\n", no),
    ]
    for label, text, want in cases:
        try:
            got = _yaml_subset(text)
        except WorkflowSyntaxError:
            got = no
        ok(f"reader: {label}", _same(got, want))



def _selftest_parity(ok):
    """Parity branches, asserted on fixture workflows."""
    saved_gates, saved_notes = list(GATES), dict(CI_PARITY_NOTES)
    try:
        GATES[:] = [("alpha", ["tools/alpha.py", "check"]), ("beta", ["tools/beta.py"]),
                    ("gamma", ["tools/gamma.py"]), ("delta", ["tools/delta.py"]),
                    ("epsilon", ["tools/epsilon.py"]), ("zeta", ["tools/zeta.py"])]
        CI_PARITY_NOTES.clear()
        CI_PARITY_NOTES.update({"gamma": "covered by a superset step, fixture reason"})
        on = "on:\n  push:\n    branches: ['**']\n"
        wf = (on + "jobs:\n  guard:\n    runs-on: x\n    steps:\n"
              "      - name: A\n        run: python3 tools/alpha.py check\n"
              "      - name: B\n        if: false\n        run: python3 tools/beta.py\n"
              "      - name: D\n        continue-on-error: true\n        run: python3 tools/delta.py\n"
              "      - name: E\n        run: |\n          set +e\n          python3 tools/epsilon.py\n"
              "      - name: V\n        run: python3 tools/version.py --check\n")
        nightly = ("  nightly:\n    if: github.event_name == 'schedule'\n    runs-on: x\n    steps:\n"
                   "      - name: Z\n        run: python3 tools/zeta.py\n")
        missing, noted, stale, ci_only, cond = parity_report(wf + nightly)
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
        missing = parity_report(wf.replace("alpha.py check", "alpha.py reconcile") + nightly)[0]
        ok("parity: a different subcommand does not cover the gate", any("alpha" in m for m in missing))
        stale = parity_report(wf + "      - name: G\n        run: python3 tools/gamma.py\n" + nightly)[2]
        ok("parity: a note whose gate CI now runs directly is flagged stale",
           any("BOTH noted and run directly" in x for x in stale))
        def report(text):
            try:
                return parity_report(text)[0]
            except Exception as exc:  # noqa: BLE001 - a crash fails the pin that called it
                return [f"crash: {type(exc).__name__}: {exc}"]

        def counts(text):
            """True when the alpha gate counts, False when it does not, None when the report crashed."""
            missing = report(text)
            if any(m.startswith("crash:") for m in missing):
                return None
            return not any("alpha" in m or "cannot be read" in m for m in missing)

        def refused(text):
            missing = report(text)
            return len(missing) == 1 and "cannot be read" in missing[0]

        head = on + "jobs:\n  j:\n    runs-on: x\n"
        step = "      - run: python3 tools/alpha.py check\n"
        job = head + "    steps:\n" + step
        ok("parity: `if: success()`, `if: true` and `if: ${{ always() }}` steps count",
           counts(job + "        if: success()\n") is True and counts(job + "        if: true\n") is True
           and counts(job + "        if: ${{ always() }}\n") is True)
        ok("parity: only always(), success() and true, bare or in ${{ }}, keep an `if:` step blocking",
           _ALWAYS_RUNS == {"always()", "success()", "true", "${{ always() }}", "${{ success() }}", "${{ true }}"})
        ok("parity: a job-level continue-on-error after `steps:` is not coverage",
           counts(job + "    continue-on-error: true\n") is False)
        ok("parity: a job-level `if:` after `steps:` is not coverage", counts(job + "    if: false\n") is False)
        ok("parity: a job-level `if:` after a list-valued matrix is not coverage",
           counts(head + "    strategy:\n      matrix:\n        py:\n          - '3.12'\n"
                  "    if: false\n    steps:\n" + step) is False)
        ok("parity: a commented-out step does not exist",
           counts(head + "    steps:\n      - run: echo\n#" + step) is False)
        ok("parity: a workflow the reader refuses counts no gate and names the line",
           refused(job + "  broken: &a\n") and "(line 9:" in report(job + "  broken: &a\n")[0])
        ok("parity: a workflow without a `jobs:` mapping, or a job that is not a mapping, counts no gate",
           refused(on + "jobs: x\n") and refused(on + "jobs:\n  j: x\n"))
        ok("parity: a plain `run:` value continued onto a second line is not coverage",
           counts(job + "          || true\n") is False)
        ok("parity: a quoted `if` key is read", counts(job + "        'if': false\n") is False)
        ok("parity: `-   run:` items, a job key with a trailing comment and a job body indented six are read",
           counts(head + "    steps:\n      -   run: python3 tools/alpha.py check\n          if: false\n") is False
           and counts(on + "jobs:\n  j:   # c\n    if: false\n    runs-on: x\n    steps:\n" + step) is False
           and counts(on + "jobs:\n  j:\n      if: false\n      runs-on: x\n      steps:\n"
                      "        - run: python3 tools/alpha.py check\n") is False)
        ok("parity: a `run:` item outside `steps:` is not a step",
           counts(head + "    strategy:\n      matrix:\n        include:\n"
                  "          - run: python3 tools/alpha.py check\n    steps:\n      - run: echo\n") is False)
        ok("parity: a `steps:` value that is not a list, or a step that is not a mapping, counts no gate",
           refused(head + "    steps: 5\n") and refused(head + "    steps:\n      - x\n"))
        ok("parity: a job without `steps:` (a reusable-workflow call) runs no gate and does not stop the read",
           counts(on + "jobs:\n  r:\n    uses: ./.github/workflows/x.yml\n  j:\n    runs-on: x\n    steps:\n" + step) is True
           and counts(on + "jobs:\n  r:\n    uses: ./.github/workflows/x.yml\n") is False)
        ok("parity: comments after `jobs:` and a job key, and a step list at its key's indentation, count",
           counts(on + "jobs:   # c\n  j:   # c\n    runs-on: x\n    steps:\n    - run: python3 tools/alpha.py check\n") is True)
        ok("parity: a folded `run:` value counts",
           counts(head + "    steps:\n      - run: >-\n          python3 tools/alpha.py\n          check\n") is True)
        ok("parity: a `run:` value on the next line counts",
           counts(head + "    steps:\n      - run:\n          python3 tools/alpha.py check\n") is True)
        ok("parity: a flow-mapping step counts",
           counts(head + "    steps:\n      - {name: A, run: python3 tools/alpha.py check}\n") is True)
        ok("parity: a workflow without a push trigger is not coverage",
           counts(job.replace(on, "on: workflow_dispatch\n")) is False
           and counts(job.replace(on, "on:\n  pull_request:\n")) is False)
        ok("parity: `on: push`, `on: [push]` and a push with no filters count",
           counts(job.replace(on, "on: push\n")) is True and counts(job.replace(on, "on: [push]\n")) is True
           and counts(job.replace(on, "on:\n  push:\n")) is True)
        ok("parity: a push trigger limited to some branches, or with a `!` pattern, is not coverage",
           counts(job.replace("['**']", "[main]")) is False
           and counts(job.replace("['**']", "['**', '!main']")) is False)
        ok("parity: `branches: '**'` written as a string counts", counts(job.replace("['**']", "'**'")) is True)
        ok("parity: a push trigger filtered by paths is not coverage",
           counts(job.replace("['**']\n", "['**']\n    paths: [src]\n")) is False)
        ok("parity: a push trigger that is not a mapping is not coverage",
           counts(job.replace(on, "on:\n  push: [main]\n")) is False
           and counts(job.replace(on, "on:\n  push: true\n")) is False)
        ok("parity: a step `shell:` other than bash or sh is not coverage, and bash and sh count",
           all(counts(job + f"        shell: {s}\n") is False for s in ("python", "pwsh", "cmd", "bash {0}", "sh -e {0}"))
           and counts(job + "        shell: bash\n") is True and counts(job + "        shell: sh\n") is True)
        ok("parity: the shells that keep a step blocking are exactly bash and sh", _SAFE_SHELLS == {"bash", "sh"})
        ok("parity: a step `working-directory:` is not coverage", counts(job + "        working-directory: sub\n") is False)
        ok("parity: a workflow `defaults.run.shell` other than bash or sh is not coverage, and bash counts",
           counts(job.replace("jobs:\n", "defaults:\n  run:\n    shell: bash {0}\njobs:\n")) is False
           and counts(job.replace("jobs:\n", "defaults:\n  run:\n    shell: bash\njobs:\n")) is True)
        ok("parity: a job `defaults.run.working-directory` is not coverage",
           counts(head + "    defaults:\n      run:\n        working-directory: sub\n    steps:\n" + step) is False)
        ok("parity: a non-mapping `defaults` or `defaults.run` is not coverage",
           counts(job.replace("jobs:\n", "defaults:\n  run: x\njobs:\n")) is False
           and counts(job.replace("jobs:\n", "defaults: x\njobs:\n")) is False)
        nd = (on + "jobs:\n  nightly:\n    if: github.event_name == 'schedule'\n    runs-on: x\n"
              "    steps:\n      - run: echo\n  after:\n    needs: nightly\n{cond}    runs-on: x\n"
              "    steps:\n      - run: python3 tools/alpha.py check\n")
        ok("parity: a job that needs a job with a gate is not coverage", counts(nd.format(cond="")) is False)
        ok("parity: needs plus `if: success()` or `if: true` is not coverage (GitHub adds success())",
           counts(nd.format(cond="    if: success()\n")) is False and counts(nd.format(cond="    if: true\n")) is False)
        ok("parity: needs plus `if: always()` counts, and only always() exempts",
           counts(nd.format(cond="    if: always()\n")) is True and _ALWAYS_ONLY == {"always()", "${{ always() }}"})
        chain = (nd.format(cond="") + "  last:\n    needs: [after]\n    runs-on: x\n    steps:\n"
                 "      - run: python3 tools/beta.py\n")
        ok("parity: needs propagates through a chain of jobs", any("beta" in m for m in report(chain)))
        ok("parity: needs propagates through jobs written before the jobs they need",
           any("beta" in m for m in report(on + "jobs:\n  last:\n    needs: after\n    runs-on: x\n    steps:\n"
                                            "      - run: python3 tools/beta.py\n  after:\n    needs: nightly\n"
                                            "    runs-on: x\n    steps:\n      - run: echo\n  nightly:\n"
                                            "    if: github.event_name == 'schedule'\n    runs-on: x\n"
                                            "    steps:\n      - run: echo\n")))
        ok("parity: needs naming a job the workflow does not define counts no gate",
           refused(nd.format(cond="").replace("needs: nightly", "needs: ghost")))
        multi = parity_report(on + "jobs:\n  j:\n    runs-on: x\n    steps:\n      - name: M\n"
                              "        run: |\n          echo scanning\n          python3 tools/omega.py --all $R\n")[3]
        ok("parity: a command on one line of a multi-line step is reported as CI-only",
           multi == ["python3 tools/omega.py --all $R (one line of step 'M')"])
        co = (on + "jobs:\n  j:\n    runs-on: x\n    steps:\n      - uses: actions/checkout@v4\n"
              "        with:\n          ref: v0.1.0\n      - run: python3 tools/alpha.py check\n")
        ok("parity: a step after a checkout setting `ref:`, `repository:` or `path:` is not coverage",
           all(counts(co.replace("ref: v0.1.0", f"{k}: v")) is False for k in ("ref", "repository", "path")))
        ok("parity: a checkout with only fetch-depth leaves later steps blocking",
           counts(co.replace("ref: v0.1.0", "fetch-depth: 0")) is True)
        envd = on + "jobs:\n  j:\n    runs-on: x\n{job}    steps:\n      - run: python3 tools/alpha.py check\n{step}"

        def env_counts(job="", step=""):
            return counts(envd.format(job=job, step=step))

        ok("parity: each runtime variable in a step `env:` is not coverage",
           all(env_counts(step=f"        env:\n          {v}: x\n") is False
               for v in ("BASH_ENV", "ENV", "PATH", "SHELLOPTS", "BASHOPTS", "LD_PRELOAD", "LD_LIBRARY_PATH",
                         "CI", "PYTHONPATH", "GIT_DIR")))
        ok("parity: a job with `container:` or a PYTHON* variable in `env:` is not coverage",
           env_counts(job="    container: busybox\n") is False and env_counts(job="    env:\n      PYTHONPATH: x\n") is False)
        ok("parity: a workflow-level runtime `env:` or a non-mapping `env:` is not coverage",
           counts(job.replace("jobs:\n", "env:\n  BASH_ENV: x\njobs:\n")) is False
           and env_counts(step="        env: ${{ fromJSON(vars.E) }}\n") is False)
        ok("parity: an unrelated `env:` leaves the step blocking", env_counts(step="        env:\n          TZ: UTC\n") is True)
        flaky = on + ("jobs:\n  flaky:\n    continue-on-error: true\n    runs-on: x\n    steps:\n"
                      "      - name: K\n        run: python3 tools/alpha.py check\n")
        ok("parity: a job-level continue-on-error before `steps:` is not coverage",
           any("alpha" in m for m in parity_report(flaky)[0]))
        steps = _ci_steps(on + "jobs:\n  j:\n    runs-on: x\n    steps:\n"
                          "      - name: S\n        if: success()\n        with:\n          if: false\n"
                          "        run: python3 tools/alpha.py check\n"
                          "      # - name: C\n      #   run: python3 tools/beta.py\n")
        ok("parity: `if: success()` does not gate a step, a key under `with:` is not a step key, and a "
           "commented-out step does not exist", [(s["name"], s["gates"]) for s in steps] == [("S", [])])
        CI_PARITY_NOTES["retired"] = "a gate that no longer exists, fixture reason"
        stale = parity_report(wf + nightly)[2]
        ok("parity: a note naming no battery gate is flagged stale",
           any("names no battery gate" in x for x in stale))
    finally:
        GATES[:] = saved_gates
        CI_PARITY_NOTES.clear()
        CI_PARITY_NOTES.update(saved_notes)


def ci_parity(workflow=None) -> int:
    """Compare the battery roster with CI (.github/workflows/ci.yml unless another workflow path
    is passed). A gate counts when a step that _ci_steps reads as blocking runs exactly the gate's
    command as its whole step; a leading `python` or `python3` is dropped. P94 matched the script
    path in the step text, so a step disabled with `if: false`, or `source_sync.py reconcile`
    standing in for `source_sync.py check`, still counted.
    A workflow that _yaml_subset refuses counts no gate, and the report names the line.
    Gates CI covers by a different route are declared in CI_PARITY_NOTES with a reason; a note
    whose gate CI now runs directly, or that names no gate, fails as stale. Steps that run a
    command and have a gate are listed as not counted. CI-only commands are printed: the command
    of a single-line blocking step, and each line of a multi-line blocking step, whose first word
    after the interpreter is a tools/ script or bash and that is not a gate.

    Limits of this reading:
      * what an earlier step or action does to the checkout, to a gate script or to the
        environment ($GITHUB_ENV, $GITHUB_PATH), the runner image, and workflow files other than
        the one read are outside it."""
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
    print(f"battery parity: {len(GATES) - len(noted)} of {len(GATES)} battery gates run as blocking "
          f"CI steps; {len(noted)} covered differently (listed above)")
    return 0


def parity_report(text):
    """(missing, noted, stale, ci_only, conditional) for a workflow's text. Pure (no filesystem),
    so _selftest_parity can assert its branches on fixture workflows. A workflow the reader
    refuses gives one missing entry naming the line, and no gate counts."""
    try:
        steps = _ci_steps(text)
    except WorkflowSyntaxError as exc:
        return [f"the workflow cannot be read ({exc}); no gate is counted"], [], [], [], []
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
    ci_only = set()
    for st, cmd in commands:
        lines = [" ".join(st["run"][0].split())] if cmd is not None else st["run"]
        for line in lines:
            words = cmd if cmd is not None else _step_command({"run": [line]})
            if words and words not in wanted.values() and (words[0].startswith("tools/") or words[0] == "bash"):
                ci_only.add(line if cmd is not None else f"{' '.join(line.split())} (one line of step {st['name']!r})")
    ci_only = sorted(ci_only)
    conditional = [st["name"] or st["run"][0] for st in steps if st["gates"] and st["run"]]
    return missing, noted, stale, ci_only, conditional


def _txt(value):
    """A parsed value as the text an `if:` or a flag holds (true or false for booleans)."""
    if value is True or value is False:
        return "true" if value else "false"
    return "" if value is None else str(value).strip()


def _push_gate(on):
    """Why a push to any branch might not run the workflow, or "" when every push runs it."""
    if isinstance(on, str):
        on = [on]
    if isinstance(on, list):
        return "" if "push" in on else "on: has no push trigger"
    if not isinstance(on, dict) or "push" not in on:
        return "on: has no push trigger"
    push = on["push"]
    if push is None or push == {}:
        return ""
    if not isinstance(push, dict):
        return f"on.push is {_txt(push)!r}"
    extra = sorted(str(k) for k in push if k != "branches")
    if extra:
        return f"on.push filters on {', '.join(extra)}"
    branches = push["branches"]
    branches = [branches] if isinstance(branches, str) else branches
    if isinstance(branches, list) and "**" in branches and not any(str(b).startswith("!") for b in branches):
        return ""
    return f"on.push.branches {_txt(branches)} may not match every branch"


# `shell:` values that keep GitHub's exit-on-error wrapper (bash -eo pipefail, sh -e).
_SAFE_SHELLS = {"bash", "sh"}


def _defaults_gates(block, where):
    """Gates from a workflow's or a job's `defaults.run`."""
    run = block.get("defaults")
    run = run.get("run") if isinstance(run, dict) else run
    if run is None:
        return []
    if not isinstance(run, dict):
        return [f"{where} defaults: {_txt(block.get('defaults'))}"]
    gates = []
    if "shell" in run and _txt(run["shell"]) not in _SAFE_SHELLS:
        gates.append(f"{where} defaults.run.shell: {_txt(run['shell'])}")
    if "working-directory" in run:
        gates.append(f"{where} defaults.run.working-directory: {_txt(run['working-directory'])}")
    return gates


# The only job `if:` that runs a job whose needed job was skipped (GitHub adds success() to others).
_ALWAYS_ONLY = {"always()", "${{ always() }}"}


# Variables that change a step's shell start-up, interpreter or search path, or whether a gate
# fails closed when git is unavailable (CI); _env_gates also gates PYTHON* and GIT_* variables.
_RUNTIME_ENV = {"BASH_ENV", "ENV", "PATH", "SHELLOPTS", "BASHOPTS", "LD_PRELOAD", "LD_LIBRARY_PATH",
                "CI"}


def _env_gates(block, where):
    """Gates from an `env:` block that sets a _RUNTIME_ENV, PYTHON* or GIT_* variable, or that is
    not a mapping."""
    env = block.get("env")
    if env is None:
        return []
    if not isinstance(env, dict):
        return [f"{where} env: {_txt(env)}"]
    return [f"{where} env sets {k}" for k in env
            if str(k) in _RUNTIME_ENV or str(k).startswith(("PYTHON", "GIT_"))]


def _steps_from_doc(doc):
    """Every item of every job's `steps:` list, as {job, name, run: [command lines], gates: [why
    the step is not blocking]}; a step is blocking when `gates` is empty. A step gets a gate when
      * its job's or its own `if:` is anything but always(), success() or true, bare or in ${{ }}
      * its job or the step sets continue-on-error to anything but false
      * `on:` has no push trigger, or filters pushes by anything but a `branches` value holding
        '**' and no '!' pattern
      * the step sets `shell:` to anything but bash or sh, or sets `working-directory:`, or the
        workflow or the job sets `defaults.run.shell` to anything but bash or sh, sets
        `defaults.run.working-directory`, or sets `defaults` or `defaults.run` to a non-mapping
      * its job needs, directly or through other jobs, a job with a gate, and its own `if:` is not
        always() (GitHub skips a job whose needed job was skipped unless its `if:` is always())
      * an earlier `actions/checkout` step in its job sets `ref:`, `repository:` or `path:`
      * the workflow, the job or the step sets in `env:` BASH_ENV, ENV, PATH, SHELLOPTS, BASHOPTS,
        LD_PRELOAD, LD_LIBRARY_PATH, CI, or a PYTHON* or GIT_* variable, or sets `env:` to a
        non-mapping, or the job sets `container:`; any other `env:` variable leaves it blocking
    Workflow, job and step keys not named here are not read."""
    if not isinstance(doc, dict) or not isinstance(doc.get("jobs"), dict):
        raise WorkflowSyntaxError(0, "the workflow has no `jobs:` mapping")
    base = []
    base += _env_gates(doc, "workflow")
    base += _defaults_gates(doc, "workflow")
    base += [g for g in [_push_gate(doc.get("on"))] if g]
    jobs, job_gates = doc["jobs"], {}
    for jid, job in jobs.items():
        if not isinstance(job, dict):
            raise WorkflowSyntaxError(0, f"job {jid!r} is not a mapping")
        gates = list(base)
        gates += _env_gates(job, "job")
        if job.get("container") is not None:
            gates.append(f"job container: {_txt(job['container'])}")
        gates += _defaults_gates(job, "job")
        if _txt(job.get("if", True)) not in _ALWAYS_RUNS:
            gates.append(f"job if: {_txt(job['if'])}")
        if job.get("continue-on-error", False) is not False:
            gates.append(f"job continue-on-error: {_txt(job['continue-on-error'])}")
        job_gates[jid] = gates
    needs = {}
    for jid, job in jobs.items():
        need = job.get("needs", [])
        need = [need] if isinstance(need, str) else need
        if not isinstance(need, list) or any(not isinstance(n, str) or n not in jobs for n in need):
            raise WorkflowSyntaxError(0, f"job {jid!r} needs a job this workflow does not define")
        needs[jid] = need
    changed = True
    while changed:
        changed = False
        for jid, job in jobs.items():
            if _txt(job.get("if", True)) in _ALWAYS_ONLY:
                continue
            for n in needs[jid]:
                why = f"needs {n}, which is not blocking"
                if job_gates[n] and why not in job_gates[jid]:
                    job_gates[jid].append(why)
                    changed = True
    steps = []
    for jid, job in jobs.items():
        items = job.get("steps")
        items = [] if items is None else items
        if not isinstance(items, list):
            raise WorkflowSyntaxError(0, f"job {jid!r} has a `steps:` value that is not a list")
        moved = []
        for st in items:
            if not isinstance(st, dict):
                raise WorkflowSyntaxError(0, f"a step of job {jid!r} is not a mapping")
            gates = list(job_gates[jid])
            gates += _env_gates(st, "step")
            gates += moved
            if "shell" in st and _txt(st["shell"]) not in _SAFE_SHELLS:
                gates.append(f"shell: {_txt(st['shell'])}")
            if "working-directory" in st:
                gates.append(f"working-directory: {_txt(st['working-directory'])}")
            if _txt(st.get("if", True)) not in _ALWAYS_RUNS:
                gates.append(f"if: {_txt(st['if'])}")
            if st.get("continue-on-error", False) is not False:
                gates.append(f"continue-on-error: {_txt(st['continue-on-error'])}")
            text = "" if st.get("run") is None else str(st["run"])
            run = [ln.strip().split(" #", 1)[0].rstrip() for ln in text.split("\n")]
            steps.append({"job": str(jid), "name": _txt(st.get("name", "")),
                          "run": [ln for ln in run if ln and not ln.startswith("#")], "gates": gates})
            inputs = st.get("with") if isinstance(st.get("with"), dict) else {}
            if _txt(st.get("uses", "")).lower().startswith("actions/checkout"):
                moved += [f"an earlier checkout sets {k}: {_txt(inputs[k])}"
                          for k in ("ref", "repository", "path") if k in inputs]
    return steps


def _ci_steps(text):
    """The steps of a workflow's text; raises WorkflowSyntaxError when the reader refuses it.
    A `run:` outside a job's `steps:` list is data, not a step."""
    return _steps_from_doc(_yaml_subset(text))


# The workflow reader. _yaml_subset reads the block YAML that GitHub workflows are written in and
# refuses everything else with WorkflowSyntaxError, so parity fails closed instead of guessing. It
# reads block mappings and lists (including a list written at its key's indentation), plain values
# (continuation lines are folded the way YAML folds them), single- and double-quoted values on one
# line, flow lists and mappings on one line, literal and folded block scalars with chomping and
# indentation indicators, comments, and one leading `---`. Plain values resolve under the YAML 1.2
# core schema, as GitHub's parser does, so `on` stays a string. It refuses anchors, aliases, tags,
# `?` keys, `<<` merge keys, duplicate keys, quoted or flow values that span lines, a tab anywhere
# except inside a block scalar or on a comment line, `- -` on one line, `: ` inside a plain value,
# directives, and a second document. _selftest_reader pins what it returns for each form.


class WorkflowSyntaxError(ValueError):
    """The workflow uses YAML outside the subset _yaml_subset reads."""

    def __init__(self, line, why):
        super().__init__(f"line {line}: {why}" if line else why)
        self.line, self.why = line, why


_NON_PRINTABLE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f  \ud800-\udfff￾￿]")
_ESCAPES = {"0": "\0", "a": "\a", "b": "\b", "t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r",
            "e": "\x1b", " ": " ", '"': '"', "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0",
            "L": " ", "P": " "}
_HEX_ESCAPES = {"x": 2, "u": 4, "U": 8}


def _typed(text):
    """A plain scalar under the YAML 1.2 core schema (null, bool, int, float, else the string)."""
    if text in ("", "~", "null", "Null", "NULL"):
        return None
    if text in ("true", "True", "TRUE", "false", "False", "FALSE"):
        return text[0] in "tT"
    if re.fullmatch(r"[-+]?[0-9]+", text):
        return int(text)
    if re.fullmatch(r"0o[0-7]+", text):
        return int(text[2:], 8)
    if re.fullmatch(r"0x[0-9a-fA-F]+", text):
        return int(text[2:], 16)
    if re.fullmatch(r"[-+]?(\.[0-9]+|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?", text):
        return float(text)
    if re.fullmatch(r"[-+]?\.(inf|Inf|INF)", text):
        return float("-inf") if text[0] == "-" else float("inf")
    if re.fullmatch(r"\.(nan|NaN|NAN)", text):
        return float("nan")
    return text


def _is_dash(body):
    return body == "-" or body.startswith("- ")


class _Subset:
    """Recursive descent over the lines of one document; see the comment above for the subset."""

    def __init__(self, text):
        text = text[1:] if text.startswith("﻿") else text
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        bad = _NON_PRINTABLE.search(text)
        if bad:
            raise WorkflowSyntaxError(text.count("\n", 0, bad.start()) + 1,
                                      f"character {bad.group()!r} is outside the subset")
        self.lines = text.split("\n")
        self.final_break = self.lines[-1] == ""
        if self.final_break:
            self.lines.pop()
        self.i = 0

    def fail(self, ln, why):
        raise WorkflowSyntaxError(ln + 1, why)

    def parse(self):
        ln = self._next()
        if ln is not None and self.lines[ln].startswith("%"):
            self.fail(ln, "a directive is outside the subset")
        if ln is not None and re.fullmatch(r"---( +#.*| *)", self.lines[ln]):
            self.i = ln + 1
            ln = self._next()
        if ln is None:
            return None
        node = self._node(self._indent(ln), -1)
        ln = self._next()
        if ln is not None:
            self.fail(ln, "content after the end of the document")
        return node

    def _next(self):
        """The index of the next line from self.i that is neither blank nor a comment."""
        i = self.i
        while i < len(self.lines):
            s = self.lines[i].lstrip(" ")
            if s and not s.startswith("#"):
                return i
            i += 1
        return None

    def _blank(self, i):
        return not self.lines[i].strip(" ")

    def _indent(self, i):
        return len(self.lines[i]) - len(self.lines[i].lstrip(" "))

    def _body(self, i):
        line = self.lines[i]
        if "\t" in line:
            self.fail(i, "a tab outside a block scalar or a comment line is outside the subset")
        if line[:3] in ("---", "...") and line[3:4] in ("", " "):
            self.fail(i, "a document marker inside the workflow is outside the subset")
        return line.strip(" ")

    def _node(self, ind, parent):
        ln = self._next()
        body = self._body(ln)
        if _is_dash(body):
            return self._seq(ind)
        if self._key(body, ln) is not None:
            return self._map(ind)
        if parent < 0:
            self.fail(ln, "the document is neither a mapping nor a list")
        if body[0] in "|>":
            self.fail(ln, "a block scalar header on its own line is outside the subset")
        self.i = ln + 1
        return self._scalar(body, parent, ln)

    def _below(self, parent, indentless):
        """The value written on the lines after `key:` or `-` (None when there is none)."""
        ln = self._next()
        if ln is None:
            return None
        ind = self._indent(ln)
        if ind > parent:
            return self._node(ind, parent)
        if indentless and ind == parent and _is_dash(self._body(ln)):
            return self._seq(ind)
        return None

    def _seq(self, ind):
        out = []
        while True:
            ln = self._next()
            if ln is None or self._indent(ln) < ind:
                return out
            body = self._body(ln)
            if self._indent(ln) > ind:
                self.fail(ln, "unexpected indentation")
            if not _is_dash(body):
                return out
            rest = body[1:].lstrip(" ")
            self.i = ln + 1
            if not rest or rest.startswith("#"):
                out.append(self._below(ind, False))
            elif _is_dash(rest):
                self.fail(ln, "a `- -` list on one line is outside the subset")
            elif self._key(rest, ln) is not None:
                out.append(self._map(ind + len(body) - len(rest), (ln, rest)))
            else:
                out.append(self._scalar(rest, ind, ln))

    def _map(self, ind, first=None):
        out = {}
        while True:
            if first is not None:
                (ln, body), first = first, None
            else:
                ln = self._next()
                if ln is None or self._indent(ln) < ind:
                    return out
                body = self._body(ln)
                if self._indent(ln) > ind:
                    self.fail(ln, "unexpected indentation")
            pair = None if _is_dash(body) else self._key(body, ln)
            if pair is None:
                self.fail(ln, "expected a `key: value` line")
            key, rest = pair
            if key in out:
                self.fail(ln, f"duplicate key {key!r}")
            self.i = ln + 1
            out[key] = self._below(ind, True) if not rest or rest[0] == "#" else self._scalar(rest, ind, ln)

    def _key(self, body, ln):
        """(key, text after `: `) when the line is a mapping entry, else None."""
        c = body[0]
        if c in "'\"":
            key, k = self._quoted(body, 0, ln)
            rest = body[k:].lstrip(" ")
            if rest[:1] == ":" and rest[1:2] in ("", " "):
                return key, rest[1:].lstrip(" ")
            return None
        if c in "&*!":
            self.fail(ln, "anchors, aliases and tags are outside the subset")
        if c in "?:" and body[1:2] in ("", " "):
            self.fail(ln, f"a {c!r} indicator is outside the subset")
        if c in "[{|>%@`,]}#":
            return None
        k = body.find(": ")
        k = len(body) - 1 if k < 0 and body.endswith(":") else k
        if k < 0 or 0 <= body.find(" #") < k:
            return None
        key = body[:k].rstrip(" ")
        if key == "<<" or len(key) > 1024:
            self.fail(ln, "a `<<` merge key or an overlong key is outside the subset")
        return _typed(key), body[k + 1:].lstrip(" ")

    def _scalar(self, text, parent, ln):
        """A value that starts on line ln (self.i is already past it)."""
        c = text[0]
        if c in "|>":
            return self._block(text, parent, ln)
        if c in "'\"":
            val, k = self._quoted(text, 0, ln)
        elif c in "[{":
            val, k = self._flow(text, 0, ln)
        else:
            return self._plain(text, parent, ln)
        rest = text[k:]
        if rest.strip(" ") and not (rest[0] == " " and rest.lstrip(" ")[0] == "#"):
            self.fail(ln, "text after a quoted or flow value is outside the subset")
        return val

    def _plain_line(self, text, ln):
        cut = text.find(" #")
        body = (text if cut < 0 else text[:cut]).rstrip(" ")
        if ": " in body or body.endswith(":"):
            self.fail(ln, "a `: ` inside a plain value is outside the subset")
        return body, cut >= 0

    def _plain(self, text, parent, ln):
        c = text[0]
        if c in "&*!":
            self.fail(ln, "anchors, aliases and tags are outside the subset")
        if c in "%@`,]}" or (c in "-?:" and text[1:2] in ("", " ")):
            self.fail(ln, f"a value starting with {c!r} is outside the subset")
        val, commented = self._plain_line(text, ln)
        parts, blanks, i = [val], 0, ln + 1
        while i < len(self.lines):
            if self._blank(i):
                blanks, i = blanks + 1, i + 1
                continue
            if self.lines[i].lstrip(" ").startswith("#") or self._indent(i) <= parent:
                break
            if commented:
                self.fail(i, "a plain value continued after a comment is outside the subset")
            more, commented = self._plain_line(self._body(i), i)
            parts += ["\n" * blanks if blanks else " ", more]
            blanks, i = 0, i + 1
            self.i = i
        return _typed("".join(parts))

    def _quoted(self, text, k, ln):
        """(value, index after the closing quote) for the quoted scalar opening at text[k]."""
        q, out, j = text[k], [], k + 1
        while j < len(text):
            c = text[j]
            if c == q and q == "'" and text[j + 1:j + 2] == "'":
                out.append("'")
                j += 2
            elif c == q:
                return "".join(out), j + 1
            elif c == "\\" and q == '"':
                e = text[j + 1:j + 2]
                if e in _ESCAPES:
                    out.append(_ESCAPES[e])
                    j += 2
                elif e in _HEX_ESCAPES:
                    n = _HEX_ESCAPES[e]
                    h = text[j + 2:j + 2 + n]
                    if not re.fullmatch(f"[0-9a-fA-F]{{{n}}}", h) or 0xD800 <= int(h, 16) <= 0xDFFF \
                            or int(h, 16) > 0x10FFFF:
                        self.fail(ln, "an escape outside the subset")
                    out.append(chr(int(h, 16)))
                    j += 2 + n
                else:
                    self.fail(ln, "an escape outside the subset")
            else:
                out.append(c)
                j += 1
        self.fail(ln, "a quoted value that spans lines is outside the subset")

    def _fskip(self, text, k, ln):
        while k < len(text) and text[k] == " ":
            k += 1
        if k >= len(text) or text[k] == "#":
            self.fail(ln, "a flow value that spans lines is outside the subset")
        return k

    def _flow(self, text, k, ln):
        """(value, index after the closing bracket) for the flow collection opening at text[k]."""
        close = "]" if text[k] == "[" else "}"
        out, k = ([] if close == "]" else {}), k + 1
        while True:
            k = self._fskip(text, k, ln)
            if text[k] == close:
                return out, k + 1
            item, k = self._fitem(text, k, ln)
            k = self._fskip(text, k, ln)
            if close == "]":
                if text[k] == ":":
                    self.fail(ln, "a `key: value` pair inside a flow list is outside the subset")
                out.append(item)
            else:
                if text[k] != ":" or text[k + 1:k + 2] not in ("", " ", ",", "}"):
                    self.fail(ln, "a flow mapping entry without `: ` is outside the subset")
                k = self._fskip(text, k + 1, ln)
                val = None
                if text[k] not in ",}":
                    val, k = self._fitem(text, k, ln)
                    k = self._fskip(text, k, ln)
                if isinstance(item, (list, dict)) or item in out:
                    self.fail(ln, "a duplicate or collection key in a flow mapping is outside the subset")
                out[item] = val
            if text[k] == ",":
                k += 1
            elif text[k] != close:
                self.fail(ln, f"expected `,` or `{close}` in a flow value")

    def _fitem(self, text, k, ln):
        c = text[k]
        if c in "[{":
            return self._flow(text, k, ln)
        if c in "'\"":
            return self._quoted(text, k, ln)
        if c in "&*!%@`,]}#|>" or (c in "-?:" and text[k + 1:k + 2] in ("", " ", ",", "[", "]", "{", "}")):
            self.fail(ln, f"a flow value starting with {c!r} is outside the subset")
        j = k
        while j < len(text) and text[j] not in ",]}":
            if text[j] == "#" and text[j - 1] == " ":
                break
            if text[j] in "[{?":
                self.fail(ln, f"{text[j]!r} inside a flow value is outside the subset")
            if text[j] == ":":
                if text[j + 1:j + 2] in ("", " ", ",", "]", "}"):
                    break
                self.fail(ln, "a `:` inside a flow value is outside the subset")
            j += 1
        return _typed(text[k:j].rstrip(" ")), j

    def _block(self, text, parent, ln):
        """A literal (|) or folded (>) block scalar, following YAML's folding and chomping."""
        m = re.fullmatch(r"([|>])([-+]?)([1-9]?)([-+]?)( +#.*| *)", text)
        if not m or (m.group(2) and m.group(4)):
            self.fail(ln, "a block scalar header outside the subset")
        folded, chomp, n = m.group(1) == ">", m.group(2) or m.group(4), len(self.lines)
        if m.group(3):
            indent = max(parent, 0) + int(m.group(3))
        else:
            top, j = 0, self.i
            while j < n and self._blank(j):
                top, j = max(top, len(self.lines[j])), j + 1
            indent = max(parent + 1, 1, top, self._indent(j) if j < n else 0)

        def brk(j):
            return "\n" if j + 1 < n or self.final_break else ""

        def is_break(j):
            return j < n and self._blank(j) and len(self.lines[j]) <= indent

        def is_text(j):
            return j < n and not is_break(j) and self._indent(j) >= indent

        def breaks_from(j):
            out = []
            while is_break(j):
                out += [brk(j)] if brk(j) else []
                j += 1
            return out, j

        breaks, j = breaks_from(self.i)
        if not is_text(j):
            self.fail(ln, "an empty block scalar is outside the subset")
        chunks, line_break = [], ""
        while is_text(j):
            chunks += breaks
            line = self.lines[j][indent:]
            chunks.append(line)
            line_break = brk(j)
            breaks, j = breaks_from(j + 1)
            if not is_text(j):
                break
            if folded and line_break == "\n" and line[0] not in " \t" \
                    and self.lines[j][indent:indent + 1] not in (" ", "\t"):
                chunks += [] if breaks else [" "]
            else:
                chunks.append(line_break)
        if chomp != "-":
            chunks.append(line_break)
        if chomp == "+":
            chunks += breaks
        self.i = j
        return "".join(chunks)


def _yaml_subset(text):
    """The parsed workflow; raises WorkflowSyntaxError for YAML outside the subset."""
    return _Subset(text).parse()


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
