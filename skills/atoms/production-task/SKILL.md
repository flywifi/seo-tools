---
file: skills/atoms/production-task/SKILL.md
name: production-task
description: break a signed deal or content project into a discrete production task list with owners (Alex), due dates relative to publish date, dependencies, and a critical path. Use when a spoke needs to translate a deliverable set into an actionable pre-production to post checklist. Do NOT use to schedule tasks in an external system, generate content, or evaluate deal terms.
load:
  - shared/pipeline-engine.md
  - shared/brand-engine.md
---

# production-task

Given a project title, publish date, and deliverable list, compute a discrete task list covering
every production phase from pre-production through post, with relative due dates, sequential
dependencies, and a critical path that identifies must-not-slip tasks.

## Purpose

Signed deals and content projects arrive as a deliverable list and a hard publish date. Translating
those into an ordered, date-anchored task list is a single, repeatable operation that should not be
re-invented inside each spoke. This atom handles that operation so that deal-activate, video-development,
and similar spokes can call it once and receive a structured, dependency-aware schedule Alex can act on
immediately.

The output covers six production phases in sequence:

- pre-production: research, scripting, shot-list, asset sourcing, brand review window (if required)
- shoot: filming day(s), b-roll capture, product or sponsored asset photography
- edit: rough cut, color and audio pass, motion graphics, brand asset integration
- caption: auto-caption correction, keyword alignment, chapter markers
- review: self-review, sponsor or brand review (if applicable), final approval
- post: upload and metadata entry, thumbnail finalization, community tab and short-form teasers,
  any contractual deliverable submission

All due dates are computed relative to the publish date so the list stays valid regardless of when
the project is activated. Alex is owner of every task unless a special requirement names an external
party (e.g., a brand review window); in that case the task notes flag the dependency explicitly.

## Inputs

```json
{
  "project_title": "string (working title or deal name)",
  "publish_date": "YYYY-MM-DD (ISO 8601, hard deadline)",
  "deliverables": [
    "string (each deliverable from the deal or content brief)"
  ],
  "deal_id": "string (optional, pipeline record identifier)",
  "special_requirements": [
    "string (optional, e.g. '72-hour brand review window', 'sponsor asset delivery by D-14')"
  ]
}
```

Field notes:
- `project_title` is required. Use the deal name or working title as it appears in the brief.
- `publish_date` is required. All task due dates are anchored to this date using negative offsets
  (D-N means N days before publish). The atom does not validate whether the date is available on
  the calendar; call `calendar-slot` upstream if slot validation is needed.
- `deliverables` is required and must be a list. Each entry names one output Alex must produce
  (e.g., "60-second integration in main video", "dedicated Instagram Reel", "affiliate link in
  description"). The task list is derived from this list; tasks are not invented beyond what the
  deliverables require.
- `deal_id` is optional. When present it is echoed in the output for traceability back to the
  pipeline record. The atom does not read or write the pipeline store directly.
- `special_requirements` is optional. Each entry becomes a constraint that adjusts task due dates
  or adds a dependency. A brand review window, for example, inserts a brand-review task and pushes
  final-approval and upload tasks to respect the window length.

## Output

```json
{
  "tool": "production-task",
  "project_title": "string",
  "publish_date": "YYYY-MM-DD",
  "deal_id": "string | null",
  "task_list": [
    {
      "task_name": "string",
      "category": "pre-production | shoot | edit | caption | review | post",
      "due_date": "YYYY-MM-DD",
      "offset_label": "string (e.g. 'D-21', 'D-7', 'D-0')",
      "owner": "Alex",
      "depends_on": ["string (task_name of prior task this cannot start before)"],
      "notes": "string | null (flags external dependencies, brand review windows, or special handling)"
    }
  ],
  "critical_path": [
    "string (task_name, ordered from earliest must-not-slip to publish day)"
  ],
  "special_requirements_applied": ["string"],
  "human_review_required": true
}
```

Output notes:
- `task_list` is ordered chronologically by `due_date` ascending (earliest first).
- `due_date` is an absolute ISO-8601 date derived from `publish_date` minus the phase offset.
  The atom must compute this from the provided `publish_date`; it must not fabricate a date.
- `offset_label` is a human-readable shorthand (D-21, D-14, D-7, D-3, D-1, D-0) for quick
  scanning. D-0 is the publish date itself.
- `depends_on` lists the `task_name` values of all tasks that must be complete before this task
  can begin. An empty list means no upstream dependency within this project.
- `critical_path` names only the tasks where a slip propagates directly to a missed publish date.
  At minimum it includes: script-approval, shoot-day, rough-cut-delivery, brand-review-approval
  (when applicable), final-export, and upload-and-schedule. Omit tasks that have float.
- `special_requirements_applied` echoes every entry from the input that was acted on, so Alex can
  confirm requirements were not silently dropped.
- `human_review_required` is always `true`. Alex confirms dates and task scope before treating
  the list as locked.

## Do NOT use for

- Scheduling or writing tasks into any external system (Notion, Asana, Google Calendar, or
  otherwise). This atom outputs a task list for Alex to copy and load; it does not integrate with
  external tools.
- Generating content: scripts, hooks, outlines, thumbnails, or captions are produced by their
  own atoms. This atom only plans when and in what order production steps occur.
- Evaluating whether a deal should be accepted or what rate to charge (use rate-card-fill and
  deal scoring upstream).
- Validating deliverables against brand guidelines or quality gates (govern-artifact handles that
  as a separate step).
- Resolving calendar conflicts across multiple projects at once (call calendar-slot per project
  before calling this atom if slot validation is required).

## Pipeline note

Follows `shared/method.md` at the Production Planning step. Deal and deliverable context is
sourced from the pipeline record referenced by `deal_id`; the atom does not mutate that record.
Brand constraints and integration requirements that affect task scope come from
`shared/brand-engine.md`. Output passes to `protocols/quality-gates.md` before the task list
is treated as final.
