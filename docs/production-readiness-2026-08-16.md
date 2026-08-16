# Production readiness audit — 2026-08-16 (P73)

Six-dimension audit of the whole tree before any release decision: integrity, completeness,
accuracy, truthfulness, consistency, adaptability. Run as monitored agent waves with a hard
triage gate between them; every agent finding was reproduced by the main loop before it was
accepted, and two agent claims were narrowed on reproduction rather than taken at face value.

Method follows `docs/AUDIT-PROTOCOL.md`: derived coverage sets (§1), re-verification of each
finding against the harness (§4), a mandatory unexercised list (§5), the five-part deliverable
shape (§6), and an independent close-out (§7).

## 1. Summary index

| id | sev | one line | status |
|---|---|---|---|
| F4 | HIGH | MCP annotation gate was fail-open; an unanticipated write tool inherited `readOnlyHint: True` | fixed |
| F12 | HIGH | `configure_tool` overwrote an unparseable local config, destroying the remote token and publishing flags | fixed |
| D5-1 | HIGH | Plain ChatGPT web surface contradicted the packaging docs on whether live tools are reachable | fixed |
| D5-2 | HIGH | Custom GPT workspace-only gate missing from two of three upgrade paths | fixed |
| D5-3 | HIGH | `AGENTS.md` stated the registry single-writer rule with a narrower writer set than `CLAUDE.md` | fixed |
| D5-4 | MED | `AGENTS.md` omitted four machine-enforced non-negotiables | fixed |
| D5-5 | MED | `README.md` and the ChatGPT packaging README enumerated 14 spokes while claiming 22 | fixed |
| D5-6 / F14 | MED | P73's own commits shipped with no CHANGELOG, STATE or ledger entry | fixed |
| D5-7 | MED | Unreleased CHANGELOG carried two contradictions, a duplicate, and a never-shipped intermediate state | fixed |
| D5-8 / D4-8 | MED | Six disabled capabilities had no `degraded_behavior` entry; parity check is one-directional | fixed (entries); check still one-directional |
| D5-10 | LOW | `chatgpt_desktop` "Work with Apps" limit stated unconditionally though the feature is macOS-only | fixed |
| F1 | MED | 64 of 66 sources promising a sub-30-day cadence have never been checked once | partially fixed, then blocked |
| F2 | MED | Three divergent "batteries"; the entry-point doc carried none of them and included a build step | fixed |
| F3 | MED | Mac signal vocabulary pinned against narrowing, with no widening trigger | fixed |
| F5 | MED | Count-truth invariant used a curated list; enrolment had already been forgotten once | fixed |
| F6 | MED | Projection manifest hashed only sources, never the projection's own bytes | fixed |
| F7 | MED | Scheme-less shorthand citations were invisible to both citation guards | fixed |
| F8 | MED | Registry writes were non-atomic with no documented recovery | fixed |
| F9 | MED | Wizard port hardcoded, coupled to registered OAuth redirect URIs, no override | fixed |
| F10 | MED | Launcher trusted a `.venv` that exists but cannot run | fixed |
| F11 | LOW | Corrupt cache index returned a raw traceback instead of the rebuild hint | fixed |
| F13 / PRE-4 | LOW | `docs/AUDIT-PROTOCOL.md` referenced a plan structure defined nowhere | fixed |
| F15 | MED | Highest-priority backlog item marked proposed after being applied; three deferrals described passed dates as future | fixed |
| D5-9 | LOW | Nine of 52 ledger decisions carry no `rationale` | accepted, deliberately |
| PRE-1 | MED | `release.py execute()` has no preconditions | open (see §2) |
| PRE-2 / PR5-1 | MED | `release.py --plan` would tag v0.1.0 for a tree carrying 80 unreleased bullets | open by design (§6) |
| PRE-3 | MED | `handoff_sim.py` (38 checks) has no `--selftest`, so nothing runs it automatically | open (see §2) |
| PRE-5 | LOW | Unreleased section is 17 phase-repeated blocks | open by design (§6) |
| D1-1 | MED | Invariant count inflated (58 reported, 57 enforced) | fixed |
| D1-2 | MED | `videoedit_validate.py` had no selftest and was absent from the sweep | fixed |
| D1-3 | MED | `AGENTS.md` invariant count was unguarded | fixed |
| D1-4 | MED | CI commit-message backstop scans an empty range on direct main pushes | open (see §2) |
| D1-5 | MED | commit-msg hook omits the author-email rule ADR 0015 says it enforces | open (see §2) |
| D1-6 | MED | tool selftest coverage: the "37 of 103" figure was wrong (34), and the flat count conflated three tiers | corrected; coverage in progress (see §2) |
| D1-7 | LOW | Two prose sites presented advisory invariant 47 as CI-enforced | fixed (live doc) |
| D1-8 | LOW | Installed commit-msg hook prepends a bogus `sys.path` entry | open (see §2) |
| D1-9 | LOW | `videoedit_validate` module docstring overclaimed | fixed |
| D2-1 | MED | "Only four remain unstamped" was false; three more T1 sources were unstamped | fixed |
| D2-2 | LOW | The "27 macOS-relevant sources" denominator was unreproducible | fixed |
| D3-1 | CRIT | `requirements-mcp.txt` pinned bare `mcp` after 2.x went stable | fixed |
| D3-2 | MED | A live plan-eligibility citation was in no registry entry | fixed |
| D3-3 | LOW | Three excerpt-confidence hints recorded no extracted facts | fixed |
| D3-4 | MED | Homebrew cask date recorded day-precise when the source states only a month | fixed |
| D3-5 | MED | Intel Tier-3 bottle change omitted; cutoff misattributed to macOS 27 | fixed |
| D4-1 | HIGH | `_LOOPBACK_HOSTS` accepted `""`, which binds all interfaces | fixed |
| D4-2 | HIGH | Four video flags gated nothing; docs (and my own fix) overclaimed | fixed |
| D4-3 | MED | A selftest label claimed to cover a gate branch it never executed | fixed |
| D4-4 | MED | ChatGPT web "what does NOT work" table predated the connector routes | fixed |
| D4-5 | MED | `post_status` docstring promises engagement mapping its body never performs | fixed |
| D4-6 | LOW | `schedule_post` docstring opened with "Dispatch" | fixed |
| D4-7 | LOW | `LOCAL_CONTEXT` claimed a stray `git add -A` "cannot" commit personal data | fixed |

