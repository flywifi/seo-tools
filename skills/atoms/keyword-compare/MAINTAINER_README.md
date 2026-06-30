---
file: skills/atoms/keyword-compare/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for keyword-compare so it stays stable under iteration.
---

# keyword-compare: Maintainer README

## Purpose

keyword-compare is a leaf atom (no workflow.json) that takes an existing keyword list and produces
a structured cross-platform comparison matrix — intent, SERP feature, format fit, competition
estimate, seasonal relevance, and optional momentum — per keyword per platform. Its job ends at
matrix production. It does not discover keywords (keyword-cluster and long-tail-expand do that),
does not rank keywords by volume (no volume API access), and does not write titles or descriptions.
It is the "where should I use this keyword?" layer that sits between keyword discovery and execution.

## Non-negotiable invariants

- Shared: references `shared/method.md` in procedure; self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md` (no em dashes in any output field; ranges use "to").
- Skill-specific:
  - `competition_estimate` always carries `[estimated]` in the output — never a number, never
    a source that was not retrieved. The SERP feature map provides the estimate; the map is
    not a volume API.
  - `seasonal_relevance` is only populated when `season` is explicitly provided in inputs.
    Do not infer seasonality from keyword text alone.
  - `momentum` is only populated when `check_trend_momentum: true` AND retrieval succeeded.
    Otherwise null, not unknown — null means "not checked," unknown means "checked but inconclusive."
  - `cross_platform_verdict` must use the exact three values: universal | platform_specific |
    niche_long_tail. No custom verdicts, no combined labels.
  - Input truncation at 10 keywords is hard: take the first 10, log the rest in retrieval_gaps.
    Never silently drop keywords.
  - The `strongest_platform` tiebreaker is: YouTube > Pinterest > TikTok > Google. This is a
    deterministic rule, not a model judgment call.

## Known failure modes

1. Competition estimate mistaken for a volume figure: the estimate is derived from SERP feature
   type and niche density patterns, not an API. If the model cites a number, it is fabricated.
   Guard: the `[estimated]` label in the field value and the no-fabrication protocol must both
   be present.
2. Seasonal relevance inferred from keyword text: "fall mantel" should not get
   `seasonal_relevance: peak` without a `season` input — peak/off_season timing depends on the
   current date and the canonical peak windows, which require seasonal-map logic to evaluate.
3. Momentum set to `flat` when retrieval failed: `flat` implies a real signal. The correct value
   when retrieval is inconclusive is `unknown`; when not checked at all, `null`.
4. Platform profiles generated for a platform not in the `platforms` input: only produce cells for
   platforms explicitly listed (or the default set if omitted). Never add an extra platform.
5. `universal_keywords` list populated with keywords that only meet 2-platform fit: the threshold
   for universal is 3 or more platforms. Enforce strictly.

## Fragile fallbacks that must not become defaults

- `seasonal_relevance: null` when season is absent: correct default, but must not silently
  appear in outputs labeled as "evergreen" — null means "not evaluated," evergreen means
  "evaluated and confirmed year-round relevance."
- `retrieval_gaps` entry for truncated keywords: required, not optional. If the list was
  truncated, the gap must be logged. Silent truncation reads as "all keywords analyzed."
- Warning for large trend-check requests (>20 cells): must appear in the output even if the
  creator did not ask for it. Do not suppress the warning because the request already ran.

## Regression cases to preserve

1. **Single keyword, all platforms, no season** (eval-001): one keyword, four platforms, no
   season or momentum. Expected: four platform_profiles; seasonal_relevance null on all;
   momentum null on all; cross_platform_verdict computed from format fit alone.

2. **Keyword list (10 items), 2 platforms, fall season** (eval-002): 10 keywords, YouTube and
   Pinterest, season=fall. Expected: 20 cells total (10 × 2); seasonal_relevance populated on all
   cells; universal_keywords contains those with strong fit on both YouTube and Pinterest;
   platform_exclusive lists separate YouTube-only and Pinterest-only entries.

3. **Input truncation at 11 keywords** (eval-003): 11 keywords supplied. Expected: exactly 10
   keywords analyzed; 11th keyword appears in retrieval_gaps with truncation note; output
   keywords_analyzed has exactly 10 entries.

4. **check_trend_momentum: true, 3 keywords × 3 platforms = 9 cells** (eval-004): within the
   20-cell warning threshold. Expected: momentum field populated on all 9 cells (rising/flat/
   declining/unknown — never null); no warning emitted.

5. **check_trend_momentum: true, 6 keywords × 4 platforms = 24 cells** (eval-005): above the
   20-cell threshold. Expected: warning appears in output notes or retrieval_gaps; momentum
   may be unknown for some cells if retrieval timed out.

6. **All keywords produce platform_specific verdict** (eval-006): highly platform-specific
   keywords provided (e.g., TikTok audio trend terms). Expected: universal_keywords is [];
   platform_exclusive_opportunities correctly populated per platform; output includes note
   that broader candidates may emerge from keyword-cluster or long-tail-expand.

7. **Navigational intent on TikTok** (eval-007): keyword with navigational intent (e.g., a brand
   name) run against TikTok. Expected: serp_feature set to "not_applicable" for that cell;
   notes field explains why; recommendation still provides actionable guidance (e.g., "use as
   a hashtag for brand awareness rather than search discovery").

## Approval-gated changes

- Any change to the `cross_platform_verdict` enum values (currently: universal, platform_specific,
  niche_long_tail).
- Any change to the `strongest_platform` tiebreaker order.
- Any change to the universal threshold (currently: 3 or more platforms).
- Any change to the per-cell competition estimate methodology (currently: SERP feature map +
  niche density patterns from seo-intelligence-engine.md).
- Adding or removing engines from `engines_required` in SKILL.md frontmatter.
- Adding momentum to the default output when `check_trend_momentum` is false (currently: null).

## Minority-report policy

**Season vs. keyword-inferred timing:** If a keyword contains seasonal language (e.g., "fall
mantel", "christmas garland") and `season` is not provided, the atom sets `seasonal_relevance:
null` rather than inferring from the keyword text. Rationale: seasonal_relevance depends on
the current date and the canonical peak windows (e.g., "fall" is peak in September to October but
off_season in February). Keyword text alone cannot resolve this without date context. What would
overturn this: add `current_month` as an optional input and, if provided, infer seasonality from
the keyword text using the canonical peak windows.

**Competition estimate sourcing:** The SERP feature type is used as a proxy for competition
level (video_carousel = medium for a new channel; featured_snippet = high; image_pack = medium to
low for Pinterest niche content). This is acknowledged as an approximation — the actual
competition depends on SERP depth and competitor authority. What would overturn this: direct
integration with a keyword tool API (Ahrefs, SEMrush) returning actual competition scores, at
which point the `[estimated]` label would change to cite the source.

## Update checklist

1. Edit the relevant section in SKILL.md or this file.
2. If the output schema changes (new field, renamed field, new enum value), update
   `evals/evals.json` to reflect the new expected output and update the output contract in SKILL.md.
3. If the universal threshold changes, update eval-002 expected output and the SKILL.md
   Step 4 definition.
4. If engines are added or removed, update `engines_required` in SKILL.md frontmatter and
   verify the engine file exists in `shared/`.
5. If the tiebreaker order changes, update eval-001 expected `strongest_platform`.
6. Run `python3 tools/sync_check.py` — must exit 0 before committing.
