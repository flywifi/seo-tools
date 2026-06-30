# keyword-compare — Maintainer Reference

## What this atom does

Compares a list of keywords across platforms by combining `search-intent` output, the SERP feature
map from `seo-intelligence-engine.md`, platform format rules from `platform-engine.md`, and
optionally seasonal lead times and trend momentum signals. Returns a structured matrix and three
cross-platform verdicts (universal, platform_specific, niche_long_tail).

## Invariants

1. `keywords` input is capped at 10. Overflow keywords are reported in `keywords_overflow` and
   excluded from analysis — never silently truncated.
2. `competition_estimate` is always labeled `[estimated]`. Never assert a specific search volume
   number (e.g., "5,400 monthly searches") without an attributed API source.
3. `seasonal_relevance` is null for all cells when `season` is not provided. Never infer
   seasonality from keyword text alone.
4. `momentum` is null when `check_trend_momentum: false` (the default). When true, it is
   populated from `trend-check` output or `"unknown"` on failure — never fabricated.
5. `cross_platform_verdict` is derived strictly from the `platform_profiles` computed in the
   same call. Never assert a verdict without supporting profile data.
6. `platform_exclusive_opportunities` is an empty array (not null) when no platform-exclusive
   keywords are found.

## Computation model

### Step 1: search-intent per pair
For each (keyword, platform) pair, call `search-intent` with the platform parameter.
Output: `intent` (informational / navigational / commercial / transactional), `format_fit`.

### Step 2: SERP feature map (from seo-intelligence-engine.md)
Map intent + platform to the dominant SERP feature:
- Tutorial / how-to + YouTube or Google: `video_carousel`
- Inspiration / aesthetic + Pinterest or Google: `image_pack`
- "Best of" / recommendation: `featured_snippet`
- Product / purchase queries: `shopping`
- Local queries ("near me"): `local_pack`

Competition estimate derived from feature type:
- `video_carousel` in a competitive niche: `high [estimated]`
- `image_pack`, `featured_snippet`: `medium [estimated]`
- `local_pack`, TikTok evergreen: `low [estimated]`

These are orientation guides. Verify with platform analytics before significant investment.

### Step 3: seasonal relevance (when season is provided)
Use seasonal lead times from `seo-intelligence-engine.md` (Part 7):
- Fall: peak September 15 to October 20
- Holiday: peak November 20 to December 15
- Spring: peak March 1 to April 15
- Summer: peak May 1 to June 30

`peak` = primary search window overlaps requested season. `moderate` = adjacent season.
`evergreen` = no strong seasonal pattern. `off_season` = peak is in a different season.

### Step 4: cross-platform verdict
After computing all platform_profiles for a keyword:
- Count platforms where `format_fit` aligns with `serp_feature` (primary match).
- 3 or more align: `universal`.
- 1 to 2 align: `platform_specific` — `strongest_platform` = the best-aligning one.
- All platforms show `low [estimated]`: `niche_long_tail`.

## Regression cases (map to evals/evals.json)

| Case | Input | Expected |
|---|---|---|
| Single keyword, all platforms | 1 keyword, 4 platforms, no season | 1 matrix row, 4 profiles, no null competition_estimate |
| 10-keyword batch, 2 platforms | 10 keywords | 10 rows, 2 profiles each, keywords_overflow empty |
| 11-keyword overflow | 11 keywords | first 10 analyzed, 1 in keywords_overflow |
| Season context | 3 keywords, fall | seasonal_relevance non-null; seasonal_timing_summary present |
| Trend momentum enabled | 2 keywords x 2 platforms, check_trend_momentum=true | momentum non-null in each cell or "unknown" with retrieval_gap |
| Momentum warning trigger | 6 keywords x 4 platforms, check_trend_momentum=true | retrieval_gaps includes momentum scope warning (24 > 20) |
| Universal verdict | keyword with strong fit across 3+ platforms | cross_platform_verdict=universal |
| Platform-specific verdict | niche keyword fitting only Pinterest | cross_platform_verdict=platform_specific, strongest_platform=pinterest |

## Update checklist

When `seo-intelligence-engine.md` SERP feature map changes:
- Update competition estimate logic in SKILL.md Step 2
- Re-run eval case "Single keyword, all platforms"

When platform format rules in `platform-engine.md` change:
- Update `format_fit` mapping in SKILL.md Step 1
- Re-run eval cases "Universal verdict" and "Platform-specific verdict"

When `search-intent` or `trend-check` atom output contracts change:
- Update field name references in the procedure steps
- Update the affected eval cases
