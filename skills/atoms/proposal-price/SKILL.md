---
name: proposal-price
atom: true
standalone: true
description: "computes a standardized price floor for a proposal or contract draft: the cost floor (estimate total plus margin) versus the negotiation floor (personal rate card, then playbook pricing standard), with the binding constraint named and benchmark-range flags raised; math by tools/finance.py proposal_price. Decision support only: the consequential-action gate applies before any number is quoted to a brand. Do NOT use to build the cost estimate (cost-estimate), to fill a rate card for a media kit (rate-card-fill), or to draft the agreement language (contract-draft)."
engines_required:
  - shared/finance-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/safety.md
  - protocols/formatting-metadata.md
---

# proposal-price

What should I charge, grounded. One operation: cost data and rate positions in, a price floor
with its binding constraint named out. The human quotes; this atom informs.

## When to use this skill
- "what should I charge for this", "price this proposal", "is 2000 enough for this scope",
  "build the pricing for the pitch", routed as `proposal_price`. Output feeds
  `pitch-paragraph`, `contract-draft`, and the playbook `pricing_and_rates` posture.

Do NOT use for:
- Building the underlying cost estimate (use `cost-estimate` first).
- Presenting per-format rates in a media kit (use `rate-card-fill`).
- Drafting agreement language (use `contract-draft`; it echoes the agreed number, never
  computes one).

## Input
```json
{
  "cost_total": null,
  "margin_percent": null,
  "rate_floor": "the negotiation floor: personal rate card entry for the format, else the playbook pricing_and_rates standard, else null",
  "format": "optional rate-card format key (e.g. youtube_dedicated_long_form); resolves rate_floor from the rate card when rate_floor is absent",
  "benchmark_range": { "low": null, "high": null }
}
```
`cost_total` comes from a `cost-estimate` run; `rate_floor` from the personal rate card
(`rate-card.local.json` under pipeline/finance/, gitignored; template
`pipeline/finance/rate-card.template.json`) or the playbook; `benchmark_range` from the structured rows in
`canonical-sources/rate-benchmarks/benchmarks.json` (labeled benchmarks, verify-before-quoting
caveat intact). Structure-only lever records exist there for usage-rights and exclusivity uplifts
(`uplift-paid-usage-30d`, `uplift-paid-usage-90d`, `uplift-category-exclusivity-30d`) and for
short-form tier rates (`rate-tiktok-dedicated-50-100k`, `rate-reel-50-100k`): all carry null values
with `needs_research: true` until a cited research pass fills them, so pricing null-flags them by
name instead of quoting a range.

## Core procedure
Run `python3 tools/finance.py --price <payload.json>`:
`price_floor = max(available floors)` where `cost_floor = cost_total x (1 + margin_percent / 100)`
(only when both cost inputs are supplied) and `negotiation_floor = rate_floor`. Cost inputs are
OPTIONAL: a rate-floor-only run works and carries a `no_cost_basis` gap (true margin unknown; run
cost-estimate and re-price). Supplying only one cost input yields a `partial_cost_inputs` gap,
never a guessed value. The result names which floor bound, and flags when the floor sits above the
benchmark high (expect pushback or justify scope) or below the benchmark low (the market may bear
more). A price below documented cost is flagged, never silently accepted
(`shared/finance-engine.md` pricing standardization).

For a multi-deliverable package (e.g. a long-form video plus a TikTok), run
`python3 tools/finance.py --price-package <payload.json>` with
`{line_items: [{label, rate_floor | cost inputs, benchmark_range?}], package_benchmark_range?}`:
per-item floors are summed into `package_floor`; an item with no computable floor is listed in
`unpriceable_items` and EXCLUDED from the sum with a package-level gap (never treated as 0), so the
package floor is explicitly an understatement until every item is priced.

Present the floor(s), the inputs, and the flags; the consequential-action gate (amount,
counterparty, explicit yes) applies before the human quotes anything externally.

## Output contract
The `proposal_price` result verbatim (`price_floor`, `bound`, `cost_floor`,
`negotiation_floor`, `benchmark_range`, `flags`, `computed_by`, `gaps`) plus a short prose
recommendation that never invents a number: every figure traces to the estimate, the rate card,
the playbook, or a labeled benchmark.

## Standalone usability
Given a cost total and a margin, the floor alone tells the creator the minimum viable quote for
the scope, with the reasoning attached.

## Failure modes
- No cost estimate yet: `gaps[]` says to run `cost-estimate` first; nothing is priced from thin
  air.
- No rate card entry and a null playbook standard: the cost floor stands alone and the output
  says the negotiation posture is unset (point at the playbook `pricing_and_rates` family).
- Benchmark rows with null values (unverified) are never used as a range; the flag logic simply
  skips them and says so.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
