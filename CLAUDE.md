# CLAUDE.md
Conventions for working in the Creator OS repository (the `seo-tools` repo).

## What this repo is
Creator OS is a hub-and-spoke ecosystem of Claude Agent Skills for YouTube and social media
creators. A routing hub (`creator-core`) classifies each
request into one of three lanes (Content, Document, Pipeline/CRM), loads only the engines that lane
needs, enforces the protocols, and dispatches to a capability spoke. Spokes are thin orchestrators
that compose single-operation atoms. Read `docs/ARCHITECTURE.md` for the design. Live status:
`STATE.md`.

## Layout
- `shared/` flat engines (source of truth): `brand-engine.md`, `audience-engine.md`,
  `platform-engine.md`, `adaptation-engine.md`, `pipeline-engine.md`, `web-intel-engine.md`,
  `injection-guard-engine.md`, `method.md`, plus `cache/` (the scoop tier) and
  `connectors/` (the connector registry and evidence-routing model).
- `protocols/` the five governance protocols. `quality-gates.md` is authoritative.
- `pipeline/` the CRM records store (`accounts/`, `deals/`). Source of truth for all CRM facts. Real
  data is gitignored; only schemas and blank structures are committed.
- `skills/` flat. The hub `creator-core/`, the governance skill `quality-review/`, the 22 spokes, and
  `atoms/` (single-operation sub-skills).
- `canonical-sources/` reference data the scoop cache indexes (keyword library, platform specs,
  personas, rate benchmarks, seasonal aesthetic).
- `tools/` `sync_check.py` (drift guard), `new_skill.py` (scaffolder), `version.py`,
  `package_skill.py`, `sync_cache.py` (scoop L3), `skill-template/`, `sync_manifest.json`.
  `tools/dashboard/` is the Scheduling Dashboard (`python3 tools/dashboard/server.py`, port 8766).
  `tools/wizard.py` is the setup wizard (port 8765), including `/publishing-setup` for platform
  API credential configuration.
- `implementation/` platform packaging (claude, gpt, gemini). `docs/`, `ledger/`, `examples/`.

## Build, verify, and the battery
Every change must leave the battery green before commit. The one runner (P81) is:
```bash
python3 tools/battery.py             # every gate, raw exit codes; refuses on unstaged tracked edits
python3 tools/battery.py --py /usr/bin/python3.12   # rerun under a second interpreter when a floor moved
```
It runs, in order: the drift guard (`sync_check.py`), scenarios, the selftest sweep,
`doc_freshness.py --check`, projections, `count_truth.py` (canonical counts; never restate counts by
hand), `hash_audit.py`, `source_sync.py check`, `package_skill.py --check-manifest`, `eval_lint.py`,
`preflight_push.py`, the staged secret scan, the launcher syntax check, and `version.py --check`.
`--list` prints the roster.
`tools/package_skill.py --all` is a BUILD step that writes `dist/`, not a validation step; CI runs
it separately. Rituals: if you edit a macOS-relevant file, re-bless it with
`python3 tools/mac_surface_manifest.py reconcile` (a NEW file needs `--accept-new` after review);
if you stamp any registry source, run `python3 tools/build_freshness_bundle.py --apply`.

## Branching and git
- Develop on the feature branch (currently `claude/repo-access-confirm-wxe50a`). Never push to `main`.
- Push with `git push -u origin <branch>`; retry network failures with backoff.
- Do not open a PR unless explicitly asked.

## How skills reference shared files
Skills reference canonical engines and protocols by repo-root path directly (for example,
`shared/brand-engine.md`, `protocols/quality-gates.md`). There are no per-skill byte-identical copies.
Edit the canonical file in `shared/` or `protocols/`; the drift guard validates that every reference
resolves.

## Adding a skill
```bash
python3 tools/new_skill.py <spoke-name>          # a spoke under skills/<name>/
python3 tools/new_skill.py --atom <atom-name>    # an atom under skills/atoms/<name>/
python3 tools/sync_check.py                       # must pass
```
Then edit `SKILL.md` (specific, pushy, scoped description with a "Do NOT use for" clause) and
`MAINTAINER_README.md`. Spokes carry a `workflow.json` that composes atoms.

## Agent orchestration
- Subagents are **read-only research tools**: they read files, query MCP tools, search the web,
  and return structured findings, and their operating rules forbid creating, editing, or deleting
  files and committing or pushing. Claude Code enforces each definition's YAML frontmatter:
  `disallowedTools` removes Write, Edit, NotebookEdit and Agent from every agent, the GitHub and
  Google Drive MCP servers' tools from the five product agents, and every MCP tool from the
  `auditor`, which also runs in its own git worktree. Other MCP servers stay inherited by the
  product agents. Bash stays write-capable for every agent: for the `auditor`, a PreToolUse hook
  (`tools/readonly_bash_guard.py`) refuses the write forms it recognizes, and a script that writes
  as a side effect still passes it. The main loop aggregates findings and proposes changes to the
  user.
