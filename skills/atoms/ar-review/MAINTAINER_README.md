---
file: skills/atoms/ar-review/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for ar-review so it stays stable under iteration.
---

# ar-review: Maintainer README

## Purpose
Portfolio-wide accounts-receivable aging, computed read-only by `tools/finance.py ar_scan`.
This atom interprets; the tool computes. Single-deal narrative belongs to `invoice-status`;
drafting belongs to `invoice-generate`; sending belongs to the human.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Read-only and flag-free, always available (the obligations `--scan` discipline). Never writes
  a record, never mutates a status.
- Every figure is the tool's exact-decimal string; the model never re-adds, re-rounds, or
  reconciles by hand.
- Aging bucket edges are inclusive on the left (31/61/91 boundaries pinned by the finance
  selftest); contractual due dates are never weekend-rolled, only chase action dates roll.
- Disputed invoices: excluded from outstanding totals and penalty accrual, reported separately.
  Paid invoices leave the report.
- Penalty structures beyond flat / percent-per-month are flagged, never approximated.

## Known failure modes
- Records missing due dates cannot be aged (gap, not a guess).
- A stale local store misreads as "nothing outstanding": the empty state names the store path so
  the human can tell empty from missing.

## Fragile fallbacks that must not become defaults
- Prose summaries drifting from the tool's numbers (the JSON is authoritative).
- Treating the deal's denormalized `invoice` summary as the source when standalone records exist.

## Regression cases to preserve
1. 32 days past due lands in 31_to_60 (finance selftest golden).
2. Due in 7 days: bucket current, urgency band red.
3. Paid excluded and disputed excluded from outstanding (5500.00 fixture golden).
4. Chase send-by never lands on a weekend or US federal holiday.
5. Empty book: zero totals, empty queue, no fabricated entries.
Mapped to evals/evals.json and `python3 tools/finance.py --selftest`.

## Approval-gated changes
Bucket edges, the disputed/paid handling, output schema, and any move away from read-only.

## Minority-report policy
When the standalone records and a deal's embedded summary disagree, report the standalone record
and flag the stale summary; never average or pick silently.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/finance.py --selftest` passes 102 of 102.
3. `python3 tools/sync_check.py` exits 0.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
