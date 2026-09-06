---
file: skills/atoms/product-fit/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for product-fit so it stays stable under iteration.
---

# product-fit: Maintainer README

## Purpose
Scores one pitched product against stored audience personas, content pillars, seasonal timing, and
stored exclusivity commitments, and returns a structured fit verdict. Its job ends at the verdict:
pricing belongs to `proposal-price`, replies to `pitch-paragraph`, content planning to the
content-strategy spoke.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- `data_basis` is mandatory on every output. Niche-default personas are never passed off as
  measured audience data.
- Persona reasoning must reference the persona's stored pain point or want text.
- Exclusivity conflicts come from stored exclusivity fields only (pipeline read path), never
  inferred from brand names; an unreadable store is reported as unverified, never as "no
  conflict".
- Any exclusivity red flag caps the verdict at `conditional_fit`.
- `human_review_required: true` always; output passes through govern-artifact.
- The product link is never fetched by this atom (web-intel lane, consent-gated).

## Known failure modes
- Category unclear from the pitch: scores proceed on the name with a `category_unresolved`
  condition; never guess the category from marketing copy.
- Empty or missing deal store: exclusivity check degrades to `unverified` in `conditions[]`.
- No local creator profile: pillar check falls back to the `shared/brand-engine.md` default
  framework, flagged as unconfirmed.

## Fragile fallbacks that must not become defaults
- `data_basis: niche_default_personas` is acceptable only while no creator audience data exists;
  the output must keep prompting for real data.
- Default pillar framework is a labeled fallback, not a source of truth.

## Regression cases to preserve
1. Portable AC pitch scores The Renter strong with pain-point-tied reasoning and
   `data_basis: niche_default_personas` flagged (evals: product-fit-renter-strong).
2. A stored active exclusivity clause covering the product category produces a named red flag and
   caps the verdict (evals: product-fit-exclusivity-conflict).
3. An out-of-niche product yields `decline_recommended` with per-persona poor/weak scores
   (evals: product-fit-out-of-niche).
4. Missing product name halts with a gap record; nothing scored
   (evals: product-fit-missing-product).
5. A season-sensitive product proposed against the wrong window carries a timing caveat citing the
   seasonal record id (evals: product-fit-seasonal-mismatch).

## Approval-gated changes
Output schema (`references/artifact-types.md`), the verdict enum, the persona scoring scale, the
exclusivity capping rule, and any new engine or store read path.

## Minority-report policy
When persona scores and pillar alignment point in different directions (for example strong persona
fit but zero pillar alignment), record both signals in the output, choose the verdict from the
persona scores, and state in `conditions[]` what would overturn it.

## Update checklist
1. Edit SKILL.md / references and keep the output contract in sync with evals/evals.json.
2. Re-run the five regression evals above.
3. python3 tools/sync_check.py
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
