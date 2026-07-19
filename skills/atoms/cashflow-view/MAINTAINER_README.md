---
file: skills/atoms/cashflow-view/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for cashflow-view so it stays stable under iteration.
---

# cashflow-view: Maintainer README

## Purpose
Weekly cash-movement view computed by `tools/finance.py cashflow` from open invoices, dated
scheduled inflows, and dated estimate outflows. Movement, never a balance. AR chasing belongs
to `ar-review`; statistical forecasting to the `forecast` atom.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md`, `protocols/safety.md`
  (financial boundary), and `protocols/formatting-metadata.md`.
- All bucketing and arithmetic is the tool's; the model never re-buckets, re-adds, or rounds.
- Overdue receivables are NEVER placed in a week (collection timing unknown); undated items are
  totaled separately with gaps; nothing is guessed into a bucket.
- The movement-not-balance note stays on every output; no opening balance is ever invented.
- Redacted mode (banded amounts, initialed names) is used for anything leaving the machine;
  redacted output is never fed back into bookkeeping.
- Read-only; no flag gates the view (obligations --scan discipline).

## Known failure modes
- A trend line from the forecast atom being read as deterministic (it carries its own
  computation_source label; keep the two visually separate).
- Scheduled rows with triggers not yet mapped to dates (deal-resourcing's job) silently
  shrinking the view: the gaps name each one.

## Fragile fallbacks that must not become defaults
- Prose summaries citing figures absent from the tool result.
- Treating beyond-horizon inflows as available cash this quarter.

## Regression cases to preserve
1. Due-in-7-days invoice lands in week 1; scheduled deposit in its dated week (finance
   selftest goldens).
2. Overdue receivable excluded with the overdue_receivables gap.
3. Undated outflow and undated scheduled row totaled separately with gaps.
4. Paid and disputed invoices never appear.
5. Redacted output: bands with "to", initials, `_redacted: true`, original untouched.
Mapped to evals/evals.json and `python3 tools/finance.py --selftest` (99 checks).

## Approval-gated changes
Bucket width (weekly), the exclusion rules (overdue/undated/beyond-horizon), output schema,
the redaction key sets, and any move away from read-only.

## Minority-report policy
When a scheduled row and an issued invoice describe the same expected payment, count the
invoice and flag the duplicate; never both.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/finance.py --selftest` passes 102 of 102.
3. `python3 tools/sync_check.py` exits 0.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
