---
file: skills/atoms/contract-draft/SKILL.md
name: contract-draft
atom: true
description: "assembles a PLAIN-LANGUAGE draft agreement from the creator's deal-playbook standard positions plus the deal's agreed terms: for each clause family it emits a plain-language term tagged deal_agreed, playbook_standard, generic_default (provisional mode), or MISSING (null, flagged), under a prominent NOT-VETTED / NOT-BINDING banner; it is a starting point to formalize with a qualified professional and NEVER invents an unknown term; outputs legal information only (not legal advice); does NOT emit operative legalese, indemnity or warranty language, or anything meant to be signed as-is."
load:
  - shared/contract-engine.md
  - protocols/safety.md
  - protocols/no-fabrication.md
---

# contract-draft

Assemble a plain-language starting point for a brand-partnership agreement from terms that are already
known: the deal's agreed terms plus the creator's playbook standard positions. For each clause family
it emits one plain-language term with a source tag, under a prominent not-vetted, not-binding banner.
It is a starting point to formalize with a qualified professional, never a document to sign as-is. It
never invents an unknown term. Legal information only, NOT legal advice.

## First line of every output (verbatim)

```
RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.
```

## Purpose

Once a creator and a brand have agreed the shape of a deal, the creator often wants something written
down before taking it to a professional. This atom produces that: a plain-language term sheet across
the nine clause families in `shared/contract-engine.md`, filled from what is actually known. Each term
carries the source it came from, so the creator can see at a glance what was agreed, what fell back to
their own standard opening position, and what nobody has settled yet. It is deliberately not a
contract. It contains no operative legalese, no indemnity or warranty language, and nothing framed as
vetted or ready to sign. It is the material a creator hands to a qualified professional to formalize.

## The consequential-action gate

Turning these terms into a signed agreement is a consequential action. This atom always: states plainly
that formalizing and signing has legal and financial consequences; produces the draft as a
plain-language starting point for review, not as a document to sign or send; sets `ready_to_sign: false`
and `human_review_required: true`; and never advances the deal, signs, or sends anything. Agents produce
material for a human and a qualified professional to act on; they never commit the creator.

## Source precedence (assembly model)

Fill each clause family by the precedence defined in `shared/contract-engine.md` ("Plain-language draft
assembly"), and tag the term with the source used:

1. `deal_agreed`: a term explicitly agreed in the deal record or the supplied `agreed_terms`. Agreed
   terms always win; quote the source field exactly.
2. `playbook_standard`: where the deal is silent and a real playbook is configured, the creator's
   `standard` tier for that clause (the opening position, never a `fallback` or `never` line).
3. `generic_default`: provisional mode only (null-template playbook). The generic creator-side defaults
   in the engine, offered as guidance and never presented as the creator's committed position.
4. `MISSING`: no source provides the term. The term is null, the family is flagged and listed in
   `missing_terms`, and nothing is invented to fill it.

## Inputs

```json
{
  "deal_id": "string or null -- read the deal record from pipeline/deals/ and any linked contract from pipeline/contracts/ for agreed terms",
  "agreed_terms": "object or null -- clause_family keyed plain-language terms already agreed; used directly, quoted exactly",
  "focus": "string or null -- optional clause family to lead with; all nine families are still emitted"
}
```

- Supply `deal_id` OR `agreed_terms`. If neither, return `{ "error": "no_source", "message": "supply a deal_id or an agreed_terms object" }`.
- Read the creator's positions from the deal-playbook (`pipeline/user-context/deal-playbook.template.json`,
  real values in the gitignored `.local.json`). If it is still the null template, set `provisional: true`,
  prefix the banner with `[PROVISIONAL: no playbook configured]`, and fill deal-silent families from the
  generic defaults in `shared/contract-engine.md` tagged `generic_default`, never from invented positions.
- This atom does not parse raw contract text. Clause extraction from raw text is `usage-rights-check`;
  reviewing or scoring clauses is `contract-review`. This atom assembles from structured, known terms.

## Procedure

1. Resolve the source. With a `deal_id`, read the deal record (and any linked contract in
   `pipeline/contracts/`) for agreed terms. Otherwise use the `agreed_terms` object. If neither is
   present, return the `no_source` error.
2. Read the playbook. If it is the null template, set `provisional: true` and prefix the banner.
3. For each of the nine clause families, fill one `plain_language_term` by the source precedence above.
   Quote `source_evidence` exactly from the deal field, agreed_terms value, or the playbook standard
   text; for `generic_default`, reference the engine default. Never invent a fee, date, party, or term.
4. Write every term in plain English. Do NOT write operative legalese, indemnity, warranty, or any
   binding language, and do not phrase anything as if a lawyer drafted it to be signed.
5. Flag every family whose source is `MISSING`, `generic_default`, or `playbook_standard` (an opening
   position, not an agreed term): these need human confirmation before formalizing. List `MISSING`
   families in `missing_terms`.
6. Emit the not-vetted, not-binding `banner` and the `consequential_action_note`. Set
   `ready_to_sign: false`, `human_review_required: true`, and `recommend_counsel: true` (a plain-language
   draft to be formalized always recommends a qualified professional).

