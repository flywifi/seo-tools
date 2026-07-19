# Changelog

All notable changes to Creator OS are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This history was reconstructed from `STATE.md` and `ledger/ledger.json`; it records only
what those sources state. Per-phase detail lives in `STATE.md`; the reasoning behind major
decisions lives in `docs/adr/`. Only one version has been released so far (`0.1.0`, the
baseline release cut in P47), so all pre-release development is folded into that entry;
work after the baseline sits under Unreleased.

## [Unreleased]

### Security
- Remote MCP endpoint (`tools/mcp_server.py --serve-remote`) gains two in-process backstops
  (P67-B) behind the documented TLS+auth proxy: it refuses to bind a non-loopback `--host` when no
  `CREATOR_OS_MCP_TOKEN` (or `remote_mcp_token` in `creator-os-config.local.json`) is set and
  `--insecure` is not passed (no accidental open public endpoint), and enforces an in-process
  bearer gate (constant-time compared, 401 otherwise) when a token is set. A loopback bind behind
  the proxy is unchanged and needs no token. Package-independent selftest covers the serve
  decision and the bearer gate; runbook and cross-modality docs reconciled.

### Changed
- Invariants 14, 16, and 17 rebuilt from substring/marker tests into property checks (P67, closes
  the P65 guard-shallowness backlog): inv 14 requires a non-empty parsed Allowed-tools allowlist;
  inv 16 additionally requires an `agent()` call to consume an earlier agent/parallel/pipeline
  result (marker-in-a-comment with no second agent now fails); inv 17 additionally forbids any
  mutation tool (Write/Edit/NotebookEdit) in a read-only agent's allowlist. Each tuned against the
  real tree (5 agent defs, 5 workflows stay green) with a crafted-bad proof. Invariant count
  unchanged at 56.

### Added
- Invariant 36 keystone assertion (ADR 0048): a `check_*` function carrying an `Invariant N`
  docstring label but never called in `main()` now fails the guard, closing the audit-proven
  hole where the top-numbered invariant could be silently dropped while every count stayed green.
- Invariant 54 Layer 3: the sixteen CLIs the P65 audit caught raw-tracebacking on a >255-byte
  path keep their thin-main OSError boundary structurally (fails on the pre-fix tree naming all
  sixteen); the Layer 2 fs-call set gains `read_bytes`/`stat`/`glob`/`iterdir`/`unlink`.
- Advisory invariant 56 (invariants 55 to 56): `registry_io.save_registry` stamps a
  `_content_digest` over `sources[]` and the guard recomputes it, so an out-of-band in-place
  edit to an existing registry entry — invisible to the id-level freshness digest — surfaces.
- `tools/selftest_sweep.py`: scripted discovery of every CLI selftest under `tools/` and
  `shared/` (argparse flag, argv probe, or subcommand; package entries via `-m`), run by the CI
  guard job alongside `scenario_check`, `count_truth`, and `doc_freshness --check` — the
  behavioral battery the audit found absent from CI. 63+ selftests, seconds of runtime, and a
  new tool's selftest is CI-gated automatically.
- `tools/validate_agent_output.py --selftest`: offline fixtures for all five fabrication rules,
  schema auto-detect, and the end-to-end gate; the authority-allowlist loader now warns loudly
  when its config is missing instead of silently disabling the fabricated-URL rule.
- Competitor export screening: every free-text field parsed from competitor HTML is screened by
  the offline injection scanner and the secret/PII scanner before it may enter the committed
  `competitor-channels.json`; QUARANTINE/BLOCK or PII matches are nulled and flagged
  (null-and-flag), REVIEW-level matches are flagged for the session tier.

### Fixed
- The three HIGH data-boundary gaps from the P65 audit (ADR 0048): the generic `sk-` secret
  pattern now matches current hyphenated provider key formats and fine-grained `github_pat_`
  tokens; the tracked-content scan reads EVERY tracked file behind a binary sniff instead of a
  suffix allowlist; and invariant 20's forbidden tracked suffixes expand to a single shared
  tiered list (`FORBIDDEN_DATA_SUFFIXES`: spreadsheets, columnar exports, financial application
  files, credential/key stores, databases, backups, email/contacts, disk images, archives,
  office binaries, capture media) consumed by the drift guard, the pre-commit gate, and CI.
