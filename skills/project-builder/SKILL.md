---
file: skills/project-builder/SKILL.md
name: project-builder
description: "builds a complete DIY home decor project brief: snapshot, materials list, step sequence, styling variants, and renter alternatives; does NOT generate hooks, titles, scripts, or SEO strategy."
load: always
---

# project-builder

## Purpose

project-builder is the Content lane spoke responsible for turning a topic or working title into a
fully structured DIY home decor project brief. It composes six atoms in sequence, assembling a
snapshot, materials list, step sequence, styling variants, and renter alternatives into a single
`project_brief` object. It applies the safety protocol to flag any steps that cross into licensed
trades (electrical, plumbing, structural), ensuring the creator never publishes guidance that requires
a permit or a licensed contractor.

## Inputs

| Field | Type | Required | Notes |
|---|---|---|---|
| topic or working_title | string | yes | The project idea or draft title to build from |
| pillar | enum | yes | One of the 5 brand pillars defined in shared/brand-engine.md |
| persona | string | no | Target audience persona; defaults to primary persona from audience-engine if omitted |
| renter_friendly | boolean | no | When true, renter-alt atom runs on every eligible step |
| budget_tier | enum | no | One of: low, mid, high; informs materials-list atom |

## Primary outputs

The spoke returns a single `project_brief` object with the following fields:

- **snapshot** -- summary card produced by the project-snapshot atom (title, pillar, estimated time, difficulty, budget range)
- **materials** -- structured materials list produced by the materials-list atom (item, quantity, estimated cost, sourcing note)
- **steps** -- ordered step sequence produced by the step-sequence atom; each step carries a licensed-trade flag if the safety protocol triggers
- **variants** -- 2 to 3 styling variant objects produced by the styling-variant atom (aesthetic angle, swap list, mood note)
- **renter_alts** -- per-step renter alternative produced by the renter-alt atom; present only on steps where a renter-safe substitution exists
- **quality_gate_result** -- pass/fail/flag record produced by govern-artifact; a failed gate blocks delivery and surfaces the reason

## Atoms composed

Atoms are called in the order listed. govern-artifact always runs last.

1. project-snapshot
2. materials-list
3. step-sequence
4. styling-variant
5. renter-alt (conditional on renter_friendly flag or per-step eligibility)
6. govern-artifact

## Engines required

- shared/brand-engine.md -- enforces pillar alignment, aesthetic voice, and brand rules across all atom outputs
- shared/adaptation-engine.md -- applies persona and platform context to tone, vocabulary, and complexity level

## References

- protocols/safety.md -- DIY boundary rules and licensed trade flag logic; any step that touches electrical, plumbing, or structural work must be flagged and scoped down or removed
- protocols/quality-gates.md -- authoritative pass/fail criteria; govern-artifact enforces these gates before the brief is returned
- protocols/no-fabrication.md -- materials, costs, brand names, and sourcing notes must be real or explicitly marked as placeholder; no invented data
- shared/adaptation-engine.md -- see Engines required
- shared/brand-engine.md -- see Engines required

## Do NOT use for

- Generating hooks, titles, or video scripts -- use the video-development spoke
- SEO keyword strategy, search clustering, or metadata optimization -- use the seo-keywords spoke
- Brand deal tracking, rate negotiation, or sponsorship outreach -- use the deal-pipeline spoke
- Any workflow that requires live trend data or real-time search signals without first running trend-check -- project-builder does not call external data sources

## Cross-modality
Class: A.
Runs on: every surface, including a consumer Gemini Gem (knowledge-only). No tool required.
Mechanism: Reasoning over shared/method.md, shared/brand-engine.md, and shared/adaptation-engine.md to compose six atoms (project-snapshot, materials-list, step-sequence, styling-variant, renter-alt, govern-artifact) into a project_brief; no tool of its own — for residential-construction builds, steps 2 to 3 defer construction facts to construction-lookup/code-lookup (Class B scoop-cache lookups) and math to build-calc (Class C, tools/build_calc.py).
Fallback: Runs everywhere as knowledge-only; on surfaces without the construction-desk atoms it null-flags construction dimensions, code citations, and quantities (never estimates them) and delivers the brief with those fields marked "verify locally".
See `shared/cross-modality-engine.md`.