## 2. Findings detail

Findings that are fixed are described in the CHANGELOG entry for this phase and are demonstrable
from the commits listed in §3. This section details what is **not** closed, because that is the
part a reader cannot reconstruct from a green build.

### D5-8 / D4-8 — six disabled capabilities have no degraded behavior — MED — partially fixed
- Claim: `creator-os-config.json` has 62 capabilities (59 disabled) and 47 `degraded_behavior`
  entries. After resolving every fan-out and rename key, exactly six disabled capabilities have no
  degraded entry: `playwright`, `google_workspace`, `microsoft_365`, `task_tracking`,
  `shipment_tracking`, `coverage_verification`.
- Reproduction: `check_degraded_orphans` (`tools/sync_check.py`) iterates
  `degraded_behavior` and reports keys with no capability. There is no loop in the other
  direction, and the check is `advisory(...)`, not blocking.
- Fixed: all six now carry a `degraded_behavior` entry stating what the system does instead and
  what it must not imply.
- Still open: `check_degraded_orphans` remains one-directional and advisory. Making it
  bidirectional and blocking would turn an advisory into a build failure across a config surface
  this audit did not otherwise touch, and the six concrete gaps it would have caught are now
  closed, so the remaining risk is a future capability added without a degraded entry.

### F1 — the currency cadence is a promise nothing keeps — MED — partially fixed, then blocked
- Claim: 66 registry sources declare a check interval under 30 days; 64 of them have
  `last_checked: null`. Repo-wide, 182 of 257 sources have never been checked. Only two entries
  have ever been polled at a sub-monthly cadence.