## Output

```json
{
  "header": "RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.",
  "tool": "contract-draft",
  "provisional": false,
  "draft_status": "NOT_VETTED_NOT_BINDING",
  "banner": "PLAIN-LANGUAGE STARTING POINT ONLY. NOT VETTED. NOT BINDING. NOT A CONTRACT. Do not sign or send this. Formalize any agreement with a qualified professional before signing.",
  "consequential_action_note": "Turning these terms into a signed agreement has legal and financial consequences. This is a plain-language starting point for you and a qualified professional to formalize; nothing here is binding, and nothing is signed or sent by producing it.",
  "source_summary": {
    "deal_id": "string or null",
    "playbook_configured": true,
    "agreed_terms_supplied": false
  },
  "clause_terms": [
    {
      "clause_family": "string -- one of the nine families in shared/contract-engine.md",
      "plain_language_term": "string in plain language, or null when MISSING",
      "source": "deal_agreed | playbook_standard | generic_default | MISSING",
      "source_evidence": "string quoted from the deal field / agreed_terms value / playbook standard, or the generic-default reference; null when MISSING",
      "flagged": true,
      "note": "string or null -- why it is flagged: needs confirmation, generic default used, opening position not yet agreed, or missing"
    }
  ],
  "missing_terms": ["string -- clause families with source MISSING"],
  "unresolved_or_flagged": ["string -- families needing human confirmation before formalizing"],
  "recommend_counsel": true,
  "recommend_counsel_reason": "string -- always set; a plain-language draft must be formalized with a qualified professional",
  "human_review_required": true,
  "ready_to_sign": false,
  "retrieval_gaps": [],
  "profile_gaps": [
    {
      "field": "string -- the creator-profile field left as a placeholder: e.g. legal_name, business_address, governing_law_state",
      "placeholder_used": "string -- the placeholder text that appears in the draft",
      "fix": "fill creator-profile.local.json under pipeline/user-context/ (profile import or the setup wizard's /brand-deals screen)"
    }
  ]
}
```

Field rules:
- `plain_language_term` is plain English, never operative legalese, indemnity, or warranty language, and
  never framed as vetted or ready to sign.
- `source_evidence` is quoted exactly from the source or null; never paraphrased into a quote and never
  invented. A `MISSING` term is `null` with the family listed in `missing_terms`, never a guessed value.
- A multi-deliverable agreement (any mix of posts, videos, story sets, scripts, video ideas, UGC)
  enumerates EVERY deliverable with its type and count from the agreed terms; deliverables are never
  collapsed into a single line item or summarized away.
- `source` is honest provenance: `deal_agreed` only for explicitly agreed terms, `playbook_standard` only
  when a real playbook supplies it, `generic_default` only in provisional mode.
- `ready_to_sign` is always `false`; this atom drafts a starting point, it does not produce a signable
  agreement.
- `recommend_counsel` is `true` and `human_review_required` is `true` on every output.
- `profile_gaps` is MANDATORY on every output: one entry per placeholder the draft carries because
  creator-profile.local.json is missing or incomplete (legal name, business address, governing-law
  state, and any other party-identity field). An empty array means the profile supplied every
  party-identity value. The draft is never blocked by profile gaps; the gaps travel with the
  artifact through govern-artifact so the human sees exactly what to fill before formalizing.

## Do NOT use for

- Emitting operative legalese, indemnity or warranty clauses, or a binding agreement to sign as-is
  (this atom produces a labeled not-vetted, not-binding plain-language starting point only).
- Ruling on enforceability, validity, or which party would prevail (that requires a licensed attorney).
- Reviewing or scoring an existing contract clause by clause (use `contract-review`) or the fast inbound
  verdict (use `contract-triage`).
- Parsing raw contract text into clauses (use `usage-rights-check`).
- Version-to-version comparison across amendments (use `amendment-trace`, which reuses the version model
  and source precedence in `shared/contract-engine.md`).
- Assembling the creator's saved attorney-vetted contract template (use `template-assemble`, which
  swaps whole vetted blocks and fills brackets via `tools/doctemplates.py`). When a vetted contract
  doc-template exists in the template store, this atom reports `vetted_template_available: true`
  and recommends that path; contract-draft remains the no-template plain-language path.
- Signing, sending, or advancing the deal stage, or writing to `pipeline/contracts/` or `pipeline/deals/`
  (a human confirmation and a separate write path are required; agents never sign or send).
- Releasing output without passing through `govern-artifact`.

## Pipeline note

Reads the deal record and any linked contract in `pipeline/contracts/`, plus the deal-playbook; follows
`shared/contract-engine.md` for the clause taxonomy, the four-tier playbook model, the generic
provisional defaults, and the plain-language draft assembly precedence. Does not re-parse raw text
(`usage-rights-check`) or re-implement review (`contract-review`). Gated behind the `contract_drafting`
flag (requires `contract_management`); when off, contract-desk degrades per `creator-os-config.json`.
Obeys `protocols/no-fabrication.md` and `protocols/safety.md`. Pass output to `govern-artifact` before
the spoke surfaces it.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
