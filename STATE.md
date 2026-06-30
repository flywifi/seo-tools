# STATE.md
Live build status for Creator OS. Update at phase boundaries and after a skill ships.

## Current phase
P6 through P11 are complete. Drift guard exits 0. Branch: `claude/repo-access-confirm-wxe50a`.

- P6: voice engine, source currency, and em-dash scope fix — shipped (commit b28f13e).
- P7: SEO intelligence engine, recursive source traversal, and 4 new atoms — shipped (commit 8b044f0).
- P8: platform API signal enrichment (TikTok 15 signals, YouTube Shorts 10 signals, Reels) — shipped (commit efce070).
- P9: deep competitive intelligence pipeline — offline HTML snapshots, ytInitialData extraction, SQLite index — shipped (commit 4c9bf0a).
- P10: keyword-compare atom — cross-platform keyword comparison matrix — shipped (commit 45f9493).
- P11: implementation packaging, MCP server, examples, and deployment docs — shipped.

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

### Atoms layer (P3) - 35 atoms
- idea-generate, pillar-classify, trend-check, hook-write, title-generate, thumbnail-concept,
  keyword-cluster, search-intent, short-extract, seasonal-map, calendar-slot, competitor-scan,
  persona-map, project-snapshot, materials-list, step-sequence, safety-check (DIY boundary),
  styling-variant, renter-alt, script-section, b-roll-note (via short-extract), repurpose-unit,
  pin-write, caption-write, hashtag-set, mediakit-section, rate-card-fill, pitch-paragraph,
  deal-stage-advance, account-health, renewal-signal, invoice-status, usage-rights-check,
  roi-metric, benchmark-compare, production-task, injection-scan (govern-artifact + gap-record +
  ingest-route as cross-cutting atoms).

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
- `tools/mcp_server.py`: stdio MCP server (FastMCP) exposing 7 tools to Claude Desktop —
  `cache_query`, `competitor_scan`, `source_staleness`, `drift_check`, `quality_score`,
  `add_competitor`, `get_capabilities`. Each tool delegates via subprocess to existing Python scripts.
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
- End-to-end slice: drive creator-core with a Content prompt and a CRM prompt; confirm routing
  object, atom composition, quality-review verdict, and formatting compliance.
- Scoop verification: `python3 shared/cache/cache.py --build` then `--query`;
  `python3 tools/sync_cache.py --manifest --write bucket.manifest.json`.
- Competitor intelligence: populate competitor-channels.json with real channel entries via
  `python3 tools/competitor_snapshot.py --add-competitor <url> --platform youtube`.
- Voice profile: fill `pipeline/user-context/voice-profile.json` with Alex's actual phrasing.
- MCP server smoke test: `echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 tools/mcp_server.py`
  (requires `pip install mcp` first via `requirements-mcp.txt`).
- Claude Projects: upload the 8 knowledge files from `implementation/claude/project/knowledge/`
  and paste `implementation/claude/project/system-prompt.md` as Project Instructions.