- Reproduction: `python3 -c "import json;d=json.load(open('canonical-sources/source-registry.json'));print(sum(1 for x in d['sources'] if (x.get('check_interval_days') or 999)<30 and not x.get('last_checked')))"` → `64`.
- What was done: the token-free stamping pass (`dependency_currency.py check --apply`) ran and
  stamped every reachable dependency entry. That does not touch the sub-30-day population, which
  is documentation and web sources.
- Why blocked: the honest fix is to re-band intervals the repo has never once met. No sanctioned
  CLI can change `check_interval_days` — `source_currency update-source` accepts only
  url/category/name/tier/extraction-hint/used-by — and hand-editing the registry violates the
  single-writer rule. **This is the same gap that blocks `vc-dep-mcp-validated-version`**: two
  registry fields have no sanctioned writer. Recommended fix: a `set-baseline` /
  `set-interval` verb on `dependency_currency` or `source_currency`, writing through
  `registry_io`. Recorded in `canonical-sources/volatile-corrections.2026-07-14.json`.

### PRE-1 — `release.py execute()` has no preconditions — MED — open
- Claim: `execute()` checks nothing before tagging: no battery run, no `version.py --check`, no
  CHANGELOG-section check, no existing-tag check.
- Why still open: the release path is a Tier-A, user-owned decision and this audit deliberately
  did not modify it (see §6). Adding preconditions is the right fix and is recommended, but
  changing the release mechanism during an audit that is *recommending* a release would be
  changing the thing being judged.

### PRE-3 — the deepest end-to-end test is run by nothing — MED — open
- Claim: `tools/handoff_sim.py` covers 10 phases and 38 checks and has no `--selftest`, so
  `selftest_sweep.py` never discovers it and no automated path executes it.
- Status: it was run explicitly in this audit and passes 38/38 (§3). Wiring it into the sweep is
  the obvious fix; it is left open only because its write phases need the sandbox redirect
  reviewed before it runs unattended in CI, which is more than a wiring change.

### D1-4, D1-5, D1-8 — commit-message and hook gaps — MED/LOW — open
- D1-4: the CI commit-message backstop scans `origin/main..HEAD`, which is empty once a direct
  push to main lands; the boundary SHA in `tools/secret-scan-allowlist.json` is never used to
  bound the range. Pull-request and branch pushes are covered.
- D1-5: the installed commit-msg hook calls only `scan_text`, omitting the author-email rule that
  `scan_commit_messages` enforces — while ADR 0015 states the rule is "enforced by the commit-msg
  hook and the CI backstop", and the CI half is D1-4.
- D1-8: the installed hook prepends a `sys.path` entry derived from `__file__`, which is
  `"<stdin>"` in that context. Harmless today, import-order-sensitive later.
- Why open: all three sit in the commit/CI boundary. They are a coherent unit of work and were
  scoped out rather than partially patched.

### D1-6 — tool selftest coverage — MED — figure corrected, coverage in progress

**This finding's own number was wrong.** The report said "37 of 103". Re-derived with the sweep's
own discovery rule (`tools/selftest_sweep.py:28-31`: an argparse `--selftest`, an argv probe, or a
`selftest` subparser) the figure is **34 of 103** tracked `tools/**/*.py`. Across `tools/` and
`shared/` together: 110 files, 70 covered, 40 uncovered. A miscounted denominator inside a
coverage finding is the same defect class as D1-1, so it is recorded here rather than quietly
edited.

**The flat count also conflated three different situations**, which made the gap look both larger
and more uniform than it is. Import analysis alone is misleading, because guards execute some
modules dynamically — `sync_check.py:2286` loads `shared/connectors/connectors.py` through
`importlib` and calls `resolve({})` (invariant 53), and `selftest_sweep.py:62-64` runs
`tools/publishing` as `python -m publishing --selftest`. Neither is visible to a plain import
graph. The honest split:

- **Tier A — no selftest and no runner (7).** The real gaps: `traversal_engine` (484 lines),
  `rate_governor` (255), `shared/docintel/parse_text` (224), `local_privacy` (150),
  `shared/cache/semantic` (65), `videoedit/compressor` (59), `videoedit/commandpost` (38).
- **Tier B — no selftest, but executed on some path (23).** Being imported proves a module loads,
  **not** that its logic is asserted. P74-0 — the OG extractor that returned one value for every
  property — lived in a Tier B file and survived anyway, which is the proof that Tier B is not
  coverage. Highest-risk members all parse external or untrusted input:
  `parse_competitor_meta` (427), `videoedit/fcpxml` (381), `acquire` (359), `fetch_diag` (236),
  `shared/cache/cache` (204), `fetch_resilient` (203), `geo_source_fetch` (186).
- **Tier C — is itself a battery runner (10).** `sync_check` (2906), `handoff_sim`,
  `geo_e2e_proof`, `count_truth`, `version`, `package_skill`, `registry_io`, `sync_cache`,
  `new_skill`, `update`. Running these IS the test; a `--selftest` would be ceremony. Counting
  `sync_check.py` as untested debt would inflate the gap as dishonestly as hiding one.

**Status.** `parse_competitor_meta` now has a selftest (added with the P74-0 fix; the sweep rose
from 69 to 70). The remaining top-20 — all of Tier A plus the highest-risk Tier B files — are being
covered, after which an enrolment guard requires every new tool to wire a `--selftest` or land on a
reasoned exemption list, and the residue is named in a "still needs a selftest" table rather than
left as a silent gap. Writing all 34 by hand was rejected as a rebuild rather than a repair.

### D4-5, D4-7 — docstring and prose overclaims — MED/LOW — fixed
- D4-5: `post_status`'s docstring promised live connector status and engagement mapping; the body
  reads one flag and returns a constant envelope. The docstring now states its real scope, and
  says plainly that `include_engagement_snapshot` has no effect today and is not zero-filled. The
  parameter was kept rather than removed, because whether it should eventually work is a product
  decision, not an audit one.
- D4-7: `docs/LOCAL_CONTEXT.md` claimed a stray `git add -A` "cannot" commit personal data. It now
  distinguishes the two mechanisms honestly: the pre-commit hook prevents but only after
  `install_hooks.py` has been run, and invariant 19 always detects but only after the fact.

### F13 / PRE-4 — dangling plan-structure pointer — LOW — fixed
- `docs/AUDIT-PROTOCOL.md` tells a maintainer that findings which become work "get a plan with the
  repo's resume-protocol + change-ledger structure". `grep -rn "resume-protocol|change-ledger" .`
  returns exactly one hit: that line. Neither structure is defined anywhere.
- Fixed as the adaptability pass recommended: `AUDIT-PROTOCOL.md` gained a `## 8. Plan structure`
  section defining the six parts a remediation plan carries, including the change-ledger row
  lifecycle and the explicit non-action list. Deliberately not a new standalone document — README
  could not reach it, which is the problem F2 describes.

### D5-9 — nine ledger decisions lack `rationale` — LOW — accepted, deliberately
Those nine use `why`, `adr`, or `alternatives_rejected` to carry the same information, and
`ledger.json` promises no schema (`id`/`date`/`decision` are present on all 52). Writing a
`rationale` for a decision made in an earlier phase would mean inventing reasoning nobody
recorded, which the no-fabrication protocol forbids. Accepted as-is on purpose.

### D1-7 — advisory invariant described as CI-enforced — LOW — fixed in the live doc only
`docs/DRIVE-HUB.md` now states that invariant 47 runs in CI as an advisory. `docs/adr/0043` says
the same thing in its original wording and was left unedited: ADRs are immutable decision records
in this repo, and rewriting one to match a later understanding would defeat their purpose.

## 3. PASS ledger

Every tool below ran clean at HEAD `15e7353` (tree clean, equal to origin), so the next
audit need not redo it blindly.