- Privacy invariants 19/20/21 print a loud DID-NOT-RUN advisory in a non-git copy instead of
  silently passing; inv 21's git-unavailable skip no longer reads as a pass.
- Sixteen more CLIs raw-tracebacked on a >255-byte path argument (the class P64 fixed for two
  files); each now returns the clean `{"error","next_step"}` envelope, `source_currency`
  propagates its exit code, and the six with selftests carry a boundary case.
- Invariant 55's residual-origin escape was a raw substring test and origin claims were not
  surface-checked: claims are now reconciled against an explicit `_residual_origins` list and a
  per-origin surface-affinity table (the audit's phantom-origin repro now fails).
- Four agent definitions omitted the verification envelope their own schemas require;
  invariant 15 now also asserts every definition's prose names all three envelope fields.
- Nine selftest summaries printed hardcoded denominators (four already wrong: build_calc said
  24 of 24 while 29 ran, publishing_compliance 20 over 15, mediaprobe 17 over 19,
  scenario_check 13 over 14); every selftest count in the tree is now derived from a run counter.
- Two prose-named symbols lacked verify markers (`sweep_quarantine`, `render_prior`);
  `docs/CROSS-MODALITY-AUDIT.md` is headed as a historical P39 snapshot against the live
  22-spoke tree.

### Changed
- The invariant-42 writer census is AST-level: only an actual `save_registry` import or
  attribute use counts as a writer, so prose or a read-only import cannot false-positive it.
- `docs/DOC-MAINTENANCE.md` records the known guard-shallowness backlog (invariants 14/16/17
  substring recipes with drafted property-level fixes) as deliberate deferred work.
- The ENAMETOOLONG traceback class (ADR 0047): `Path.exists()` does not suppress errno 36, so a
  >255-byte CLI path argument crashed dispatch-level probes that sat upstream of the P63 loader
  guards. Every filesystem touch reachable from a CLI argument now yields the clean
  `{"error","next_step"}` envelope: obligations `--scan`/`--verify`/`--write-manifest`, finance
  `--reconcile`/`--verify`/`--write-manifest` plus the payload-derived invoice-filename write,
  and the accounts/tasks/doctemplates loaders (each in its tool-local error idiom; the finance
  CSV privacy refusal still raises for library callers and is translated only at the CLI). Every
  touched selftest gains a >255-byte boundary case.
- Selftest summary counts that had silently drifted from reality: obligations printed "16 of 16"
  while 18 checks ran, and tasks printed "46" over 45. Both summaries (and finance/accounts/
  doctemplates, already derived) now compute the count from the checks that actually ran.
- The connector resolver crashed on the committed registry (ADR 0046): the `google_drive_hub`
  entry (P60) shipped without `default_flag`, so `connectors.py --plan/--list/--json` raised
  `KeyError` and the MCP `get_connectors` tool returned an error instead of the evidence plan.
  The entry gains `default_flag: not_installed` (matching every `requires_capability` peer) and
  `resolve()`/`cmd_list()` read the key defensively, defaulting a malformed future entry to off.
- `transcript_normalize` jobs silently delivered only gap metrics: the runner passed
  `--json --gap-metrics --suggest-chapters` but the transcripts CLI modes are mutually exclusive,
  so segments and suggested chapters never reached the job result or the Outbox artifact. The
  runner now uses the new combined `--normalize` mode and its selftest runs the built argv on a
  committed fixture asserting all three keys.
- `tools/finance.py` and `tools/obligations.py` dumped raw Python tracebacks when a CLI payload
  argument was a bad path or inline JSON; both now return the clean `{"error","next_step"}`
  envelope with exit 1 across all ten payload entry points, and `build_invoice` gap-flags a
  non-dict `terms` value (`malformed_terms`) instead of crashing on a plain-English string.

### Added
- Cowork as a first-class surface pair (ADR 0047): `shared/cross-modality/transitions.json` gains
  `cowork_local` (a hypervisor-isolated VM on the user's machine: Class A/B/C native, flags
  enforced, local stores) and `cowork_remote` (the ephemeral Anthropic-hosted sandbox: Class B/C
  via remote MCP connectors only, no `local_fs` because nothing on the sandbox disk survives
  session end), mirrored across TRANSITIONS.md (eleven surfaces), the wizard surface map, the
  cross-modality engine matrix, the INJECTION-TWO-PASS availability rows, and a new DEPLOYMENT
  capability-matrix column.
- The `origins` field on every cross-modality surface row, mapping each surface to the
  compute-job origin vocabulary, with origin `other` claimed by a documented residual note.
- Drift invariant 55 (surface-origin completeness): `tools/handoff/queue.py ALLOWED_ORIGINS` must
  equal the `compute-job.json` origin enum, and every origin must be claimed by a surface or the
  residual note — the independent-oracle reconciliation that would have caught the missing Cowork
  surface the day the `cowork` origin shipped. Fail-closed.
- `docs/AUDIT-PROTOCOL.md`: the repeatable audit procedure — derived coverage sets (never
  enumerated from memory), four input-boundary classes per exercised CLI (incl. >NAME_MAX),
  per-surface empathy legs including both Cowork modes, harness-artifact re-verification, and a
  mandatory closing list of everything the audit did NOT exercise. Scenario S10 gains a
  `cowork-surface-model` leg executing the committed transitions matrix on every battery run.
- `shared/docintel/transcripts.py --normalize`: one combined object (segments + silence gaps +
  suggested chapters) for the transcript_normalize job, additive beside the unchanged single-mode
  flags, plus the tool's first `--selftest`.
- Drift invariant 53 (connector resolver smoke): executes `resolve()` over the committed
  `connectors.json` so an entry the resolver cannot process fails the build (invariants 18/23/41
  are static and missed the P60 defect). Fail-closed.
- Drift invariant 54 (payload-loader robustness): AST-asserts the finance/obligations payload
  loaders keep their try/except guard (the invariant-35 sibling for the offline money/legal CLIs).
  Fail-closed.
- Two-pass injection screening (ADR 0045): the offline pattern tier is now a genuine FIRST pass
  whose verdict feeds the authoritative in-session semantic guard, which can catch reworded attacks
  the regex misses. `injection_scan.render_prior` renders the offline verdict as a category+score
  advisory line (never raw content); `shared/injection-guard-engine.md` defines the
  `<untrusted_content>` envelope, the reconciliation model, and the fail-safe. Drop-folder records
  carry the `offline_pattern_scan` prior and `pass2_pending`; `inbox.reconcile` combines the prior
  with the authoritative session verdict, and `approve` persists the `{offline_pattern_scan,
  injection_scan_result, reconciliation}` triple and refuses to route anything the offline tier
  sealed (the session can never un-seal it) or the session escalated. Formalized in
  `shared/schemas/injection-scan.json`; the ingest-route and inbox-routing atoms gained the prior
  input, the reconciliation output, and the envelope discipline. Coverage varies by modality
  (`both` / `offline_only` / `session_only`), recorded in `shared/cross-modality-engine.md`; the
  ChatGPT and Gemini packaging instruct the same discipline as their own second pass (instruct, not
  enforce). New `docs/INJECTION-TWO-PASS.md` documents the architecture, the availability matrix, the
  OWASP-grounded limits, and the per-engine command/trust posture with dated vendor-doc citations
  (Anthropic mitigate-jailbreaks, OpenAI Model Spec 2025-12-18, Google/Gemini layered defense,
  OWASP LLM01:2025), registered in the source registry via the sanctioned seed path.
- The offline injection pattern tier (`tools/injection_scan.py`): a stdlib implementation of the
  injection-guard engine's machine-scoreable spec (eight categories with per-match points, the
  SOCIAL co-occurrence rule, the CLEAN/REVIEW/QUARANTINE/BLOCK thresholds, the engine's record
  shape), with a category-sync selftest so the rulebook and the tool cannot drift. Wired as a
  buffer on every unattended ingest surface: job-ticket free text is screened in
  `queue.validate_ticket` (fail-closed), the offline inbox scan reads text files and seals
  QUARANTINE/BLOCK verdicts into `Inbox/Quarantine/<date>/` via `sweep_quarantine` (the second
  sanctioned Inbox writer; the sealed subtree is skipped by scan, refused by approve, unreachable
  by follow-ups and rules), import previews carry a pattern summary, and the wizard renders each
  finding's matched phrasing escaped for human review. The verdict travels as
  `offline_pattern_scan`, never the session guard's field; the full guard in a session stays
  authoritative. Scenario S10 runs a poisoned file through the live catch-and-seal chain.
