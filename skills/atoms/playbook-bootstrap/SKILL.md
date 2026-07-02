---
file: skills/atoms/playbook-bootstrap/SKILL.md
name: playbook-bootstrap
atom: true
description: "proposes a starting four-tier deal-playbook from example past contracts (mode bootstrap) or flags a term the creator keeps accepting off-standard and proposes updating the default (mode nudge); every position is PROPOSED with the example that supports it plus a confidence label, clause families the examples do not support are omitted (never invented to fill a tier), and nothing is ever written to the playbook (the creator confirms, edits, and saves deal-playbook.local.json by hand); outputs legal information only (not legal advice); does NOT rule on enforceability, draft binding clause language, or write any file."
load:
  - shared/contract-engine.md
  - shared/pipeline-engine.md
  - protocols/safety.md
  - protocols/no-fabrication.md
---

# playbook-bootstrap

Help the creator stand up or tune their negotiating playbook. In `bootstrap` mode it reads example
past contracts and proposes a starting four-tier position per clause family. In `nudge` mode it reads
a set of recent deals and proposes updating a default the creator has repeatedly accepted off-standard.
Both modes are proposal-only: this atom never writes `deal-playbook.local.json`. The creator reviews,
edits, and saves it themselves. Legal information only, NOT legal advice.

## First line of every output (verbatim)

```
RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.
```

## Purpose

The four-tier playbook (standard, fallbacks, never, the_one_thing per clause family, defined in
`shared/contract-engine.md`) is what every other contract atom compares against. A creator starting
from the null template in `pipeline/user-context/deal-playbook.template.json` has nothing to compare
against, so this atom bootstraps a first draft from real examples they already have. Later, when the
creator has closed several deals, it surfaces drift: a term they keep conceding that no longer matches
their written standard. In both cases the atom only proposes; the playbook stays the creator's own
document and is only ever changed by the human.

## Proposal-only, no write

This atom produces a proposal. It never writes, saves, or modifies `deal-playbook.local.json` or any
file. Every output carries this note verbatim:

```
Confirm before saving. Nothing is written to your playbook automatically. You review, edit, and save deal-playbook.local.json yourself.
```

Changing a negotiating default has downstream consequences (every future review compares against it),
so `human_review_required` is always `true` and `recommend_counsel` defaults to `true` whenever a
proposed position touches legal exposure (usage and licensing, exclusivity, morality, territory) or the
supporting evidence is thin. This atom never rules on enforceability and never drafts binding clause
language; proposed positions are plain-language negotiating preferences, not vetted contract text.

## Inputs

```json
{
  "mode": "string -- 'bootstrap' or 'nudge' (required)",
  "examples": "array or null -- bootstrap only: past contracts/terms the creator provides, each { source_ref, contract_text or terms }",
  "deals": "array or null -- nudge only: recent deals/contracts to scan, each { deal_id or source_ref, contract_text or extracted terms }",
  "lookback": "integer or null -- nudge only: optional cap on how many recent deals to consider; never invent deals to reach it"
}
```

- `mode` is required. If it is not `bootstrap` or `nudge`, return
  `{ "error": "unknown_mode", "message": "set mode to bootstrap or nudge" }`.
- Bootstrap requires at least one example. If `examples` is empty or null, return
  `{ "error": "no_examples", "message": "provide at least one example contract or set of terms to propose positions from" }`.
- Nudge requires deals to compare. With fewer than two deals it cannot establish a repeated pattern;
  return the envelope with `proposed_updates: []`, `provisional: true`, and a note that there is not
  enough history to detect a pattern.
- Nudge reads the creator's current positions from the deal-playbook
  (`pipeline/user-context/deal-playbook.template.json`; real values in the gitignored local file). If
  it is still the null template, `current_standard` is `null`, comparison falls back to the generic
  defaults in `shared/contract-engine.md`, and output is prefixed `[PROVISIONAL: no playbook configured]`.
- For per-example clause extraction, call `usage-rights-check`; do not re-implement clause parsing.
  Do not re-implement `exclusivity-check`.

## Procedure

### Mode: bootstrap

1. For each example, extract clauses with `usage-rights-check` (rights, exclusivity, ownership, FTC,
   flags); keep the example's own wording as evidence. Never re-parse what that atom returns.
2. Group the extracted terms by the clause families in `shared/contract-engine.md`
   (`usage_licensing_rights`, `exclusivity`, `deliverables_and_revisions`, `payment_terms_and_kill_fee`,
   `ftc_disclosure`, `content_approval_and_veto`, `whitelisting_and_paid_boosting`, `morality_clause`,
   `territory`).
3. For each family the examples actually address, propose a `standard` (the most favorable position
   the examples support), any `fallbacks` (weaker positions that also appear), a `never` line only when
   an example shows a term the creator clearly resisted or that crosses a generic-default red line, and
   `the_one_thing` when one point plainly dominates. Leave a tier empty rather than inventing it.
4. Attach `evidence` to every proposed value: the `source_ref` and an exact `quote` from the example
   that supports it. Tag each value with a `confidence` label (explicit, high, medium, low) per the
   engine.
5. Omit any clause family the examples do not address and list it in `omitted_clauses` with the reason.
   Never fabricate a position to fill a family.
