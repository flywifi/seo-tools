---
file: skills/atoms/export-gem/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for export-gem so it stays stable under iteration.
---

# export-gem: Maintainer README

## Purpose

The export-gem atom packages a selected subset of Creator OS engines, protocols, and skill
instructions into a Gemini Gem configuration bundle. It produces a system instruction document,
a knowledge file manifest (maximum 10 files), and a Gem metadata summary. Its job ends at
package generation — it does not upload to Google AI Studio or manage Gem deployment. It does
not package for GPT (use export-gpt) or for Claude (use the native skill installation).

## Non-negotiable invariants

1. References the pipeline (`shared/method.md`); self-checks against `protocols/quality-gates.md`;
   obeys `protocols/no-fabrication.md` and `protocols/formatting-metadata.md`.
2. Knowledge file count must not exceed 10 (Gemini Gem platform limit).
3. System instruction text must be under 32,000 characters.
4. `brand-engine.md` must always be included in the knowledge file manifest.
5. No real CRM data or PII in the exported package — `pipeline/` data is never bundled.
6. `protocols/formatting-metadata.md` rules apply to the system instruction text.
7. File sizes must be validated against Gemini's per-file limit before inclusion.

## Known failure modes

1. Exceeding 10 knowledge files without surfacing a warning to the caller.
2. System instruction exceeding 32,000 characters and being silently truncated.
3. Including `pipeline/` data (real CRM records or deal details) in the export bundle.
4. Omitting `brand-engine.md` from the knowledge file manifest, stripping brand identity.
5. Including gitignored `.local.json` configuration files in the export.

## Regression cases to preserve

1. A basic export with 5 engines and 2 protocols produces a valid manifest under 10 files and
   a system instruction under 32,000 characters. (eval: `export-gem-basic`)
2. A request that would require 12 knowledge files triggers a `limit_exceeded` warning and
   suggests a prioritized subset. (eval: `export-gem-file-limit`)
3. A system instruction at 31,500 characters passes validation; the same content padded to
   33,000 characters triggers a `char_limit_exceeded` warning. (eval: `export-gem-char-limit`)
4. An export request that references deal or account data never includes `pipeline/` content
   in the output bundle. (eval: `export-gem-no-pii`)

## Update checklist

1. Make the change in the atom source files.
2. Verify that `brand-engine.md` inclusion logic is intact.
3. Confirm knowledge file count validation fires at the 10-file boundary.
4. Confirm system instruction character count validation fires at 32,000 characters.
5. Run all evals: review `evals/evals.json` for passing results.
6. Check that no `pipeline/` paths appear in any generated output.
7. Update `SKILL.md` if the atom's scope or interface changed.
8. Run `python3 tools/sync_check.py` — must exit 0.
