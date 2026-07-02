---
file: skills/atoms/obligation-extract/SKILL.md
name: obligation-extract
atom: true
description: "pulls the deliverables, deadlines, and payment terms out of a SIGNED brand contract into obligation rows (one row per distinct duty) using the obligation-row schema in shared/contract-engine.md; quotes evidence exactly and null-and-flags anything missing; hands the rows to the offline date-math tool (tools/obligations.py) rather than computing dates itself; outputs legal information only (not legal advice); does NOT rule on enforceability, compute dates, or write the register."
load:
  - shared/contract-engine.md
  - protocols/safety.md
  - protocols/no-fabrication.md
---

# obligation-extract

Read a signed brand-partnership contract and pull out every distinct duty as an obligation row:
what has to happen, who owes it, what triggers it, and when it is due. It extracts and quotes; it
does not compute dates and does not decide anything legal. The dates are computed offline, in code,
by `tools/obligations.py` (no LLM tokens). Legal information only, NOT legal advice.

## First line of every output (verbatim)

```
RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.
```

## Purpose

Once a deal is signed, the creator has a set of obligations buried in the contract: deliverables and
their due dates, revision windows, payment and kill-fee terms, exclusivity windows, usage windows.
This atom surfaces them as one clean row per duty, quoting the source, so the deadlines can be put on
a calendar and the payments tracked. It runs only on a signed contract (before signing, use
contract-review). It never invents a term and never does the date arithmetic itself: the rows it emits
are the input to `tools/obligations.py --build`, which computes send-by dates, weekend and holiday
roll-back, and urgency bands deterministically in the local compute lane.

## Inputs

```json
{
  "contract_text": "string or null -- the signed contract text",
  "deal_id": "string or null -- optional; read the signed contract from pipeline/contracts/ and the deal from pipeline/deals/",
  "focus": "string or null -- optional clause family to prioritize; all duties are still extracted"
}
```

- Supply `contract_text` OR `deal_id`. If neither, return `{ "error": "no_source" }`.
- Only extract from a signed contract. If the deal stage is before `signed`, note that review (not
  obligation extraction) is the right step and return an empty `obligations` array with a flag.
- Reuse `usage-rights-check` for the rights, exclusivity, and FTC extraction rather than re-parsing
  those clauses; add the deliverable, revision, and payment duties on top.

## Procedure

1. Resolve the signed contract from `contract_text` or the `deal_id` record.
2. Emit one row per distinct duty (never merge unrelated duties). Use the obligation-row columns from
   `shared/contract-engine.md`: `document`, `section`, `clause_family`, `obligation_type`,
   `obligated_party`, `beneficiary_or_counterparty`, `required_action`, `trigger`,
   `timing_or_deadline`, `consequence_if_stated`, `evidence_text`, `confidence`, `notes`.
3. Put the deadline as the contract states it in `timing_or_deadline` (an ISO date when the contract
   gives one, or the exact phrase such as "net 30 from delivery" when it does not). Do NOT convert or
   compute a date here; that is the offline tool's job.
4. Preserve the direction of each duty (who owes whom). Quote `evidence_text` from the contract. If a
   duty's date or term is absent, leave the field null and add a gap, never a guess.
5. Tag each row's `confidence` (`explicit`, `high`, `medium`, `low`) per the engine.
6. Set `human_review_required: true` and `recommend_counsel: true` when any term is ambiguous or a
   consequence is unclear.

## Output

```json
{
  "header": "RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.",
  "tool": "obligation-extract",
  "contract_ref": "string or null",
  "deal_id": "string or null",
  "obligations": [
    {
      "document": "string or null",
      "section": "string or null",
      "clause_family": "string",
      "obligation_type": "string -- e.g. deliverable, revision, payment, disclosure, exclusivity, usage",
      "obligated_party": "creator | brand | string",
      "beneficiary_or_counterparty": "string or null",
      "required_action": "string",
      "trigger": "string or null -- what starts the clock, e.g. signature, delivery, publish",
      "timing_or_deadline": "ISO date or the exact phrase from the contract, or null",
      "consequence_if_stated": "string or null",
      "evidence_text": "string quoted from the contract",
      "confidence": "explicit | high | medium | low",
      "notes": "string or null"
    }
  ],
  "missing": ["string -- expected duties not found (e.g. no payment date stated)"],
  "next_step": "Pass obligations[] to tools/obligations.py --build to compute send-by dates, weekend and holiday roll-back, and urgency bands (offline; no tokens).",
  "recommend_counsel": true,
  "human_review_required": true,
  "retrieval_gaps": []
}
```

Field rules:
- One row per distinct duty. Never merge; never split a single duty into duplicates.
- `evidence_text` is quoted from the source. `timing_or_deadline` is the contract's own date or phrase,
  never a computed or inferred date.
- `missing` lists duties a signed brand deal would normally have but this contract does not state; the
  corresponding row (if emitted) has null fields, never invented ones.

## Do NOT use for

- Computing send-by dates, urgency bands, or any date arithmetic (that is `tools/obligations.py`, run
  offline in the local compute lane).
- Ruling on enforceability or giving legal advice (that requires a licensed attorney).
- Extracting from an unsigned draft (use `contract-review` before signing).
- Writing the obligation register or any `pipeline/` record (the register is written by
  `tools/obligations.py` when `contract_obligations` is on; a human confirms).
- Releasing output without passing through `govern-artifact`.

## Pipeline note

Gated by the `contract_obligations` capability. Reuses `usage-rights-check`; follows
`shared/contract-engine.md` (obligation-row schema, non-advisory boundary). Obeys
`protocols/no-fabrication.md` and `protocols/safety.md`. Emits rows for `tools/obligations.py` and the
`obligation-register.template.json` store; passes output to `govern-artifact` before the spoke surfaces
it.
