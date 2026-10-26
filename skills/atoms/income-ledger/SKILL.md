---
name: income-ledger
atom: true
standalone: true
description: "records what the content business RECEIVED (brand fees, platform payouts, affiliate deposits, revenue share, gifted or loaned product) in the income ledger, and reports it per payer and per month for a tax year, as a gift register with each item's price source, as a check of each 1099 the creator enters against the ledger, as a CSV export for the CPA, and as a set-aside figure at a percentage the creator chooses. Triggers: 'log this payment', 'what did each brand pay me this year', 'list the gifted products and their retail prices', 'does this 1099 match my records', 'export my income for taxes'. All arithmetic is tools/books.py offline; entries are proposed and the human confirms. Do NOT use to draft or chase invoices (invoice-generate, ar-review), to match a bank export (payment-reconcile), to record spending (cost actuals via finance-desk), or for tax advice of any kind."
engines_required:
  - shared/finance-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/safety.md
  - protocols/formatting-metadata.md
---

# income-ledger

The incoming side of the money book. Invoices and accounts receivable say what was billed; this
atom says what arrived, in cash or in product, from whom, and when.

## First line of every output (verbatim)

```
ARITHMETIC AND RESEARCH NOTES. NOT TAX, ACCOUNTING, OR INVESTMENT ADVICE. REVIEW WITH A CPA OR TAX PROFESSIONAL BEFORE FILING OR RELYING ON CATEGORIZATIONS.
```

## When to use this skill
- "log the payment from Hearthline", "add the nailer they sent as a gift", "what did each brand
  pay me in 2026", "which gifts still have no price", "the 1099 from VidTube says 312.40, does
  that match", "export my 2026 income for the accountant", "if I set aside 25 percent, how much is
  that so far". Routed as `income_ledger`.

Do NOT use for:
- Drafting or chasing invoices (`invoice-generate`, `ar-review`, `dunning-draft`).
- Matching a bank or PayPal export to invoices (`payment-reconcile`).
- Recording spending from a receipt (`receipt-extract`, which writes cost actuals through
  `tools/books.py --add-cost`).
- Deciding what is taxable, deductible or how a gift should be valued. The atom records a retail
  price with its source; the creator and the CPA decide the treatment.

## Inputs
One of:
- an entry to add: `date` (YYYY-MM-DD, not after today), `payer`, `payer_type` (brand,
  platform, affiliate_network, agency, other), `kind` (cash, product, affiliate, ad_revenue,
  revenue_share, refund), `amount` for a cash kind (negative for a refund), and for a product
  `product.item`, `quantity` (a whole number, 1 when not given), and the retail price WITH
  `price_source` (brand_page, retailer_page, user_stated), `price_source_ref` (the page, required
  for a brand or retailer price) and `price_captured_at`; optional `deal_id`, `invoice_id`,
  `shipment_id`, `content_refs`, `evidence_ref`, `notes`, and `sequence` (2, 3 and so on) for a
  second identical payment on the same day;
- a confirm or void of an existing `entry_id`;
- a report request: `year`, and for set-aside a `percent` the creator states.

## Core procedure
Follow `shared/method.md`. Call `tools/books.py` (or the `books_add`, `books_summary` and
`books_export` MCP tools); the model never adds figures itself.

### Step 1: add or confirm
- `python3 tools/books.py --add entry.json --write` validates, normalizes (cents, `tax_year`, a
  deterministic `entry_id` that compares payer and item without case or extra spaces, so the same
  event proposed twice is one entry) and appends the entry as `proposed`, whatever status the
  input carries. A second identical payment on one day is refused as a duplicate unless it
  carries its own `evidence_ref` or `sequence: 2`. The write needs `finance_management` on;
  otherwise the validated entry comes back with the gate named and nothing is written.
- A product with a retail price but no source, or a brand or retailer price with no page, is <!-- verify: tools/books.py::validate_entry -->
  refused with the field named. A product with no price is accepted with a gap that says what to
  provide. The atom never estimates a value.
- `--propose-from-invoices` lists the paid invoices (`tools/finance.py mark_paid`) the ledger does
  not hold yet, and under `skipped` the paid ones that do not make a valid entry, with the
  reason; `--write` appends the proposals as proposed.
- After the creator's explicit yes per entry: `--confirm <entry_id>`; a mistake: `--void <entry_id>`.
  Void entries leave every report.

### Step 2: report
- `--summary --year YYYY`: per payer, cash received (refunds subtract), product value received <!-- verify: tools/books.py::payer_summary -->
  (priced items only), unpriced item count, entries still proposed; cash by month; year totals.
- `--gifts --year YYYY`: every product entry with its price, price source and page, disposition,
  and the content it was featured in; unpriced items first.
- `--form-check --year YYYY`: each form in `forms_received` against the ledger's cash total for <!-- verify: tools/books.py::form_check -->
  that payer (names compared without case or extra spaces), with the difference, plus payers with
  cash and no form. A form whose amount is not a number is listed with the problem. The atom
  reports the difference; it does not explain it.
- `--set-aside --year YYYY --percent P`: year-to-date net (cash plus priced product minus this
  year's cost actuals) times P. P is the creator's number (`25` or `25%`); there is no default.
- `--export --year YYYY [--out PATH]`: `<year>-income.local.csv` and `<year>-gifts.local.csv`
  under `pipeline/finance/exports/`, each starting with the boundary line. A relative `--out` is
  read from the repo root; a path inside the repo must be a `.local.csv` file under
  `pipeline/finance/`, and an existing file is replaced only when it is an earlier export, or the
  tool refuses it.
- Add `--redacted` (banded amounts, initialed payers and items, page references, notes and
  content references hidden) for anything quoted off this machine.

## Output contract
The tool's JSON verbatim: the boundary line first, `computed_by`, `human_review_required: true`,
and for an add the `entry` with its `entry_id`, `status`, `confidence` and `gaps[]`. Plus a short
walk-through of what was proposed and what still needs the creator (an unpriced gift, a form that
differs, an entry awaiting confirmation).

## Standalone usability
The per-payer summary and the gift register are usable as the year's income worksheet on their
own; the CSV export is what goes to the CPA.

## Failure modes
- `finance_management` off: the entry is validated and returned, nothing is written, the gate is
  named.
- A ledger file that does not parse: the write stops and the file is left as it was.
- A gift with no priced source: recorded with a gap, counted as an unpriced item, never valued.
- A 1099 that differs from the ledger: reported with the difference; the usual causes (gross
  before platform fees, a processor's 1099-K repeating a brand's 1099-NEC) are for the creator
  and the CPA.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom
carries no independent surface wiring and runs wherever the spoke that composes it runs.