| tool + verb | result |
|---|---|
| `sync_check.py` | clean, all 57 invariants hold |
| `scenario_check.py` | 10/10 scenarios, 0 open gaps |
| `selftest_sweep.py` | 69/69 |
| `doc_freshness.py --check` | all bound docs current |
| `count_truth.py` | 22 spokes / 106 atoms / 57 invariants / 60 MCP tools / 85 mac-surface files |
| `projection_manifest.py --check` | no stale projections |
| `surface_budgets.py --selftest` | 0 violations |
| `version.py --check` | consistent at 0.1.0 |
| `eval_lint.py` | 129 eval files structurally clean |
| `preflight_push.py` | clean |
| `secret_scan.py --tracked` / `--staged` | clean |
| `handoff_sim.py --json` | 38 passed, 0 failed, 0 skipped |
| `geo_e2e_proof.py` | 17/17 |
| `publishing_compliance.py --selftest` | 15/15 |
| `persona_audit.py` | 26 screens, 0 red, 0 amber, 0 render errors, 0 orphans |
| `validate_agent_output.py --selftest` | 11/11 |
| `injection_scan.py --selftest` | 23/23 (pattern tier only; the semantic tier is in-session) |
| `coverage_verify.py --selftest` | 19/19 |
| `videoedit_validate.py --selftest` | pass, 0 failures |
| `release.py --selftest` | 9/9 (never `--execute`) |
| `mcp_server.py --selftest` | pass, package-independent tier; static tool count 60 |
| `wizard.py --selftest` | pass (OAuth CSRF, exchange, no-clobber, macOS seam, port collision, 0 network) |
| `mac_surface_manifest.py --selftest` | pass, 0 failures |
| `local_audit.py report` | no schema drift |
| `source_sync.py check` | no unregistered or mismatched citations |
| `dependency_currency.py check --apply` | reachable entries stamped; blocked entries labelled, not assumed current |

**Guard red-teams — each made to fail, then restored.** A guard that has never failed is an
untested guard.

| replay | result |
|---|---|
| unclassified MCP tool with no mutation-signal name | refused (permanent selftest case) |
| classified-but-renamed tool | reported stale |
| malformed local config | backed up, original bytes intact |
| projection hand-edited with sources unchanged | flagged |
| projection rewritten after a source moved | reports the source, no false hand-edit flag |
| faked count in an enrolled doc | failed |
| new unenrolled doc stating a true count | failed |
| unregistered shorthand citation in `tools/surface_budgets.py` | failed |
| unregistered shorthand citation in a packaging README | failed |
| file using a macOS concept outside the vocabulary | advisory raised |
| broken `.venv` interpreter | launcher fell through to fallback |
| working `.venv` interpreter | launcher still preferred it |

`git status --short` was asserted clean after every replay block.

## 4. Not exercised

This sandbox cannot run the following. None of it is claimed as verified.

**Real-Mac behaviors**, verified only against vendor documentation: the Gatekeeper
block-and-Open-Anyway dialog, the TCC permission prompt on a protected folder, Rosetta translation
on Intel, Metal as the whisper.cpp default, a real Claude Desktop MCP spawn, and Drive-for-desktop
mirror materialization latency. Runbook to execute them: `docs/MAC-VALIDATION.md`.

**Live OAuth and real posting.** Needs per-platform developer apps and the user's own accounts.
`live_publishing_enabled` stayed off for the entire audit; no connector call was made.

**A live ChatGPT connector round-trip**, and real paste-tests of the packaged instructions on
chatgpt.com and claude.ai. Artifact sizes are machine-checked against documented caps; the paste
itself is not.

**Hosted-endpoint deployment.** The remote MCP surface was exercised only through its argv and
bind-decision logic, not by being deployed.

**A true cold-clone bootstrap.** Approximated with a `/tmp` copy, which is not a real clone: it has
no `.git`, so the git-dependent invariants take their DID-NOT-RUN path by design.

**help.openai.com facts remain excerpt-confidence.** The site refuses direct fetches, so articles
8554397, 8096356, 12584461, 10169521 and 10119604 are marked excerpt-confidence in the registry
rather than fetched-verified. That marked state is the pass condition, not evidence of drift.

