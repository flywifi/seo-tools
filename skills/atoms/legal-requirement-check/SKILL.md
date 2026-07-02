---
file: skills/atoms/legal-requirement-check/SKILL.md
name: legal-requirement-check
atom: true
description: "checks a brand contract against creator-relevant legal requirements: FTC disclosure obligation, usage-rights conflicts, exclusivity overlap with active deals, missing payment or kill-fee terms, and the perpetual-usage-for-flat-fee flag; cites the curated FTC sources in canonical-sources/source-registry.json; outputs legal information only (not legal advice) for US agreements; does NOT rule on enforceability or draft language."
load:
  - shared/contract-engine.md
  - protocols/safety.md
  - protocols/no-fabrication.md
---

# legal-requirement-check

Check a brand-partnership contract against the specific legal requirements that matter to a US
creator, and cite the primary source behind each flag. This atom flags and points to authority; it
does not interpret the law or rule on enforceability. Legal information only, NOT legal advice.

## First line of every output (verbatim)

```
RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.
```

## Purpose

Some contract problems are not about the creator's preferences; they are about rules that apply
regardless. The clearest is FTC disclosure: a material connection to a brand must be disclosed, and a
contract cannot waive that. This atom runs a fixed checklist of creator-relevant requirements, flags
each as satisfied, at-risk, or missing, and cites the primary FTC or reference source for each flag so
the creator and their attorney can verify. It is US-only, matching its sources.

## Inputs

```json
{
  "contract_text": "string or null -- the raw contract text",
  "deal_id": "string or null -- optional; read the linked contract and deal from pipeline/ instead",
  "deal_context": {
    "fee": "number or null -- never invent one",
    "is_sponsored": "boolean or null",
    "is_gifted": "boolean or null",
    "is_affiliate": "boolean or null",
    "category": "string or null"
  }
}
```

- Supply `contract_text` OR `deal_id`. If neither, return `{ "error": "no_source" }`.
- When `deal_id` is present, run `exclusivity-check` for cross-deal exclusivity overlap and read
  invoice state via `invoice-status`. Cite sources from `canonical-sources/source-registry.json` by
  their registry id (the FTC and reference entries whose `used_by` includes this atom).
- Jurisdiction is US only. If the contract names a non-US governing law, flag that the US sources may
  not apply rather than applying them.

## The checklist

1. **FTC disclosure obligation.** If the deal is sponsored, gifted, or affiliate, disclosure is
   required and cannot be waived. Flag whether the contract requires, is silent on, or attempts to
   waive disclosure. Cite `ftc-disclosures-101` and `ftc-endorsement-guides`.
2. **Usage-rights conflict.** Flag rights that exceed what the creator likely intends: perpetual,
   worldwide, sublicensable, or ownership-assigning grants. Cite `us-copyright-basics`.
3. **Perpetual usage for a flat fee.** Specifically flag any perpetual or in-perpetuity usage grant
   paired with a one-time flat fee, as a high-attention combination.
4. **Exclusivity overlap.** Flag exclusivity that overlaps an active deal (via `exclusivity-check`
   when a deal_id is available) or that is open-ended or whole-niche.
5. **Missing payment or kill-fee terms.** Flag the absence of a stated fee, a payment timing, or a
   kill fee on a cancellable scope. Never invent a figure.

## Output

```json
{
  "header": "RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.",
  "tool": "legal-requirement-check",
  "jurisdiction": "US",
  "jurisdiction_warning": "string or null -- present when the contract names a non-US governing law",
  "flags": [
    {
      "requirement": "ftc_disclosure | usage_rights_conflict | perpetual_usage_flat_fee | exclusivity_overlap | missing_payment_terms",
      "status": "satisfied | at_risk | missing | not_applicable",
      "evidence_text": "string quoted from the contract, or null when the finding is an absence",
      "detail": "string -- one plain-English sentence on what was found and why it matters",
      "sources": ["string -- registry ids, e.g. ftc-disclosures-101"],
      "confidence": "explicit | high | medium | low"
    }
  ],
  "recommend_counsel": true,
  "counsel_reason": "string or null",
  "human_review_required": true,
  "retrieval_gaps": []
}
```

Field rules:
- Every FTC-related flag cites at least one FTC registry id in `sources`. Do not cite a source that
  does not exist in `canonical-sources/source-registry.json`.
- `status: not_applicable` is used, for example, when the deal is neither sponsored, gifted, nor
  affiliate for the FTC flag; state why.
- `evidence_text` is quoted or null. A `missing` status has `evidence_text: null`.
- Never invent a fee, date, or clause to resolve a `missing` flag.

## Do NOT use for

- Ruling on enforceability or giving legal advice (that requires a licensed attorney).
- The full clause-by-clause review or redline suggestions (use `contract-review`).
- Non-US agreements without flagging that the US sources may not apply.
- Fabricating a citation or a term.
- Writing to `pipeline/` records, or releasing output without `govern-artifact`.

## Pipeline note

Reuses `exclusivity-check` and `invoice-status`; cites `canonical-sources/source-registry.json`.
Follows `shared/contract-engine.md`. Obeys `protocols/no-fabrication.md` and `protocols/safety.md`.
Pass output to `govern-artifact` before the spoke surfaces it.
