# export-gem — Maintainer Reference

## What this atom does

Packages Creator OS engines, protocols, and spoke instructions into a Google Gemini Gem. Selects
up to 10 knowledge files (Gem platform limit), generates a system instruction designed for
Gemini's approximately 82% instruction adherence rate, and outputs a manifest with paths and sizes.
Loads `shared/brand-engine.md` and `shared/voice-engine.md` to preserve brand fidelity.

## Invariants

1. `total_files` never exceeds 10. If the ranked file list has more than 10 entries, files are
   merged or excluded — never silently dropped.
2. `shared/brand-engine.md` and `shared/voice-engine.md` are always included as standalone files
   (not merged into a combined file). These are non-negotiable for brand fidelity.
3. The system instruction repeats the 3 to 5 most critical rules at the end ("reminder block")
   to compensate for Gemini's instruction adherence gap.

## Failure modes

1. **More than 10 high-priority files.** The atom merges protocols and secondary engines into
   combined files. If still over 10, it excludes the lowest-ranked files and notes them in
   `warnings`.
2. **Requested spoke does not exist.** Noted in `warnings`. The atom does not fabricate a
   SKILL.md for a non-existent spoke.
3. **Large file (> 100KB).** Noted in `warnings` as a retrieval quality risk. The file is still
   included unless the 10-file limit forces exclusion.

## Regression cases (map to evals/evals.json)

| # | Case | Eval ID |
|---|---|---|
| 1 | Full export — all spokes, under 10 files | eg-001 |
| 2 | Focused export — 2 spokes, brand and voice always present | eg-002 |
| 3 | Non-existent spoke requested — warning emitted | eg-003 |

## Update checklist

1. If Gemini Gem platform limits change (file count, size), update Step 2 and invariants.
2. If `shared/brand-engine.md` or `shared/voice-engine.md` structure changes, update Step 3
   system instruction generation.
3. If new engines are added to `shared/`, update the priority ranking in Step 1.
4. Re-run all evals after any change.
5. Run `python3 tools/sync_check.py`.
