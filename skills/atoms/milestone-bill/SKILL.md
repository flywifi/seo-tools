---
name: milestone-bill
atom: true
standalone: true
description: "determines when a project's payment milestone becomes billable and hands the amount and terms to the finance lane. When a deliverable event fires (delivery, approval, publish), it flips the matching milestone to billable and drafts a citation-carrying invoice task; nothing is sent. Triggers: 'can I bill for this yet', 'the brand approved the final, is the balance due', 'what milestones are ready to invoice'. Do NOT send an invoice (finance-desk drafts, the human sends) or change task status (task-status)."
engines_required:
  - shared/tasks-engine.md
  - shared/finance-engine.md
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# milestone-bill

Answers "can I bill yet, and how much" by tying billable-readiness to the deliverable events the contract
names, then handing the ready milestone to the finance lane as a cited invoice task. It never sends money.

## First line of every output (verbatim)

```
ORGANIZATIONAL TRACKING, NOT FINANCIAL OR TAX ADVICE. Confirm amounts and timing against the signed contract and review with a CPA before billing. Invoices are drafted, never sent.
```

## When to use this skill
- "can I bill for this yet", "the brand approved the final cut, is the balance due now", "which milestones
  are ready to invoice", "the deposit is due on signing, track it", routed as `milestone_bill`.

Do NOT use for:
- Actually sending an invoice (finance-desk drafts it; the human sends, per the consequential-action gate).
- Changing a task's status (use `task-status`).
- Inventing an amount (amounts stay null until a real figure is on the contract).

## Inputs
The payment schedule (milestones with their triggers and amounts) and the deliverable event that fired
(delivery / approval / publish), typically from a `task-status` approval or a `shipment-track` delivery.

## Core procedure
Follow `shared/method.md`. Call `tools/tasks.py` (billable functions) / the `milestone_status` MCP tool.

### Step 1: apply the event
When a deliverable event lands, flip `billable_ready` on the matching milestones (acceptance-required ones
only on approval). Each newly-ready milestone becomes a citation-carrying billable task (event_derived
source: the milestone rule + the deliverable event).

### Step 2: hand to finance
Pass the ready milestone (amount, percent, net terms) to `shared/finance-engine.md` / `invoice-generate`,
which drafts the invoice under the finance gates. The human confirms before anything is sent.

## Output contract
The list of ready-to-bill milestones with their citations and amounts, and the drafted invoice task. Honor
`protocols/no-fabrication.md`; `human_review_required`.

## Engines and protocols loaded
`shared/tasks-engine.md`, `shared/finance-engine.md`; `protocols/safety.md`, `protocols/no-fabrication.md`,
`protocols/formatting-metadata.md`.

## Atoms used
Feeds `invoice-generate` (finance-desk). Directly callable and used by `task-desk`.

## Standalone usability
Reports which milestones are billable and drafts the invoice task offline, without sending anything.

## Failure modes
- A milestone with no real amount stays null and flagged, never guessed.
- An acceptance-required milestone does not fire on delivery, only on approval.
- The invoice is drafted only; the consequential-action gate keeps the send with the human.
