# export-gpt — Maintainer Reference

## What this atom does

Packages Creator OS engines, protocols, and spoke instructions for an OpenAI Custom GPT. Compresses
the system into an 8K-character instruction, selects knowledge files (up to 20), and optionally
generates an Actions schema (OpenAPI YAML). Loads `shared/brand-engine.md` and `shared/voice-engine.md`
to preserve brand fidelity through compression.

## Invariants

1. `instruction_chars` never exceeds 8000. If the raw instruction is too long, lower-priority
   content is moved to knowledge files — never silently truncated.
2. The instruction always includes the brand identity block, no-fabrication rule, and top anti-AI
   patterns. These are non-negotiable and are never moved to knowledge files.
3. `actions_schema_path` is null when `include_actions` is false. When true, the schema contains
   only real, documented API endpoints — never fabricated ones.

## Failure modes

1. **Instruction exceeds 8K.** The atom progressively compresses: move spoke instructions to
   knowledge files, reduce anti-AI patterns to top 5, shorten voice mode rules. Each compression
   is noted in `warnings`.
2. **Requested spoke does not exist.** Noted in `warnings`. The atom does not fabricate a
   SKILL.md.
3. **Actions schema for APIs needing auth.** The atom generates the schema but notes in `warnings`
   that the user must configure authentication in GPT Builder.

## Regression cases (map to evals/evals.json)

| # | Case | Eval ID |
|---|---|---|
| 1 | Full export — instruction within 8K, knowledge files listed | gpt-001 |
| 2 | Focused export with actions schema | gpt-002 |
| 3 | Non-existent spoke requested — warning emitted | gpt-003 |

## Update checklist

1. If OpenAI Custom GPT instruction limit changes, update Step 2 and the 8000-character cap.
2. If `shared/voice-engine.md` anti-AI pattern list changes, update compression priorities in
   Step 2.
3. If new external APIs are added to spokes, update Step 4 Actions schema generation.
4. Re-run all evals after any change.
5. Run `python3 tools/sync_check.py`.
