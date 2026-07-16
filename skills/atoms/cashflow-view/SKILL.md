---
name: cashflow-view
atom: true
standalone: true
description: "a deterministic cash-movement view over the next 90 days (or any horizon): expected inflows from open invoice due dates and dated scheduled invoices, outflows from dated cost estimates, weekly buckets, all computed offline by tools/finance.py cashflow. Overdue receivables and undated items are reported separately with gaps, never guessed into a week; the view is cash MOVEMENT, not a bank balance. Supports redacted output (banded amounts, initialed brands) for anything that leaves the machine. Do NOT use for AR aging and chasing (ar-review), statistical revenue forecasting from historical series (the forecast atom), or drafting invoices (invoice-generate)."
engines_required:
  - shared/finance-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/safety.md
  - protocols/formatting-metadata.md
---

# cashflow-view

When money is expected to arrive and leave, week by week, from records only.

## When to use this skill
- "what does my cash look like for the next 90 days", "when does the Hearthline money land",
  "can I afford the workshop build next month", routed as `cashflow_projection`.

Do NOT use for:
- Who is late and how to chase them (use `ar-review`).
- Trend forecasting from historical revenue series (use the `forecast` atom; its output can be
  attached to this view as a labeled trend, `computation_source` intact).
- Anything presented as a bank balance. This is movement over the horizon; the opening balance
  is not known here and is never invented.

## Input
```json
{
  "horizon_days": 90,
  "scheduled": [ { "amount": null, "due_date": null, "label": "" } ],
  "estimates": [ { "estimate_id": "", "totals": { "grand": null }, "expected_date": null } ],
  "redacted": false
}
```
Open invoices are read from `pipeline/finance/` automatically; `scheduled` rows come from
deal-resourcing's invoice schedule (triggers already mapped to dates); `estimates` from
cost-estimate records, dated by the human.

## Core procedure
Run `python3 tools/finance.py --cashflow [inputs.json] [--horizon-days N] [--redacted]`. The
tool buckets inflows and outflows into weeks (Decimal, `computed_by`), totals overdue
receivables, beyond-horizon inflows, and undated outflows SEPARATELY with gaps naming the fix,
and reports net movement with a running total. Read-only, no flag. Interpret for the human:
the tight weeks, what is riding on overdue collections, and which numbers are undated. When
output will leave the machine (a screenshot, a shared summary), use `redacted: true` (bands
plus initials) per `shared/finance-engine.md`.

## Output contract
The `cashflow` result verbatim: `weeks[]{week_start, inflow, outflow, net, running_net}`, <!-- verify: tools/finance.py::cashflow -->
`totals{inflow, outflow, net_movement}`, `overdue_receivables`, `beyond_horizon`,
`undated_outflows`, the movement-not-balance note, `computed_by`, `gaps[]`. Plus a short prose
read. Every figure is the tool's; the model never re-buckets or re-adds.

## Standalone usability
The weekly table alone answers "when does money move" with no other skill involved.

## Failure modes
- No open invoices and nothing scheduled: an honest all-zero horizon, not a fabricated pipeline.
- Undated estimates or scheduled rows: totaled separately with gaps, never assigned a week.
- Overdue receivables: excluded from buckets (collection timing is unknown) and pointed at
  ar-review; never counted as expected cash on a made-up date.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
