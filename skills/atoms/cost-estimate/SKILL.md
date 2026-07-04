---
name: cost-estimate
atom: true
standalone: true
description: "builds a projected-cost estimate for a future project or proposal: sourced line items (vendor quote, cost library, cost research, or labeled assumption), expense vs capex classification, and time cost from production phases at the rate card's effective hourly (or a labeled assumption); totals computed offline by tools/finance.py cost_rollup. Carries the CPA boundary on every output. Do NOT use to record actual spend (cost-actuals records), to set a price (proposal-price), to plan production tasks (production-task), or to compute deal ROI (roi-metric)."
engines_required:
  - shared/finance-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/safety.md
  - protocols/formatting-metadata.md
---

# cost-estimate

What will this project actually cost. Line items with named sources, capex split, time cost,
and totals from `tools/finance.py`; unknown costs stay null and flagged, never guessed.

## First line of every output (verbatim)

```
ARITHMETIC AND RESEARCH NOTES. NOT TAX, ACCOUNTING, OR INVESTMENT ADVICE. REVIEW WITH A CPA OR TAX PROFESSIONAL BEFORE FILING OR RELYING ON CATEGORIZATIONS.
```

## When to use this skill
- "what would this project cost", "estimate the materials and time for the workshop tour",
  "price out what I need to buy", "build the cost side of this proposal", routed as
  `cost_estimate`.

Do NOT use for:
- Recording money actually spent (that is the cost-actuals record in `pipeline/finance/`).
- Setting the price to charge (use `proposal-price`; it consumes this estimate).
- Task scheduling (use `production-task`) or deal ROI from a given rate (use `roi-metric`).

## Input
```json
{
  "project_ref": "string",
  "deal_id": "string or null",
  "line_items": [
    { "category": "production_materials | equipment_capex | software_subscriptions | contractor_labor | travel | shipping_and_fees",
      "description": "", "quantity": 1, "unit_cost": null, "amount": null, "is_capex": false,
      "source": "quote | cost_library | cost_research | assumption", "citation": null }
  ],
  "time": { "phases": [ { "phase": "", "hours": null } ], "hourly_rate": null }
}
```

## Core procedure
1. Assemble line items. Every figure names its source: a vendor `quote` the human supplied, a
   dated `cost_library` entry (`canonical-sources/cost-library/costs.json`), a cited
   `cost_research` finding (the cost-researcher agent, only when the `cost_research` flag is on
   and the operator dispatched it), or a labeled `assumption`. A cost nobody knows stays null.
2. Classify each line expense vs capex per the taxonomy in `shared/finance-engine.md`
   (organizational classification, not a tax determination; the boundary line applies).
3. Time cost: phase hours come from the human or a labeled estimate tied to `production-task`
   phases; the hourly rate is the personal rate card's `effective_hourly` when present, else an
   explicit labeled assumption. Never presented as measured when assumed.
4. Run `python3 tools/finance.py --rollup <estimate.json>`: category sums, expense/capex split,
   time cost, and the grand total, all exact-decimal with `computed_by`. Null amounts come back
   as `gaps[]` and are excluded from totals, never guessed into them.
5. Persist as a `pipeline/finance/` cost-estimate record only when `finance_management` is on;
   otherwise return the estimate for the human to save.

## Output contract
The cost-estimate record shape (`pipeline/finance/cost-estimate.template.json`): sourced
`line_items[]`, `time` phases, `totals{expense, capex, time_cost, grand, computed_by}`,
`human_review_required: true`, the boundary line, and `gaps[]` naming every unknown. Plus a
short prose read: the biggest cost drivers and which numbers are assumptions.

## Standalone usability
The estimate alone is a usable shopping-and-hours budget; `proposal-price` turns it into a
price floor when asked.

## Failure modes
- No cost data for a line: null plus a gap naming the fix (quote it, look it up, or label an
  assumption); the total says what it excludes.
- No hourly rate anywhere: time cost is null with a gap, not a silent zero.
- cost_research flag off: web research is not dispatched; the degrade note says estimates use
  quotes, the library, and labeled assumptions only.
