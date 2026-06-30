# STATE.md
Live build status for Creator OS. Update at phase boundaries and after a skill ships.

## Current phase
P3 (atoms) and P4 (spokes) are complete. P5 packaging is green. All 52 skills packaged cleanly.
Drift guard exits 0. Branch: `claude/repo-access-confirm-wxe50a`.

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
- `docs/DEPLOYMENT.md` and `implementation/` (claude/, gpt/api+web/, gemini/).
- `examples/` cross-skill gold outputs for end-to-end validation.
- End-to-end slice: drive creator-core with a Content prompt and a CRM prompt; confirm routing
  object, atom composition, quality-review verdict, and formatting compliance.
- Scoop verification: `python3 shared/cache/cache.py --build` then `--query`;
  `python3 tools/sync_cache.py --manifest --write bucket.manifest.json`.
