---
file: skills/atoms/invoice-status/MAINTAINER_README.md
purpose: keep invoice-status to read-only reporting; it never issues invoices or sends reminders.
---

# invoice-status: Maintainer README

## Purpose
Report invoice and payment state from pipeline/deals/ records. Surfaces overdue items and recommends follow-up. No writes.

## Non-negotiable invariants
- Reads pipeline/deals/ only; never issues invoices, sends payment reminders, or modifies records.
- days_overdue is computed from due_date relative to as_of_date; never guessed.
- When as_of_date is not provided, the computation uses today's date; this is stated in the output.

## Known failure modes
- Estimating due_date when it is not in the record; always null if missing.
- Reporting days_overdue as a negative number for a pending (not yet due) invoice.
- Issuing a recommendation to "send a payment reminder" via an external channel (out of scope).

## Regression cases to preserve
1. Invoice with no due_date: status is pending; days_overdue is null with a note.
2. Multiple overdue invoices: total_outstanding_usd is the sum of all; recommended_actions has one entry per invoice.

## Update checklist
- Run python3 tools/sync_check.py.
