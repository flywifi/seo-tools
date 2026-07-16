---
name: deal-status
atom: true
standalone: true
description: "answers 'where are we with the Lumen deal?' by reporting a deal's lifecycle status VERBATIM from the record in pipeline/deals/: current stage, the latest stage_history event, payment_due_date, and the denormalized invoice.status. It resolves a fuzzy brand phrase to the account first (via account-resolve) and lists that account's deals, or takes an explicit deal_id. It does NO money math (aging, penalties, and totals are ar-review / tools/finance.py) and NO stage transitions (that is deal-pipeline, evidence-gated). Read-only; every field is quoted from the record, never inferred."
engines_required:
  - shared/pipeline-engine.md
protocols:
  - protocols/no-fabrication.md
---

# deal-status

The "where does this deal stand" read: the stage and the last thing that happened, straight from
the record. No arithmetic, no advancing, no interpretation.

## When to use this skill
- "where are we with that lightbulb company contract?", "what stage is the Hearthline deal?",
  "did we invoice Lumen yet?" reached through the deal-pipeline `deal_status` action. <!-- verify: tools/accounts.py::deal_status -->

Do NOT use for:
- Advancing or regressing a deal stage (that is `deal-stage-advance` in deal-pipeline, which is
  evidence-gated).
- Money math: what is owed, days late, accrued penalties, or portfolio totals (that is
  `ar-review` / `tools/finance.py`).
- Reading account contacts (use `contact-lookup`) or scoring account health (`account-health`).
- Any write. This atom reads `pipeline/deals/*.local.json`; it never edits a deal.

## Input
```json
{
  "query": "string or null -- a brand phrase; resolved to an account, then its deals are listed",
  "deal_id": "string or null -- an explicit deal id, bypassing resolution"
}
```
Provide exactly one of `query` or `deal_id`.

## Core procedure
1. If `deal_id` is given, read that deal. Otherwise call `tools/accounts.py --deal-status
   "<query>"`, which resolves the brand through the shared resolver and lists that account's
   deals. An unresolved brand returns no deals, only the resolver's candidates.
2. For each deal, report VERBATIM: `stage`, the last entry in `stage_history`, `payment_due_date`,
   and `invoice.status`. The model quotes these; it never computes a date or infers a stage the
   record does not state.
3. If the account resolves but has no deal records, or the deal_id is unknown, return a gap that
   says so. Never fabricate a stage or a date.

## Output contract
```json
{
  "query": "",
  "deal_id": "",
  "deals": [{
    "deal_id": "",
    "brand_name": "",
    "stage": "the record's stage, verbatim",
    "latest_stage_event": "the last stage_history entry, or null",
    "payment_due_date": "verbatim or null",
    "invoice_status": "the denormalized invoice.status, verbatim or null"
  }],
  "computed_by": "tools/accounts.py.deal_status",
  "gaps": []
}
```

## Standalone usability
Given a resolvable brand or a deal id, the atom returns the deal's current standing on its own.

## Failure modes
- Ambiguous or unknown brand: no deals returned, the resolver candidates are surfaced for the
  human to choose.
- Account resolves but has no deals, or the deal_id is unknown: a gap says so; no stage is
  invented.
- A caller wanting "how much is overdue": out of scope; route to `ar-review` for the money math.

## Cross-modality
Inherits its calling spoke's class (Class B); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