- The two-step work order: approving an inbox batch files it, then a second screen lists the
  exact follow-up jobs (per-item checkboxes, an "Anything to change?" note carried verbatim as
  the ticket `consent_note` -- data for review, never parsed or executed) and a second click
  queues only the checked work. Background-work ON/OFF banners show the compute switch state and
  where to change it on the work-order and inbox screens. New `transcript_normalize` job type
  (segments, silence gaps, suggested chapters for a dropped transcript). Direct library saves
  exist only behind the new default-off `job_store_writes_enabled` capability (62 capabilities,
  47 degraded notes) whose wizard toggle requires an acknowledged risk warning; the runner
  re-reads the LOCAL capability at build time, so a forged ticket flag alone can never enable a
  write.
- The offline keyword tool (`tools/keyword_offline.py`): one deterministic, zero-network report
  over all eight committed keyword-library files plus the scoop cache, with a structural honesty
  envelope (`search_volumes` always null, `data_basis` naming the local sources). The
  `keyword_offline` job type is now wired -- every allowlisted job type runs (supersedes the
  "remains refused" note recorded in ADR 0043).
- Outbox delivery: report-style done jobs also write their JSON output to
  `<hub>/Outbox/<job_type>.<stamp>Z.mac.json` (failed jobs never deliver), and the Drive API
  transport uploads staged Outbox artifacts. A real two-tier `--selftest` for
  `tools/mcp_server.py` (package-independent checks always; live registered-tool count == static
  source count when the mcp package is installed -- first live-import proof: 58 tools).

