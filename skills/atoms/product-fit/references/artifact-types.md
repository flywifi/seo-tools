---
file: skills/atoms/product-fit/references/artifact-types.md
role: the artifact types this skill produces and the required elements of each.
---

# product-fit artifact types

## Fit verdict (the only artifact)

```json
{
  "tool": "product-fit",
  "product": {
    "name": "string",
    "category": "string or null",
    "link_provided": true
  },
  "verdict": "strong_fit | conditional_fit | weak_fit | decline_recommended",
  "persona_fit": [
    {
      "persona_id": "string -- id from canonical-sources/personas/personas.json (or a creator-audience segment id)",
      "score": "strong | moderate | weak | poor",
      "reasoning": "string -- must reference the persona's stored pain point or want; never free-associated"
    }
  ],
  "pillar_alignment": ["list of content pillars the product serves; empty if none"],
  "seasonal_timing": {
    "assessment": "string or null -- alignment or mismatch with the proposed timing",
    "source": "string or null -- the seasonal record id from canonical-sources/seasonal-aesthetic/seasonal.json"
  },
  "conditions": ["caveats that keep a conditional_fit honest, e.g. category_unresolved, exclusivity check unverified"],
  "red_flags": ["hard problems, e.g. an active exclusivity commitment covering this category, named"],
  "data_basis": "niche_default_personas | creator_audience_data",
  "human_review_required": true
}
```

Required elements:
- Every persona in the loaded persona set appears exactly once in `persona_fit`.
- `data_basis` is always present. `niche_default_personas` means the scores rest on the shipped
  default personas, not measured audience data, and the surrounding prose must say so.
- Any exclusivity `red_flags` entry caps `verdict` at `conditional_fit`.
- `human_review_required` is always true; the atom recommends, the human decides.

Quality-gate dimensions that most apply: no-fabrication (scores tied to stored text), completeness
(every persona scored, exclusivity checked or declared unverified), honesty of caveats
(`data_basis`, `conditions`).
