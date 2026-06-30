---
file: skills/atoms/gap-record/MAINTAINER_README.md
purpose: keep gap-record the honest alternative to a silent blank or an invented value.
---

# gap-record: Maintainer README

## Purpose
Record an explicit gap object when data cannot be retrieved or a field is unknown.

## Non-negotiable invariants
- Always four fields: gap_type, description, impact, recommended_next_step.
- Never paired with an invented value; the gap replaces the guess.

## Known failure modes
- Recording a gap and then filling the field anyway.
- Burying the gap in a prose caveat.

## Regression cases to preserve
1. web-intel blocked at all levels: gap_type all_acquisition_levels_failed with a clear next step.
2. Unknown CRM field: gap_type unknown_field, the field left null.

## Update checklist
- Run python3 tools/sync_check.py.
