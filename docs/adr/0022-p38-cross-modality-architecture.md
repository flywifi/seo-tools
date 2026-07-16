# 22. P38 Cross Modality Architecture

- Date: 2026-07-07
- Status: Accepted

## Context

P38-6/7: the ecosystem targets Claude Desktop/Code, claude.ai, Custom GPT, Gemini, and no-AI users; the ArcGIS/FEMA/Census endpoints do point-in-polygon server-side, so the universal path (call the public endpoint) reaches every surface except consumer Gemini Gems. Skills must know their class + mechanism so users can set them up per surface rather than hit a gap at use time.

## Decision

Made every skill declare where/how it runs outside Claude, and packaged the jurisdiction overlay for non-Claude surfaces. shared/cross-modality-engine.md defines the model: three capability classes (A pure-reasoning, B offloadable to a public/hosted endpoint, C local-runtime), a per-surface matrix, a packaging map, and a degrade-never-fail fallback ladder. All 23 spokes carry a ## Cross-modality declaration; jurisdiction gets a GPT Action OpenAPI schema, Gemini function declarations, and docs/CROSS-MODALITY.md (access matrix). The setup wizard gained a /cross-modality screen that prints per-surface wiring steps and what runs there. Two new drift invariants: 28 (spokes declare cross-modality) and 29 (implementation/ schemas parse, which would have caught the GPT Action YAML typo).

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P38-cross-modality-architecture`.