- Every agent prompt must include the read-only operating rules block from
  `shared/research-orchestration-engine.md`.
- Agent output must use a JSON Schema (passed via the `schema` option on `agent()` in workflows,
  or via structured output conventions in ad-hoc Agent tool calls). Prose-only agent returns are
  not acceptable for multi-agent pipelines.
- Spawn agents only when the task spans 3+ sources, requires multi-platform comparison, deep
  competitor analysis, or citation chain traversal. Single-source lookups do not warrant an agent.
- Agent definitions live in `.claude/agents/`. Workflow scripts live in `.claude/workflows/`.
  Structured output schemas live in `shared/schemas/`.
- The six agent roles are: `seo-researcher`, `competitor-analyst`, `content-writer`,
  `deal-reviewer`, `cost-researcher`, and `auditor` (a read-only review of a change against a
  pinned commit). Each has a scoped tool list defined in its agent definition file; the five
  product roles also name their engines.
- Every agent output must include `minority_report`, `confidence_evidence`, and `source_citations`
  fields (the verification envelope defined in `shared/schemas/verification-envelope.json`).
- Every workflow includes an adversarial verification step — a second agent that independently
  challenges the primary agent's claims before the main loop aggregates findings.
- Agent definitions must include explicit `## Forbidden tools (machine-enforced)` and
  `## Allowed tools (explicit allowlist)` sections. See `shared/research-orchestration-engine.md`
  Section 2.1 for the contract specification. Each file also starts with YAML frontmatter
  (`name`, `description`, `disallowedTools`); a file without it is loaded as documentation, not
  as an agent, and none of its tool rules apply.
- Bracket a read-only pass with `python3 tools/tree_pin.py pin` before it and
  `python3 tools/tree_pin.py verify '<pin>'` after it; verify exits 1 and names what moved (HEAD,
  tracked changes, untracked or ignored files by size and mtime, refs, `.git/config` and
  `.git/hooks`). This is the backstop for a write the tool rules miss. It excludes `.venv/`,
  `dist/`, `__pycache__/`, `.claude/worktrees/` and the `worktree-*` branches of isolated agents,
  and it does not see writes outside the repository or to other files under `.git`.
- `tools/validate_agent_output.py` is the offline fabrication detection tool. It checks source
  citations against the registry, validates confidence-tier alignment, and flags unsourced numbers.
- Drift guard invariants 14 to 17 structurally enforce agent contracts: agent definition sections
  and frontmatter, plus the auditor's worktree isolation and Bash-guard wiring (14), schema
  verification fields (15), workflow verification steps (16), and the read-only mandate marker
  (17).

## Non-negotiables (enforced by the drift guard / Quality Gates)
- No em dashes in user-facing output (scripts, captions, pitch copy, media kit sections, pin titles).
  Internal docs (SKILL.md, engine files, protocol files, architecture docs) may use em dashes freely.
  The drift guard enforces this for `examples/` only. See `protocols/formatting-metadata.md`.
- Write ranges with "to" everywhere, including internal docs (`protocols/formatting-metadata.md`).
- Never fabricate data, metrics, rates, brands, or sources (`protocols/no-fabrication.md`). Null and
  flag instead.
- No real CRM data or PII committed to the repo. The `pipeline/` store keeps real data gitignored.
- Nothing is released until it passes the Quality Gates (`protocols/quality-gates.md`).
- **A commit subject names the mechanism it changed.** A stage pushed before its verification stage
  returns says in its subject what the code now does, not the property the stage aims at; the
  property is reported after that verification returns, narrowed to what survived. `tools/commit_claims.py` runs invariant 60's detector on the subject: the commit-msg
  hook and a blocking step in the CI guard job refuse a flagged subject whose `Claim-Proof:`
  trailer is absent or does not resolve. Merge, revert and autosquash subjects that restate a
  checked subject are skipped. The CI step covers the commits after
  `CLAIM_SUBJECT_BOUNDARY` that the hook does not see (`--no-verify`, clones without the hooks,
  commits made through the GitHub API).
- **Audit output stays out of the repository.** Findings, verdicts, triage tables, pass records
  and a pass's change ledger are kept in the working plan outside the repository. A commit
  carries the change and the docs that state what the code does; its prose describes behavior,
  not how a defect was found. `STATE.md` and `ledger/ledger.json` record decisions and phases,
  not review results or conversations. Drift invariant 20 and the pre-commit hook refuse a
  tracked or staged audit-record file as `tools/secret_scan.py::audit_record_name` defines it: a
  file name with a suffix on `AUDIT_RECORD_TEXT_SUFFIXES` that carries a date and a review keyword (in
  the name or in a directory above it), or a path on `AUDIT_RECORD_PATHS`.
