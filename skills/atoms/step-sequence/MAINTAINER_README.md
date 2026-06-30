---
file: skills/atoms/step-sequence/MAINTAINER_README.md
purpose: keep step-sequence safety-flagged at licensed trade boundaries and honest about licensed_trade_required.
---

# step-sequence: Maintainer README

## Purpose
Write the numbered step-by-step process for a DIY project. Any step requiring a licensed trade is flagged with licensed_trade_required: true and a hard boundary note.

## Non-negotiable invariants
- Per protocols/safety.md: any electrical, gas, structural, or load-bearing step must have licensed_trade_required: true and include the note "licensed professional required; this step is out of scope for DIY."
- broll_tag is present on every step (even if just "close-up of hands working").
- warnings list appears at the top level of the output, not buried in step notes.

## Known failure modes
- Missing the licensed_trade_required flag on an electrical wiring step.
- Omitting broll_tag for simple steps.
- Providing a workaround for a licensed trade step instead of a hard boundary note.

## Regression cases to preserve
1. Electrical outlet step: licensed_trade_required: true; no DIY workaround suggested.
2. Simple painting step: safety_note is null (no risk); broll_tag is "close-up of brush strokes on wall."

## Update checklist
- Run python3 tools/sync_check.py.
