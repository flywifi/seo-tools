# Creator OS

A hub-and-spoke ecosystem of Claude Agent Skills that acts as an all-in-one strategic partner for
YouTube and social media creators. It covers content strategy, video and short-form production, SEO,
project planning, brand partnerships, channel analytics, and social media scheduling.

## How it works
A routing hub (`creator-core`) classifies every request into one of three lanes, loads only the
engines that lane needs, enforces the protocols, and dispatches to a capability spoke. Spokes are
thin orchestrators that compose single-operation atoms.

The 22 spokes, by lane:

- Content lane (14): content-strategy, project-builder, video-development, shortform-repurposing,
  seo-keywords, analytics-insights, analytics-compute, audience-research, competitor-analysis,
  seasonal-trends, content-distributor, content-library, construction-desk, jurisdiction-desk.
- Document lane (1): document-studio.
- Pipeline/CRM lane (7): account-manager, deal-pipeline, deal-resourcing, partnership-mediakit,
  contract-desk, finance-desk, task-desk.
- Governance: quality-review applies the nine-dimension Quality Gates with a deterministic scorer.
  It is the governance skill, not a spoke, so it is not part of the 22.

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

## Setting it up
- On a Mac, start with `docs/SETUP_MAC.md`; the guided setup wizard is documented in
  `docs/WIZARD.md`. Run `python3 tools/setup.py --install-deps` first: it builds the private
  `.venv` the wizard expects.
- Deploying to Claude Desktop, ChatGPT, or Gemini: `docs/DEPLOYMENT.md`.
- After cloning, run `python3 tools/install_hooks.py` once. It installs the pre-commit secret scan
  and the commit-message check; CI backstops clones that skip it, but the hooks catch problems
  before they are committed rather than after.

## Validation
The full battery. Every one of these must be clean before a commit; CI runs the same guards.

```bash
python3 tools/sync_check.py          # drift guard, the keystone
python3 tools/scenario_check.py      # end-to-end routing scenarios
python3 tools/selftest_sweep.py      # every tool's own selftest
python3 tools/doc_freshness.py --check
python3 tools/count_truth.py         # canonical counts; never restate a count by hand
python3 tools/version.py --check     # version consistency
python3 tools/preflight_push.py
```

`python3 tools/package_skill.py --all` is a **build** step, not validation: it writes `dist/`.
Run it when you need packaged artifacts, not to check the tree.
