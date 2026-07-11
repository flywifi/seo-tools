---
file: skills/task-desk/SKILL.md
name: task-desk
description: "the project task and obligation desk: tracks event-triggered, source-cited tasks per deal and contract; who is responsible (creator vs brand vs agency); backwards-planning from a deadline; recurring duties; waiting-on-the-brand follow-ups; shipment anchors; payment-milestone billable readiness; and deliverable requirement-coverage verification. Composes task-extract, email-to-task, task-plan, task-status, task-radar, coverage-verify, shipment-track, and milestone-bill, then governs the output. Every task cites a real source (anti-phantom); nothing is sent, invoiced, or posted automatically. Does NOT give legal advice (contract-desk / attorney), do money math or send invoices (finance-desk / CPA), or manage the deal lifecycle stages (deal-pipeline)."
load: for task-desk requests (task tracking, backwards planning, waiting-on, shipments, milestones, coverage) when task_tracking is enabled
---

# task-desk

task-desk is the Pipeline/CRM spoke that tracks the outstanding work a brand deal generates: what is due, who
owes it, from what source, and whether a deliverable met its requirements. It complements deal-pipeline (deal
lifecycle), contract-desk (the contract document), and finance-desk (invoicing). Every task traces to a real,
human-created item; nothing leaves the machine without the human's confirmation.

## First line of every output (verbatim)

```
ORGANIZATIONAL TRACKING, NOT LEGAL, FINANCIAL, OR COMPLIANCE ADVICE. Verify dates and tasks against the contract and counterparty. Nothing is sent, filed, invoiced, or posted automatically.
```

## When to use this skill
- Tracking and planning: "what am I waiting on", "what do I owe", "when is my draft due if the product ships
  Monday", "work backward from the launch date", "add these contract deadlines as tasks" (`task_plan` /
  `task_status`).
- Waiting-on and hand-offs: "the brand owes approval on the short", "the reel was approved", "the brand asked
  for changes" (`task_status`).
- Shipments: "the sample shipped, start the clock" (`shipment_update`).
- Billing readiness: "can I bill for this yet", "which milestones are ready to invoice" (`milestone_bill`).
- Coverage: "did the final cut cover the approved talking points" (`coverage_check`).

Do NOT use for:
- Legal advice or reading a contract's enforceability (use `contract-desk`; refer to an attorney).
- Money math or sending invoices (use `finance-desk`; the human sends; refer to a CPA).
- Moving the deal through its lifecycle stages (use `deal-pipeline`).

## Inputs
A deal and contract, plus the sources that create tasks (obligation rows, emails, user statements, shipment
events) and the requirement points / transcripts for coverage. No network is required for the core; live
email and carrier tracking are optional flag-gated connectors.

## Core procedure
Follow `shared/method.md`. Compose atoms via `workflow.json`.

### Step 1: classify the request
Route to `task-extract`/`email-to-task` (create cited tasks), `task-plan` (schedule / reverse-plan),
`task-status` (governed transition + waiting-on), `task-radar` (what is outstanding), `shipment-track`
(anchor), `milestone-bill` (billable readiness), or `coverage-verify` (deliverable coverage). A request may
use several.

### Step 2: run, cite, and govern
Every task carries a source; every date is computed offline by `tools/tasks.py`; waiting-on items surface as
aging follow-ups; billable milestones hand off to finance; coverage cites the supporting sentence or
abstains. Hand the assembled output to `govern-artifact` and emit the boundary. Nothing is sent.

## Output contract
Cited tasks with due dates and responsible parties, schedules and feasibility, status changes with an audit
event, the waiting-on vs I-owe view, shipment anchors, billable milestones, and coverage verdicts, each with
`human_review_required`. Honor `protocols/formatting-metadata.md`; no fabricated dates or coverage
(`protocols/no-fabrication.md`).

## Engines and protocols loaded
`shared/tasks-engine.md`, `shared/finance-engine.md`, `shared/injection-guard-engine.md`;
`protocols/safety.md`, `protocols/no-fabrication.md`, `protocols/research-citation.md`,
`protocols/quality-gates.md`, `protocols/formatting-metadata.md`.

## Atoms used
`task-extract`, `email-to-task`, `task-plan`, `task-status`, `task-radar`, `coverage-verify`,
`shipment-track`, `milestone-bill`, and `govern-artifact`. Each is directly callable; `deal-resourcing` seeds
tasks and `finance-desk` receives billable milestones.

## Standalone usability
Tracks, plans, and reports cited tasks offline from the register, with no downstream skill and no network.

## Failure modes
- A task with no citable source is refused (anti-phantom).
- An infeasible deadline surfaces the negative-slack conflict, not a false "on track".
- Coverage abstains rather than inferring; input conflicts go to the minority report and the human gate.
- Nothing is sent; nudges, replies, and invoices are drafted for the human.

## Cross-modality
Class: C.
Runs on: Claude Desktop/Code (native, MCP + the tool module); claude.ai via a hosted remote-MCP connector; Custom GPT / Gemini only when the tool is hosted behind a remote MCP or an Action; Gems: no.
Mechanism: tools/tasks.py (scheduling, recurrence, date math), tools/shipments.py, tools/coverage_verify.py over the task store; MCP task tools; .ics export.
Fallback: No runtime or hosted seam -> reason over the tasks-engine date rules against pasted tasks, flag unverified, name the command; never fabricate a schedule or a shipment status. On ChatGPT this is reasoning-only and outputs are labeled provisional (no local tools, no flag enforcement); the desktop app can reach the full tool only via a deployed remote MCP connector in developer mode (implementation/gpt/mcp-connector/README.md).
See `shared/cross-modality-engine.md`.