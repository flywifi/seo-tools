---
file: skills/atoms/escalation-brief/SKILL.md
name: escalation-brief
atom: true
description: "turns flagged contract findings into a decision-ready brief for the creator or their attorney: for each issue it states the point, the exact contract quote, the accept/counter/walk options, and a decide-by date; drafts the ask but NEVER sends it; passes the consequential-action gate; outputs legal information only (not legal advice)."
load:
  - shared/contract-engine.md
  - protocols/safety.md
  - protocols/no-fabrication.md
---

# escalation-brief

Turn the flagged findings from triage, review, or the legal-requirement check into a short,
decision-ready brief: one page the creator can act on or hand to an attorney. It drafts the ask; it
never sends anything and never commits the creator. Legal information only, NOT legal advice.

## First line of every output (verbatim)

```
RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.
```

## Purpose

A review can produce many findings; a decision needs a short list framed as choices. For each item
worth raising, this atom states the issue in one sentence, quotes the exact clause, lays out the
realistic options (accept as is, counter with a specific plain-language change, or walk away) with the
trade-off of each, and proposes a decide-by date. The output is a brief for a human to use in a
negotiation or an attorney conversation. It is never a message that gets sent, and it never marks the
deal as agreed.

## The consequential-action gate

Anything that leads to signing, sending, or committing money is a consequential action. This atom
always: states plainly that the next step has legal and financial consequences; produces the brief as
material to review, not to transmit; and requires an explicit human yes before any downstream step
acts on it. Agents never send the ask, counter the brand, or advance the deal stage. The brief exists
to inform the human, who decides.

## Inputs

```json
{
  "findings": "array -- flagged findings from contract-triage, contract-review, or legal-requirement-check (each with a point/clause, evidence_text, and severity)",
  "deal_context": {
    "brand_name": "string or null",
    "response_deadline": "string or null -- an ISO date the brand asked for a response by, if stated; never invent one",
    "relationship": "string or null -- new, returning, or unknown"
  }
}
```

- `findings` is required and non-empty; if empty, return `{ "note": "no flagged findings to escalate" }`.
- Do not invent a `response_deadline`. If none is provided, propose a reasonable decide-by based on
  urgency band (per `shared/contract-engine.md`) and label it as a suggestion.

## Procedure

1. For each flagged finding, write a one-sentence `issue` and carry its exact `evidence_text` quote.
2. Give three `options`: accept, counter, walk. For counter, state the specific plain-language change
   to request (not binding language). For each option, state the trade-off in one sentence.
3. Mark a `recommended_path` only as the creator's likely preference given the playbook, clearly
   labeled a suggestion, never a directive and never legal advice.
4. Set `decide_by`: use the brand's stated deadline if present; otherwise propose one from the urgency
   band and label it a suggestion.
5. State the consequential-action gate line and set `human_review_required: true`,
   `ready_to_send: false`.

## Output

```json
{
  "header": "RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.",
  "tool": "escalation-brief",
  "consequential_action_note": "This step has legal and financial consequences. This brief is for you and your attorney to review; nothing is sent or agreed by producing it.",
  "items": [
    {
      "issue": "string -- one sentence",
      "evidence_text": "string quoted from the contract",
      "severity": "string -- carried from the source finding (legal_risk / business_friction or triage verdict)",
      "options": {
        "accept": { "action": "accept as written", "trade_off": "string" },
        "counter": { "action": "string -- the specific plain-language change to request; NOT binding language", "trade_off": "string" },
        "walk": { "action": "decline the deal", "trade_off": "string" }
      },
      "recommended_path": "accept | counter | walk | null -- labeled a suggestion, never a directive"
    }
  ],
  "decide_by": "string -- ISO date; the brand's stated deadline, or a suggested one labeled as such",
  "decide_by_source": "brand_stated | suggested",
  "ready_to_send": false,
  "recommend_counsel": true,
  "human_review_required": true,
  "retrieval_gaps": []
}
```

Field rules:
- `ready_to_send` is always `false`; this atom drafts, it does not send.
- `evidence_text` is quoted from the source finding; never paraphrased into a quote.
- `recommended_path` is a labeled suggestion grounded in the playbook, never a legal recommendation.
- `decide_by_source` says whether the date came from the brand or is a suggestion.

## Do NOT use for

- Sending the ask, emailing the brand, or advancing the deal stage (this atom never transmits or
  commits; a human confirmation and a separate send path are required).
- Giving legal advice or recommending a term as enforceable or safe (that requires a licensed
  attorney).
- Producing the review itself (use `contract-review`) or the fast verdict (use `contract-triage`).
- Drafting binding contract language.
- Releasing output without passing through `govern-artifact`.

## Pipeline note

Consumes findings from `contract-triage`, `contract-review`, and `legal-requirement-check`. Follows
`shared/contract-engine.md` (consequential-action gate, urgency bands). Obeys
`protocols/no-fabrication.md` and `protocols/safety.md`. Pass output to `govern-artifact` before the
spoke surfaces it.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
