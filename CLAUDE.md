# CLAUDE.md
Conventions for working in the Creator OS repository (the `seo-tools` repo).

## What this repo is
Creator OS is a hub-and-spoke ecosystem of Claude Agent Skills for the creator, a YouTube
creator in the moody-vintage home decor and DIY niche. A routing hub (`creator-core`) classifies each
request into one of three lanes (Content, Document, Pipeline/CRM), loads only the engines that lane
needs, enforces the protocols, and dispatches to a capability spoke. Spokes are thin orchestrators
that compose single-operation atoms. Read `docs/ARCHITECTURE.md` for the design. Live status:
`STATE.md`.

## Layout
- `shared/` flat engines (source of truth): `brand-engine.md`, `audience-engine.md`,
  `platform-engine.md`, `adaptation-engine.md`, `pipeline-engine.md`, `web-intel-engine.md`,
  `injection-guard-engine.md`, `method.md`, plus `cache/` (the scoop tier).
- `protocols/` the five governance protocols. `quality-gates.md` is authoritative.
- `pipeline/` the CRM records store (`accounts/`, `deals/`). Source of truth for all CRM facts. Real
  data is gitignored; only schemas and blank structures are committed.
- `skills/` flat. The hub `creator-core/`, the governance skill `quality-review/`, the 14 spokes, and
  `atoms/` (single-operation sub-skills).
- `canonical-sources/` reference data the scoop cache indexes (keyword library, platform specs,
  personas, rate benchmarks, seasonal aesthetic).
- `tools/` `sync_check.py` (drift guard), `new_skill.py` (scaffolder), `version.py`,
  `package_skill.py`, `sync_cache.py` (scoop L3), `skill-template/`, `sync_manifest.json`.
- `implementation/` platform packaging (claude, gpt, gemini). `docs/`, `ledger/`, `examples/`.

## Branching and git
- Develop on the feature branch (currently `claude/repo-access-confirm-wxe50a`). Never push to `main`.
- Push with `git push -u origin <branch>`; retry network failures with backoff.
- Do not open a PR unless explicitly asked.

## How skills reference shared files
Skills reference canonical engines and protocols by repo-root path directly (for example,
`shared/brand-engine.md`, `protocols/quality-gates.md`). There are no per-skill byte-identical copies.
Edit the canonical file in `shared/` or `protocols/`; the drift guard validates that every reference
resolves.

## Adding a skill
```bash
python3 tools/new_skill.py <spoke-name>          # a spoke under skills/<name>/
python3 tools/new_skill.py --atom <atom-name>    # an atom under skills/atoms/<name>/
python3 tools/sync_check.py                       # must pass
```
Then edit `SKILL.md` (specific, pushy, scoped description with a "Do NOT use for" clause) and
`MAINTAINER_README.md`. Spokes carry a `workflow.json` that composes atoms.

## Non-negotiables (enforced by the drift guard / Quality Gates)
- No em dashes in user-facing output (scripts, captions, pitch copy, media kit sections, pin titles).
  Internal docs (SKILL.md, engine files, protocol files, architecture docs) may use em dashes freely.
  The drift guard enforces this for `examples/` only. See `protocols/formatting-metadata.md`.
- Write ranges with "to" everywhere, including internal docs (`protocols/formatting-metadata.md`).
- Never fabricate data, metrics, rates, brands, or sources (`protocols/no-fabrication.md`). Null and
  flag instead.
- No real CRM data or PII committed to the repo. The `pipeline/` store keeps real data gitignored.
- Nothing is released until it passes the Quality Gates (`protocols/quality-gates.md`).
- Every spoke in the hub's downstream list exists; every atom a workflow names is installed.
- `tools/source_currency.py` is the only tool that writes to `canonical-sources/source-registry.json`.
  Do not edit source-registry.json by hand.

## Commit messages
Describe the change and reference the affected engine, protocol, or skill. Update `STATE.md` at phase
boundaries and after a skill ships.
