---
name: ar-review
atom: true
standalone: true
description: "portfolio-wide accounts-receivable review: who owes what, aged into current/1-30/31-60/61-90/over-90 buckets, with per-brand totals, accrued late penalties under each invoice's frozen terms, chase send-by dates, and a prioritized action queue; computed read-only by tools/finance.py --ar-scan (always available, no flag). Do NOT use to check a single deal's invoice state narrative (invoice-status), to draft an invoice (invoice-generate), or to send reminders (nothing here sends anything)."
engines_required:
  - shared/finance-engine.md
  - shared/pipeline-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# ar-review

The money owed, aged and prioritized. One read-only operation over the standalone invoice
records; all math by `tools/finance.py`.

## When to use this skill
- "who owes me money", "what is outstanding", "AR aging", "which invoices are overdue",
  "how late is the Hearthline payment", routed as `finance_review`.

Do NOT use for:
- One deal's invoice story in prose (use `invoice-status`).
- Drafting or issuing an invoice (use `invoice-generate`).
- Sending reminders. This atom reports; any chase message is drafted separately and sent by
  the human.

## Input
```json
{
  "as_of_date": "ISO date or null (defaults to today)",
  "invoices": "optional inline records; omitted = read pipeline/finance/*.local.json"
}
```

## Core procedure
Run `python3 tools/finance.py --ar-scan [--today YYYY-MM-DD]`. The tool ages every open invoice
into accounting buckets (edges inclusive on the left: day 31 is 31 to 60), totals per bucket and
per brand, accrues late penalties under each invoice's `terms_snapshot` (full elapsed months
past grace, no proration), computes a chase send-by date (action dates roll backward over
weekends and holidays; contractual due dates never move), and sorts the action queue by days
past due. Paid invoices drop out; disputed invoices are excluded from outstanding totals and
penalty accrual and reported on their own line. This is read-only and needs no flag.

Interpret the scan for the human: which follow-ups matter this week, which penalties have
actually accrued under the terms, and which invoices are missing data (`gaps[]`).

## Output contract
The `ar_scan` result verbatim (buckets, `bucket_totals`, `total_outstanding`, `per_brand`,
`action_queue`, `disputed`, `computed_by`, `gaps`) plus a short prose summary. Every figure is
the tool's exact-decimal string; the model never re-adds or rounds. An empty book is reported
honestly (zero totals, no fabricated pipeline).

## Standalone usability
The scan output alone is a complete AR aging report the creator can act on with no other skill.

## Failure modes
- No invoice records yet: honest empty state, plus a pointer to `invoice-generate`.
- An invoice without a due date cannot be aged: it appears in `gaps[]` with the fix (normalize
  the terms), never guessed into a bucket.
- Penalty terms the math cannot express (anything beyond flat or percent-per-month) are flagged
  for manual handling, never approximated.
