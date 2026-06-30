---
file: skills/atoms/production-task/MAINTAINER_README.md
purpose: keep production-task scoped to task list generation; it never schedules tasks in external systems or invents deliverables.
---

# production-task: Maintainer README

## Purpose
Break a project into a task list with categories, due dates relative to publish date, and a critical path. The output is for the creator to copy into her own system.

## Non-negotiable invariants
- All due dates are relative to publish_date (e.g., "T-14 days" for pre-production), not absolute dates, unless publish_date is provided in ISO 8601.
- critical_path contains only tasks that cannot slip without delaying publish_date.
- Does not write to any external scheduling or project management system.

## Known failure modes
- Setting absolute due dates when publish_date is not ISO 8601 (use relative instead).
- Omitting the brand_review_window task when special_requirements includes a brand review period.
- An empty critical_path when the project has clear hard dependencies.

## Regression cases to preserve
1. Brand review window provided: a "brand review" task appears in the task list with its window duration.
2. publish_date is known: due_dates are ISO 8601; critical_path identifies the last date any slip is recoverable.

## Update checklist
- Run python3 tools/sync_check.py.
