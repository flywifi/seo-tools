---
name: payment-reconcile
atom: true
standalone: true
description: "matches a bank or PayPal export against open invoices and PROPOSES which payment settles which invoice, with confidence tiers (exact, probable, uncertain); the human confirms each match and only then does the gated mark-paid write happen. Structural privacy boundary: tools/finance.py REFUSES to read any CSV inside the repo unless its filename carries .local. (bank exports live at pipeline/finance/<name>.local.csv, gitignored, or outside the repo). Do NOT use to see who is overdue (ar-review), to draft an invoice (invoice-generate), or to import general analytics CSVs (data-query)."
engines_required:
  - shared/finance-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/safety.md
  - protocols/formatting-metadata.md
---

# payment-reconcile

Which deposit pays which invoice. Proposals in tiers, human confirmation, then the gated write.

## When to use this skill
- "match my PayPal export against my invoices", "did Hearthline actually pay", "reconcile this
  bank statement", routed as `payment_reconcile`.

Do NOT use for:
- The overdue picture and chasing (use `ar-review`).
- Drafting or issuing invoices (use `invoice-generate`).
- Querying analytics CSVs (use `data-query`; that is a different lane entirely).

## Input
```json
{
  "csv_path": "pipeline/finance/<name>.local.csv, or a path OUTSIDE the repo",
  "window_days": 5,
  "amount_tolerance": "0.00",
  "mapping": { "date": null, "amount": null, "description": null }
}
```
The export NEVER goes anywhere unprotected: inside the repo it must be a `.local.` file
(covered by the gitignore allowlist-invert rules and refused otherwise by the tool itself);
outside the repo it is simply read in place.

## Core procedure
1. Run `python3 tools/finance.py --reconcile <csv> [--window-days N] [--amount-tolerance X]`.
   Column heuristics handle common export shapes (ISO or US dates, $ and comma amounts,
   parenthesized negatives); pass `mapping` when they guess wrong. Matching per row against
   OPEN invoices: exact amount + date window + brand substring in the description = `exact`;
   exact amount + window = `probable`; tolerance or brand-only = `uncertain`. Each invoice is
   matched at most once (best tier, then smallest date delta). Unmatched rows and unmatched
   invoices are listed, never force-paired. PROPOSAL-ONLY output with
   `human_review_required: true`.
2. Walk the human through each proposal (amount, dates, description, confidence). Uncertain
   proposals get extra scrutiny; nothing is assumed.
3. Only after an explicit yes per invoice: `python3 tools/finance.py --mark-paid <invoice_id>
   --paid-date YYYY-MM-DD [--method x]` (gated on `finance_management`; refuses otherwise and
   touches nothing).
4. Point at `ar-review` afterward for the updated book.

## Output contract
The `reconcile` result verbatim: `proposals[]{row_index, row_date, row_amount, row_description,
invoice_id, invoice_amount, brand_name, date_delta_days, confidence}`, `unmatched_rows`,
`unmatched_invoices`, the proposal-only note, `computed_by`, `gaps[]` (unparseable rows named,
never guessed). Plus the confirmation walk-through. Redact (`--redacted`) anything that will be
quoted off this machine.

## Standalone usability
The proposal list alone is a usable reconciliation worksheet even if the human updates records
elsewhere.

## Failure modes
- CSV inside the repo without `.local.` in the name: refused by the tool with the fix named
  (the privacy boundary, `shared/finance-engine.md`). Never bypassed.
- Ambiguous columns: unparseable rows become gaps; pass an explicit `mapping`.
- Two candidate invoices for one deposit: the better tier wins the proposal and the other stays
  unmatched for the human to resolve; never both.
