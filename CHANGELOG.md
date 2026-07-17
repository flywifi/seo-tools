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

### Added
- The Drive hub convention (`docs/DRIVE-HUB.md`): one Google Drive folder every surface shares,
  with a fixed layout (Inbox, Store, Jobs, Knowledge, Profile, Outbox), an append-only/create-only
  write rule, a dated-file naming convention, and the async compute-job contract
  (`shared/schemas/compute-job.json`: allowlisted job types, idempotency by job id, hub-confined
  input paths, honest failure results). Three opt-in capabilities scaffold the feature
  (`compute_handoff_enabled`, `drive_api_polling`, `remote_compute_endpoint`, all default off with
  degraded-behavior notes), plus the drop-folder inbox ledger template (`pipeline/inbox/`) and two
  newly registered Google Drive for desktop reference sources.

### Fixed
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
