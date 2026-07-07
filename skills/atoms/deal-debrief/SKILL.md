---
file: skills/atoms/deal-debrief/SKILL.md
name: deal-debrief
atom: true
description: "after a deal closes, records why any off-standard term was accepted and PROPOSES a playbook memory update so the creator's defaults learn from real deals; proposal-only, it never writes the deal-playbook (the human confirms and saves); outputs legal information only (not legal advice); does NOT rule on enforceability or draft binding language."
load:
  - shared/contract-engine.md
  - protocols/safety.md
  - protocols/no-fabrication.md
---

# deal-debrief

Close the loop on a finished deal: capture why the creator accepted anything that was off their
standard position, and turn that into a proposed update to the playbook so next time the default is
smarter. It proposes; it never writes the playbook. Legal information only, NOT legal advice.

## First line of every output (verbatim)

```
RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.
```

## Purpose

A playbook only stays useful if it learns. When a deal closes, some terms will have landed off the
creator's standard position (a longer usage window, a lower fee, a broader exclusivity) for a real
reason (a big brand, a rush, a relationship). This atom records that reason against the term and
proposes a playbook memory update: either "this is your new normal, update the standard" or "this was
a one-off, note it as an accepted exception." It follows the same discipline as `playbook-bootstrap`:
every proposal is backed by evidence from the deal, and nothing is written to the playbook
automatically. The creator confirms, edits, and saves `deal-playbook.local.json` by hand.

The same proposal-only discipline extends to pricing (P30): from the closed deal's compensation
and, when cost actuals exist in `pipeline/finance/`, the effective hourly computed offline by
`tools/finance.py`, the debrief PROPOSES one rate-actual row for the personal rate card
(`pipeline/user-context/rate-card.template.json` schema). The human saves it to
`rate-card.local.json` or discards it; nothing is written automatically, and no figure is ever
estimated (`shared/finance-engine.md` pricing standardization).

## Inputs

```json
{
  "deal_id": "string or null -- the closed deal to debrief (read from pipeline/deals/)",
  "closed_deal_summary": "object or null -- alternative to deal_id: the agreed terms and outcome",
  "off_standard_terms": [
    { "clause_family": "string", "accepted_value": "string", "reason_accepted": "string or null" }
  ]
}
```

- Supply `deal_id` OR `closed_deal_summary`. If neither, return `{ "error": "no_source" }`.
- Read the creator's current positions from the deal-playbook (`pipeline/user-context/deal-playbook.template.json`,
  real values gitignored). If it is the null template, set `provisional: true` and compare against the
  generic defaults in `shared/contract-engine.md`; do not invent the creator's prior standard.
- Only debrief a deal that has actually closed. Never infer a `reason_accepted` the creator did not
  give; if the reason is unknown, leave it null and flag it.

## Procedure

1. Resolve the closed deal from `deal_id` or `closed_deal_summary`.
2. For each off-standard term, record the clause family, the accepted value (quoted from the deal),
   the creator's prior standard (from the playbook, or the generic default in provisional mode), and
   the stated reason (null if the creator did not give one).
3. Classify each as a proposed `update_standard` (looks like a new normal) or `note_exception` (a
   one-off), with the evidence and a confidence label. This is a suggestion, never a directive.
4. Emit the debrief and the proposed updates with a clear "confirm before saving; nothing is written
   to your playbook automatically" note. Set `human_review_required: true`.

## Output

```json
{
  "header": "RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.",
  "tool": "deal-debrief",
  "provisional": false,
  "deal_id": "string or null",
  "off_standard_findings": [
    {
      "clause_family": "string",
      "accepted_value": "string quoted from the deal",
      "prior_standard": "string -- the creator's standard, or the generic default in provisional mode",
      "reason_accepted": "string or null -- only if the creator stated it; null and flagged otherwise",
      "evidence": "string quoted from the deal or the creator's note"
    }
  ],
  "proposed_playbook_updates": [
    {
      "clause_family": "string",
      "proposal": "update_standard | note_exception",
      "suggested_value": "string",
      "rationale": "string -- grounded in the finding, labeled a suggestion",
      "confidence": "explicit | high | medium | low"
    }
  ],
  "save_note": "Confirm before saving. Nothing is written to your playbook automatically. You review, edit, and save deal-playbook.local.json yourself.",
  "recommend_counsel": false,
  "human_review_required": true,
  "retrieval_gaps": []
}
```

Field rules:
- `reason_accepted` is only populated when the creator stated a reason; otherwise null and flagged.
  Never invent a motive.
- `proposed_playbook_updates` are suggestions, never directives, and are never written to the playbook
  by this atom.
- `accepted_value` and `evidence` are quoted from the deal or the creator's own note.

## Do NOT use for

- Writing to `deal-playbook.local.json` or any `pipeline/` record (this atom proposes; the human
  saves).
- Debriefing a deal that has not closed.
- Ruling on enforceability or giving legal advice (that requires a licensed attorney).
- Drafting binding language.
- Releasing output without passing through `govern-artifact`.

## Pipeline note

Follows the proposal-only discipline of `playbook-bootstrap` and the four-tier model in
`shared/contract-engine.md`. Obeys `protocols/no-fabrication.md` (quote, never invent a reason) and
`protocols/safety.md`. Pass output to `govern-artifact` before the spoke surfaces it.

## Cross-modality
Inherits its calling spoke's class (the calling spoke's class); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
