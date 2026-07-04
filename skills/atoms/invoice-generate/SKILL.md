---
name: invoice-generate
atom: true
standalone: true
description: "drafts a standalone invoice record for a deal: line items from the deal's agreed figures, deterministic invoice number, terms snapshot, and a due date derived offline from structured net terms by tools/finance.py; optionally renders an invoice document via document-studio. Drafts ONLY: nothing is ever sent, human_review_required is always true, and record writes are gated by finance_management plus invoice_generation. Do NOT use to check invoice status or aging (invoice-status, ar-review), to compute what a project should cost (cost-estimate), or to set a price (proposal-price)."
engines_required:
  - shared/finance-engine.md
  - shared/pipeline-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/safety.md
  - protocols/formatting-metadata.md
---

# invoice-generate

Turn a deal's agreed figures into a draft invoice record. Every number comes from the deal
record or the caller; the arithmetic and the invoice id come from `tools/finance.py`; the human
reviews and sends.

## When to use this skill
- "invoice Hearthline for the delivered video", "draft the deposit invoice", "bill the kill fee",
  "create the final invoice for this deal", routed as `invoice_create`.

Do NOT use for:
- Checking what is owed or overdue (use `invoice-status` for one deal, `ar-review` for the book).
- Estimating project costs (use `cost-estimate`) or setting a price (use `proposal-price`).
- Sending anything. This atom drafts; the human sends (consequential-action gate,
  `shared/finance-engine.md`).

## Input
```json
{
  "deal_id": "string (required)",
  "line_items": [{"description": "", "quantity": 1, "unit_price": null, "amount": null, "deliverable_ref": null}],
  "adjustments": [{"description": "", "amount": null}],
  "seq": "integer or null (next sequence for this deal; the tool defaults to 1)",
  "anchor_date": "ISO date of the terms anchor event (for example the delivery date), from the deal record",
  "render_document": false
}
```
Line-item figures come from the deal's `compensation`, `agreed_deliverables`, and structured
terms. A figure the record does not contain stays null and becomes a gap; it is never estimated
(`protocols/no-fabrication.md`).

## Core procedure
1. Read the deal record; assemble the payload (line items, adjustments, the deal's
   `payment_terms_structured` as `terms`, and the anchor date for the stated anchor event).
2. Run `python3 tools/finance.py --build-invoice <payload.json> [--write]`. The tool computes
   the subtotal and total (Decimal, cents), derives `payment_due_date` from `net_days` plus the
   anchor (contractual dates are never weekend-rolled), freezes `terms_snapshot`, and assigns
   the deterministic id `INV-<deal_id>-<seq:03d>`. Missing terms or figures come back as
   `gaps[]`, never as invented values.
3. `--write` persists to `pipeline/finance/<invoice_id>.local.json` only when BOTH
   `finance_management` and `invoice_generation` are on; otherwise the tool returns the computed
   invoice with a `_gate` note and writes nothing. Update the deal's `invoice_refs[]` and its
   denormalized `invoice` summary only after a successful write.
4. When `render_document` is true, hand the record to `document-studio` (artifact type
   `invoice`) for a clean printable document. The document restates the record; it adds nothing.
5. Present the draft for human review with the consequential-action gate: amount, counterparty,
   terms, and an explicit ask before the human sends it.

## Output contract
The `tools/finance.py build_invoice` record (see `pipeline/finance/invoice.template.json`):
deterministic `invoice_id`, `status: "draft"`, exact-decimal `subtotal`/`total` strings,
`terms_snapshot`, derived `payment_due_date` or a gap, `human_review_required: true`, the
`_boundary` line, and `provenance.computed_by`. Plus a one-paragraph confirmation summary for
the human (what, who, how much, due when, what happens next).

## Standalone usability
With the flags off, the computed draft is still returned in full (nothing written); the creator
can copy the figures into any invoicing tool.

## Failure modes
- Flags off: `_gate` note, no write, draft still shown. Never bypassed.
- No structured terms on the deal: due date not derived; the gap says to normalize terms per
  `shared/finance-engine.md` first.
- Missing figures: line excluded from totals with a gap naming the field; the invoice is
  incomplete and says so rather than guessing.
