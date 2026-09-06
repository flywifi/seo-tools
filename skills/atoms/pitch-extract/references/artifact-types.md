---
file: skills/atoms/pitch-extract/references/artifact-types.md
role: the artifact types this skill produces and the required elements of each.
---

# pitch-extract artifact types

## Pitch extraction (the only artifact)

The structured object defined in SKILL.md's output contract: `account_skeleton` (keyed to
`pipeline/accounts/account-schema.json`), `deal_skeleton` (keyed to
`pipeline/deals/deal-schema.json`, `stage: identified` with `origin: inbound_pitch` in
`stage_history`), `citation` (Message-ID + permalink or `manual_ref`), `extraction_gaps[]`,
`injection_flags[]`, `human_review_required: true`.

Required elements:
- The verbatim first-line disclaimer.
- A citation with at least one non-null field; `manual_ref` only as a labeled fallback.
- `compensation_offered` verbatim or null with a named gap.
- Every absent field named in `extraction_gaps[]`; nothing silently blank.

Quality-gate dimensions that most apply: no-fabrication (verbatim quotes, null-and-flag),
integrity (citation binds to the real envelope), safety (injection containment, no side effects).
