---
file: skills/atoms/geo-optimize/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for geo-optimize so it stays stable under iteration.
---

# geo-optimize: Maintainer README

## Purpose

geo-optimize converts a finalized (or near-final) video title and description into GEO/AEO
artifacts: keyword-rich chapter timestamps, an annotated description diff, a companion blog post
outline, VideoObject schema action notes, and a geo_readiness_score (0 to 6). Its job ends at
artifact production. It does not do keyword research (use keyword-cluster or long-tail-expand
first) and does not write prose scripts or captions (those belong to script-section and
caption-write). It is called after the title and description are drafted and the chapter outline
is available or inferable.

## Non-negotiable invariants

- Shared: references `shared/method.md` in procedure; self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` (no invented entity names,
  no fabricated schema property values, no fake timestamps) and `protocols/formatting-metadata.md`
  (no em dashes in user-facing fields; ranges use "to").
- Skill-specific:
  - First chapter MUST be at `00:00`; never omit it even if the chapter outline starts later.
  - Minimum 3 chapters is a hard requirement for Key Moments eligibility; flag if fewer are generated.
  - Do not generate raw JSON-LD. VideoObject schema notes are creator-action bullets, not code.
  - `geo_readiness_score` uses the fixed scale: high=2, medium=1, low/absent/no=0. Max 6.
    Do not apply weights, thresholds, or adjustments beyond this.
  - `retrieval_gaps` must be non-empty whenever `chapter_outline` is absent or
    `primary_keyword` is inferred rather than supplied.
  - `creator_already_covers` and similar cross-inventory fields must always be null unless
    the calling spoke provides existing content data. Never infer coverage.

## Known failure modes

1. Hallucinated timestamps: when chapter_outline is absent, the atom may invent plausible but
   wrong timestamps. Mitigation: all generated chapters carry `"suggested": true`; the first
   line of retrieval_gaps must note that timestamps require manual confirmation.
2. Keyword stuffing in chapter titles: the 3 to 8 word rule exists to prevent this; titles that
   exceed 8 words drift toward stuffed meta tags, not natural search queries.
3. Companion blog post outline treated as prose: the outline must be markdown headers, not
   written paragraphs. A model that writes prose is out of scope and will fail formatting review.
4. Entity names fabricated to fill description annotation: when entity_list is not supplied, the
   atom may invent brand names or product names. Hard rule: extract only entities explicitly
   present in the input; add nothing.
5. geo_readiness_score computed with custom weights: any deviation from the fixed
   high=2/medium=1/low=0 table breaks the deterministic scoring contract and makes the score
   non-comparable across videos.

## Fragile fallbacks that must not become defaults

- `[inferred from title — verify against keyword research]` label on primary_keyword: acceptable
  when the keyword is absent from inputs, but must appear in output and in retrieval_gaps. Silent
  inference with no flag is not permitted.
- `[suggested — requires timestamp adjustment]` label on generated chapter timestamps: acceptable
  when chapter_outline is absent, never acceptable when the caller provides an outline.
- Empty companion_blog_post_outline: permissible only if the description is too sparse to infer
  any structure (fewer than 3 inferable topics). Must be noted in retrieval_gaps.

## Regression cases to preserve

1. **Full inputs, all fields provided** (eval-001): video_title + description + chapter_outline +
   primary_keyword + entity_list supplied. Expected: all 5 output sections populated, no entries in
   retrieval_gaps, chapter timestamps match the input outline exactly (not generated), geo_readiness
   score reflects supplied entity and chapter data.

2. **No chapter outline** (eval-002): only video_title + description + primary_keyword supplied.
   Expected: chapter_timestamps generated with `"suggested": true` on all entries, retrieval_gaps
   contains "chapter_outline not provided — timestamps are suggested, not confirmed",
   `chapter_structure` rated medium or low (never high when chapters are generated).

3. **No primary keyword or entity list** (eval-003): only video_title + description provided.
   Expected: primary_keyword inferred from title noun phrase and labeled `[inferred from title]`,
   entity_list populated only with entities found verbatim in the title and description
   (zero fabrication), retrieval_gaps lists both missing fields.

4. **Sparse description (under 100 characters)** (eval-004): description draft is too short to
   infer chapter structure or keyword placement. Expected: chapter_timestamps set to `[]`,
   description_annotation notes insufficient content for keyword density assessment,
   companion_blog_post_outline set to null or minimal skeleton, retrieval_gaps explains why.

5. **geo_readiness_score boundary: score 5 to 6** (eval-005): entity_density=high, chapter_structure=high,
   companion_post_exists=yes. Expected: score=6, output includes explicit "strong AI citation
   candidate" label in geo_readiness output.

6. **Entity names in title vs description only** (eval-006): entity_list not provided but title
   contains a brand name (e.g., "Rust-Oleum Chalked Paint"). Expected: that brand name appears
   in the entity extraction from the description annotation, not duplicated with invented
   variants, no fabricated related products added.

7. **Existing description already keyword-rich** (eval-007): first 125 characters of the draft
   already contain the primary keyword. Expected: `changes_from_input` notes "primary keyword
   already in position; no change needed to first 125 characters" rather than suggesting
   a redundant insertion.

## Approval-gated changes

These changes require explicit review before merging:

- Any change to the geo_readiness_score formula or the high/medium/low/absent mapping.
- Any change to the output JSON schema (new keys, renamed keys, type changes).
- Adding or removing engines from `engines_required` in SKILL.md.
- Changing the minimum chapter count threshold (currently 3).
- Changing the description annotation window (currently first 300 characters, keyword target
  first 125 characters).
- Any change to what `suggested` means on chapter timestamp entries.

## Minority-report policy

**Chapter structure when outline is provided but incomplete:** if the caller provides a
chapter_outline with fewer than 3 entries, the atom generates additional suggested chapters to
meet the 3-chapter minimum. Rationale: Key Moments eligibility is a hard platform requirement.
Chosen interpretation: add `"suggested": true` chapters, flag in retrieval_gaps, do not silently
drop the minimum gate. What would overturn this: if the caller explicitly sets
`require_minimum_chapters: false` in inputs (not currently in the schema; add if needed).

**Entity extraction from description when entity_list is absent:** the atom extracts entities
present verbatim in the input text. It does not infer entities from context (e.g., if the
description says "chalk paint" without naming a brand, no brand name is added). Chosen
interpretation: strict text-match only. What would overturn this: a caller-supplied
`entity_expansion: true` flag, which would require explicit operator opt-in and a no-fabrication
caveat in output.

## Update checklist

1. Edit the relevant section in SKILL.md or this file.
2. If the output contract changes, update `evals/evals.json` to reflect new expected fields.
3. If an engine is added or removed, update `engines_required` in SKILL.md frontmatter and
   verify the engine file exists in `shared/`.
4. If the geo_readiness_score formula changes, update eval-005 expected output.
5. Run `python3 tools/sync_check.py` — must exit 0 before committing.
