---
file: skills/quality-review/MAINTAINER_README.md
purpose: preserve the non-negotiable rules for quality-review so the gate stays honest and reproducible.
---

# quality-review: Maintainer README

## Purpose
The governance skill. It scores a drafted artifact against the nine Quality Gates dimensions and
returns a release verdict. It never generates the artifact it evaluates.

## Non-negotiable invariants
- Shared: applies `protocols/quality-gates.md`; the arithmetic and verdict come from
  `scripts/score.py`, never hand-computed.
- Integrity and Safety are critical: each must be 4 or higher to release, and either at 0 to 1 is a
  hard fail regardless of composite.
- Release requires no dimension below 3 and a composite average of 4.0 or higher.
- Every score carries a one-line evidence note. Absence of evidence is not a 5.
- For a CRM artifact, the verdict is recorded alongside the record in `pipeline/`.

## Known failure modes
- Scoring from impression rather than evidence.
- Treating a missing Safety or Integrity check as a pass.
- Releasing on a strong composite while a critical dimension sits below 4.
- Doing the arithmetic by hand and getting the threshold logic wrong.

## Fragile fallbacks that must not become defaults
- A "close enough" release at composite 3.9. The floor is 4.0; do not round up.

## Regression cases to preserve
1. Integrity 1 with every other dimension 5: verdict is Not released, hard_fail true.
2. Safety 3 with strong composite: Not released (critical floor), not Released.
3. One dimension at 2: Not released (below the floor of 3).
4. Composite 3.9 with all dimensions 3 or higher and criticals at 4: Not released (composite).
5. All dimensions 4 or higher with criticals at 4 and composite 4.0 or higher: Released.

## Approval-gated changes
- The dimension list, the thresholds, the critical set, or the hard-fail rule.
- The output schema of `scripts/score.py` (downstream skills parse it).

## Minority-report policy
When evidence is mixed on a dimension, record the chosen score, the conflicting evidence, why the
score was chosen, and what would change it.

## Update checklist
- `scripts/score.py --demo` still returns Released for a clean artifact.
- The five regression cases above still hold.
- Run python3 tools/sync_check.py.
