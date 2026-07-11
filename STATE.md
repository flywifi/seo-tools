# STATE.md
Live build status for Creator OS. Update at phase boundaries and after a skill ships.

## Current phase
P6 through P42 are complete. Drift guard exits 0 (31 invariants). Branch:
`claude/repo-access-confirm-wxe50a`.

- P42: creator document templates. Block-structured reusable templates (contracts, rate-card
  display docs, analytics overviews, terms/conditions) with swappable clause blocks: variant
  groups for mutually exclusive alternatives, advisory conditions for the model, never_with and
  requires enforced in code. Store `pipeline/templates/` gitignore-inverted (all-null committed
  starters; attorney text only in gitignored .local files; invariant 31 enforces starter purity).
  `tools/doctemplates.py` (26-check selftest incl. vetted-body byte-equality) assembles by
  concatenation plus bracket fills from profile/deal/rate-card/export/manual sources, writes
  gated by the `document_templates` flag. Atoms: `template-ingest` (proposal-only, exact-quote
  bodies, human saves by hand) and `template-assemble` (model selects whole blocks with reasons,
  code assembles; contract safety envelope preserved). Hub route `template_manage`;
  contract-desk branches drafting to the vetted template when one exists. Scenario S8
  regression-locks swap/exclude assembly. Runbook `docs/DOCUMENT-TEMPLATES.md`.

- P40: brand-deal flow hardening, all 10 flaws from the CoolBreeze test run fixed. Finance core:
  rate-floor-only pricing (`no_cost_basis` gap) + `price_package` (unpriceable items excluded,
  never 0). Personal rate card: `pipeline/finance/rate-card.template.json` (real card gitignored),
  format resolution with `rate_floor_source` provenance, `benchmark_tier_assumed`/`_mismatch` gaps.
  Five structure-only benchmark lever records (null, `needs_research`, do-not-quote). New atoms:
  `product-fit` (persona-scored verdict, mandatory `data_basis`, exclusivity red-flag cap) and
  `pitch-extract` (untrusted body, envelope-stamped citation, verbatim compensation). New hub route
  `pitch_triage` -> deal-pipeline chains extract -> fit -> package price -> gaps -> gate; contract
  drafting stays human-requested. Wizard `/brand-deals` readiness screen (one-click local flag
  enable); degraded messages name the exact flag + wizard route; contract-draft output carries
  mandatory `profile_gaps[]`. Acceptance: 10/10 assertions on the live CLI + repo state (throwaway
  sandbox removed); scenario `S7-coolbreeze-pitch` regression-locks the flow (7/7 suite green).
  Runbook: `docs/BRAND-DEALS.md`. P41 follow-up: score.py rejects unknown dimension keys (S4 leg);
  the specific `no_rate_card_entry` gap suppresses the generic `missing_input` twin in both pricing
  paths; the rate-card format vocabulary is documented OPEN (posts, story sets, scripts, ideation,
  UGC rows added, all null) and mixed-deliverable packages price item by item, never forced into a
  video format (selftest 99/99, S7 extended to a 3-type package).

- P39: audited + corrected the P38-7 cross-modality declarations against evidence. Full adversarial
  audit completed across three resumed runs: 23/23 classifiers + 23/23 skeptics (22 upheld, 1
  overturned an over-call). Class corrections applied; all 96 atoms carry an inherited one-line
  declaration; invariant 28 hardened to reject a stub (Class/Runs on/Mechanism/Fallback required).
  Final A=2/B=7/C=14. docs/CROSS-MODALITY-AUDIT.md has the per-skill verdicts + packaging candidates.

- P38: hardened the jurisdictional overlay and loaded REAL Orlando/Orange data. Unified live-network
  consent (`tools/geo_consent.py`): default-on but ask-first once per session, headless/declined falls
  back with no call, governing both `geo_fetch.py` (FEMA) and the new `tools/geo_geocode.py` (US Census
  address to point). The master `jurisdictional_overlay` switch is now default-on. An independent
  adversarial gate (5 properties + confirm pass) caught + fixed two safety-discard bugs in
  `resolve_conflict`: non-comparable stringency, and comparison across incommensurable units, now
  escalate to human review (a safety floor is never silently discarded). `tools/geo_source_fetch.py` is
  the universal-path fetcher + build cacher: cached all 6 City of Orlando historic-district boundaries +
  the R-2B/T/HP zoning polygon as real GeoJSON with provenance (`orlando-boundaries/`), resolved via a
  new `geometry_ref: cache:` loader. Authored 11 cited overlay records (`orlando-overlays.json` +
  statewide FL Building Code edition); 6 sources seeded + a currency baseline stamped (registry
  186->192). Fixed a versioned-fact over-fire (rutherford scoped to its county); `*.example.json` demos
  excluded from production resolution; invariant 27 now requires every versioned-fact to declare
  `applicability`. Selftests: geo_overlay 37/37, geo_consent 12/12, geo_geocode 9/9, geo_fetch 13/13,
  e2e proof 17/17. 809 E Amelia resolves offline to Lake Eola Heights + R-2B/T/HP + FBC 8th Edition,
  with flood/SJRWMD as consent-gated live gaps. Everything advisory-not-legal-determination. Ledger:
  `P38-jurisdictional-overlay-hardening-orlando`.
  Cross-modality (P38-6/7): `docs/CROSS-MODALITY.md` + a GPT Action
  (`implementation/gpt/actions/jurisdiction_overlay_action.yaml`) + Gemini function declarations make
  the overlay reachable off Claude (Custom GPT, Gemini API, remote MCP, curl; consumer Gems is the one
  dead end). `shared/cross-modality-engine.md` defines the model (capability classes A/B/C, surface
  matrix, packaging map, fallback ladder); every spoke SKILL.md now carries a `## Cross-modality`
  declaration; the setup wizard added a `/cross-modality` per-surface screen. New drift invariants: 28
  (every spoke declares cross-modality) and 29 (every `implementation/` schema parses).

- P37: added an OPTIONAL, advisory jurisdictional-overlay bucket on top of the construction base
  (default off). `tools/geo_overlay.py` (selftest 26/26) is a stdlib EPSG:4326 engine: point-in-polygon
  (half-open vertex rule, holes, multipolygon), bbox pre-filter + true ring test, GeoJSON/KML ingest,
  three overlay kinds (geometry / attribute / versioned-fact), and a conflict-resolution cascade
  (floor/ceiling preemption + Dillon/Home-Rule authority + lex specialis + human-review escape) with a
  W3C PROV audit. `tools/geo_fetch.py` (10/10) is the live FEMA NFHL flood connector behind a SECOND
  default-off flag (`jurisdictional_overlay_live`): with it off it makes no network call (proven by an
  exploding-getter test). The optional `canonical-sources/jurisdiction/` bucket (fl-overlays +
  nc-overlays) auto-indexes into the scoop cache; 14 FL+NC GIS/legal sources are seeded under a new
  `jurisdiction-gis` cadence category with P36 currency wiring (registry 172->186); drift invariant 27
  (`check_jurisdiction`) keeps every overlay cited, kind-typed, and advisory-flagged. MCP tools
  `jurisdiction_resolve` and `overlay_conflict`. Everything is advisory-not-legal-determination;
  genuine legal conflicts escalate to human review. NC modeled honestly (Rutherford has no steep-slope
  ordinance; Asheville Sec. 7-9-2; MRPA layer is screening-only). Docs: `docs/JURISDICTION-OVERLAY.md`,
  `docs/JURISDICTION-OVERLAY-PLAN.md`. Ledger: `P37-jurisdictional-overlay`. (Hub `jurisdiction-desk`
  spoke + routing is the remaining optional wiring.)