- **Claims about this repo's own behavior meet the same bar as a plan: executed evidence, or
  they are not written.** A universal claim ("no", "never", "every", "all", "only", "nothing",
  "always", "none", "cannot") in a commit subject, a doc sentence, a CHANGELOG entry, or a report
  to the owner either names the executed pin that proves it or is narrowed to what was actually
  tested. Test the PROPERTY
  claimed, not the mechanism changed. The independent pass that checks a claim
  runs BEFORE the claim is reported or merged (`docs/AUDIT-PROTOCOL.md` section 7.1), the claim
  waits for that pass's verification stage to return rather than its first findings, a pass
  whose agents could not run is reported as DID NOT RUN rather than as clean, and the adversarial
  vectors are chosen by the reviewer rather than the author (section 7.2); and a new
  guard's scan set is derived from the tree, never a hand list of the files the change happened
  to touch. The promises in this section and in `docs/INSTALL-SCOPE.md` are bound to their
  proofs in `tools/claim-proof-manifest.json`; drift invariant 60 fails the build when a bound
  claim drifts from its proof, when a named pin is renamed away, when a recommended install
  route stops being detectable, or when an unproven universal claim joins the list. When a
  check fails, report it honestly with the output; never claim a skipped step ran.
- Installs are user-scoped by default: everything lands under the user's home folder (repo
  `.venv`, `~/.local`, `~/Applications`, `~/Library`); nothing under `/Applications`,
  `/opt/homebrew`, or via `sudo` unless explicitly labeled "machine-wide alternative (affects
  the whole computer)". Policy, approved locations, and the one exception (Apple CLT git):
  `docs/INSTALL-SCOPE.md`. Drift invariant 59 enforces the labeling across every tracked
  guidance file (derived denominator, written-reason exemptions); the code side never writes
  into a machine-wide site-packages at all: the repo `.venv` is the only install target, and
  when it cannot be created the installer refuses with the remedy rather than falling back to
  the base interpreter (`tools/setup.py::install_dependencies`, `tools/wizard.py::_install_uv`).
- Every spoke in the hub's downstream list exists; every atom a workflow names is installed.
- `canonical-sources/source-registry.json` is written only through `tools/registry_io.py`
  (`load_registry`/`save_registry`), the single shared write implementation. Five tools funnel
  through it. Four import it directly: `tools/source_currency.py` (report/check/mark-checked/
  seed-sources/seed-partners/update-source/remove-source), `tools/traversal_engine.py` (`accept`,
  which appends a graph-discovered source), `tools/dependency_currency.py` (`check --apply`, which
  stamps dependency freshness), and `tools/update_check.py` (`apply_stamp`, which stamps the
  repo-self-update source). A fifth, `tools/competitor_snapshot.py` (`register-competitor`), writes
  through `source_currency`'s re-exported `save_registry`. Do not edit source-registry.json by hand;
  use `seed-sources` for new sources, `update-source` for corrections, and `accept` for traversal
  discoveries.
- `tools/dependency_currency.py` is the token-free version-drift checker for pip packages, system
  binaries, and MCP servers (categories `software-dependency`, `mcp-server`): it queries PyPI and
  GitHub Releases directly (stdlib, honoring the env proxy + CA bundle) and computes drift from each
  registry entry's own `validated_version` and `pinned_constraint`. Those two fields are the only
  baselines it reads; they are transcribed by hand from `requirements-*.txt` and from the
  validated-run record `docs/video-tooling-integration-evidence.json` via `source_currency
  update-source`, and drift invariant 25 fails the build when a requirements specifier and the
  registry pin disagree. `report`/`check` are read-only; `check --apply` stamps
  `last_checked`/`latest_seen` for reachable entries via `registry_io` so routine currency
  maintenance runs with no model tokens. Binary/manual entries degrade to advisory.
- `tools/traversal_engine.py` is the only tool that writes to `traversal-candidates.json` and
  `traversal-visited.json`.
- `shared/connectors/connectors.json` is the source of truth for the connector registry. The
  resolver (`shared/connectors/connectors.py`) reads this file plus, automatically,
  `creator-os-config.local.json` to produce the active evidence plan; a dedicated flags file
  (copy `shared/connectors/feature-flags.example.json` to gitignored
  `creator-os-connectors.local.json`) is consulted only when passed explicitly via `--flags`.
  Do not edit `connectors.json` for deployment-specific state changes. Every registry entry
  carries a `default_flag`; drift invariant 53 executes the resolver over the committed registry
  so a malformed entry fails the build.
