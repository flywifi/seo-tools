---
file: skills/atoms/product-fit/SKILL.md
name: product-fit
description: score a pitched product against the creator's audience personas, content pillars, seasonal timing, and existing exclusivity commitments, returning a structured fit verdict with per-persona reasoning. Use when a spoke is evaluating an inbound brand pitch or a prospective partnership and needs "does this product fit my audience" answered with evidence. Do NOT use to price the deal (proposal-price), to write the pitch reply (pitch-paragraph), or to plan the content itself (content-strategy spoke).
load:
  - canonical-sources/personas/personas.json
  - canonical-sources/seasonal-aesthetic/seasonal.json
  - shared/audience-engine.md
  - protocols/no-fabrication.md
---

# product-fit

Does this product belong in front of this audience. One operation: a product (name, category,
optional link) in, a structured fit verdict out, with every persona scored and every score tied to
a stored pain point. The human decides whether to pursue the deal; this atom informs.

## Purpose

Inbound pitches arrive constantly and the expensive mistake is asymmetric: promoting a poor-fit
product burns audience trust that took years to build. This atom centralizes the fit check so every
spoke that triages pitches or evaluates partnerships scores products the same way, against the same
stored audience data, with the same honesty about what that data is.

## Inputs

```json
{
  "product": {
    "name": "string -- required",
    "category": "string or null -- e.g. home appliance, decor, organization; inferred from name only when obvious, else null and flagged",
    "link_provided": "boolean -- whether the pitch included a product link (the link is reference only; never fetched without the web-intel consent path)"
  },
  "requested_platforms": ["optional -- platforms the brand asked for, e.g. youtube, tiktok"],
  "proposed_timing": "string or null -- when the brand wants the content live, if stated"
}
```

Field rules:
- `product.name` is required; if absent, halt with a gap record. Nothing is scored without knowing
  what the product is.
- `product.category` is never guessed from marketing copy. If the category is genuinely unclear,
  it stays null and the verdict carries a `category_unresolved` condition.

## Core procedure

1. **Load the audience basis.** Read `canonical-sources/personas/personas.json`. If
   `creator-profile.local.json` supplies real audience data (demographics, survey results,
   analytics-derived segments), that takes precedence and `data_basis` is
   `creator_audience_data`. Otherwise the niche-default personas are used and `data_basis` is
   `niche_default_personas` -- this flag is mandatory, never omitted (the verdict is only as good
   as the audience data behind it).
2. **Score each persona.** For every persona, assign `strong | moderate | weak | poor` with
   reasoning tied to that persona's stored pain point or want. Reasoning that does not reference
   the stored text is invalid; do not free-associate.
3. **Check pillar alignment.** Compare the product against the creator's content pillars
   (`creator-profile.local.json` `content_pillars`, else the `shared/brand-engine.md` default
   framework, flagged as unconfirmed).
4. **Check seasonal timing.** Read `canonical-sources/seasonal-aesthetic/seasonal.json`; if the
   product or the proposed timing is season-sensitive, state the alignment or mismatch and cite
   the seasonal record id as `seasonal_timing.source`.
5. **Check exclusivity conflicts.** Read the deal and account stores (the `deal_status` /
   `account-health` read path, `shared/pipeline-engine.md`): if any active account's stored
   exclusivity clause covers the product's category, that is a `red_flags[]` entry naming the
   conflicting commitment. Conflicts come from stored exclusivity fields only, never inferred from
   brand names alone. If the stores are empty or unavailable, say so in `conditions[]` rather than
   silently reporting no conflict.
6. **Render the verdict.** `strong_fit | conditional_fit | weak_fit | decline_recommended`, driven
   by the persona scores, pillar alignment, and red flags. Any exclusivity red flag caps the
   verdict at `conditional_fit` and says why.

## Output contract

The structured object defined in `references/artifact-types.md`: `product`, `verdict`,
`persona_fit[]` (one entry per persona, with `persona_id`, `score`, `reasoning`),
`pillar_alignment[]`, `seasonal_timing`, `conditions[]`, `red_flags[]`, `data_basis`, and
`human_review_required: true` always. Honor `protocols/formatting-metadata.md` (no em dashes in
user-facing text, ranges with "to").

## Do NOT use for

- Pricing the deal or computing a floor (use `proposal-price`).
- Writing the reply to the brand (use `pitch-paragraph`).
- Planning the video or content angle in depth (use the `content-strategy` spoke; this atom only
  hands off which personas scored strong).
- Fetching the product link or researching the brand online (web-intel lane, consent-gated).
- Inventing audience data, demographics, or survey results (`protocols/no-fabrication.md`). The
  `data_basis` flag states exactly what the scores rest on.
- Final release decisions; output passes through govern-artifact before the spoke surfaces it.

## Standalone usability

Even with no downstream skill available, the persona-by-persona scores plus the `data_basis` flag
tell the creator whether a pitched product deserves a reply.

## Failure modes

- Missing product name: gap record, halt; nothing scored.
- Unclear category: `category_unresolved` condition; persona scores proceed on the name alone with
  reasoning marked lower-confidence.
- No local audience data: verdict proceeds on niche-default personas with
  `data_basis: niche_default_personas` stated prominently; the recommendation notes that real
  audience data would harden the verdict.
- Deal store unreadable: exclusivity check reports `unverified` in `conditions[]`; it never
  reports "no conflicts" without having read the store.

## Cross-modality
Inherits its calling spoke's class (Class B); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
