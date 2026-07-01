# STATE.md
Live build status for Creator OS. Update at phase boundaries and after a skill ships.

## Current phase
P6 through P20 are complete. Drift guard exits 0. Branch: `claude/repo-access-confirm-wxe50a`.

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
  added; `youtube_publishing`, `instagram_publishing`, `tiktok_publishing`, `pinterest_publishing`
  direct API connectors added with `content_publishing` in their provides arrays.
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
