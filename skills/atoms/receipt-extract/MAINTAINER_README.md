---
file: skills/atoms/receipt-extract/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for receipt-extract so it stays stable under iteration.
---

# receipt-extract: Maintainer README

## Purpose
The Inbox handler for `invoice_receipt`, realized by `tools/receipt_extract.py`: one receipt,
remittance or payout statement becomes one proposed entry, written by `tools/books.py`
(`add_entry` for money received, `add_cost_actual` for money paid) only after the person's yes.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md`, `protocols/safety.md`
  (financial boundary), and `protocols/formatting-metadata.md`.
- Proposal-only: the tool writes nothing; the write is the person's tick or yes.
- The extracted text runs through the offline injection tier; QUARANTINE or BLOCK withholds the <!-- verify: tools/receipt_extract.py::extract -->
  record.
- A field the text does not show is null with a gap; `payer_type` is always the person's choice.
- Amounts are exact decimals in cents; a name or line description is cut at 120 characters with
  control characters dropped.
- The record cites the file by its hub-relative path and its sha256; one receipt is one
  cost-actuals entry (a second write of the same sha256 is refused).

## Known failure modes
- A receipt that prints the total on a line the patterns do not name: `uncertain`, total asked.
- A US date read month first (03/05/2026 is March 5).

## Fragile fallbacks that must not become defaults
- Guessing the direction from the file name.
- Filling `payer_type` with "brand" because most payers are brands.

## Regression cases to preserve
1. A typed receipt: total, date, vendor, last four, lines reconciling, `exact`, a cost-actuals record.
2. A remittance email: money received, the header date, an income-ledger record with the hash.
3. Flagged text gets no record; a file over 2 MB is not read.
Mapped to evals/evals.json and `python3 tools/receipt_extract.py --selftest`.

## Approval-gated changes
The confidence rule, the direction phrases, the record shapes, and anything that writes.

## Minority-report policy
When the document and the person disagree, the person's correction is written and the proposal's
reading stays in the wizard's confirmation text.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/receipt_extract.py --selftest` and `python3 tools/books.py --selftest` pass.
3. `python3 tools/sync_check.py` exits 0.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
