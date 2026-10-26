---
file: skills/atoms/income-ledger/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for income-ledger so it stays stable under iteration.
---

# income-ledger: Maintainer README

## Purpose
The incoming side of the money book, realized by `tools/books.py`: one record,
`pipeline/finance/income-ledger.local.json` (blank schema `income-ledger.template.json`), with
proposed and confirmed entries for cash and product received, per-payer and per-month reports, a
gift register, a 1099 check, a CSV export and a set-aside figure. Invoices and AR stay with <!-- verify: tools/books.py::export_csv -->
`tools/finance.py`; bank exports with `payment-reconcile`; spending with cost actuals.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md`, `protocols/safety.md`
  (financial boundary), and `protocols/formatting-metadata.md`.
- The boundary line opens every report, CSV and set-aside result.
- A retail price is stored only with `price_source` and `price_captured_at`, and a brand or <!-- verify: tools/books.py::validate_entry -->
  retailer price only with its page (`price_source_ref`); with no source the price is null and
  `gaps[]` names what to provide. The tool never estimates a value.
- Writes gate on `finance_management`; a refused write returns the validated entry and the gate's
  name, and touches nothing.
- `entry_id` is deterministic over date, payer (without case or extra spaces), kind, amount,
  invoice id, evidence hash, evidence reference and sequence, and for a product its item (compared
  the same way), quantity and retail price; a duplicate id is refused, so one receipt or invoice is
  one entry. A second identical payment on one day needs its
  own evidence reference or `sequence: 2`.
- An added entry is stored as `proposed` whatever status it carries; only `--confirm` confirms.
- A ledger file that does not parse (an empty file included) or has another shape stops the
  write; it is never overwritten.
- An export inside the repo must be a `.local.csv` file under `pipeline/finance/` (a `.local.csv` <!-- verify: tools/books.py::export_csv -->
  elsewhere in the repo is not gitignored), judged on the resolved path for both files; a
  relative path is read from the repo root; an existing file is replaced only when it is an
  earlier export (its first line is the boundary line).
- The selftest's file checks run from a temporary folder, so a mutant that reads a relative path
  from the current folder writes there and never into the checkout.
- Set-aside has no default percentage; the creator's number is the only input.
- Void entries leave every report; proposed and confirmed entries both count, each flagged.

## Known failure modes
- A payer named two ways (an agency paying for a brand) splits one relationship across two rows;
  the creator chooses one name per payer and the form check follows that name. Names that differ
  only in case or spacing are one payer.
- A platform's 1099 reports gross before its fee while the ledger holds the net deposit; the
  check reports the difference and leaves the explanation to the creator and the CPA.

## Fragile fallbacks that must not become defaults
- Accepting a retail price without its page "just this once".
- A default set-aside percentage.
- Treating a proposed entry as confirmed in a report without the flag that says it is proposed.

## Regression cases to preserve
1. A brand price without its page is refused; an unpriced product is accepted with a gap.
2. The gate refuses a write with `finance_management` off and no file appears.
3. The same event added twice is one entry (duplicate id refused), also with the payer re-cased;
   another event on the same day, or a `sequence: 2` repeat, is written.
4. Refunds are negative and net against cash; another tax year's entries stay out; void entries
   leave the summary.
5. The form check reports the difference between a 1099 and the ledger's cash for that payer.
6. An in-repo export that is not a `.local.csv` under `pipeline/finance/` is refused, also through
   `..`; an export never overwrites the ledger or a file that is not an earlier export; both
   written CSVs start with the boundary; an out name without `-income` keeps two files.
7. A ledger that does not parse stops the write and is left as it was.
8. Redacted output carries no amount (with or without its cents), payer, item, page reference,
   note or content reference, and keeps one row per payer when initials collide.
Mapped to evals/evals.json and `python3 tools/books.py --selftest`.

## Approval-gated changes
The entry shape, the price-provenance rule, the gate, the id derivation, the export path rule,
and anything that writes a value the creator did not provide.

## Minority-report policy
When a document and the creator disagree on an amount or a date, the entry keeps the document's
figure as proposed with the disagreement in `notes`; the creator's confirm or void settles it.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/books.py --selftest` passes.
3. `python3 tools/sync_check.py` exits 0.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
