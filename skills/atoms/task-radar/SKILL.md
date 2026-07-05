---
name: task-radar
atom: true
standalone: true
description: "shows what is outstanding across a project's tasks: a waiting-on (ball in the brand's court) versus I-owe (creator's next actions) split, plus due-soon, overdue, and aging follow-ups. Triggers: 'what am I waiting on', 'what do I owe', 'what's due this week', 'what's overdue', 'show the outstanding tasks for this deal'. Do NOT create tasks (task-extract), change status (task-status), or schedule (task-plan). Read-only; every item cites its source and carries its due date and responsible party."
engines_required:
  - shared/tasks-engine.md
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# task-radar

The at-a-glance view of outstanding work: what the brand owes you versus what you owe, what is due soon, what
is overdue, and which waiting-on items have gone stale. Read-only and source-cited.

## First line of every output (verbatim)

```
ORGANIZATIONAL TRACKING, NOT LEGAL, FINANCIAL, OR COMPLIANCE ADVICE. This is a read-only view of your tracked tasks; verify against the contract and counterparty.
```

## When to use this skill
- "what am I waiting on", "what do I owe", "what's due this week", "what's overdue", "show the outstanding
  tasks for this deal", "which brand approvals are stale", routed as `task_status` (read) or a status check.

Do NOT use for:
- Creating tasks (use `task-extract`).
- Changing status or logging a hand-off (use `task-status`).
- Scheduling dates (use `task-plan`).

## Inputs
The task register (from the store), and optionally a deal id to scope the view and a date for the due bands.

## Core procedure
Follow `shared/method.md`. Call `tools/tasks.py` (`scan`) / the `task_scan` MCP tool.

### Step 1: compute the derived views
Read the register and compute (never store) the split: `waiting_on_counterparty` (status waiting_external),
`i_owe` (open, creator-actionable), `overdue`, and `due_soon`, plus aging waiting-on items past their
response-due date.

### Step 2: present with source and party
Show each item with its due date, responsible party, and its cited source. Aging brand-owed items surface as
follow-ups (drafted nudges), not silent creator to-dos.

## Output contract
The waiting-on vs I-owe split with due-soon/overdue/aging bands, each item cited. Read-only, offline. Honor
`protocols/formatting-metadata.md`; `human_review_required` for any follow-up action.

## Engines and protocols loaded
`shared/tasks-engine.md`; `protocols/safety.md`, `protocols/no-fabrication.md`,
`protocols/formatting-metadata.md`.

## Atoms used
None. Read-only over tasks from `task-extract`/`task-status`. Directly callable and used by `task-desk` and
the scheduling dashboard.

## Standalone usability
Returns the outstanding-task split and due bands offline from the register, with no downstream skill.

## Failure modes
- A task with a null due date appears under "no date", never guessed into a due band.
- Blocked-by state is computed live from real blocker status, not a stored flag.
- Nothing is sent; aging items produce drafted follow-ups for the human.
