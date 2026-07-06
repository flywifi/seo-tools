---
file: skills/jurisdiction-desk/references/artifact-types.md
role: the artifact types this skill produces and the required elements of each.
---

# jurisdiction-desk artifact types

## Jurisdictional overlay briefing (advisory)
The composed artifact the desk hands off: the applicable overlays plus any conflict decision.

Required elements:
- The verbatim advisory boundary line as the first line of output.
- The applicable-overlays report from `overlay-resolve` (each overlay cited and with its decided-by
  basis; unknown facts null-and-flagged).
- Any precedence decision from `conflict-check` when two applicable overlays collide: the governing
  overlay with its cited basis, or `human_review_required` with its W3C PROV audit.
- The governance pass from `govern-artifact`: the advisory boundary enforced, citations present, no
  fabricated boundaries/values, and `protocols/formatting-metadata.md` honored.

Quality-gate dimensions that most apply: Integrity, Accuracy, Governance, Safety, User intent.
