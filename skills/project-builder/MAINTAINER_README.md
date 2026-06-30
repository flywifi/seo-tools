---
file: skills/project-builder/MAINTAINER_README.md
purpose: keep project-builder applying the DIY safety boundary at every step sequence and never generating scripts or SEO copy.
---

# project-builder: Maintainer README

## Purpose
The "plan this project" spoke for the Content lane. Produces a complete DIY project brief by composing project-snapshot, materials-list, step-sequence, styling-variant, and renter-alt.

## Non-negotiable invariants
- step-sequence always invokes the licensed-trade safety check per protocols/safety.md; any step requiring a licensed trade is flagged, never worked around.
- Cost ranges in materials-list are always labeled as estimates.
- govern-artifact gates the output before it reaches the user.

## Known failure modes
- Providing a DIY workaround for an electrical or gas step instead of a hard boundary note.
- Stating a material cost as an exact price rather than an estimated range.
- Generating hooks, titles, or scripts instead of stopping at the project brief.

## Fragile fallbacks that must not become defaults
- Omitting styling-variant when the request has no explicit aesthetic variant signal (include 2 to 3 variants by default).

## Regression cases to preserve
1. Electrical step in a renovation: step is present with licensed_trade_required: true; no DIY workaround suggested.
2. Renter_friendly: true in input: renter-alt runs for every relevant step; renter_alts appear in the brief.
3. High-budget input: materials-list reflects higher-quality options; estimates remain labeled as estimates.

## Approval-gated changes
- The atom wiring in workflow.json and any changes to the safety check integration.

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
