# Architecture Decision Records

This log uses the [MADR](https://adr.github.io/madr/) format. ADRs 1 to 5 are the
foundational architecture decisions, reconstructed from `CLAUDE.md` and
`docs/ARCHITECTURE.md`. ADRs 6 and up are a faithful reformat of the structured
decision records in `ledger/ledger.json` (one ADR per recorded decision); nothing is
added beyond what those records state. New decisions get the next number via
`docs/adr/0000-template.md`.

| # | Title | Date | Status |
|---|---|---|---|
| [0001](0001-hub-and-spoke-routing.md) | Hub And Spoke Routing | 2026-06-01 | Accepted |
| [0002](0002-atoms-compose-into-spokes.md) | Atoms Compose Into Spokes | 2026-06-01 | Accepted |
| [0003](0003-drift-guard-as-structural-enforcement.md) | Drift Guard As Structural Enforcement | 2026-06-01 | Accepted |
| [0004](0004-no-fabrication-null-and-flag.md) | No Fabrication Null And Flag | 2026-06-01 | Accepted |
| [0005](0005-local-first-privacy-boundary.md) | Local First Privacy Boundary | 2026-06-01 | Accepted |
| [0006](0006-p26-slot-render-export.md) | P26 Slot Render Export | 2026-07-02 | Accepted (shortlist) |
| [0007](0007-p26-slot-scene-chapters.md) | P26 Slot Scene Chapters | 2026-07-02 | Accepted (shortlist) |
| [0008](0008-p26-slot-shorts-reframe.md) | P26 Slot Shorts Reframe | 2026-07-02 | Accepted (shortlist) |
| [0009](0009-p26-slot-silence-cuts.md) | P26 Slot Silence Cuts | 2026-07-02 | Accepted (shortlist) |
| [0010](0010-p26-video-tooling-eval.md) | P26 Video Tooling Eval | 2026-07-02 | Accepted (shortlist) |
| [0011](0011-p27-evidence-governance-patterns.md) | P27 Evidence Governance Patterns | 2026-07-03 | Accepted |
| [0012](0012-p28-transcript-chapters-footage-routing.md) | P28 Transcript Chapters Footage Routing | 2026-07-03 | Accepted |
| [0013](0013-p29-media-tool-integration.md) | P29 Media Tool Integration | 2026-07-03 | Accepted |
| [0014](0014-p30-accounting-bucket.md) | P30 Accounting Bucket | 2026-07-04 | Accepted |
| [0015](0015-p31-finance-privacy-boundary.md) | P31 Finance Privacy Boundary | 2026-07-04 | Accepted |
| [0016](0016-p32-close-all-scenario-gaps.md) | P32 Close All Scenario Gaps | 2026-07-04 | Accepted |
| [0017](0017-p33-source-dependency-currency.md) | P33 Source Dependency Currency | 2026-07-04 | Accepted |
| [0018](0018-p34-construction-knowledge-base.md) | P34 Construction Knowledge Base | 2026-07-04 | Accepted |
| [0019](0019-p35-task-tracker.md) | P35 Task Tracker | 2026-07-05 | Accepted |
| [0020](0020-p36-source-currency-freshness.md) | P36 Source Currency Freshness | 2026-07-05 | Accepted |
| [0021](0021-p37-jurisdictional-overlay.md) | P37 Jurisdictional Overlay | 2026-07-06 | Accepted |
| [0022](0022-p38-cross-modality-architecture.md) | P38 Cross Modality Architecture | 2026-07-07 | Accepted |
| [0023](0023-p38-jurisdictional-overlay-hardening-orlando.md) | P38 Jurisdictional Overlay Hardening Orlando | 2026-07-07 | Accepted |
| [0024](0024-p39-cross-modality-audit.md) | P39 Cross Modality Audit | 2026-07-07 | Accepted |
| [0025](0025-p40-brand-deal-flow-hardening.md) | P40 Brand Deal Flow Hardening | 2026-07-11 | Accepted |
| [0026](0026-p41-rerun-observations-open-vocabulary.md) | P41 Rerun Observations Open Vocabulary | 2026-07-11 | Accepted |
| [0027](0027-p42-creator-document-templates.md) | P42 Creator Document Templates | 2026-07-11 | Accepted |
| [0028](0028-p43-chatgpt-surfaces-and-transitions.md) | P43 Chatgpt Surfaces And Transitions | 2026-07-12 | Accepted |
| [0029](0029-p44-background-updating.md) | P44 Background Updating | 2026-07-12 | Accepted |
| [0030](0030-p45-content-import.md) | P45 Content Import | 2026-07-12 | Accepted |
| [0031](0031-p46-content-import-hardening.md) | P46 Content Import Hardening | 2026-07-13 | Accepted |
| [0032](0032-p47-currency-versioning-push-integrity.md) | P47 Currency Versioning Push Integrity | 2026-07-14 | Accepted |
| [0033](0033-p48-update-channels-branch-fallback.md) | P48 Update Channels Branch Fallback | 2026-07-14 | Accepted |
| [0034](0034-p49-audit-remediation.md) | P49 Audit Remediation | 2026-07-15 | Accepted |
| [0035](0035-p50-onboarding-remediation.md) | P50 Onboarding Remediation | 2026-07-15 | Accepted |
| [0036](0036-p51-publishing-oauth-live-upload.md) | P51 Publishing Oauth Live Upload | 2026-07-15 | Accepted |
| [0037](0037-p52-maintainer-doc-accuracy-guards.md) | P52 Maintainer Doc Accuracy Guards | 2026-07-16 | Accepted |
| [0038](0038-p54-macos-venv-and-path-fixes.md) | P54 macOS Venv And Path Fixes | 2026-07-16 | Accepted |
| [0039](0039-p55-doc-source-trigger.md) | P55 Doc Source Trigger | 2026-07-16 | Accepted |
| [0040](0040-p56-p57-publishing-wizard-audit.md) | P56 P57 Publishing Wizard Audit | 2026-07-16 | Accepted |
| [0041](0041-p58-audit-hardening.md) | P58 Audit Hardening | 2026-07-16 | Accepted |
| [0042](0042-p59-currency-accuracy-audit.md) | P59 Currency Accuracy Audit | 2026-07-16 | Accepted |
| [0043](0043-p60-drive-hub-omnichannel.md) | P60 Omnichannel Drive Hub | 2026-07-17 | Accepted |
| [0044](0044-p61-work-orders-and-ingest-screening.md) | P61 Work Orders and Ingest Screening | 2026-07-17 | Accepted |
| [0045](0045-p62-two-pass-injection-screening.md) | P62 Two-pass Injection Screening | 2026-07-18 | Accepted |
| [0046](0046-p63-sweep-remediation.md) | P63 Sweep Remediation | 2026-07-18 | Accepted |
| [0047](0047-p64-cowork-surface-and-audit-completeness.md) | P64 Cowork Surface and Audit Completeness | 2026-07-19 | Accepted |
