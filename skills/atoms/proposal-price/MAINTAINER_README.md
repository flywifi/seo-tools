---
file: skills/atoms/proposal-price/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for proposal-price so it stays stable under iteration.
---

# proposal-price: Maintainer README

## Purpose
The standardized price floor: cost floor (estimate plus margin) versus negotiation floor (rate
card, then playbook), binding constraint named, benchmark flags raised. Math by
`tools/finance.py proposal_price`; the human quotes, always behind the consequential-action
gate.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md`, `protocols/safety.md`
  (financial boundary), and `protocols/formatting-metadata.md`.
- `price_floor = max(cost_floor, negotiation_floor)` with the bound named; the arithmetic is
  the tool's, never the model's.
- Every input traces to a source: the cost total to a `cost-estimate` run, the rate floor to
  human-saved rate-card data or the playbook `pricing_and_rates` standard, benchmark ranges to
  the structured `benchmarks.json` rows with their verify-before-quoting caveat.
- Null-valued (unverified) benchmark rows are never used as a range.
- A floor below documented cost is flagged, never silently accepted; a floor above the
  benchmark high is flagged, never hidden.
- Decision support only: the consequential-action gate precedes any externally quoted number,
  and `contract-draft` echoes the agreed figure rather than recomputing it.

## Known failure modes
- Pricing without an estimate (the gap says run `cost-estimate` first; nothing prices from thin
  air).
- An unset playbook pricing standard leaving the cost floor alone (said explicitly, with a
  pointer to the `pricing_and_rates` family).

## Fragile fallbacks that must not become defaults
- Treating the benchmark range as the negotiation floor (it is a flag input, not a floor).
- Prose recommendations introducing numbers absent from the tool result.

## Regression cases to preserve
1. Cost 500 at 30 percent margin: floor 650.00, bound cost_floor (finance selftest golden).
2. Rate floor 800 binds over cost floor 650 (bound negotiation_floor).
3. Floor above benchmark high raises exactly one flag.
4. Missing inputs: null floor plus a gap, never a guess.
5. Null-valued benchmark rows are skipped with a note.
Mapped to evals/evals.json and `python3 tools/finance.py --selftest`.

## Approval-gated changes
The max() floor rule, the flag semantics, output schema, and any change letting this atom quote
externally without the gate.

## Minority-report policy
When the rate card and the playbook standard disagree on the negotiation floor, surface both
with provenance and let the human choose; record the choice for deal-debrief.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/finance.py --selftest` passes 102 of 102.
3. `python3 tools/sync_check.py` exits 0.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
