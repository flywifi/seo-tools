---
file: skills/atoms/contract-review/SKILL.md
name: contract-review
atom: true
description: "produces a clause-by-clause review of a brand contract against the creator's playbook: for each clause it reports what the playbook wants, what the contract says (exact quote), the gap, dual severity (legal risk and business friction), why it matters, and a plain-language redline suggestion; outputs legal information only (not legal advice); does NOT rule on enforceability or emit binding language."
load:
  - shared/contract-engine.md
  - protocols/safety.md
  - protocols/no-fabrication.md
---

# contract-review

Review a brand-partnership contract clause by clause against the creator's playbook, ranking
deal-breakers first. Every finding traces to a quoted clause or is labeled as a missing term. This
atom explains and suggests plain-language changes; it never rules on enforceability and never drafts
binding language. Legal information only, NOT legal advice.

## First line of every output (verbatim)

```
RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.
```

## Purpose

After triage says a contract is worth a full read, this atom does the read. For each clause family in
`shared/contract-engine.md` it compares the creator's position (from the playbook) against the
contract's actual language and produces a structured finding: what the playbook wants, what the
contract says (quoted), the gap, how bad it is on two independent axes (legal risk and business
friction), why it matters in plain English, and a suggested plain-language change plus the playbook
fallback. This gives the creator a decision-ready picture and the attorney a focused list.

## Inputs

```json
{
  "contract_text": "string or null -- the raw contract text",
  "deal_id": "string or null -- optional; read the linked contract from pipeline/contracts/ instead",
  "focus": "string or null -- optional clause family or topic to prioritize; all families are still reviewed"
}
```

- Supply `contract_text` OR `deal_id`. If neither, return `{ "error": "no_source" }`.
- Read the creator's positions from the deal-playbook (`pipeline/user-context/deal-playbook.template.json`,
  real values in the gitignored `.local.json`). If it is still the null template, prefix output with
  `[PROVISIONAL: no playbook configured]` and compare against the generic creator-side defaults in
  `shared/contract-engine.md`.
- Call `usage-rights-check` for the rights, exclusivity, ownership, and FTC extraction, and
  `exclusivity-check` when a deal_id is available to surface cross-deal conflicts. Do not re-parse
  what those atoms already return.

## Procedure

1. Extract clauses with `usage-rights-check`; when a deal_id is present, run `exclusivity-check` for
   cross-deal conflicts and fold any conflict into the exclusivity finding.
2. For each clause family (usage and licensing, exclusivity, deliverables and revisions, payment and
   kill fee, FTC and disclosure, content approval and veto, whitelisting and paid boosting, morality,
   territory): build one finding.
3. In each finding record `playbook_says`, `contract_says` (exact quote or null if the clause is
   missing), `gap`, `legal_risk`, `business_friction`, `why_it_matters`, `redline_suggestion` (plain
   language, explicitly not binding), and `playbook_fallback`.
4. Tag each finding with a `confidence` label (explicit, high, medium, low) per the engine.
5. Order findings deal-breakers first: any finding with `high` on either severity axis leads, then
   `medium`, then the rest.
6. Set `human_review_required: true`; set `recommend_counsel: true` unless every clause is present,
   unambiguous, and within the playbook.

## Output

```json
{
  "header": "RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.",
  "tool": "contract-review",
  "provisional": false,
  "findings": [
    {
      "clause_family": "string",
      "clause_title": "string or null -- the contract's own label when present",
      "playbook_says": "string -- the creator's standard position, or the generic default in provisional mode",
      "contract_says": "string quoted from the contract, or null if the clause is missing",
      "gap": "string -- how the contract differs from the playbook, or 'missing' when absent",
      "legal_risk": "none | low | medium | high",
      "business_friction": "none | low | medium | high",
      "why_it_matters": "string -- plain English, grounded in the clause",
      "redline_suggestion": "string -- a plain-language change the creator could request; explicitly NOT binding language and NOT legal advice",
      "playbook_fallback": "string or null -- the next position the creator can accept",
      "confidence": "explicit | high | medium | low",
      "evidence_text": "string quoted from the contract, or null"
    }
  ],
  "deal_breakers": ["string -- clause_family names with high on either axis"],
  "missing_clauses": ["string -- clause families with no language found"],
  "recommend_counsel": true,
  "counsel_reason": "string or null",
  "human_review_required": true,
  "retrieval_gaps": []
}
```

Field rules:
- `contract_says` and `evidence_text` are quoted from the source or null. Never paraphrase into a
  quote and never invent clause language.
- `redline_suggestion` is plain-language and framed as a request the creator can raise with the brand
  and their attorney. It is never presented as vetted or binding.
- `legal_risk` and `business_friction` are independent; a clause can be low on one and high on the
  other. Do not average them.
- A missing clause is a finding with `contract_says: null`, `gap: "missing"`, and listed in
  `missing_clauses`.

## Do NOT use for

- Ruling on enforceability, validity, or which party would prevail (that requires a licensed attorney).
- Drafting a binding agreement or addendum (Phase 2 contract drafting produces a plain-language,
  labeled-not-vetted draft; it is not this atom and never emits binding language).
- The fast pre-read verdict (use `contract-triage`).
- Version-to-version comparison across amendments (Phase 2 amendment tracing).
- Writing to `pipeline/contracts/` or `pipeline/deals/` (a CRM write atom does that).
- Releasing output without passing through `govern-artifact`.

## Pipeline note

Composes `usage-rights-check` and `exclusivity-check`; follows `shared/contract-engine.md` for the
clause taxonomy, dual-severity axis, and confidence labels. Obeys `protocols/no-fabrication.md` and
`protocols/safety.md`. Pass output to `govern-artifact` before the spoke surfaces it.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
