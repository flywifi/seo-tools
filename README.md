# Creator OS

A hub-and-spoke ecosystem of Claude Agent Skills that acts as an all-in-one strategic partner for a
YouTube creator in the moody-vintage home decor and DIY niche. It covers content strategy, video and
short-form production, SEO, DIY project planning, brand partnerships, and channel analytics.

## How it works
A routing hub (`creator-core`) classifies every request into one of three lanes, loads only the
engines that lane needs, enforces the protocols, and dispatches to a capability spoke. Spokes are
thin orchestrators that compose single-operation atoms.

- Content lane: content-strategy, project-builder, video-development, shortform-repurposing,
  seo-keywords, analytics-insights, audience-research, competitor-analysis, seasonal-trends.
- Document lane: document-studio.
- Pipeline/CRM lane: account-manager, deal-pipeline, deal-resourcing, partnership-mediakit.
- Governance: quality-review applies the nine-dimension Quality Gates with a deterministic scorer.

## The shared core
- Engines (`shared/`): brand, audience, platform, adaptation, pipeline, web-intel, injection-guard,
  and the unified `method` pipeline.
- Protocols (`protocols/`): quality-gates, safety, no-fabrication, research-citation,
  formatting-metadata.
- Scoop cache (`shared/cache/`): a local-first, offline, zero-token retrieval tier over the canonical
  reference data, with a portable hash-verified bucket manifest for distribution.

## Layout
See `CLAUDE.md` for working conventions and `docs/ARCHITECTURE.md` for the design. Live build status
is in `STATE.md`.

## Validation
```bash
python3 tools/sync_check.py        # drift guard
python3 tools/version.py --check   # version consistency
python3 tools/package_skill.py --all
```
