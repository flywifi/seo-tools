---
name: task-plan
atom: true
standalone: true
description: "computes the schedule for a project's tasks with tools/tasks.py: forward from a trigger event (draft due 7 business days after product receipt), backward from a hard deadline (when must each upstream step start to hit the publish date), and a feasibility check that flags negative-slack conflicts when the chain cannot fit. Triggers: 'when is everything due', 'work backward from the launch date', 'can we still make the deadline'. Do NOT create tasks (task-extract), change status (task-status), or bill (milestone-bill). All date math is offline and cited to the rule + anchor event."
engines_required:
  - shared/tasks-engine.md
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# task-plan

The scheduler. Given a project's tasks and the known event dates, it computes due dates forward from
triggers, must-start dates backward from a deadline, and whether the chain is even feasible, all offline and
deterministically.

## First line of every output (verbatim)

```
ORGANIZATIONAL TRACKING, NOT LEGAL, FINANCIAL, OR COMPLIANCE ADVICE. Dates are computed from your sources; verify against the contract and permit dates. Nothing is scheduled externally.
```

## When to use this skill
- "when is everything due", "the product ships Monday, when is my draft due", "work backward from the Sept 15
  launch", "can I still make the deadline if the sample arrives Friday", routed as `task_plan`.

Do NOT use for:
- Creating tasks (use `task-extract`).
- Changing a task's status or logging a hand-off (use `task-status`).
- Money or billing (use `milestone-bill` / finance-desk).

## Inputs
The project's tasks (from the register) and a map of resolved event dates (product received, contract signed,
publish date). For a reverse plan, the deadline task and its date.

## Core procedure
Follow `shared/method.md`. Call `tools/tasks.py` (`plan`) or the `task_plan` MCP tool.

### Step 1: forward or reverse
Forward pass for earliest due dates from triggers; backward `reverse_plan` for the latest each upstream step
must finish to hit a deadline. Unresolved triggers leave the due null and flagged, never guessed.

### Step 2: feasibility
Run the negative-slack check: if any task's earliest-possible due is later than its must-finish-by, the chain
cannot fit the deadline. Surface the conflict with the slack, never silently.

## Output contract
Per-task due (forward) or must-finish-by (reverse) dates, gaps for unresolved triggers, and any feasibility
conflicts. Business-day aware. Honor `protocols/formatting-metadata.md`; `human_review_required`.

## Engines and protocols loaded
`shared/tasks-engine.md`; `protocols/safety.md`, `protocols/no-fabrication.md`,
`protocols/formatting-metadata.md`.

## Atoms used
None. Reads tasks produced by `task-extract`. Directly callable and used by `task-desk`.

## Standalone usability
Computes a forward or reverse schedule with a feasibility verdict offline, from the tasks and event dates.

## Failure modes
- An unresolved trigger event leaves the task deferred with a null due and a gap, never a guessed date.
- A dependency cycle is reported as an error, not silently resolved.
- An infeasible deadline surfaces the negative-slack conflict rather than a false "on track".

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