- **Human confirmation required before every post.** `schedule-post` always sets
  `human_review_required: true`. No connector call is made, and no post is queued or published,
  without an explicit human confirmation step. Agents never post directly — they produce
  confirmation summaries for human review only. `tools/publishing_compliance.py` is the shared
  FTC/AIGC/tier/credential gate used by both `schedule_post` (which reports) and the dashboard
  confirm path (which refuses on a failed gate). Real platform publishing lives in
  `tools/publishing/` and is gated behind the `live_publishing_enabled` flag (default off); while
  off, the dashboard schedules and advances items to `ready_to_post` for manual posting and makes
  no network call.

## Planning depth (a plan is finished when execution holds no surprises)
Plan before you build, and plan far enough that the implementation is a formality. A plan for
anything beyond a trivial edit carries all of:
- **who / what / when / where / why / how** for every work package, not just a task list.
- **Risks with concrete mitigations**, each tied to a real failure this repo can have, not generic
  caution.
- **Citable evidence**: a `file:line`, a command's actual output, or a URL. An assertion with no
  pointer is not evidence.
- **Code that has been executed and shown to pass**, not code that looks plausible. Import the
  module, call the function, paste what it returned.

If a contract was guessed rather than verified, that is a defect in the plan, not a surprise to
discover mid-implementation. Verifying beats assuming: running a plan's own example
assertions is what exposes a regex that silently corrupts data, or a function whose contract
differs from its obvious reading. The planning phase
is expected to be the majority of the work.

## Documentation truth (docs change in the same PR as the code)
When you change code, update its maintainer/SKILL/docs prose in the SAME change, never in a later
cleanup pass. If you add or rename a symbol a doc names, update or add its `<!-- verify: path::symbol -->`
marker; if you change a global count (a spoke, atom, invariant, scenario, agent role), fix every
live-doc claim; if the prose cites a new external authority, declare it in the doc's fenced `sources`
block and seed it into the registry (`tools/source_sync.py reconcile` generates the seed; invariant 52
fails the build on an undeclared-in-registry citation); add a `CHANGELOG.md` entry under Unreleased;
record any architectural decision as an ADR in `docs/adr/`. The drift guard enforces path resolution,
symbol references, count truth, URL provenance, and doc-declared source registration, and stamps
content-hash staleness. Full model and citations: `docs/DOC-MAINTENANCE.md`.

## Commit and PR hygiene (non-negotiable, machine-enforced)
Nothing leaves this machine that reveals more than the code change itself:
- Commit messages, PR titles/bodies, and issue comments never contain: claude.ai session links,
  personal email addresses, real dollar amounts, real brand or counterparty names from the
  pipeline, credentials, or any PII. Fictional examples only, and only when needed.
- The commit author email is the GitHub noreply address (repo-local `git config user.email`),
  never a personal address.
- After cloning, run `python3 tools/install_hooks.py` once: the pre-commit hook runs
  `tools/secret_scan.py --staged` (blocks staged secrets, `.local.` files, CSV/spreadsheet
  exports, key material, `.env*`, audit-record file names), and the commit-msg hook rejects messages carrying session
  links, emails, or secret patterns.
- CI backstops clones that skipped the hooks: the guard job scans all tracked content
  (invariant 21) and every commit message plus author email after the policy boundary SHA
  recorded in `tools/secret-scan-allowlist.json`. History before the boundary is not rewritten
  and not re-litigated.
- Verified false positives are exempted only in `tools/secret-scan-allowlist.json`, each with a
  written reason. Never exempt a real secret; fix the file instead.
- Data at rest: drift invariants 19 (no tracked `.local.` files), 20 (tracked files under
  `pipeline/` must be on the explicit allowlist; no tracked sensitive-format file anywhere —
  spreadsheets, CSV/columnar exports, financial app files (QBW/QIF/OFX/QFX/TAX), credential/key
  stores (PEM/KEY/P12/KDBX/keychain), databases, backups, email/contacts (PST/MBOX/VCF), archives,
  office binaries, capture media, or `.env*`; the single list is
  `tools/secret_scan.py::FORBIDDEN_DATA_SUFFIXES`, shared by the drift guard, the pre-commit hook,
  and CI; audit-record file names are refused by the same invariant through
  `tools/secret_scan.py::audit_record_name`), and 21 (content scan of EVERY tracked text file, binary-sniffed rather than
  suffix-gated) fail the build on violation and fail closed in CI. In a non-git copy all three
  print a loud DID-NOT-RUN advisory instead of silently passing.

## Commit messages
Keep them short: a few sentences at most, describing only what was added or changed and the
affected engine, protocol, or skill. Never include conversation details, decision background,
personal information, or links of any kind. Update `STATE.md` at phase boundaries and after a
skill ships. Subject to the hygiene rules above. All work stays in this repository only.