- The Drive hub convention (`docs/DRIVE-HUB.md`): one Google Drive folder every surface shares,
  with a fixed layout (Inbox, Store, Jobs, Knowledge, Profile, Outbox), an append-only/create-only
  write rule, a dated-file naming convention, and the async compute-job contract
  (`shared/schemas/compute-job.json`: allowlisted job types, idempotency by job id, hub-confined
  input paths, honest failure results). Three opt-in capabilities scaffold the feature
  (`compute_handoff_enabled`, `drive_api_polling`, `remote_compute_endpoint`, all default off with
  degraded-behavior notes), plus the drop-folder inbox ledger template (`pipeline/inbox/`) and two
  newly registered Google Drive for desktop reference sources.
- The async compute hand-off itself (`tools/handoff/`): a transport-agnostic queue and runner
  (atomic writes, duplicate and Drive-conflict-copy suppression, per-type timeouts, structural
  refusal of anything outside the job-type allowlist, honest failure results) fed by three
  ingresses — the Drive-for-desktop folder watcher (default; cron/launchd `--once` convention with
  mirror-folder detection and the wizard `/drive-hub` and `/compute` screens), opt-in Drive API
  polling (`drive.file` scope, create-only uploads, an injectable zero-network transport, a new
  `google_drive` OAuth entry and `google_drive_hub` connector), and opt-in remote MCP tools
  (`submit_compute_job` / `job_status`, doubly gated; the MCP server now exposes 58 tools).
- The drop folder ("divvy up"): the `inbox-routing` atom (proposal-only, standalone; atoms
  105 to 106) over the `shared/docintel/inbox_rules.json` dispatch table and the offline scanner
  `tools/handoff/inbox.py` (scan is read-only and never guesses a content category; approve is the
  sole writer with sha256 idempotency and a `Processed/<date>/` move), the wizard `/inbox`
  scan-preview-approve flow with a single-use batch token, the `inbox_scan` job type, the expanded
  `ingest-route` category taxonomy, and scenario S10 (scenarios 9 to 10) running the real scanner
  with the routing pinned absent on purpose.