- P36: turned the dormant source-currency system into an always-fresh, per-user, self-contained
  freshness system that keeps every deployment's reference data accurate on every modality WITHOUT the
  freshness runtime ever touching GitHub. `tools/freshness_overlay.py` (selftest 30/30) adds the
  read-only-baseline + user-controlled overlay: an append-only event log with deterministic
  union-merge, a provenance envelope on every refreshed value, selector-scoped hashing, RFC 9111
  max-age, a two-tier SLA, Wayback link-rot, a local dashboard, and a store adapter over
  local_fs/google_drive/remote_mcp (reusing the P35 store model). `source_currency.py` gained an
  `--overlay` path so report/check/detect-changes/dashboard write only to the user's own store, never
  the repo registry or GitHub. `data-currency-map.json` now tracks 12 embedded-fact prose/config
  artifacts (the connector registry, integrations/contract/construction/compute/tasks/platform
  engines, config, wizard, video-tooling evidence) under drift invariant 25. Four seed files add 33
  monitorable sources (registry 139->172): connector API changelogs, a new `ai-surface-spec` category
  (MCP/.mcpb/Skills/GPT-Actions/Apps-SDK/Gemini), creator content data (Google Search feeds, Trends
  API, Sprout/Hootsuite, IMH/HypeAuditor, Shopify), and compliance (eCFR Part 465, FTC/Fed-Register/
  USCO feeds, NY/CA AI-disclosure laws, DOE IECC, ICC map). `tools/build_freshness_bundle.py`
  (selftest 9/9) stamps a visible freshness date on the 11 knowledge digests under drift invariant 26.
  The wizard gained a `/freshness-setup` store step; the MCP server gained currency_scan/
  currency_detect_changes/freshness_refresh (overlay-only writes); a local launchd/cron scheduler
  example ships; the weekly CI currency job is retired for zero GitHub coupling. Docs:
  `docs/FRESHNESS.md`. Ledger: `P36-source-currency-freshness`.

- P35: added the offline, source-cited, human-gated project task and obligation tracker for brand deals.
  `shared/tasks-engine.md` defines the model: the anti-phantom rule (every task cites a document,
  event_derived, or user_stated source; there is never a task the tool cannot cite), a seven-state
  lifecycle with a first-class waiting_external state, and history[] as the append-only source of truth
  that status/responsible_party/billable_ready fold over. `tools/tasks.py` (selftest 46/46) does the
  offline compute: forward/backward/reverse-plan scheduling with a negative-slack feasibility check on the
  obligations date math, RRULE recurrence materialized on demand, waiting-on handoff nudge/escalate,
  two-party approval ping-pong, payment-milestone billable-readiness into the finance lane, .ics export +
  reminders digest, and a store adapter (local_fs / google_drive / remote_mcp) whose append-only event-log
  union-merge makes a shared Google Drive store concurrency-safe (not last-writer-wins). `tools/shipments.py`
  (15/15) normalizes carrier status to a canonical enum, polls EasyPost/Ship24 with env-only keys (or takes
  manual entry), and sets the immutable delivered_at planning anchor. `tools/coverage_verify.py` (18/18)
  reconciles multiple media transcripts to a canonical truth (surfacing every credible dissent as a
  conflict) and verifies required talking points with extractive citations, abstaining rather than inferring.
  Eight atoms compose the `task-desk` spoke, hub-routed as task_status/task_plan/coverage_check/
  shipment_update/milestone_bill; MCP tools and a dashboard tasks view added. Cross-surface continuity for a
  non-technical Mac user runs the same tasks on claude.ai web, the Claude desktop app, and mobile via the
  Drive/Sheets store, with an optional remote-MCP transport unlocking ChatGPT/Gemini. Four config
  capabilities (task_tracking, shipment_tracking, coverage_verification, task_store_backend). Drift invariant
  24 enforces task-tracker integrity; the S6 creator-core scenario exercises a two-party ping-pong plus
  milestone, shipment, and coverage on fictional fixtures. Docs: `docs/TASK-TRACKER.md`. Ledger:
  `P35-task-tracker`.

- P34: added the offline residential construction and DIY knowledge base scoped to Florida and North
  Carolina. `shared/construction-engine.md` defines the offline-dictionary schema, the cite-and-link-only
  redistribution model (the codes are copyrighted, so we author cited prose keyed to section numbers and
  never bundle code text), and FL/NC edition awareness. The dictionary
  (`canonical-sources/construction/*.json`: 12 trades plus glossary, assemblies, fl-nc-specifics,
  edition-status, diagram-index) is indexed by the scoop cache and answerable offline via
  `construction_lookup`. `tools/build_calc.py` adds eight first-principles calculators (selftest 24/24).
  Three atoms (construction-lookup, code-lookup, build-calc) compose the new `construction-desk` spoke,
  hub-routed as `construction_question`/`code_lookup`/`build_calc`, with `project-builder` consuming them;
  MCP tools `construction_lookup`/`code_lookup`/`build_calc` added. Five original CC0 SVG diagrams with a
  license-tagged index. `tools/construction_fetch.py` downloads only public-domain/open assets and
  structurally refuses copyrighted hosts (selftest 12/12). 37 sources registered under new `building-code`
  (cite-only, 365d) and `construction-authority` (180d) currency categories; `edition-status.json` and the
  data-currency-map watch the NC 2024 and FL 9th-Edition transitions. Drift invariant 22 enforces
  edition-aware citations, per-diagram licenses, and diagram_ref resolution. Docs: `docs/CONSTRUCTION.md`.

- P33: audited and modernized the source-currency system. Fixed its config bugs (legal-authority
  and cost-vendor cadence overrides added to traversal-config so they are no longer treated as
  7-day-due; corrected the stale MCP-spec and TikTok changelog URLs; deduped two duplicate entries;
  filled or pruned the four placeholder stubs; allowlist gained tiktok.com, copyright.gov,
  law.cornell.edu, github.com, ecfr.gov). Extracted `tools/registry_io.py` as the single shared
  registry writer (source_currency, traversal_engine, dependency_currency import it) and added a
  `source_currency.py update-source` correction subcommand. Closed the dependency blind spot: the
  registry gained `software-dependency` and `mcp-server` categories (fields upstream_api, check_url,
  package, pinned_constraint, validated_version, latest_seen) and 28 seeded entries (12 pip, 6
  binaries, 10 MCP servers), each naming what it protects and why a bump matters.
  `tools/dependency_currency.py` is the token-free version-drift checker (PyPI JSON + GitHub
  Releases, deterministic drift with major-bump-is-breaking, advisory offline degradation, --apply
  stamping, 21-check selftest); `source_currency.py check --detect-changes` adds token-free
  content-change detection (conditional GET + sha256 stored on the entry; unchanged stamped, changed
  queued; 10-check selftest). Added content sources (FTC eCFR 16 CFR 255, three cost vendors, a
  github-seo upstream) and `data-currency-map.json` classifying every canonical file
  (watched/static/dated/tool-managed) so the audit's orphan finding is resolved permanently. Drift
  invariant 23 fails if a requirements package or MCP-backed connector has no registry entry; a
  read-only weekly `currency-report` CI job runs both reports; `docs/CURRENCY.md` is the runbook.
  A dependency baseline --apply ended the pip deps' dormancy. Ledger: `P33-source-dependency-currency`.