**The Homebrew September 2026 changes and the macOS 27 Intel drop are future-dated.** They are
recorded with the precision the source actually uses (a month, not a day) and cannot be confirmed
until they happen.

## 5. Verdict

| criterion | verdict | evidence |
|---|---|---|
| PR-1 integrity enforced | **PASS** | §3 PASS ledger and the 12 red-team replays; every guard touched was made to fail before it was trusted |
| PR-2 safety boundaries | **PASS** | Both fail-open safety defects (F4, F12) fixed fail-closed with permanent selftest cases; `live_publishing_enabled` off; human confirmation required; data-at-rest invariants 19 to 21 clean |
| PR-3 dimensions clean | **PASS with noted exceptions** | 0 open CRITICAL or HIGH. 9 MEDIUM and 4 LOW remain open, each with a written reason in §2 |
| PR-4 honest coverage | **PASS** | §4 states what was not exercised, in both directions |
| PR-5 release mechanics | **NOT READY** | Version triple is consistent, but see §6 — the release cannot be cut coherently as-is |

**Overall: production-ready for use, not yet ready to tag.** The system's enforcement mechanisms
enforce, its safety boundaries hold, and its honesty claims match its mechanisms. What is not
ready is the *release ceremony*: the version and CHANGELOG state would produce a tag that
misdescribes the tree (§6). That is a five-minute fix the maintainer must decide on, not a defect
in the system.

The nine open MEDIUM findings share a shape worth naming: none is a defect in what the system
does, and all nine are gaps in what it would *catch or recover from next*. That is the correct
residual risk profile for a system going into use, but it is not zero, and §2 says where it sits.

## 6. Release preparation — the maintainer's decision, nothing executed

Releasing is a Tier-A, user-owned decision. Nothing here was run.

The blocker: `VERSION` is 0.1.0, and `CHANGELOG.md` already has a dated `[0.1.0] - 2026-07-14`
section, while 80 bullets sit above it under Unreleased covering roughly eleven phases.
`release.py --plan` reads VERSION and would therefore tag **v0.1.0** for a tree that is far past
what the 0.1.0 section describes. The plan output is internally correct; the tag would lie.

Suggested order:

1. Roll the Unreleased blocks into one `## [0.2.0] - <date>` section. Current content:
   Added 38, Fixed 25, Changed 11, Security 6 (80 total). The four roll-up hazards this audit
   found (a retracted justification, a superseded duplicate, a closed backlog described as
   deferred, an invariant scope that never shipped) are already resolved, so the merge is
   mechanical. The remaining cosmetic issue is that the blocks repeat per phase (PRE-5).
2. Bump the version triple, then confirm `python3 tools/version.py --check` reports 0.2.0.
3. Re-run `python3 tools/release.py --plan`; it must now propose v0.2.0.
4. Tag and push. `gh` is unavailable in this environment, so the GitHub-release step runs from a
   machine with `gh` authenticated. The tag alone is enough to move `update_check` off its
   `no_release` state.

Consider adding preconditions to `release.py execute()` first (PRE-1): it currently tags with no
battery run, no version check, and no existing-tag check.

## 7. Method note

Findings came from six dimension agents, each scoped to a charter and returning a fixed schema.
Agent output was treated as a claim, never as a result: every finding was reproduced by the main
loop before entering the ledger, and the reproduction changed the conclusion twice — a historical
audit document was misread as count drift, and the shorthand-citation class turned out to be
genuinely unguarded but with zero unregistered instances. Two findings were defects introduced by
this audit's own earlier commits, and are recorded as such rather than quietly corrected.

One correction happened mid-fix and is worth recording: the shorthand-citation guard was first
written against `_reference_scan_files()`, which excludes `tools/*.py` and the packaging READMEs —
two thirds of the real citation sites, including the tool whose enforced size caps depend on them.
That version would have closed the finding on paper while remaining blind to it. The guard now
scans the tracked file list. This is the same failure mode the audit exists to catch, and it
nearly shipped inside the fix for it.
