# CLAUDE.md
Conventions for working in the Creator OS repository (the `seo-tools` repo).

## What this repo is
Creator OS is a hub-and-spoke ecosystem of Claude Agent Skills for YouTube and social media
creators. A routing hub (`creator-core`) classifies each
request into one of three lanes (Content, Document, Pipeline/CRM), loads only the engines that lane
needs, enforces the protocols, and dispatches to a capability spoke. Spokes are thin orchestrators
that compose single-operation atoms. Read `docs/ARCHITECTURE.md` for the design. Live status:
`STATE.md`.

## Layout
- `shared/` flat engines (source of truth): `brand-engine.md`, `audience-engine.md`,
  `platform-engine.md`, `adaptation-engine.md`, `pipeline-engine.md`, `web-intel-engine.md`,
  `injection-guard-engine.md`, `method.md`, plus `cache/` (the scoop tier) and
  `connectors/` (the connector registry and evidence-routing model).
- `protocols/` the five governance protocols. `quality-gates.md` is authoritative.
- `pipeline/` the CRM records store (`accounts/`, `deals/`). Source of truth for all CRM facts. Real
  data is gitignored; only schemas and blank structures are committed.
- `skills/` flat. The hub `creator-core/`, the governance skill `quality-review/`, the 14 spokes, and
  `atoms/` (single-operation sub-skills).
- `canonical-sources/` reference data the scoop cache indexes (keyword library, platform specs,
  personas, rate benchmarks, seasonal aesthetic).
- `tools/` `sync_check.py` (drift guard), `new_skill.py` (scaffolder), `version.py`,
  `package_skill.py`, `sync_cache.py` (scoop L3), `skill-template/`, `sync_manifest.json`.
  `tools/dashboard/` is the Scheduling Dashboard (`python3 tools/dashboard/server.py`, port 8766).
  `tools/wizard.py` is the setup wizard (port 8765), including `/publishing-setup` for platform
  API credential configuration.
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

## Agent orchestration
- Subagents are **read-only research tools**. They read files, query MCP tools, search the web,
  and return structured findings. They never create, edit, write, or delete files. They never
  commit or push. The main loop aggregates findings and proposes changes to the user.
- Every agent prompt must include the read-only operating rules block from
  `shared/research-orchestration-engine.md`.
- Agent output must use a JSON Schema (passed via the `schema` option on `agent()` in workflows,
  or via structured output conventions in ad-hoc Agent tool calls). Prose-only agent returns are
  not acceptable for multi-agent pipelines.
- Spawn agents only when the task spans 3+ sources, requires multi-platform comparison, deep
  competitor analysis, or citation chain traversal. Single-source lookups do not warrant an agent.
- Agent definitions live in `.claude/agents/`. Workflow scripts live in `.claude/workflows/`.
  Structured output schemas live in `shared/schemas/`.
- The four agent roles are: `seo-researcher`, `competitor-analyst`, `content-writer`,
  `deal-reviewer`. Each has a scoped tool list and engine set defined in its agent definition file.
- Every agent output must include `minority_report`, `confidence_evidence`, and `source_citations`
  fields (the verification envelope defined in `shared/schemas/verification-envelope.json`).
- Every workflow includes an adversarial verification step — a second agent that independently
  challenges the primary agent's claims before the main loop aggregates findings.
- Agent definitions must include explicit `## Forbidden tools (machine-enforced)` and
  `## Allowed tools (explicit allowlist)` sections. See `shared/research-orchestration-engine.md`
  Section 2.1 for the contract specification.
- `tools/validate_agent_output.py` is the offline fabrication detection tool. It checks source
  citations against the registry, validates confidence-tier alignment, and flags unsourced numbers.
- Drift guard invariants 14 to 17 structurally enforce agent contracts: agent definition sections
  (14), schema verification fields (15), workflow verification steps (16), and the read-only
  mandate marker (17).

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
- `tools/traversal_engine.py` is the only tool that writes to `traversal-candidates.json` and
  `traversal-visited.json`. Do not populate the registry by directly editing source-registry.json;
  use `--accept` in traversal_engine.py which calls source_currency.py for the registry write.
- `shared/connectors/connectors.json` is the source of truth for the connector registry. The
  resolver (`shared/connectors/connectors.py`) reads both this file and `creator-os-config.local.json`
  to produce the active evidence plan. Per-deployment overrides go in `creator-os-connectors.local.json`
  (gitignored); do not edit `connectors.json` for deployment-specific state changes.
- **Human confirmation required before every post.** `schedule-post` always sets
  `human_review_required: true`. No connector call is made, and no post is queued or published,
  without an explicit human confirmation step. Agents never post directly — they produce
  confirmation summaries for human review only.

## Commit messages
Describe the change and reference the affected engine, protocol, or skill. Update `STATE.md` at phase
boundaries and after a skill ships.