- P32: closed all seven remaining scenario-suite gaps (G1 to G7); the P24 gap ledger (G1 to G10)
  is now empty, all closed deliberately. The CRM read lane: `tools/accounts.py` is a third offline
  compute-lane instance (stdlib, CREATOR_OS_ROOT sandbox, computed_by, gaps[], 27-check selftest,
  read-only) with a tiered brand resolver (exact, alias, substring, difflib fuzzy, brand-category
  term map) that never auto-picks past a confident exact or alias match, a contacts reader, and a
  verbatim deal-status reader (no money math). Three atoms (`account-resolve`, `contact-lookup`,
  `deal-status`); account-manager gains a `contact_lookup` action and an account-resolve step,
  deal-pipeline a deal-status read step. account-schema v0.2.0 reconciled to the pipeline engine
  (brand_category enum incl. lighting, secondary_contacts, relationship_health, aliases,
  channel_preferences, deal_history_summary, renewal_candidate). Hub classifications
  `account_read`, `deal_status`, `content_critique`. Seasonal: new
  `canonical-sources/seasonal-aesthetic.md` plus the `seasonal.json` seasonal-windows entry with
  resolved ISO dates (reference_year 2026, annual recurrence); engine table, seasonal-map table,
  and JSON reconciled; drift invariant 22 validates frontmatter load refs and canonical-sources
  joined KNOWN_ROOTS. Media-kit critique: `mediakit-critique` (benchmark-compare per metric plus a
  structural review, honest `structural_only` degradation when benchmarks are unsourced) routed via
  content_critique to partnership-mediakit. Two MCP tools (`contact_lookup`, `deal_status`,
  read-only and PII-masked; 36 total). Contact PII stays on-machine; reads redact for anything
  quoted off-machine. Ledger: `P32-close-all-scenario-gaps`.

- P31: finance features on a hardened privacy boundary. Security first: allowlist-invert
  `.gitignore` for `pipeline/finance/` plus repo-wide export/key/env ignore patterns; drift
  invariant 20 (every tracked file under `pipeline/` must be on the explicit allowlist; no
  tracked CSV/XLSX/OFX/QFX/PEM/KEY/.env anywhere) and invariant 21 (content secret scan), both
  failing closed in CI; `tools/secret_scan.py` (stdlib scanner: key material, credential values,
  session links, emails, amount-plus-brand pairs in pipeline files; selftest on concatenated
  fixtures) with `tools/secret-scan-allowlist.json` (reasoned exemptions plus the commit-policy
  boundary SHA); `tools/install_hooks.py` (pre-commit staged scan, commit-msg hygiene hook); CI
  gains a tracked-content scan and a commit-message/author backstop; CLAUDE.md gains the
  machine-enforced commit and PR hygiene non-negotiables. Then the features on top:
  `finance.cashflow()` (weekly cash-movement buckets over a horizon; overdue, beyond-horizon,
  and undated flows totaled separately with gaps), `finance.redact()` (banded amounts, initialed
  brands; `--redacted` CLI flag and MCP parameter), `finance.reconcile()` (bank/PayPal CSV to
  open invoices in exact/probable/uncertain tiers, proposal-only, structural refusal of any
  in-repo non-`.local.` CSV) with the gated `mark_paid()` write, dashboard AR tab (read-only
  aging plus chase queue at `/api/ar`), and three new atoms (`cashflow-view`,
  `payment-reconcile`, `dunning-draft` with its bucket-keyed tone ladder that never sends).
  Hub classifications `cashflow_projection`, `payment_reconcile`, `dunning_draft`; finance-desk
  actions `cashflow`, `reconcile`, `dun`. finance.py selftest now 71 checks. Two MCP tools
  (34 total). Ledger: `P31-finance-privacy-boundary`.

- P30: the accounting bucket. `pipeline/finance/` record store (standalone invoices with line
  items and frozen terms_snapshot, cost estimates, cost actuals; deal.invoice becomes a
  denormalized summary plus `invoice_refs[]`, resolving the P23-era drift toward the engine's
  standalone model). Structured money terms, additive: `payment_terms_structured` (net days,
  anchor, deposit, late penalty, kill fee), `revenue_share`, `commission`, `ip_license_fee` on
  deal v0.3.0 and contract schemas, filled only from quoted evidence; playbook gains
  `pricing_and_rates` and `revenue_share_and_commission` families. `tools/finance.py` is the
  second offline compute lane instance (imports the obligations date machinery; exact Decimal;
  44-check selftest): AR aging, late-penalty accrual, revenue-share/commission clamps from
  reported basis figures only, cost rollups, proposal price floors, deterministic invoice ids,
  sha256 manifest, CREATOR_OS_ROOT sandbox; reads always on, writes gated by
  `finance_management` + `invoice_generation` (+ `cost_research` for agent dispatch). New
  `finance-desk` spoke (atoms `invoice-generate`, `ar-review`, `cost-estimate`,
  `proposal-price`; hub classifications `invoice_create`, `finance_review`, `cost_estimate`,
  `proposal_price`); document-studio gains the `invoice` artifact type; invoice-status upgraded
  to standalone records and the six-state lifecycle. G8 closed deliberately (structured
  benchmark rows plus 6 sourced-or-null metric rows; scenario suite now 7 gaps, all observed).
  Personal rate card template with the deal-debrief proposal-only feedback loop. Fifth agent
  role `cost-researcher` (envelope schema, observed-or-null prices) with the cost library and
  vendor pricing sources registered via source_currency.py. Five MCP tools (32 total). Verbatim
  financial boundary (NOT TAX, ACCOUNTING, OR INVESTMENT ADVICE) plus a consequential-action
  gate before any external money commitment; invoices are drafted, never sent. Ledger:
  `P30-accounting-bucket`.

- P29: the P26 media-tool shortlist integrated as optional, runtime-detected backends over the P28
  transcript floor. `tools/videoedit/mediaprobe.py` (silence: ffmpeg silencedetect -> PyAV RMS ->
  gap_metrics; scenes: PySceneDetect -> ffmpeg scdet with the luma caveat attached ->
  suggest_chapters; 17-check selftest on committed raw-stderr fixtures),
  `tools/videoedit/reframe.py` (crop geometry always available, render gated on `shorts_reframe`,
  12-check selftest), `tools/videoedit/mltxml.py` (MLT XML as the second Lane A format, Shotcut
  native; render gated on the new `media_render` flag, APP_DRIVING tier; 13-check selftest). Every
  result carries `computed_by` plus a `backend_chain` audit trail; no backend means honest
  `gaps[]`, never numbers. Three new atoms (`silence-scan`, `scene-scan`, `shorts-reframe`), two
  new flags (`mlt_timeline_export`, `media_render`), four MCP tools (27 total), preflight
  detection and degrade notes, `requirements-videoedit.txt` (optional only). `otio_core.merge` now
  unions incoming `gaps[]` and adopts an enabled reframe directive (both were silently dropped).
  All backends live-verified against the P26 goldens
  (`docs/video-tooling-integration-evidence.json`); unverified and recorded: melt render
  execution, macOS paths, editor-side .mlt opening, otio-kdenlive-adapter reading our MLT, and
  auto-editor (bootstrap still 403-blocked; conditionally shortlisted only). Ledger:
  `P29-media-tool-integration`.
- P28: transcript-to-chapters capability shipped and gaps G9 + G10 closed (the scenario suite now
  declares 8 gaps, all observed). `shared/docintel/transcripts.py` gained `gap_metrics()`
  (inter-segment silence detection, promoted from the runner-owned evidence code the P26 S-0 spike
  validated) and `suggest_chapters()` (chapter boundaries from silences plus words_per_minute
  drops; titles always null, never invented), plus `--gap-metrics` and `--suggest-chapters` CLI
  flags. `tools/scenario_check.py` `op_gap_metrics` now delegates to the product function. New
  `footage_breakdown` classification routes to `video-development`; new `footage-analysis` atom
  (shortcut on video-development) is the realizer: local timing math, model names chapters from
  transcript text only, `human_review_required: true`. Scenario S5 flipped from ambiguous to
  present routing and its silence leg asserts the product `computed_by`. Zero new dependencies;
  the P26 media-tool shortlist (PySceneDetect, ffmpeg, auto-editor, PyAV) remains a future
  integration phase above this stdlib floor. Ledger: `P28-transcript-chapters-footage-routing`.
