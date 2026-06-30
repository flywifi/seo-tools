# MAINTAINER — __ATOM_NAME__

## Purpose
`SKILL.md` is the runtime contract; this file preserves non-negotiable behavior for `__ATOM_NAME__`.

## Non-negotiable invariants
- Never fabricate data — all results from verified sources only.
- `human_review_required: true` on any compliance-facing output.
- References `skills/shared/minority-report.md` policy.

Atom-specific:
- <bullets unique to this atom>

## Known failure modes
- <list failure modes>

## Regression cases to preserve
1. <case>

## Approval-gated changes
- Changing the input or output schema.

## Minority-report policy
See `skills/shared/minority-report.md`.

## Update checklist
- [ ] SKILL.md "Do NOT use for…" clause intact
- [ ] `python3 tools/sync_check.py` passes
- [ ] evals/evals.json has ≥3 cases
