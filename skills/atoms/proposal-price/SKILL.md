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
  "benchmark_range": { "low": null, "high": null }
}
```
`cost_total` comes from a `cost-estimate` run; `rate_floor` from
`pipeline/user-context/rate-card.template.json` data (human-saved actuals) or the playbook;
`benchmark_range` from the structured rows in `canonical-sources/rate-benchmarks/benchmarks.json`
(labeled benchmarks, verify-before-quoting caveat intact).

## Core procedure
Run `python3 tools/finance.py --price <payload.json>`:
`price_floor = max(cost_floor, negotiation_floor)` where
`cost_floor = cost_total x (1 + margin_percent / 100)`. The result names which floor bound, and
flags when the floor sits above the benchmark high (expect pushback or justify scope) or below
the benchmark low (the market may bear more). A price below documented cost is flagged, never
silently accepted (`shared/finance-engine.md` pricing standardization). Present the floor, the
inputs, and the flags; the consequential-action gate (amount, counterparty, explicit yes)
applies before the human quotes anything externally.

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