- P27: evidence governance patterns adopted from the maintainer's prior meeting-evidence system
  (reviewed offline; the source document itself is not committed). Five additive changes: the
  five-mode evidence acquisition ladder (connectors.md + connectors.json v0.2.0
  `evidence_modes`), the field-level memory safety model and write stop conditions
  (pipeline-engine.md), identity confidence split from claim confidence plus
  `artifact_completeness` (verification-envelope.json, exposed in deal-review.json), the
  unknown-over-false-certainty and explicit-stop-conditions rules
  (research-orchestration-engine.md Section 7), and two concrete stop gates in deal-review.js
  (target ambiguous; evidence too thin). Ledger: `P27-evidence-governance-patterns`.
- P26: open-source video tooling evaluation (evaluation only; no integration, no flag changes; G9
  and G10 stay open and the scenario probes still observe them). 15 candidates scored against the
  two-lane videoedit architecture with a 9-criterion rubric; 7 hands-on spikes against synthetic
  media sharing ground truth with the committed `workshop-footage.srt` fixture; 4 research agents
  plus 1 adversarial verifier (8 load-bearing claims attacked: 3 upheld, 5 refined). Headlines:
  PySceneDetect found all 4 authored cuts frame-exact including an isoluminant cut that ffmpeg
  misses by default (luma-only YUV scoring, source-verified, `format=rgb24` workaround); ffmpeg
  silencedetect hit authored silences within 0.021 s; PyAV reproduced silence detection in-process
  with no binary; MoviePy v2 passed the 9:16 reframe spike fully self-contained; the stdlib S-0
  control recovered all transcript gaps with zero dependencies (the degradation floor); auto-editor
  is conditionally shortlisted (emits our exact Lane A formats, but its PyPI wheel is a binary-
  downloading bootstrap and the fcpxml.py round-trip is still unvalidated, S-2 network-blocked);
  Kdenlive/Shotcut verified to have no edit-automation API, confirming the two-lane thesis (their
  surface IS the MLT XML project file + melt). Remotion excluded on its non-OSI license; Revideo/
  editly/ffmpeg-python/Olive/ffmpeg-concat confirmed dormant or stalled. Deliverables:
  `docs/VIDEO_TOOLING_EVAL.md`, `docs/video-tooling-scores.json` (machine-recomputable totals),
  `docs/video-tooling-spike-evidence.json`, first real `ledger/ledger.json` decisions (umbrella +
  4 feature slots).

- P25: the 38-check handoff simulation is now committed and offline-runnable
  (`python3 tools/handoff_sim.py`), completing the offline test battery. All write phases run in a
  throwaway sandbox: `tools/obligations.py` now honors `CREATOR_OS_ROOT` (same pattern as
  `mcp_server.py`), the sim sets it to a temp dir before loading the stack, REFUSES to run write
  phases if the redirect did not take, and Phase J proves reality untouched (real
  `creator-os-config.local.json` and obligation register byte-identical after the run, no tracked
  `.local` files, drift guard green). Verified: 38/38 twice, sentinel-file proof, and a mid-run
  SIGKILL proof (real files byte-identical). Full battery: scenario_check (5 scenarios, 10-gap
  contract) + handoff_sim (38) + obligations selftest (15) + scenario_check selftest (12) +
  sync_check (19 invariants).

- P24: realistic scenario test suite. Five realistic cross-lane utterances ("what's the email for
  that guy from my Hearthline account?", "where are we with that lightbulb company contract?",
  seasonal prep, media kit critique, raw-footage breakdown) pinned as a committed, re-runnable
  contract: `skills/creator-core/evals/scenarios.json` + fictional fixtures, run by
  `tools/scenario_check.py` (stdlib, deterministic, pinned clock 2026-09-15, writes nothing).
  Deterministic legs run through the real product code: obligations date math (register, bands,
  net-30 anchor), transcript parsing, chapter fan-out + YouTube-rule validation, Quality Gates
  verdict arithmetic, benchmark rows. **Findings-as-contract**: the suite fails if a leg breaks, if
  a declared-absent classification appears in the hub routing table, or if any of the 10 gap-ledger
  probes stops observing its gap (closing a gap requires updating the contract + docs/SCENARIOS.md
  deliberately; proven by negative test). Gap ledger G1 to G10 (docs/SCENARIOS.md) is the
  later-phase backlog: no CRM read/contact/fuzzy-resolver capability (G1 to G3), account-schema
  drift vs pipeline-engine (G4), seasonal-map broken load ref + prose-only seasonal dates (G5, G6),
  no media-kit critique path + sparse benchmarks (G7, G8), no transcript-to-chapters/cuts analysis
  (G9), no footage-breakdown routing (G10). TEST-ONLY phase per user decision: gaps documented, not
  built. Result: 5/5 scenarios pass, 10/10 gaps observed, runner selftest 12/12.

