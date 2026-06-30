---
file: skills/atoms/invoice-status/SKILL.md
name: invoice-status
description: "reads invoice and payment state from pipeline/deals/ records and surfaces overdue, pending, and paid invoices; does NOT issue invoices, send payment reminders, or modify records."
load:
  - shared/pipeline-engine.md
  - protocols/no-fabrication.md
---

# invoice-status

## Purpose

Read invoice and payment state from `pipeline/deals/` records and surface overdue, pending, and paid invoices. This atom is a read-only lens over the deals store. It classifies each invoice by status relative to the current or supplied date, computes days overdue, and aggregates total outstanding balance. It does not modify any record, send any communication, or create new invoices.

## Inputs

| Field | Type | Required | Notes |
|---|---|---|---|
| `deal_id` | string | No | If omitted, the atom returns all non-paid invoices across all deal records. If supplied, the atom scopes output to that single deal. |
| `as_of_date` | ISO 8601 date string (YYYY-MM-DD) | No | The reference date used to compute overdue status and days overdue. Defaults to the current date when omitted. |

## Output

```json
{
  "invoices": [
    {
      "deal_id": "<string>",
      "brand_name": "<string>",
      "amount": "<number>",
      "issued_date": "<YYYY-MM-DD>",
      "due_date": "<YYYY-MM-DD>",
      "status": "<pending | overdue | paid>",
      "days_overdue": "<integer, 0 if not overdue>"
    }
  ],
  "total_outstanding_usd": "<number>",
  "recommended_actions": [
    {
      "deal_id": "<string>",
      "brand_name": "<string>",
      "action": "<string describing the follow-up step for this overdue item>"
    }
  ]
}
```

Field definitions:

- `invoices` -- list of invoice objects matching the input scope. Each object carries the deal identifier, the brand name, the invoice amount in USD, the dates the invoice was issued and is due, the computed status, and the integer count of days overdue (0 for pending or paid items).
- `status` values are exactly `pending` (due date is today or in the future, not yet paid), `overdue` (due date is before `as_of_date`, not yet paid), or `paid` (payment recorded in the deal record).
- `total_outstanding_usd` -- sum of `amount` across all invoices with status `pending` or `overdue` in the current result set.
- `recommended_actions` -- one entry per overdue invoice only. The `action` string is a plain-language follow-up step derived from pipeline norms in `shared/pipeline-engine.md`. This field is an empty list when no invoices are overdue.

If a required field is absent from the source deal record, the atom surfaces `null` for that field and does not fabricate a value. See `protocols/no-fabrication.md`.

## Do NOT use for

- Issuing new invoices or generating invoice documents.
- Sending payment reminders or any outbound communication to brands.
- Modifying, updating, or deleting deal records.
- Approving, disputing, or reconciling payments.
- Any write operation against `pipeline/deals/`.
- Forecasting future revenue or modeling cash flow projections.

## Pipeline note

All source data is read from `pipeline/deals/`. Real deal records are gitignored per the non-negotiables in `CLAUDE.md`; only schemas and blank structures are committed to the repository. This atom must never be seeded with fabricated deal data during development or testing. Use the blank structures and placeholder values provided in the `pipeline/` schema files for any local validation work.