- The Projects dual projection (`tools/project_docs.py`): a local lane copying the knowledge pack
  into the hub's `Knowledge/` folder (freshness stamps preserved, pack-to-projection staleness
  check, a Refresh button on `/drive-hub`, the `project_docs` job type) and an opt-in Google Docs
  lane that creates real Docs via the Drive import conversion and updates the same doc id on
  re-projection so a private claude.ai Project live-syncs; the static pack is unchanged. The
  transitions doc records that web Claude with the Drive connector can create dated export files
  directly (append-only), so export-and-you-save is no longer the only web write path.

### Fixed
- Adversarial audit of the P61 ingest-screening and quarantine code closed five confirmed defects,
  each now pinned by an `inbox.py` selftest regression: a poisoned transcript that tripped the
  binary sniff (a NUL or high-byte payload) was format-routed WITHOUT the offline screen -- a
  text-format file the tier cannot read is now held for a session, never routed unscreened; the
  quarantine sweep and the approve move overwrote a same-name file in a dated folder (destroying
  a sealed false positive or an earlier approved file) -- both now keep a collision as `name (2)`
  and never delete; `approve` moved a file by a raw `hub / rel` with no confinement (a `..`
  proposal escaped the hub) and its Quarantine lock was a case-sensitive string match a lowercase
  path could dodge on a case-insensitive filesystem -- both are now realpath containment; and the
  screener degraded fail-OPEN (routing files when the tool could not load, contradicting its own
  docstring) -- text-format routing is now fail-closed. Behavior-only hardening; counts unchanged.
- The `library_complete` job builder passed positional arguments the CLI rejects, so every queued
  job of that type failed with an argparse error; it now passes `--export-dir`, pinned by a
  selftest that runs the built argv. The `transcribe_media` builder writes its SRT under
  `Jobs/results/` instead of littering `Inbox/Processed/`. The `project_docs` API lane read the
  stored Google access token verbatim (401 after about an hour); it now refreshes and persists
  via the watcher's proven oauth path, degrading to an honest reconnect note on a dead grant.
- Currency/accuracy audit across versioning, maintainer files, README/docs, and diagnostic surfaces:
  the dashboard scheduler no longer records a failed platform publish (empty media, missing public
  URL, upload failure, missing board, disallowed privacy) as "published" — success is keyed on the
  client result's `ok` field and refusals land as "failed" with the client's error, pinned by a new
  dashboard selftest. Corrected stale prose the guards could not see: the publishing maintainer
  invariants (which still described the pre-P57 caller-only gate and the removed `account_id`
  fallback), seven finance selftest pass-count claims, the wizard doc's bind address and missing
  security-guard description, the architecture doc's atoms table (27 of 105 presented as complete),
  and the `versions.json` `updated` stamp. The doc-freshness manifest was re-blessed and the finance
  maintainer docs are now content-hash-bound to `tools/finance.py`.

### Security
- Audit-hardening pass (the LOW cluster the first remediation deferred): OAuth refresh distinguishes a
  transient error from a dead grant and classifies a dead Instagram token as reconnect-required; the
  publishing clients reject an empty media file before any network call, pin the YouTube resumable
  upload to a Google host, and require a real Instagram account id; the setup wizard bounds the request
  body, backs up a corrupt Claude Desktop config before overwriting it, allowlists the speech-model
  tier before downloading, and ties an import batch to a single-use token so two browser tabs cannot
  cross-approve. `ftc_disclosure_verified` is documented as a presence check, not content validation.
  A map-and-verify pass over three previously-unaudited surfaces (installer, drift guards, source
  trigger) found no new issues.
- Adversarial-audit remediation of the P50/P51 publishing + wizard code (all findings were behind
  `live_publishing_enabled=OFF`, so no user was exposed): the publish `dispatch()` now structurally
  enforces the live-publishing flag and an explicit human confirmation instead of trusting the caller,
  the dashboard passes the full credentials map (the live path returned "reconnect" for everyone
  before), a token-rotation `persist` callback is threaded through so a refreshed TikTok token is
  saved, and the scheduler only dispatches a `direct_api`-tier platform. The setup wizard now confines
  the import-scan folder and the filesystem-MCP folder to the user's home tree (was `os.path.isdir`
  only), rejects cross-site POSTs with an Origin/Referer check, and validates + escapes the
  `nightly_branch` value (which feeds `git pull`). Pinterest/Instagram OAuth redirect host moved from
  `localhost` to `127.0.0.1` to avoid an IPv6 `::1` dead-end. Added the previously-missing
  `publishing_compliance --selftest`.

