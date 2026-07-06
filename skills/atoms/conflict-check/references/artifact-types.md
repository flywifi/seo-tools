---
file: skills/atoms/conflict-check/references/artifact-types.md
role: the artifact types this skill produces and the required elements of each.
---

# conflict-check artifact types

## Precedence decision (advisory)
The single artifact conflict-check produces.

Required elements:
- The verbatim advisory boundary line as the first line of output.
- The two overlays under comparison (ids), each with its `jurisdiction_level`, `preemption_type`
  (floor / ceiling / field / none), `local_authority`, and `specificity_scope`.
- Either the governing overlay id with the cited basis (which cascade step decided it), or
  `human_review_required: true` for a genuine legal conflict, never a fabricated winner.
- The W3C PROV audit record of the decision.

Quality-gate dimensions that most apply: Integrity (no fabricated resolution), Accuracy (basis is
cited and correct), Governance (human-review escape honored), Safety (advisory only).
