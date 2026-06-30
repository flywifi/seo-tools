---
file: skills/atoms/calendar-slot/MAINTAINER_README.md
purpose: keep calendar-slot to date assignment only; it never generates content or resolves conflicts across multiple projects in one call.
---

# calendar-slot: Maintainer README

## Purpose
Assign one content idea to a recommended publish date and a staggered short-form drop schedule. All output is advisory; human_review_required is always true.

## Non-negotiable invariants
- Produces dates only; no content, outlines, or scripts.
- Respects existing_slots when provided; does not silently overwrite a taken date.
- human_review_required is always true in the output.

## Known failure modes
- Scheduling two projects on the same date when existing_slots is provided but not checked.
- Returning fewer than 3 short_form_drop_dates when the window allows more.
- Anchoring to a date outside the publish_by_window.

## Regression cases to preserve
1. existing_slots contains the ideal date: the atom picks the next available date and notes the conflict avoidance.
2. Biweekly cadence with a 3-week window: short-form drops respect the longer spacing.

## Update checklist
- Run python3 tools/sync_check.py.
