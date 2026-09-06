---
file: skills/atoms/usage-rights-check/SKILL.md
name: usage-rights-check
description: "extracts and evaluates usage rights from a deal record or contract text; outputs legal information only (not legal advice) per protocols/safety.md; does NOT negotiate terms or draft contracts."
load:
  - shared/pipeline-engine.md
  - protocols/safety.md
  - protocols/no-fabrication.md
---

# usage-rights-check

Extract and evaluate usage rights from a deal record or from raw contract text. Every field in the
output traces directly to the input source. Nothing is inferred, estimated, or constructed from
general knowledge. This atom outputs legal information only, NOT legal advice.

## Purpose

Brand partnership contracts contain usage rights clauses that govern where, how long, and by whom
sponsored content may be used. Missing or ambiguous clauses create downstream risk: a brand may
repurpose content beyond the agreed scope, an exclusivity window may block competing deals, or FTC
disclosure obligations may be unclear. This atom centralizes the extraction and flagging of those
clauses so that any pipeline or document spoke can surface structured rights data without duplicating
parsing logic or making legal judgments it is not qualified to make.

This atom outputs legal information, NOT legal advice. It identifies what language is present or
absent and flags ambiguous or high-risk clauses. It does not interpret contract law, assess
enforceability, or recommend a course of legal action. When terms are ambiguous, high-value, or
structurally incomplete, `recommend_counsel` is always set to `true` so the caller and user know to
involve a qualified attorney before signing or relying on the output.

Every null field reflects an actual absence in the source material. The atom never fills a gap with
a default assumption.

## Inputs

```json
{
  "deal_id": "string or null -- optional; when provided, the atom reads the deal record from pipeline/deals/ and extracts the contract_text field from it",
  "contract_text": "string or null -- optional; raw contract or clause text supplied directly by the caller",
  "question": "string or null -- optional; a specific clause or topic to focus the evaluation on, e.g. platform exclusivity or whitelisting rights"
}
```

Field rules:
- Supply `deal_id` OR `contract_text`, not both. If both are provided, `deal_id` takes precedence
  and `contract_text` is ignored; include a note in `flags` documenting which source was used.
- If neither is provided, return an error object with `error: "no_source"` and a message asking the
  caller to supply either `deal_id` or `contract_text`.
- `question` is optional. When supplied, the atom prioritizes extracting and evaluating the clause
  or topic named. All other output fields are still populated from available source text; `question`
  does not restrict the output to a single field.
- Do not read any deal record other than the one identified by `deal_id`. Do not cross-reference
  other accounts or deals unless explicitly instructed by the calling spoke.

## Output

```json
{
  "tool": "usage-rights-check",
  "source": "deal_id | contract_text",
  "deal_id": "string or null",
  "exclusivity": {
    "scope": "string or null -- what categories, niches, or competitors are covered; null if not stated",
    "platform": "string or null -- which platforms the exclusivity applies to, e.g. YouTube, Instagram, TikTok, or all platforms; null if not stated",
    "duration": "string or null -- expressed as a plain range or date, e.g. 30 days from publish or 2025-01-15 to 2025-04-15; null if not stated"
  },
  "ownership": "string or null -- who holds copyright in the content as stated in the source; null if not stated",
  "license_grant": "string or null -- summary of the rights granted to the brand, e.g. non-exclusive license to repost on brand-owned social channels for 6 months; null if not stated",
  "platform_restrictions": [
    "string -- each restriction listed as a plain statement, e.g. brand may not run paid amplification without a separate whitelisting addendum"
  ],
  "ftc_disclosure_required": {
    "value": true,
    "reason": "string -- cite the specific language or absence of language that drives this determination, e.g. contract does not waive disclosure obligation and content is sponsored; null only if value is false and the contract text explicitly states disclosure is not required"
  },
  "flags": [
    {
      "clause": "string -- name or short description of the clause, e.g. exclusivity duration or content approval window",
      "issue": "ambiguous | missing",
      "detail": "string -- one sentence describing what is unclear or absent and why it matters"
    }
  ],
  "recommend_counsel": true,
  "counsel_reason": "string or null -- present whenever recommend_counsel is true; one sentence naming the specific reason, e.g. exclusivity scope is ambiguous and deal value exceeds standard review threshold; null only when recommend_counsel is false"
}
```

Field rules:
- `exclusivity.duration` uses plain language ranges with "to" separating start and end dates or
  values. Never use an em dash as a range separator.
- `platform_restrictions` is an empty array when no restrictions are found in the source text. Do
  not populate it with assumed defaults.
- `ftc_disclosure_required.value` defaults to `true` whenever the contract text does not explicitly
  address FTC disclosure obligations. Sponsored content carries an FTC disclosure requirement by
  default under existing guidance; the atom flags when the contract is silent on this point.
- `flags` is an empty array when no ambiguous or missing clauses are identified. Do not fabricate
  flags to appear thorough.
- `recommend_counsel` is `true` when any of the following conditions are met: one or more `flags`
  entries exist; `exclusivity.scope`, `exclusivity.platform`, or `exclusivity.duration` is null;
  `ownership` is null or ambiguous; `license_grant` is null; or the calling spoke indicates a
  high-value deal. `recommend_counsel` may be `false` only when all key fields are populated, no
  flags are raised, and the terms are unambiguous on their face. When in doubt, set it to `true`.
- `counsel_reason` is required whenever `recommend_counsel` is `true`. It must cite a specific field
  or clause gap, not a generic disclaimer.
- All string values are copied or paraphrased from the source text. Do not introduce language,
  interpretations, or legal conclusions not grounded in the source material
  (`protocols/no-fabrication.md`).

## Do NOT use for

- Negotiating contract terms, proposing alternative clause language, or advising on what terms to
  accept or reject. This atom extracts and flags; it does not advise.
- Drafting contracts, addenda, or any legal document (use a document spoke for drafting tasks).
- Providing legal advice, assessing enforceability, or making any determination that requires a
  licensed attorney.
- Evaluating deal financials, rates, or ROI (use rate-card-fill or account-health for those).
- Comparing clauses across multiple deals or building a portfolio-level rights report (the calling
  spoke must iterate this atom per deal and handle aggregation itself).
- Storing or writing extracted rights data back to a pipeline record (use the appropriate CRM write
  atom).
- Releasing output directly to the user without passing through govern-artifact.

## Pipeline note

Follows `shared/pipeline-engine.md` for deal record resolution and gap handling. When `deal_id` is
provided, the atom reads from `pipeline/deals/`; real records are gitignored and never committed.
Obeys `protocols/no-fabrication.md`: if a required field is absent from the source, that output
field is null and a flag is raised rather than estimating or constructing a value. Obeys
`protocols/safety.md`: output is scoped to legal information only and carries no legal advice.
Pass output to govern-artifact before the spoke surfaces it to the user.

## Cross-modality
Inherits its calling spoke's class (Class B); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
