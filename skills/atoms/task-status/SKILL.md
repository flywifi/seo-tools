---
name: task-status
atom: true
standalone: true
description: "records a governed task state change with tools/tasks.py: move a task through the lifecycle (not_started, in_progress, waiting_external, blocked, deferred, done, cancelled), flip responsible_party on an approval/revision hand-off, and compute the nudge and escalate dates for a waiting-on item. Triggers: 'mark the draft submitted to the brand', 'the brand requested changes', 'the short is approved', 'I'm waiting on payment'. Do NOT create tasks (task-extract), schedule dates (task-plan), or send a nudge (drafts only). Every change appends to the append-only history with its actor and source."
engines_required:
  - shared/tasks-engine.md
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# task-status

The governed way a task changes. It validates every transition, flips who owes the next move on a hand-off,
and computes when to nudge, appending an audit event each time. It never sends anything.

## First line of every output (verbatim)

```
ORGANIZATIONAL TRACKING, NOT LEGAL, FINANCIAL, OR COMPLIANCE ADVICE. Status changes are logged for you; nudges and replies are drafted, never sent automatically.
```

## When to use this skill
- "mark the draft submitted to the brand", "the brand requested changes", "the reel is approved", "I'm now
  waiting on payment", "block this until the sample arrives", routed as `task_status`.

Do NOT use for:
- Creating a task (use `task-extract`).
- Computing schedules (use `task-plan`).
- Actually sending a nudge or reply (drafts only; the human sends).

## Inputs
The task id and the target state (or the hand-off event: submit, request_changes, resubmit, approve), plus a
source reference for the change (who said so).

## Core procedure
Follow `shared/method.md`. Call `tools/tasks.py` / the `task_transition` MCP tool.

### Step 1: validate and transition
Apply the transition through the single choke point: it checks the allowed-transition table, refuses `done`
while a blocker is open, records `waiting_on_party` and the aging clock for a waiting-on move, and appends an
event to `history[]` with the actor and source. Illegal transitions are refused, not forced.

### Step 2: ping-pong and nudge
For an approval/revision hand-off, flip `responsible_party`, count the iteration (escalating past the max),
and compute the response-due, nudge (80% of the window), and escalate (50% past due) dates. The nudge is
drafted for the human.

## Output contract
The updated task with its new status, responsible party, nudge/escalate dates, and the appended history
event. Honor `protocols/formatting-metadata.md`; `human_review_required`.

## Engines and protocols loaded
`shared/tasks-engine.md`; `protocols/safety.md`, `protocols/no-fabrication.md`,
`protocols/formatting-metadata.md`.

## Atoms used
None. Operates on tasks from `task-extract`. Directly callable and used by `task-desk`.

## Standalone usability
Records a validated, audited status change and computes the nudge date offline, with no downstream skill.

## Failure modes
- An illegal transition (for example done while blocked) is refused with the reason, never forced.
- A waiting-on item that ages past its response-due surfaces as an aging follow-up, not a silent creator task.
- No source for the change: the change is flagged for the human, keeping the audit trail honest.
