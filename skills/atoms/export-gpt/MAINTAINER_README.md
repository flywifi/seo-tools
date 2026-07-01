---
file: skills/atoms/export-gpt/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for export-gpt so it stays stable under iteration.
---

# export-gpt: Maintainer README

## Purpose

The export-gpt atom packages a selected subset of Creator OS engines, protocols, and skill
instructions into a Custom GPT configuration for the OpenAI ChatGPT platform. It produces a
GPT instruction document (under 8,000 characters), a knowledge file manifest, and a GPT
metadata summary (name, description, conversation starters). Its job ends at package
generation — it does not upload to OpenAI or manage GPT deployment. It does not package for
Gemini (use export-gem) or for Claude (use the native skill installation).

## Non-negotiable invariants

1. References the pipeline (`shared/method.md`); self-checks against `protocols/quality-gates.md`;
   obeys `protocols/no-fabrication.md` and `protocols/formatting-metadata.md`.
2. Instruction text must be under 8,000 characters (Custom GPT platform limit).
3. Knowledge files should be consolidated — GPT supports fewer granular files than Gem.
4. `brand-engine.md` content must be embedded in the instruction text or included as a
   knowledge file; brand identity must never be absent from the export.
5. No real CRM data or PII in the exported package — `pipeline/` data is never bundled.
6. Conversation starters (3 to 5) must be generated and must reference the creator's niche
   topics (moody-vintage home decor, DIY), never real deal names or PII.
7. `protocols/formatting-metadata.md` rules apply to the instruction text.

## Known failure modes

1. Instruction text exceeding 8,000 characters and being silently truncated by the platform.
2. Including `pipeline/` data (real CRM records or deal details) in the export bundle.
3. Generating conversation starters that reference real brand deals or PII.
4. Omitting brand identity from the instruction text entirely.
5. Producing instruction text that conflicts with `protocols/formatting-metadata.md` rules
   (e.g., em dashes in user-facing output sections).

## Regression cases to preserve

1. A basic export produces instruction text under 8,000 characters with 3 to 5 conversation
   starters and a valid metadata summary. (eval: `export-gpt-basic`)
2. Instruction text at 8,500 characters triggers a `char_limit_exceeded` warning and suggests
   sections to cut or consolidate. (eval: `export-gpt-char-limit`)
3. An export request that references deal or account data never includes `pipeline/` content
   in the output bundle. (eval: `export-gpt-no-pii`)
4. Conversation starters reference the creator's niche topics (moody-vintage decor, DIY
   projects, seasonal styling) and never include real deal names or brand partner
   identifiers. (eval: `export-gpt-conversation-starters`)

## Update checklist

1. Make the change in the atom source files.
2. Verify that brand identity is embedded in the instruction or included as a knowledge file.
3. Confirm instruction character count validation fires at 8,000 characters.
4. Confirm conversation starters are generated in the 3 to 5 range.
5. Run all evals: review `evals/evals.json` for passing results.
6. Check that no `pipeline/` paths or real brand names appear in any generated output.
7. Update `SKILL.md` if the atom's scope or interface changed.
8. Run `python3 tools/sync_check.py` — must exit 0.
