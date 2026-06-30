---
file: skills/deal-resourcing/references/artifact-types.md
role: the artifact types deal-resourcing produces and the required elements of each.
---

# deal-resourcing artifact types

## Resource plan
A production task list and invoice status snapshot for a signed deal. Required elements: deal_id, brand_name, publish_date, task_list (each: task_name, category [pre-production/shoot/edit/caption/review/post], due_date, depends_on, notes), critical_path (ordered list of must-not-slip tasks), invoice_status (from invoice-status atom), and a govern-artifact gate result.

## Task list
A structured production checklist from production-task. Required elements: task_name, category, due_date (ISO 8601 or relative to publish_date), depends_on list, notes, and a critical_path identifier flag.

## Invoice status report
A read-only view of invoice state from invoice-status. Required elements: invoices list (each: deal_id, brand_name, amount or null, issued_date, due_date, status [pending/overdue/paid], days_overdue or null), total_outstanding_usd, and recommended_actions per overdue invoice.
