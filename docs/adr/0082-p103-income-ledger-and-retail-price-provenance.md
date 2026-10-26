# 0082. The income ledger records what the content business received, and a retail price only with its source

- Date: 2026-10-25
- Status: Accepted

## Context

The finance bucket (`shared/finance-engine.md`, P30 and P31) records what the creator billed and
spent: standalone invoices, accounts receivable, cost estimates and cost actuals. It had no record
of what arrived: a brand fee paid without an invoice, a platform payout, an affiliate deposit, a
revenue-share remittance, or a product a brand sent for a video. Those are the figures a creator's
year-end filing is built from, and a gifted product is taxed at its market value, so the gap was
the one place the money book could not answer "who paid me, how much, and what did they send".

Two forces shape the record. First, the engine's boundary: the system does arithmetic and keeps
records and never advises on tax treatment, which rules out the system valuing a gift. Second,
`protocols/no-fabrication.md`: a figure the creator did not provide and no document shows is a
null with a gap, not an estimate.

## Decision

1. One new record, `pipeline/finance/income-ledger.local.json` (blank schema
   `income-ledger.template.json`, the only tracked piece, on the invariant 20 allowlist), owned by
   `tools/books.py`: one entry per payment or product received, with payer, payer type, kind,
   amount for a cash kind, product fields for a product, links to deal, invoice, shipment and
   content, the evidence file and its hash, a `proposed`, `confirmed` or `void` status, and
   `forms_received[]` for the 1099 check.
2. Provenance over valuation: a product's `retail_price` is stored only with `price_source`
   (`brand_page`, `retailer_page`, `user_stated`) and `price_captured_at`, and a brand or
   retailer price only with the page it was read from (`price_source_ref`). Without those the
   price is null and `gaps[]` names what to provide. The tool records a retail price the human
   confirms; what that price means for a return is the creator's and the CPA's decision.
3. Proposal, then confirmation: entries proposed from paid invoices, approved receipts or a
   session land as `proposed`; the human's explicit confirm makes them `confirmed`. Reports count
   both and flag the proposed ones; void entries count nowhere.
4. The same lane as `tools/finance.py`: stdlib, exact Decimal, `CREATOR_OS_ROOT` sandbox, reads
   always on, writes behind `finance_management`, redaction for anything quoted off the machine,
   and the boundary line on every report, CSV and set-aside result. The set-aside figure has no
   default percentage; the human's number is the only input.
5. A deterministic `entry_id` (`BK-<yyyymmdd>-<8 hex>` over date, payer and item compared
   without case or extra spaces, kind, amount, invoice id, evidence hash, evidence reference and
   sequence) makes a receipt or invoice proposed twice one entry. A second identical payment on
   one day is a different event only when the human says so, by its evidence reference or by
   `sequence` 2, 3 and so on; without either it is refused as a duplicate.
6. Exports go under `pipeline/finance/exports/` as `.local.csv` files. An export path inside the
   repo must lie under `pipeline/finance/`, which git ignores, and carry `.local.` in its name
   (the bank-export reader's name rule); a `.local.csv` elsewhere in the repo is not ignored by
   git, so the location is part of the rule.

## Consequences

- The `income-ledger` atom (standalone, composed by `finance-desk`) and three MCP tools
  (`books_add`, `books_summary`, `books_export`) are the handoff; a session never adds the figures.
- The ledger is local: it is not on the profile mirror's list, so nothing from it reaches the
  Drive hub unless the human exports it on purpose.
- Not done here: receipt and remittance capture from the hub Inbox (the next package), a
  dashboard view, optical character recognition of photographed receipts, and a price-capture
  assist that reads a brand's page; each arrives flag-gated in its own change.
- Verified by `python3 tools/books.py --selftest` (run with the Windows path stand-in),
  the committed mutation rows for `tools/books.py` in `tools/file_hash.py`, drift invariant 20
  (the template is the only tracked file under `pipeline/finance/` this change adds) and
  `tools/secret_scan.py` over the template (no figure in it).