### Added
- Doc-declared source tracking: the 23 macOS/AI-surface research sources behind the stress-test
  fixes seeded into the source registry (new `os-platform` category; every URL fetch-verified first),
  fenced `sources` declaration blocks in the two macOS docs, `tools/source_sync.py` (a read-only
  reconciler that generates the seed file for any doc-declared source not yet registered), drift
  invariant 52 (`check_doc_source_registry`, fail-closed: an unregistered, URL-mismatched, or
  unparseable doc declaration fails the build), `tools/doc-source-allowlist.json` for illustrative
  ids, and two macOS platform dates (the Homebrew cask Gatekeeper change, the macOS 27 Intel drop)
  in the moving-dates calendar.
- macOS reliability fixes (from the P53 stress test): `tools/env_paths.py` (a private-`.venv`-aware
  `app_python()` and a Homebrew-prefix-aware `which()`); a venv-first dependency install in
  `tools/setup.py` that sidesteps a Homebrew Python's PEP 668 lock; a launcher that probes for a real
  Python and steers to python.org when only the built-in stub exists; an injectable `_os()/_arch()`
  simulation seam; a friendly exit on a busy port 8765; absolute Claude-Desktop MCP interpreter/command
  resolution with Quit-and-reopen + log-location guidance; arch-aware transcription copy; a
  folder-access-denied (TCC) message; DaVinci Resolve multi-path detection; a Safari OAuth caveat; and
  `docs/MACOS-MAINTENANCE.md` capturing the macOS invariants.
- Maintainer coverage for the `tools/` layer: `tools/publishing/MAINTAINER_README.md`
  documenting the publishing invariants, failure modes, dev-traps, and regression-to-selftest
  map, plus a drift check that requires and reference-checks maintainer docs for allowlisted
  `tools/` directories.
- Forward drift guards so maintainer/SKILL/doc prose cannot silently diverge from code:
  a symbol-reference invariant (`<!-- verify: path::symbol -->` markers resolved against the
  AST), extension of the path-resolution check to `docs/*.md` and `README.md`, and
  `tools/doc_freshness.py` content-hash staleness stamping for high-value docs.
- Broad retrofit of `verify:` markers across the maintainer/SKILL/docs corpus wherever prose
  names a concrete top-level `tools/` symbol.
- Process conventions: `.github/CODEOWNERS` (advisory), `docs/adr/` (MADR, backfilled),
  this `CHANGELOG.md`, and `docs/DOC-MAINTENANCE.md`.

### Changed
- Drift invariant 54 widened in place from "the two payload loader bodies contain a try" to the
  whole-path rule (ADR 0047): the loader-body layer now also covers the tasks and doctemplates
  loaders plus an accounts call-site rule, and a new AST layer scans finance/obligations
  `main`/`_main` for any argparse-derived value reaching `exists`/`read_text`/`write_text`/`open`
  outside a try. The widened check fails on the pre-fix tree naming the exact defect sites.
- Corrected stale maintainer/SKILL/doc claims surfaced by a full content-accuracy sweep
  (publishing layer no longer described as "dark/stubs", Pinterest scope, finance-desk check
  counts, contract-desk atom availability, videoedit atom list, tool-count and script-path
  references). The skill-template regression bar was lowered from five to three cases.

### Fixed
- `tools/publishing/__init__.py` docstrings now describe the four real clients, the
  `creds[plat].publish` token model, and the `live_publishing_enabled` + human-confirm gate.

## [0.1.0] - 2026-07-14

Baseline release. Everything below accumulated across phases P0 to P51.

### Added
- **Core architecture:** hub-and-spoke routing (`creator-core` classifies each request into the
  Content, Document, or Pipeline/CRM lane), 22 capability spokes composed from 105 single-operation
  atoms, the `quality-review` governance skill, and deterministic scoring (`score.py`).
