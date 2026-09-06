---
file: skills/atoms/conflict-check/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for conflict-check so it stays stable under iteration.
---

# conflict-check: Maintainer README

## Purpose
Given two applicable ADVISORY jurisdictional overlays, determine which governs by the cited
legal-precedence cascade, or flag a genuine conflict for human review. It uses
`tools/geo_overlay.py` `resolve_conflict` and returns a W3C PROV audit of the decision. Its job ends <!-- verify: tools/geo_overlay.py::resolve_conflict -->
at the precedence decision; finding which overlays apply in the first place is `overlay-resolve`.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Skill-specific:
  - The cascade is: field/ceiling preemption -> higher jurisdiction governs; floor preemption + local
    (home-rule) authority -> most-stringent governs; else lex specialis -> more-specific scope
    governs; else -> `human_review_required`.
  - A genuine legal conflict returns `human_review_required` with its PROV audit, never a fabricated
    or auto-decided winner.
  - The decision, its basis, and the audit are always returned together; no un-cited winner.

## Known failure modes
- Auto-resolving a historic-frame-requirement vs HVHZ-impact-window conflict instead of escalating.
- Letting lex specialis silently pick a winner when specificity is actually equal.
- Returning a winner without the PROV audit / cited basis.

## Fragile fallbacks that must not become defaults
- Breaking an equal-specificity tie by an arbitrary rule; equal specificity must fall through to
  human review, and only ever when the escalation is labeled.

## Regression cases to preserve
1. Historic frame requirement vs HVHZ window at equal specificity -> `human_review_required`,
   winner null.
2. Ceiling preemption -> the higher jurisdiction governs, audited.
3. Floor preemption + home-rule authority -> the more-stringent rule governs, audited.
4. Field preemption -> the higher jurisdiction governs regardless of stringency.
5. Every returned decision carries its cited basis and the W3C PROV audit record.

## Approval-gated changes
The precedence cascade order, the preemption taxonomy (floor/ceiling/field/none), the human-review
escape condition, and the audit-record schema.

## Minority-report policy
When the legal basis for precedence is contestable, record the chosen basis, the competing reading,
why it was chosen, and what authority would overturn it; when in doubt, escalate to human review.

## Update checklist
1. `python3 tools/geo_overlay.py --selftest`.
2. `python3 tools/sync_check.py` (invariant 27).
3. Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