6. Emit the proposal in the exact shape of `pipeline/user-context/deal-playbook.template.json` so the
   creator can review, edit, and paste it. Set `human_review_required: true`, `recommend_counsel: true`
   unless every proposed position is explicit-confidence, purely operational, and multiply supported.

### Mode: nudge

1. For each deal, extract the operative terms with `usage-rights-check`; carry the exact quote and the
   `deal_id` or `source_ref` as evidence.
2. For each clause family, compare the observed value against the creator's `current_standard` from the
   playbook (or the generic default when the playbook is null).
3. Flag a family only when the same off-standard value appears in at least two of the provided deals.
   Count only observed deals; never fabricate the frequency or invent a deal.
4. For each flagged family, propose an update: state `current_standard`, `observed_value`,
   `frequency` ("N of your last M deals") with the raw `count` and `of`, the supporting `evidence`, a
   `proposed_new_standard`, a `confidence` label, and a plain-language `note`
   ("you accepted X in N of your last M deals; update your standard?").
5. Families with no repeated off-standard pattern go in `no_pattern_found`. Set
   `human_review_required: true` and `recommend_counsel: true` when any flagged family touches legal
   exposure or evidence is thin.

## Output

```json
{
  "header": "RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.",
  "tool": "playbook-bootstrap",
  "mode": "bootstrap | nudge",
  "provisional": false,
  "save_note": "Confirm before saving. Nothing is written to your playbook automatically. You review, edit, and save deal-playbook.local.json yourself.",

  "proposed_playbook": {
    "usage_licensing_rights": {
      "standard": { "value": "string or null", "evidence": [ { "source_ref": "string", "quote": "string quoted from the example" } ], "confidence": "explicit | high | medium | low" },
      "fallbacks": [ { "value": "string", "evidence": [ { "source_ref": "string", "quote": "string" } ], "confidence": "explicit | high | medium | low" } ],
      "never": [ { "value": "string", "evidence": [ { "source_ref": "string", "quote": "string" } ], "confidence": "explicit | high | medium | low" } ],
      "the_one_thing": { "value": "string or null -- null unless an example plainly supports it", "evidence": [ { "source_ref": "string", "quote": "string quoted from the example" } ], "confidence": "explicit | high | medium | low" }
    }
  },
  "omitted_clauses": [ { "clause_family": "string", "reason": "no supplied example addressed it" } ],

  "proposed_updates": [
    {
      "clause_family": "string",
      "current_standard": "string or null -- from the playbook, or null when it is the null template",
      "observed_value": "string -- the term repeatedly accepted",
      "frequency": "string -- 'N of your last M deals'",
      "count": 0,
      "of": 0,
      "evidence": [ { "deal_id": "string or null", "source_ref": "string or null", "quote": "string quoted from the deal/contract" } ],
      "proposed_new_standard": "string",
      "confidence": "explicit | high | medium | low",
      "note": "string -- 'you accepted X in N of your last M deals; update your standard?'"
    }
  ],
  "no_pattern_found": [ "string -- clause families reviewed with no repeated off-standard term" ],

  "recommend_counsel": true,
  "counsel_reason": "string or null",
  "human_review_required": true,
  "retrieval_gaps": []
}
```

Field rules:
- In `bootstrap` mode emit `proposed_playbook` and `omitted_clauses`; `proposed_updates` and
  `no_pattern_found` are omitted or empty. In `nudge` mode the reverse.
- Every `quote` is copied exactly from the supplied example, contract, or deal, or the field is null.
  Never paraphrase into a quote and never invent a term, fee, date, party, or citation.
- A clause family the examples do not support is omitted and listed in `omitted_clauses`; it is never
  filled with a guessed position.
- `frequency`, `count`, and `of` reflect only observed deals; never inflate a count to make a pattern.
- Proposed positions are plain-language negotiating preferences, explicitly not vetted and not binding
  clause language.
- `provisional` is `true` when nudge has too little history, or when comparison falls back to generic
  defaults because the playbook is the null template.

## Do NOT use for

- Writing, saving, or modifying `deal-playbook.local.json` or any file (this atom proposes only; the
  human confirms and saves).
- Ruling on enforceability, validity, or whether a proposed `never` line is legally safe (that requires
  a licensed attorney).
- Drafting binding clause language or operative contract text (`contract-draft`, Phase 2, produces
  plain-language, labeled-not-vetted terms and is not this atom).
- Reviewing a single live contract clause by clause (use `contract-review`) or the fast inbound verdict
  (use `contract-triage`).
- Comparing contract versions across amendments (use `amendment-trace`, Phase 2).
- Releasing output without passing through `govern-artifact`.

## Pipeline note

Composes `usage-rights-check` for clause extraction in both modes; follows `shared/contract-engine.md`
for the clause taxonomy, the four-tier playbook model, and confidence labels, and
`shared/pipeline-engine.md` for the deal record read in nudge mode. Reads
`pipeline/user-context/deal-playbook.template.json` (shape) and, in nudge mode, recent deals shaped by
`pipeline/deals/deal-schema.json`. Obeys `protocols/no-fabrication.md` and `protocols/safety.md`. Pass
output to `govern-artifact` before the spoke surfaces it.
