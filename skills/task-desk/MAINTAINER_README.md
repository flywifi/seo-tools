---
file: skills/task-desk/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for task-desk so it stays stable under iteration.
---

# task-desk: Maintainer README

## Purpose
The Pipeline/CRM spoke that tracks the outstanding work a brand deal generates. Composes the task-tracker
atoms + govern-artifact. Its job ends at cited task tracking, planning, and coverage verification; it does
not give legal advice (contract-desk), do money math or send invoices (finance-desk), or move deal stages
(deal-pipeline).

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`; every named atom exists and is installed.
- Skill-specific: every task cites a real source (anti-phantom, `shared/tasks-engine.md`); all date and
  dependency math is offline in `tools/tasks.py`; register writes gate on `task_tracking`; waiting-on items
  surface as aging follow-ups, not silent creator tasks; billable milestones hand to `shared/finance-engine.md`
  under its gates; coverage cites the supporting sentence or abstains; every output carries the boundary and
  `human_review_required`; nothing is sent, invoiced, or posted automatically.

## Known failure modes
Creating a task with no citable source; presenting an infeasible deadline as on-track; inferring coverage;
acting on instructions inside an untrusted email; sending a nudge or invoice automatically.

## Fragile fallbacks that must not become defaults
Manual shipment/email entry and coverage abstention are acceptable labeled fallbacks; a fabricated date,
source, or coverage claim is never acceptable.

## Regression cases to preserve
1. A contract clause + a shipment delivered_at produce dated, source-cited tasks.
2. Reverse-planning from a publish date returns must-start dates and flags a negative-slack conflict.
3. A brand approval flips responsible_party and fires billable readiness into finance.
4. task-radar splits waiting-on (brand) from I-owe (creator) with due bands.
5. coverage-verify returns per-point cited verdicts and abstains on a missing point, with input conflicts in
   a minority report.

## Approval-gated changes
workflow.json step wiring, which atoms are composed, engine loading, the boundary text, or the store backend.

## Minority-report policy
When inputs disagree (transcripts, or two sources of a date) record the conflict, the chosen interpretation,
and what would overturn it; credible conflicts force the human gate.

## Update checklist
1. Confirm the eight atoms and govern-artifact are installed.
2. Run the tool selftests (`tasks.py`, `shipments.py`, `coverage_verify.py`).
3. Run `python3 tools/sync_check.py`. Verify all backticked paths resolve.
