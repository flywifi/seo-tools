---
file: skills/atoms/payment-reconcile/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for payment-reconcile so it stays stable under iteration.
---

# payment-reconcile: Maintainer README

## Purpose
Bank-export-to-invoice matching, realized by `tools/finance.py reconcile` (proposal-only) and
`mark_paid` (gated write after human confirmation). AR reporting stays with `ar-review`; <!-- verify: tools/finance.py::mark_paid -->
analytics CSVs with `data-query`.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md`, `protocols/safety.md`
  (financial boundary), and `protocols/formatting-metadata.md`.
- STRUCTURAL: `_csv_rows` refuses any in-repo CSV whose name lacks `.local.` — this refusal is <!-- verify: tools/finance.py::_csv_rows -->
  the privacy boundary and is never weakened, worked around, or made optional.
- Proposal-only: reconcile never changes a record. `mark_paid` runs only after an explicit
  human yes per invoice, and only with `finance_management` on.
- Matching is the tool's (tiers, greedy best-tier assignment, one invoice at most once); the
  model never pairs rows to invoices by eye.
- Unparseable rows are gaps with the mapping fix named; ambiguity is surfaced, never resolved
  silently.
- Paid and disputed invoices are never proposal candidates.

## Known failure modes
- Exotic export layouts defeating the column heuristics (explicit `mapping` is the remedy).
- Partial payments: no proposal tier models them yet; the near-miss lands in `uncertain` or
  unmatched, flagged for the human.

## Fragile fallbacks that must not become defaults
- Widening `amount_tolerance` to force matches.
- Marking paid from a `probable` proposal without the per-invoice human yes.

## Regression cases to preserve
1. Exact tier requires amount + window + brand substring (finance selftest goldens).
2. US dates, $ and comma amounts, and parenthesized negatives all parse.
3. One invoice, two candidate rows: single proposal, best tier wins.
4. In-repo non-`.local.` CSV refused (PermissionError); outside-repo CSV allowed.
5. mark_paid refused with the flag off, record untouched.
Mapped to evals/evals.json and `python3 tools/finance.py --selftest` (99 checks).

## Approval-gated changes
The tier definitions, the greedy assignment rule, the structural CSV refusal, output schema,
and anything that lets a write happen without both the flag and the human yes.

## Minority-report policy
When one deposit could plausibly settle either of two invoices, propose the better tier and
list the alternative in the walk-through; the human picks, the tool never does.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/finance.py --selftest` passes 105 of 105.
3. `python3 tools/sync_check.py` exits 0.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
