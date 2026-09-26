# ADR 0067 — Review output stays outside the repository, and guards prove their own coverage

- Status: accepted
- Date: 2026-09-26
- Phase: P96 (remediation pass)

## Context

Several guards proved themselves with fixtures they carried inline, so narrowing a rule to its
own fixture, or reverting a fix while keeping its fixture, left the build green. Some bound
claims rested on pins that tested a different property than the sentence stated. The CI parity
check read `.github/workflows/ci.yml` line by line, so valid YAML forms could hide or misread a
gate. Exemption maps could carry entries that exempted nothing, or entries broad enough to hide
a class of files. Dated review records and working-note prose sat in the repository alongside
the code they discussed. P96 addresses all of these in one pass.

## Decision 1: review output stays outside the repository

Working notes, verdicts, triage tables and change ledgers for a verification pass live outside
the repository and go to the maintainer. The repository receives the change itself: code, docs
that state what the code does, an ADR for a design decision, and CHANGELOG, STATE and ledger
entries that describe behaviour and phase. Enforcement:

- `tools/secret_scan.py::audit_record_name` names an audit record by path: a text file whose
  name carries a date (ISO or compact) and a review keyword, the keyword in the file name or in
  a directory above it, or an entry on `AUDIT_RECORD_PATHS`. Drift invariant 20 applies the rule
  to tracked files; the pre-commit gate applies it to staged names. Reasoned exemptions live in
  `AUDIT_RECORD_EXEMPT`. An underscore or dotted date is not matched; the guard comment states
  this limit, and a case pins it.
- The seven dated records under `docs/` are deleted. Their still-open operational steps move to
  `docs/MACOS-MAINTENANCE.md` as neutral procedure rows, and the Florida cost model moves into
  `docs/JURISDICTION-OVERLAY-PLAN.md` as design text.
- `tools/doc_freshness.py` binds docs to code only. It keeps no dated-record list and no frozen
  body hashes: a dated file is ordinary prose to this tool, needs no reconcile, and adds no
  manifest key. This supersedes ADR 0056 decision 5.
- `docs/AUDIT-PROTOCOL.md` states the pass rules: one pinned commit per pass, with each agent
  reporting the commit SHA it read (`tools/tree_pin.py` prints and verifies the fingerprint); a
  commit pushed before a pass returns names the mechanism it changed, not the property; a pass
  that could not run is reported as DID NOT RUN.

## Decision 2: commit subjects are checked mechanically

`tools/commit_claims.py` runs drift invariant 60's claim detector over the commit subject, in
the commit-msg hook and in a required CI step over the post-boundary commit range (local hooks
can be skipped; the CI range check cannot). A flagged subject needs a `Claim-Proof:` trailer
that resolves to an enforced invariant or a named selftest pin. Merge, revert and autosquash
subjects that restate an earlier subject are skipped; hand-written subjects are checked.

## Decision 3: guards prove their own coverage with committed cases

- Invariant 60's detector checks itself against `tools/claim-proof-cases.json` before scanning:
  labelled positives, negatives, escape, unit, section and sweep cases per branch; a blindness
  check fails when a branch narrowed to its own cases still passes; `check_claim_proof` fails
  when it no longer calls the case or sweep helpers; a missing or malformed case file or
  `detector_branches` entry fails closed.
- The pin resolver refuses listed shapes of a pin that cannot fail: code the selftest never
  runs, an undefined, decorated or rebound helper, untested or unpassed arguments, and
  conditions whose truth is fixed (builtins included). Each rule group is pinned by its own
  case module in `_CLAIM_PIN_CASES`. Whether a condition can be false is undecidable in
  general; the accepted residual shapes are recorded as `residual-*` cases.
- Exemption maps are held to a does-work rule: an entry must still exempt something, name an
  exact path where the map governs files, and a shape that lets one entry hide a class of
  files is refused. Secret-scan allowlist entries pin the sha256 of the text they exempt.

## Decision 4: CI parity reads the workflow as YAML and fails closed

`tools/battery.py` parses `ci.yml` with `_yaml_subset`, a stdlib reader for the block-YAML
subset GitHub workflows use. Anything outside the subset is refused, the workflow counts no
gate, and the report names the line: a refusal is a red build, never a false green.
`_steps_from_doc` reads job and step keys from the parsed mapping wherever they are written,
models `needs:` propagation (only `always()` breaks the skip chain), and treats declared
checkout, shell, working-directory, container and env forms that change what a gate runs as
non-coverage. A 42-case reader table and per-branch pins are committed; drift invariant 61 runs
the parity report inside the drift guard, so the comparison does not depend on its own CI step.
What earlier steps do to the checkout at run time is outside static reading and is stated as
the boundary.

## Decision 5: bound claims observe the property at its boundary

- Publishing: the dashboard scheduler's per-pass work is a pure `_scheduler_tick` that passes
  `allow_live=None`; `dispatch()` treats `allow_live` as a veto only; selftests record at
  `urllib.request.urlopen` and `socket.create_connection` across all four platform clients with
  the flag off, pass explicit configs, and pin the committed config shipping
  `live_publishing_enabled` false. `schedule_post`'s body is pinned in the package-independent
  tier together with the dashboard confirm-status pin.
- Install: setup and wizard selftests record the argv of every subprocess the install paths
  start, with the pip-building helpers left real, and a pip census requires every pip install
  command in the tree to be built in `setup.py::_pip_install` or `wizard.py::_install_uv`.
- Invariant 53 validates `default_flag` against the registry's declared states and executes the
  resolver CLI paths; invariant 6 checks both directions of the hub's spoke list.

## Decision 6: research and review agents are read-only by construction

Agent definitions carry YAML frontmatter with `disallowedTools` removing Write, Edit,
NotebookEdit, Agent and the writing MCP tools; the `auditor` agent additionally loses every MCP
tool, runs in its own worktree, and its Bash goes through `tools/readonly_bash_guard.py` (a
PreToolUse hook that refuses the write forms it recognizes and records its known misses). The
five product agents run in the main checkout, where the ignored local data they read lives;
`tools/tree_pin.py` is the backstop that detects what enforcement misses. Invariant 14 checks
the frontmatter; the verification verdict enum gains `did_not_run`, deal-review escalates a
missing verifier to human review, and invariant 15 keeps the enum copies in agreement.

## Consequences

- The battery grows to 14 gates (version consistency joins the roster) and the invariant
  catalog to 61; count docs move with them.
- A guard change that narrows coverage or reverts a rule fails the build through a committed
  case, not through a one-off test that ran once.
- The stated limits (underscore dates, run-time workflow behaviour, undecidable pin truth,
  novel write forms in Bash) are recorded next to the guards that carry them.
