---
file: skills/atoms/cost-estimate/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for cost-estimate so it stays stable under iteration.
---

# cost-estimate: Maintainer README

## Purpose
Projected costs for a future project: sourced line items, expense vs capex, time cost. Totals
by `tools/finance.py cost_rollup`; sources named on every line; the CPA boundary on every
output. Actual spend is the cost-actuals record; pricing is `proposal-price`.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md`, `protocols/safety.md`
  (financial boundary), and `protocols/formatting-metadata.md`.
- Every line names its source (`quote | cost_library | cost_research | assumption`);
  assumptions are labeled, cost_research findings are cited, and a cost nobody knows stays null
  with a gap. No figure is ever invented or presented above its evidence.
- Totals come from `cost_rollup` only (exact Decimal, `computed_by`); nulls are excluded from <!-- verify: tools/finance.py::cost_rollup -->
  totals and said so, never guessed in.
- Capex vs expense follows the engine taxonomy and is organizational, not a tax determination;
  the verbatim boundary line leads every output.
- Time cost: hours from the human or a labeled estimate; hourly rate from the rate card's
  `effective_hourly` or a labeled assumption. Assumed values never read as measured.
- Record writes gate on `finance_management`; the estimate is always returned regardless.

## Known failure modes
- The cost library's null-priced placeholder entries misread as free items (they are excluded
  with a gap, never zero).
- Stale `as_of` dates on library entries quoted as current (surface the date).

## Fragile fallbacks that must not become defaults
- Assumption-sourced lines dominating an estimate without the prose read saying so.
- Skipping the boundary line on outputs that show capex classification.

## Regression cases to preserve
1. Category sums, expense/capex split, and time cost match the finance selftest goldens
   (150.47 / 800.00 / 450.00 / grand 1400.47).
2. A null-amount line yields a missing_amount gap and is excluded from totals.
3. No hourly rate: time cost null plus gap, never silent zero.
4. cost_research flag off: no web dispatch; degrade note names the remaining sources.
5. Boundary line verbatim on every output.
Mapped to evals/evals.json and `python3 tools/finance.py --selftest`.

## Approval-gated changes
The source enum, the category taxonomy, output schema, and any path that lets an unlabeled
figure into a total.

## Minority-report policy
When two sources price the same item differently (quote vs library vs research), keep both with
their dates and citations and let the human pick; never average silently.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/finance.py --selftest` passes 99 of 99.
3. `python3 tools/sync_check.py` exits 0.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