- P23 (Phase 3): obligations, timelines, local-first privacy, and an offline compute lane. Two new
  atoms: `obligation-extract` (pulls deliverables/deadlines/payment terms from a SIGNED contract into
  obligation rows using the engine's obligation-row schema; quotes evidence; never computes dates) and
  `deal-debrief` (proposal-only close-out memory that proposes playbook updates and never writes the
  playbook). **Offline compute lane** `tools/obligations.py` (pure stdlib, no network) does the
  deterministic date math the model must not spend tokens on: send-by dates, weekend and US-federal-
  holiday roll-backward, and urgency bands (red 0 to 13, orange 14 to 44, yellow 45 to 89, overdue,
  out_of_band); writes `pipeline/user-context/obligation-register.local.json` (gated by
  `contract_obligations`); `--scan` is read-only and always available; sha256 bucket manifest
  (`--manifest`/`--verify`) mirrors `tools/sync_editing.py`. Tested deterministically (weekend +
  Juneteenth/July-4 roll-back, all bands, null-and-flag). MCP tools `obligation_build`,
  `obligation_scan`, `import_obligations` bridge online-to-offline (the model never does the
  arithmetic). **Local-first privacy** is now a hard guarantee: drift-guard **invariant 19**
  (`tools/sync_check.py`) fails if git tracks any personal `*.local.*` file (proven to bite), and
  `tools/local_privacy.py` reports what stays local. `pipeline/user-context/obligation-register.template.json`
  committed (null); real register `.local` and gitignored. contract-desk wired (actions `obligations`,
  `debrief`); `contract_obligations` degraded_behavior updated. Engine gains obligation-register,
  offline-compute-lane, and deal-debrief notes. New reference doc `docs/LOCAL_CONTEXT.md`. All
  non-advisory (verbatim RESEARCH NOTES header, human_review_required); nothing signed or sent; the
  creator's data stays on her machine. P23 is complete (Phases 1 to 3).
- P23 (Phase 2): contract drafting + version tracking. Three atoms, designed and adversarially
  verified by a workflow (6 agents; all returned pass_with_fixes with zero boundary/binding-language/
  fabrication/dash issues; the small required fixes were applied before writing): `contract-draft`
  (assembles a plain-language, not-vetted, not-binding starting point from the playbook standards +
  the deal's agreed terms via a tagged source precedence deal_agreed > playbook_standard >
  generic_default > MISSING; nulls unknowns; never operative legalese; ready_to_sign false),
  `amendment-trace` (net current state across contract versions using the difference labels and
  source precedence already in `shared/contract-engine.md`; quotes exactly, flags conflicts, marks
  uncertain rather than forcing a match), and `playbook-bootstrap` (proposal-only: bootstrap a
  starting playbook from example contracts, or nudge an off-standard default from recent deals; never
  writes the playbook, the human confirms). Engine gains "Plain-language draft assembly" and
  "Bootstrapping and nudging the playbook" sections. contract-desk workflow rewired (triage, review,
  amendment-trace, legal-requirement-check, escalation-brief, contract-draft, govern-artifact; new
  actions trace/draft/playbook_setup; playbook-bootstrap as a shortcut). Flags contract_drafting and
  contract_redline now ship their atoms (degraded_behavior updated); playbook_bootstrap_disabled added.
  All non-advisory: verbatim RESEARCH NOTES header, human_review_required, recommend_counsel; nothing
  signed or sent. Phase 3 (obligation register + timeline) remains, flag in place and off.
- P23 (Phase 1): deal contract management. New `contract-desk` Pipeline/CRM spoke that reviews the
  contract *document* (deal-pipeline still owns the deal record and stage transitions). Canonical
  `shared/contract-engine.md` (non-advisory boundary, clause taxonomy, four-tier playbook model, dual
  severity, confidence labels, amendment net-current-state + difference labels + source precedence,
  deadline date math, curated legal sources). Contract-artifact store `pipeline/contracts/`
  (`contract.template.json` committed; real text gitignored). Creator-side clause library
  `pipeline/user-context/deal-playbook.template.json`. `pipeline/deals/deal-schema.json` reconciled to
  `shared/pipeline-engine.md` (deal_type, per-deliverable FTC, compensation, usage_rights,
  exclusivity, invoice states; account_ref and quality_verdict) plus `contract_ref` / `contract_text`.
  5 flags (contract_management master + contract_drafting, contract_redline, contract_obligations,
  legal_requirement_checks) with degraded_behavior; no new connector (intake reuses the document
  connectors). Legal sources: `canonical-sources/legal-sources-seed.json` seeded via
  `tools/source_currency.py seed-sources` (6 new FTC/reference entries; the two existing FTC entries'
  `used_by` extended to the contract atoms via a new used_by-union in the seeder). Four atoms
  (`contract-triage`, `contract-review`, `legal-requirement-check`, `escalation-brief`), all
  non-advisory with the verbatim RESEARCH NOTES header, human_review_required, confidence labels, and
  quoted evidence; reuse `usage-rights-check` and `exclusivity-check`. Hub wired (4
  request_classification values + routing rows + downstream spoke). Legal information only, never legal
  advice; nothing is signed or sent. Reference doc `docs/CONTRACTS.md`. Phases 2 (drafting,
  amendment-trace) and 3 (obligation register + timeline) remain, flags in place and off.
- P22 (Phase 2): captions + chapters. Feature 2 (caption round-trip) via `tools/videoedit/captions.py`
  (SRT/VTT reuse `shared/docintel/transcripts.py`; iTT added; CEA-608 deferred) + the `caption-bridge`
  atom. Feature 8 (chapter fan-out) via `tools/videoedit/chapters.py` (geo-optimize outline +
  paste-ready YouTube timestamps + scheduling metadata; YouTube Key Moments rules validate-and-flag) +
  the `chapter-map` atom. MCP tools `edit_captions` + `chapter_map`. Both atoms standalone, compose via
  the shared edit-package. Phases 3 to 4 (Resolve live lane; Shorts/Compressor/Motion/CommandPost) remain.
- P22 (Phase 1, walking skeleton): video-editing bridge. Neutral core (edit-package + FCPXML,
  `shared/videoedit-engine.md`) with a lossless script->FCPXML->parse round-trip that needs no editor
  installed. 10 new flags (2 lane + 8 feature, all default off) + `degraded_behavior`; 4 connectors
  (`fcpxml_interchange`, `resolve_api`, `compressor_cli`, `commandpost_bridge`) on the `edit_artifact`
  evidence type, mapped in `CAPABILITY_TO_CONNECTOR`. `tools/videoedit/` (preflight, otio_core, fcpxml
  build/validate/parse, resolve/compressor/commandpost gated stubs) + `tools/videoedit_validate.py`
  (gate + validation) + `tools/sync_editing.py` (sha256 bucket manifest). Atoms `edit-timeline-spec`
  and `fcpxml-parse`; MCP tools `edit_preflight`, `edit_build_fcpxml`, `edit_parse_fcpxml`,
  `import_edit_artifact`, `resolve_status`. Mirrors the `live_publishing_enabled` seam. DaVinci Resolve
  live lane (Studio-only) and features 2/3/5/6/7/8 are Phases 2 to 4.
- P21: P20 adversarial-audit remediation — 27 verified findings closed. Dashboard security
  (CSRF Origin/Content-Type guards, wildcard CORS removed, stored-XSS via data-* binding, queue
  lock + atomic writes); shared `tools/publishing_compliance.py` gate wired into the dashboard
  confirm path (refuses non-compliant posts) and reused by `schedule_post`; honest scaffold
  (scheduler advances to `ready_to_post`, no fake dispatch) with a feature-flagged-off
  `tools/publishing/` real-API seam (`live_publishing_enabled`, default off); `POST /api/import-report`
  adapter for the content-distributor handoff; four dedicated `{platform}_publish_api` connectors
  wired through `CAPABILITY_TO_CONNECTOR` (+ object-form flag reading, pinterest_api mapping);
  wizard YouTube state corrected (no false "Ready" without a token); drift-guard invariant 18
  (connector requires_capability must be mapped); docs corrected.

- P6: voice engine, source currency, and em-dash scope fix — shipped (commit b28f13e).
- P7: SEO intelligence engine, recursive source traversal, and 4 new atoms — shipped (commit 8b044f0).
- P8: platform API signal enrichment (TikTok 15 signals, YouTube Shorts 10 signals, Reels) — shipped (commit efce070).
- P9: deep competitive intelligence pipeline — offline HTML snapshots, ytInitialData extraction, SQLite index — shipped (commit 4c9bf0a).
- P10: keyword-compare atom — cross-platform keyword comparison matrix — shipped (commit 45f9493).
- P11: implementation packaging, MCP server, examples, and deployment docs — shipped.
- P12: local sync workflow — `tools/setup.py`, `tools/update.py`, `.local.json` override pattern — shipped.
- P13: macOS / Apple Silicon (M2) compatibility — shipped.
- P14: account-based connector registry and evidence routing — shipped (commit 3ae970d).
- P15: Google Workspace and Microsoft 365 integration + browser-based setup wizard — shipped.

## Shipped

### Foundation and canonical layer (P0 and P1)
- Repository skeleton at the root of `seo-tools`.
- Shared engines (`shared/`): brand, audience, platform, adaptation, web-intel, injection-guard,
  pipeline, method, transcription-engine, integrations-engine, docintel-engine.
- Shared docintel layer (`shared/docintel/`): classify.py, parse_text.py, transcripts.py, wer.py.
- Protocols (`protocols/`): quality-gates, safety, no-fabrication, research-citation,
  formatting-metadata (all provided verbatim and on disk).
- Scoop cache (`shared/cache/`): L1 SQLite FTS5, L2 semantic, L3 manifest via sync_cache.py.
- Canonical sources (`canonical-sources/`): keyword-library, platform-specs, personas,
  rate-benchmarks, seasonal-aesthetic.
- Pipeline CRM store (`pipeline/`): account-schema.json, deal-schema.json (real data gitignored).
- Tooling (`tools/`): sync_check.py (drift guard), new_skill.py, version.py, package_skill.py,
  sync_cache.py, skill-template/, sync_manifest.json.
- Packaging: .claude-plugin/plugin.json and marketplace.json; VERSION 0.1.0; versions.json; CI.
- Root files: CLAUDE.md, README.md, .gitignore, .gitattributes, .semgrepignore. Ledger initialized.

### Hub and governance (P2)
- Hub: `skills/creator-core/` SKILL.md, MAINTAINER_README.md, workflow.json.
- Governance: `skills/quality-review/` with score.py and rubric.

### Atoms layer — 52 atoms total
- **P3 original (35):** idea-generate, pillar-classify, trend-check, hook-write, title-generate,
  thumbnail-concept, keyword-cluster, search-intent, short-extract, seasonal-map, calendar-slot,
  competitor-scan, persona-map, project-snapshot, materials-list, step-sequence, safety-check,
  styling-variant, renter-alt, script-section, b-roll-note (via short-extract), repurpose-unit,
  pin-write, caption-write, hashtag-set, mediakit-section, rate-card-fill, pitch-paragraph,
  deal-stage-advance, account-health, renewal-signal, invoice-status, usage-rights-check,
  roi-metric, benchmark-compare, production-task, injection-scan, govern-artifact, gap-record,
  ingest-route.
- **P7 (+4):** topical-authority-map, long-tail-expand, entity-extract, serp-feature-check.
- **P9 (+1):** deep-competitor-scan.
- **P10 (+1):** keyword-compare.
- **P16 (+8):** hypothesis-test, regression-analysis, forecast, ab-test, data-query,
  configure-stats-tool, export-gem, export-gpt.
- **P17 (+3):** exclusivity-check, geo-optimize, minority-report.

### Spokes (P4) - 14 spokes + quality-review
- **Content lane (9):** content-strategy, project-builder, video-development, shortform-repurposing,
  seo-keywords, analytics-insights, audience-research, competitor-analysis, seasonal-trends.
- **Document lane (1):** document-studio.
- **Pipeline/CRM lane (4):** account-manager, deal-pipeline, deal-resourcing, partnership-mediakit.
- All spokes have SKILL.md + workflow.json + MAINTAINER_README.md + evals/evals.json +
  references/artifact-types.md.

### Documentation (P5 - partial)
- `docs/ARCHITECTURE.md`, `docs/ROUTING_MODEL.md`, `docs/QUALITY_MODEL.md`.

### Packaging (P5)
- `python3 tools/package_skill.py --all` packages 52/52 skills cleanly.
- `python3 tools/version.py --check` reports consistent at 0.1.0.
- `python3 tools/sync_check.py` exits 0 (all invariants hold).

### Voice and source currency (P6)
- `shared/voice-engine.md`: Alex's anti-AI pattern list, vocabulary, two-mode voice model.
- `pipeline/user-context/`: channel-context, setup-context, voice-profile, content-calendar schemas.
- `canonical-sources/source-registry.json`: 22 seed entries upgraded with citation-graph fields.
- `tools/source_currency.py`: 4-mode staleness tool (`--report`, `--check`, `--mark-checked`, `--seed-partners`).
- `canonical-sources/traversal-config.json`: per-category intervals, weekly default.
- Six content-producing atom SKILL.md files updated with voice-engine in engines_required.
- Em-dash scan narrowed to `examples/` only; formatting-metadata.md and CLAUDE.md updated.

### SEO intelligence and traversal (P7)
- `shared/seo-intelligence-engine.md`: YouTube algorithm (6 signals), Pinterest algorithm (5 signals),
  topical authority hub-and-cluster model, entity SEO rules, long-tail expansion methodology,
  SERP feature map, seasonal lead times (5 windows).
- `tools/traversal_engine.py`: 5-mode recursive citation-graph traversal with domain allowlist
  (34 domains) and authority filter; reads `traversal-config.json`.
- 4 new atoms: `topical-authority-map`, `long-tail-expand`, `entity-extract`, `serp-feature-check`
  (each with SKILL.md, MAINTAINER_README.md, evals/evals.json).
- Keyword library expanded: `youtube-algorithm-signals.json`, `entity-keywords.json`,
  `long-tail-seeds.json`, `competitor-channels.json`.
- Source registry: ~40 new depth-0 entries across 7 categories (YouTube, Google, Pinterest, TikTok,
  FTC, SEO tools, seasonal intelligence).
- `skills/seo-keywords/workflow.json`: extended to 9 steps.
- `skills/competitor-analysis/workflow.json`: entity-extract step added.

### Platform API enrichment (P8)
- `shared/seo-intelligence-engine.md`: YouTube Shorts algorithm (10 signals, 3-phase distribution,
  YPP monetization thresholds); TikTok algorithm expanded to 15 signals (rewatch as #1 signal,
  micro-community clustering, SEO-driven discovery); Instagram Reels signals (DM shares primary);
  Pinterest 2025 to 2026 signals.
- `canonical-sources/keyword-library/youtube-algorithm-signals.json`: Shorts section added.
- `canonical-sources/keyword-library/tiktok-api-registry.json`: TikTok API catalog.
- `canonical-sources/keyword-library/instagram-reels-signals.json`: Reels algorithm reference.
- `canonical-sources/keyword-library/github-seo-resources.json`: curated OSS repo list.
- Source registry: 7 TikTok API entries + Meta/Instagram entries.

### Deep competitive intelligence (P9)
- Acquisition stack ported from educator-tools-k12-public (acquire.py, fetch_resilient.py,
  rate_governor.py, fetch_cache.py, fetch_diag.py — all lightly modified for seo-tools).
- `tools/parse_competitor_meta.py`: extracts ytInitialPlayerResponse tags, TikTok SIGI_STATE
  hashtags, Pinterest OG tags, and cross-platform JSON-LD/schema types.
- `tools/competitor_snapshot.py`: 5-mode orchestrator managing fetch → parse → SQLite cycle.
- SQLite index at `pipeline/competitor-snapshots/index.local.db` (gitignored).
- `.github/workflows/ci.yml`: weekly Tuesday cron + `competitor-intel` job with artifact upload.
- `skills/atoms/deep-competitor-scan/`: enhanced atom with cached/live modes; 7 eval cases.
- `traversal-config.json`: competitor-page category (3/7 day intervals).

### Cross-platform keyword comparison (P10)
- `skills/atoms/keyword-compare/`: comparison matrix atom for 1 to 10 keywords × 4 platforms;
  seasonal relevance, optional trend momentum, cross-platform verdict (universal/platform_specific/
  niche_long_tail); 7 eval cases.
- `skills/seo-keywords/workflow.json`: keyword-compare added to shortcut_atoms.

### Implementation packaging and delivery (P11)
- `tools/mcp_server.py`: stdio MCP server (FastMCP) exposing 8 tools to Claude Desktop —
  `cache_query`, `competitor_scan`, `source_staleness`, `drift_check`, `quality_score`,
  `add_competitor`, `get_capabilities`, `get_connectors`. Each tool delegates via subprocess to
  existing Python scripts. (`get_connectors` added in P14.)
- `requirements-mcp.txt`: `mcp` package dependency.
- `creator-os-config.json`: 9-flag capability registry at repo root. All default to false; operator
  sets flags to true after completing each setup step. `get_capabilities` MCP tool overlays live
  checks (SQLite existence) on top of declared flags.
- **Claude Desktop implementation** (`implementation/claude/desktop/`): technical setup README and
  `claude_desktop_config_snippet.json` MCP block for macOS/Windows.
- **Claude Projects implementation** (`implementation/claude/project/`): non-technical README,
  `system-prompt.md` (Project Instructions paste), and 8 combined knowledge files for upload:
  - `01-creator-core.md`: hub routing (creator-core SKILL.md)
  - `02-brand-voice.md`: brand-engine + voice-engine
  - `03-platform-seo.md`: platform-engine + seo-intelligence-engine
  - `04-protocols.md`: all 5 protocols combined
  - `05-content-spokes.md`: 8 content lane spoke SKILL.md files
  - `06-document-spoke.md`: document-studio SKILL.md + knowledge-only mode note
  - `07-pipeline-spokes.md`: 4 CRM spoke SKILL.md files
  - `08-key-atoms.md`: 9 key atom SKILL.md files
- **GPT API implementation** (`implementation/gpt/api/`): 5 YAML function schemas
  (creator_core, keyword_compare, seo_keywords, competitor_analysis, video_development) + Python
  integration example README.
- **GPT Web implementation** (`implementation/gpt/web/`): ChatGPT two-box custom instructions
  text + limitations README.
- **Gemini implementation** (`implementation/gemini/`): condensed system-instruction.md for
  Gemini Gems / API + setup README.
- **Gold examples** (`examples/`): 3 cross-lane reference outputs (no em dashes):
  - `content-lane/seo-keywords-dark-moody-fall-mantel.md`
  - `document-lane/project-snapshot-chalk-paint-armoire.md`
  - `pipeline-lane/deal-pipeline-home-decor-brand.md`
- `docs/DEPLOYMENT.md`: multi-platform deployment reference — 5 options (A through E),
  first-run checklist, competitor intelligence first-run, capability matrix, feature flags.

### macOS / Apple Silicon compatibility (P13)
- `tools/acquire.py`: added `_mac_playwright_chrome()` glob helper and macOS arm64/x86_64 paths
  to `CHROME_CANDIDATES`; Linux CI paths preserved at top of list.
- `tools/setup.py`: `check_platform()` function detects macOS, prints arm64 vs Rosetta status,
  and emits Homebrew install hints and `playwright install chromium` reminder.
- `docs/SETUP_MAC.md`: standalone Mac setup guide — Option B quick start for Alex, full
  Claude Desktop + MCP walkthrough for Matt, M2-specific notes and troubleshooting table.
- `docs/DEPLOYMENT.md`: Mac note added to prerequisites (SETUP_MAC.md reference + `playwright
  install chromium` one-time command).

### Account-based connector registry and evidence routing (P14)
- `shared/connectors/connectors.json`: 12-connector registry with state-based model
  (`available/disabled/not_installed/permission_blocked/metadata_only`), evidence type
  `provides` lists, authoritative_for markers, and deployment mode profiles for all 5 options.
- `shared/connectors/connectors.md`: connector model documentation — states, evidence types,
  degradation+convergence policy, restricted-evidence pattern, deployment matrix, capability
  flag mapping table, usage instructions.
- `shared/connectors/connectors.py`: offline resolver (stdlib only) — reads registry + optional
  flag file, maps boolean `creator-os-config.json` capabilities to connector states via
  `CAPABILITY_TO_CONNECTOR`, resolves per-evidence provider chains and gaps, emits restricted
  connector notes. Modes: `--list`, `--plan`, `--json`.
- `shared/connectors/feature-flags.example.json`: sample Option A (Claude Desktop + MCP)
  deployment config demonstrating restricted-evidence pattern for youtube_data_api.
- `tools/mcp_server.py`: added `get_connectors` as 8th MCP tool — calls connectors.py `--plan
  --json` and returns the active evidence plan for the deployment.
- `creator-os-config.json`: added `_connectors_note` key and missing `pinterest_api` capability.
- `CLAUDE.md`: layout section updated with `connectors/` note; non-negotiable added for
  connector registry write isolation (connectors.json is the source of truth;
  per-deployment overrides go in gitignored `creator-os-connectors.local.json`).

### Local sync workflow (P12)
- `tools/setup.py`: one-time first-run initializer — creates 5 local data files from schemas,
  builds keyword cache, runs drift guard, prints next steps.
- `tools/update.py`: regular pull script — `git pull origin main`, drift guard, cache rebuild
  if canonical sources changed. Local data files never touched.
- `.local.json` override pattern: `creator-os-config.local.json` deep-merges over the committed
  defaults (local capability flags always win); `voice-profile.local.json` and
  `content-calendar.local.json` hold real user data, never committed.
- `tools/mcp_server.py`: `_load_config()` extended to merge `creator-os-config.local.json` over
  the committed base config.
- `shared/voice-engine.md`: updated to check `voice-profile.local.json` first, then fall back to
  committed seed vocabulary.
- `docs/DEPLOYMENT.md`: first-time setup section, regular sync section, local data table.

### Google Workspace, Microsoft 365, and guided setup wizard (P15)
- `tools/wizard.py`: browser-based guided setup wizard (~350 lines, stdlib only); serves HTML
  at `http://localhost:8765`; auto-detects OS (Mac/Windows/Linux); two paths (claude.ai vs
  Claude Desktop); Google Workspace flow (workspace-mcp via uvx, 6-step credential guide);
  Microsoft 365 flow (Softeria ms-365-mcp-server via npx, device code flow); writes
  Claude Desktop config and `creator-os-config.local.json` automatically.
- `shared/connectors/connectors.json`: 6 new connectors (gmail, google_calendar,
  google_docs_sheets, microsoft_outlook_email, microsoft_outlook_calendar,
  microsoft_excel_onedrive); 3 new evidence types (email_inbox, calendar_events,
  spreadsheet_data); deployment_modes updated for all new connectors.
- `shared/connectors/connectors.py`: `google_workspace` and `microsoft_365` added to
  `CAPABILITY_TO_CONNECTOR` map.
- `creator-os-config.json`: `google_workspace` and `microsoft_365` capability flags added.
- `implementation/claude/desktop/claude_desktop_config_snippet.json`: google-workspace and
  microsoft-365 MCP server blocks added; Linux config path added.
- `docs/WIZARD.md`: non-technical wizard reference (claude.ai path, Claude Desktop path,
  behind-the-scenes explanation).
- `docs/wizard/README.md` and `docs/wizard/screenshot-guide.md`: asset placeholder structure
  with per-screen capture guide for 9 screens and 3 GIFs.
- `docs/SETUP_MAC.md`: Step 8 replaced with wizard reference; manual JSON editing removed.
- `docs/DEPLOYMENT.md`: Option A uses wizard; Option B adds native Google Workspace connector
  instructions; capability matrix adds Google Workspace and Microsoft 365 rows.

### Statistical analysis tools, platform export, and subagent orchestration (P16)
- `shared/compute-engine.md`: canonical engine for statistical computation — tool selection matrix,
  fallback chain, output labeling rules, anti-fabrication rules for statistics.
- `creator-os-config.json`: 10 new capability flags (wolfram_alpha, e2b_sandbox, duckdb_analytics,
  stats_compass, jupyter_notebook, r_statistics, monte_carlo, scikit_learn, gemini_gem_export,
  custom_gpt_export) with degraded_behavior entries.
- `shared/connectors/connectors.json`: 8 new stats/ML connectors + 4 new evidence types
  (statistical_computation, sql_analytics, notebook_session, ml_prediction).
- `shared/connectors/connectors.py`: 8 new CAPABILITY_TO_CONNECTOR entries.
- 8 new atoms: hypothesis-test, regression-analysis, forecast, ab-test, data-query,
  configure-stats-tool, export-gem, export-gpt (each with SKILL.md, MAINTAINER_README.md,
  evals/evals.json).
- `skills/analytics-compute/`: new spoke composing statistical atoms via conditional workflow.
- `skills/creator-core/SKILL.md` and `workflow.json`: 5 new request_classification values
  (statistical_analysis, forecasting, data_query, ab_test_design, platform_export).
- `tools/mcp_server.py`: 2 new MCP tools — `get_stats_tools` (reports which stats tools are
  enabled) and `configure_tool` (toggles capability flags in .local.json). Total: 10 MCP tools.
- `implementation/claude/desktop/claude_desktop_config_snippet.json`: 5 new MCP server blocks
  (wolfram-alpha, e2b-code-interpreter, stats-compass, duckdb-analytics, jupyter-notebook).
- `.claude/agents/`: 4 agent definitions (seo-researcher, competitor-analyst, content-writer,
  deal-reviewer).
- `.claude/workflows/`: 4 workflow scripts (content-pipeline, competitor-deep-dive,
  seasonal-planning, deal-review).
- `docs/STATISTICS.md`: statistical tools reference (setup, tool matrix, atoms, output labeling).
- `docs/DEPLOYMENT.md`: capability matrix expanded with stats, ML, export, and workflow rows.

### Agent orchestration upgrade (P17)
- `shared/research-orchestration-engine.md`: canonical engine defining when and how to use
  subagents — read-only mandate, structured output schemas, recursive extraction protocol,
  connector and API access rules, information aggregation process, prompt construction patterns.
- `shared/schemas/`: 4 JSON Schema files for structured agent output — `seo-research.json`,
  `competitor-analysis.json`, `content-draft.json`, `deal-review.json`.
- `.claude/agents/`: 4 agent definitions rewritten from inert atom lists to functional system
  prompts with read-only operating rules, scoped engines/protocols, permitted data sources,
  and structured output formats.
- `.claude/workflows/`: 4 prose workflow descriptions replaced with executable JavaScript
  workflow scripts for the Claude Code Workflow tool — `content-pipeline.js`,
  `competitor-deep-dive.js`, `seasonal-planning.js`, `deal-review.js`.
- `skills/creator-core/SKILL.md`: agent dispatch section added to routing object.
- `docs/ARCHITECTURE.md`: agent orchestration section added (roles, structured output, workflows,
  information flow).
- `CLAUDE.md`: agent orchestration conventions section added.
- `docs/DEPLOYMENT.md`: agent orchestration row added to capability matrix.

### Social media scheduling and content distribution (P20)
- **New spoke:** `skills/content-distributor/` — Content lane spoke accepting finalized content
  (captions + hashtags from prior shortform-repurposing or video-development runs) and
  orchestrating the full scheduling lifecycle: connector check → caption/hashtag generation
  (if needed) → schedule-post per platform → post-status check → govern-artifact.
- **3 new atoms:**
  - `skills/atoms/schedule-post/`: queues or schedules a single post via the active publishing
    connector (direct platform API > manual fallback). FTC/AIGC compliance enforced.
    `human_review_required: true` always set. 3 eval cases.
  - `skills/atoms/publish-draft/`: formats paste-ready posting packages for manual upload —
    finalized caption with disclosure and hashtags, numbered posting checklist, media spec
    reminder, optimal posting time. Zero infrastructure required. 3 eval cases.
  - `skills/atoms/post-status/`: checks status of a previously scheduled post via the active
    connector. Maps platform-native codes to Creator OS vocabulary (published, scheduled,
    processing, failed, draft, unknown). Optional engagement snapshot. 3 eval cases.
- **Connector registry (`shared/connectors/connectors.json`):** `content_publishing` evidence type
  added. Write-side publishing is provided by four dedicated connectors
  (`youtube_publish_api`, `instagram_publish_api`, `tiktok_publish_api`, `pinterest_publish_api`),
  each gated on its `{platform}_publishing` capability flag and mapped in
  `connectors.py` CAPABILITY_TO_CONNECTOR. These are separate from the read-side connectors
  (`youtube_data_api`, etc.), which no longer provide `content_publishing` (added in the P20 audit
  remediation).
- **Feature flags (`creator-os-config.json`):** 4 new capability flags — `youtube_publishing`,
  `instagram_publishing`, `tiktok_publishing`, `pinterest_publishing` — all default to
  `enabled: false`. Degraded behavior entries added.
- **Hub routing (`skills/creator-core/SKILL.md`):** `content_distribution` added to the
  request_classification enum; routing table row maps to `content-distributor`; spoke added
  to the downstream list.
- **Integrations engine (`shared/integrations-engine.md`):** "Content Publishing Endpoints"
  section added — per-platform write-side API specs (Pinterest v5, YouTube Data API v3,
  TikTok Content Posting API, Instagram Graph API v25.0), AIGC flag rules, FTC disclosure
  requirements, and human confirmation mandate.
- **Content calendar (`pipeline/user-context/content-calendar.json`):** `posts[]` array added
  to `entry_schema` tracking per-platform post_id, status, permalink, published_at,
  publishing_tier, connector_used, ftc_disclosure, and is_aigc.
- **Distribution report schema (`shared/schemas/distribution-report.json`):** JSON Schema for
  content-distributor output — `posts[]`, `distribution_summary` (total/queued/manual/failed),
  `manual_posting_packages[]`, `next_steps[]`, plus verification envelope fields.
- **MCP server (`tools/mcp_server.py`):** 3 new tools added — `schedule_post` (dispatches to
  active connector or returns manual plan), `post_status` (checks post status), and
  `get_publishing_plan` (resolves tier per platform). Total: 13 MCP tools.
- **Workflow script (`.claude/workflows/content-distribution.js`):** 4-phase adversarially-verified
  workflow (Prepare → Distribute → Verify → Report). Uses read-only agent rules per
  research-orchestration-engine.md. Verification envelope fields in all schemas.
- **Architecture docs:** Content Distribution subsection added to `docs/ARCHITECTURE.md` —
  publishing tier table, human confirmation gate, compliance checks, atoms, MCP tools, and
  content calendar integration.
- **CLAUDE.md:** Human confirmation non-negotiable added to publishing constraints.
- **Canonical sources note:** 7 new source entries for P20 are pre-seeded via the traversal_engine
  `--accept` flow rather than direct registry edits. Run `python3 tools/traversal_engine.py
  --accept` for: pinterest-api-v5-pin-creation,
  youtube-api-upload-video, tiktok-content-posting-api-docs, instagram-content-publishing-api-docs,
  ftc-endorsement-guides-social.

## Flags and follow-ups
- `shared/pipeline-engine.md` was authored from the handoff CRM spec because the canonical file was
  not provided this session. Supersede it if the original surfaces.
- `web-intel-engine.md` carries a `used_by` list with pre-rename spoke names (deal-tracker,
  platform-optimizer, seasonal-planner). Left verbatim as provided; canonical routing lives in the
  hub. Reconcile when convenient.
- `web-intel-engine.md` references a `connector-resilience-companion`. If that companion is not
  provided separately, fold its 9 failure classes into the engines' failure handling. The canonical
  protocol set stays at 5.
- Deeper brand brief (`alex_gpt_prompt_1.docx`) and the market-analysis PDF are still wanted to
  ground rate-card-fill and benchmark-compare canonical data.

## Next
- Open PR to merge `claude/repo-access-confirm-wxe50a` → `main`.
- Fill in `pipeline/user-context/channel-context.local.json` when Alex provides channel stats.
- Fill in `pipeline/user-context/voice-profile.local.json` as real content is produced.
- Configure Claude Desktop MCP and set `mcp_server: true` in `creator-os-config.local.json`.
- End-to-end slice: drive creator-core with a Content prompt and a CRM prompt; confirm routing
  object, atom composition, quality-review verdict, and formatting compliance.
- Competitor intelligence: populate competitor-channels.json with real channel entries via
  `python3 tools/competitor_snapshot.py --add-competitor <url> --platform youtube`.
- Voice profile: fill `pipeline/user-context/voice-profile.json` with Alex's actual phrasing.
- MCP server smoke test: `echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 tools/mcp_server.py`
  (requires `pip install mcp` first via `requirements-mcp.txt`).
- Claude Projects: upload the 8 knowledge files from `implementation/claude/project/knowledge/`
  and paste `implementation/claude/project/system-prompt.md` as Project Instructions.
