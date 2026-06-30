---
file: skills/deal-resourcing/MAINTAINER_README.md
purpose: keep deal-resourcing scoped to signed, in-production, and delivered deals; it never issues invoices or modifies pipeline records.
---

# deal-resourcing: Maintainer README

## Purpose
Convert a signed deal into a production resource plan: task list with categories and due dates, critical path, and an invoice status read.

## Non-negotiable invariants
- Only operates on deals in the signed, in-production, or delivered stage; returns gap-record for other stages.
- invoice-status is read-only; this spoke never issues invoices or modifies payment records.
- production-task output always includes a critical_path list.

## Known failure modes
- Attempting to resource a deal that is still in-discussion (wrong stage).
- Issuing an invoice or sending a payment reminder (out of scope).
- Returning a task list with an empty critical_path.

## Regression cases to preserve
1. Brand review window in special_requirements: a "brand review" task appears in the task list with the correct window duration.
2. Deal in invoiced stage: invoice-status returns overdue if payment is past due; recommended_action included.

## Approval-gated changes
- The set of eligible deal stages for resourcing.

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