- **Engines and protocols:** brand, audience, platform, adaptation, pipeline, web-intel, SEO
  intelligence, voice, finance, contract, tasks, videoedit, transcription, cross-modality, and
  integrations engines; the five governance protocols with `quality-gates.md` authoritative.
- **SEO and competitive intelligence:** SEO intelligence engine with recursive source traversal,
  platform API signal enrichment (TikTok, YouTube Shorts, Reels), an offline competitor-snapshot
  pipeline (browser-header + Playwright fetch, `ytInitialData` extraction, SQLite index), and a
  cross-platform keyword-compare atom.
- **Video and media:** the two-lane videoedit tool package (`tools/videoedit/`), transcript-to-
  chapters and footage-breakdown capabilities, silence/scene scanning over runtime-detected
  ffmpeg/PyAV/PySceneDetect backends, caption bridging, and offline local STT
  (`tools/transcribe.py`, whisper.cpp / faster-whisper) with a guided doctor and integrity-verified
  model fetch.
- **Content import:** import, complete, and analyze the creator's OWN past videos across YouTube,
  Instagram, TikTok, and Pinterest (`tools/video_library.py`, `tools/import_parse.py`, the live
  importer tier, and the retention-to-transcript join).
- **Pipeline / CRM:** the accounting bucket (`tools/finance.py`: invoices, AR aging, cost estimates,
  proposal pricing, cash-flow, payment reconciliation, dunning drafts), the contract desk
  (`tools/obligations.py` obligation tracking), the account resolver and contact lookup, the
  offline task and obligation tracker (`tools/tasks.py`, `tools/shipments.py`), creator document
  templates, and the brand-deal pitch-triage flow.
- **Knowledge bases:** the Florida/North Carolina residential-construction base
  (`tools/build_calc.py`, `tools/construction_fetch.py`) and the optional advisory jurisdictional
  overlay (`tools/geo_overlay.py`) with real Orlando/Orange County data.
- **Cross-surface delivery:** Claude Desktop/Code (MCP server, 56 tool definitions), claude.ai and
  ChatGPT surfaces with a documented transition matrix, Google Workspace and Microsoft 365
  connectors, and a browser-based setup wizard (`tools/wizard.py`) with guided onboarding,
  no-terminal launchers, native-first connectors, guided folder import, and default dependency
  install.
- **Publishing:** real per-platform OAuth (`tools/oauth_flow.py`, loopback flow) and gated live
  upload clients for all four platforms, plus a native folder picker (`tools/pick_folder.py`).
- **Source currency and self-update:** the token-free source/dependency currency system, the
  freshness overlay and bundle, the block-vs-gone resilient verification layer, staged volatile-
  corrections and moving-date calendar, `tools/preflight_push.py`, `tools/release.py`, and the
  self-update lane with stable/nightly channels and a before-a-release branch fallback.
- **Governance tooling:** the drift guard (`tools/sync_check.py`) with the invariant catalog, the
  scenario suite (`tools/scenario_check.py`), the content secret scanner (`tools/secret_scan.py`),
  per-clone git hooks, the read-only research-orchestration engine and agent contracts, and the
  count-truth and URL-provenance invariants.

### Changed
- Modernized and consolidated the source-currency system (P33) into an always-fresh, per-user,
  self-contained model (P36).
- Hardened the brand-deal flow, closing all ten flaws from the CoolBreeze acceptance run (P40).
- Audited and corrected the cross-modality declarations against evidence (P39).

### Security
- Machine-enforced data-at-rest and commit hygiene boundary: allowlist-invert gitignore,
  force-add detection (invariant 20), content scanning (invariant 21, CI), per-clone hooks, and a
  commit-message backstop bounded by a policy SHA (P31). No real CRM data or PII is committable.
- Live publishing is gated behind `live_publishing_enabled` (default off) with human confirmation
  before every post; the deprecated OAuth OOB flow is deliberately never implemented (P51).

[Unreleased]: https://github.com/flywifi/seo-tools/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/flywifi/seo-tools/releases/tag/v0.1.0
