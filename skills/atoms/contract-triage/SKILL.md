---
file: skills/atoms/contract-triage/SKILL.md
name: contract-triage
atom: true
description: "gives an inbound brand-partnership contract a fast GREEN/YELLOW/RED verdict before a full review: scans for hidden obligations and likely deal-breakers and routes the offer; outputs legal information only (not legal advice) per protocols/safety.md; does NOT rule on enforceability, negotiate, or draft language."
load:
  - shared/contract-engine.md
  - protocols/safety.md
  - protocols/no-fabrication.md
---

# contract-triage

Give an inbound brand-partnership contract a fast, source-grounded verdict so the creator knows
whether to relax, slow down, or stop before investing in a full clause-by-clause review. This atom
routes; it does not resolve. It outputs legal information only, NOT legal advice.

## First line of every output (verbatim)

```
RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.
```

## Purpose

A creator fields more offers than they can deep-read. Triage answers one question quickly and
consistently: is this a standard offer (GREEN), does something need attention before signing
(YELLOW), or is there a likely deal-breaker (RED)? It surfaces the two things that most often hide in
a friendly-looking sponsorship: an obligation buried where the creator will not look (a non-disclosure
or non-compete tucked into the terms) and a clause on the creator's `never` list. It reads the
creator's playbook first so the verdict reflects the creator's actual positions, not generic ones.

## Inputs

```json
{
  "contract_text": "string or null -- the raw contract or offer text",
  "deal_id": "string or null -- optional; read the linked contract from pipeline/contracts/ instead of raw text",
  "deal_context": {
    "fee": "number or null -- the stated fee, if known; never invent one",
    "category": "string or null -- product category, for exclusivity relevance",
    "brand_name": "string or null"
  }
}
```

- Supply `contract_text` OR `deal_id`. If neither is present, return `{ "error": "no_source" }`.
- Read the creator's positions from `pipeline/user-context/deal-playbook.template.json` (real values
  in the gitignored `.local.json`). If the playbook is still the null template, prefix the output with
  `[PROVISIONAL: no playbook configured]` and judge against the generic creator-side defaults in
  `shared/contract-engine.md`.
- Call `usage-rights-check` on the text to get the structured rights, exclusivity, ownership, and FTC
  extraction rather than re-parsing. Do not read any deal or contract record other than the one named.

## Procedure

1. Extract clauses via `usage-rights-check`.
2. Scan for hidden obligations: any duty the creator would not expect in a content sponsorship
   (non-disclosure, non-compete, perpetual or exclusive license, right of first refusal, automatic
   renewal, assignment of copyright). Any hidden obligation sets the verdict to YELLOW at minimum.
3. Scan for deal-breakers: terms on the creator's `never` list, or high legal-risk terms (perpetual
   worldwide rights for a flat fee, uncapped indemnity, open-ended exclusivity across the whole niche).
   Any deal-breaker sets RED.
4. Score relevance and importance separately from the verdict (per `shared/contract-engine.md`), and
   record why. Relevance is how squarely this matches the creator's active work; importance is how
   much it matters commercially if true. Keep them separate and separate from the verdict.
5. Emit the verdict, the reasons, and what a full review should focus on. Set
   `human_review_required: true` and `recommend_counsel: true` unless the verdict is GREEN with no
   flags.

## Output

```json
{
  "header": "RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.",
  "tool": "contract-triage",
  "provisional": false,
  "verdict": "GREEN | YELLOW | RED",
  "reasons": [
    { "point": "string -- one clause or issue", "evidence_text": "string quoted from the contract, or null if this is a missing-term finding", "confidence": "explicit | high | medium | low" }
  ],
  "hidden_obligations_found": [
    { "obligation": "string", "evidence_text": "string quoted from the contract", "why_it_matters": "string" }
  ],
  "deal_breakers_found": [
    { "term": "string", "evidence_text": "string quoted from the contract", "playbook_basis": "string -- the never-line or high-risk reason" }
  ],
  "relevance": "none | low | medium | high | critical",
  "importance": "none | low | medium | high | critical",
  "focus_the_full_review_on": ["string"],
  "recommend_counsel": true,
  "counsel_reason": "string or null",
  "human_review_required": true,
  "retrieval_gaps": []
}
```

Field rules:
- `verdict` is the max of the signals: RED if any deal-breaker, else YELLOW if any hidden obligation
  or attention flag, else GREEN.
- `hidden_obligations_found` and `deal_breakers_found` are empty arrays when none are found. Do not
  invent items to look thorough.
- Every `evidence_text` is quoted from the source. A missing-term finding has `evidence_text: null`
  and is described as missing, never invented.
- `relevance` and `importance` are independent of the verdict and of each other.

## Do NOT use for

- Ruling on whether a term is enforceable, or giving legal advice of any kind (that requires a
  licensed attorney).
- The full clause-by-clause review with dual severity (use `contract-review`).
- Negotiating, countering, or drafting language (use `escalation-brief` to draft the ask; drafting an
  agreement is Phase 2 and always labeled not-vetted).
- Writing anything back to `pipeline/contracts/` or `pipeline/deals/` (a CRM write atom does that).
- Releasing output to the user without passing through `govern-artifact`.

## Pipeline note

Reuses `usage-rights-check` for extraction and follows `shared/contract-engine.md`. Obeys
`protocols/no-fabrication.md` (null-and-flag, quote exactly) and `protocols/safety.md` (legal
information only). Pass output to `govern-artifact` before the spoke surfaces it.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
