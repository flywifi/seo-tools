---
name: keyword-compare
atom: true
description: Given 1 to 10 keywords and a target platform set, produces a side-by-side comparison
  matrix showing search intent, format fit, SERP feature, competition estimate, and seasonal
  relevance for each keyword across each platform — so the creator can decide where to focus and
  which keywords travel across platforms vs. belong to one. Do NOT use for generating keywords from
  scratch (use keyword-cluster or long-tail-expand first) or for full SEO strategy (use
  seo-keywords spoke).
engines_required:
  - shared/seo-intelligence-engine.md
  - shared/platform-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# keyword-compare

## When to use this atom

Use this atom when the creator already has a list of keywords and wants to know which platforms
they work on and why. Triggers: "which of these keywords works on TikTok vs. YouTube?", "compare
this keyword across platforms", "where should I focus for fall — YouTube or Pinterest?", "do these
keywords translate to Pinterest?", "show me which keywords overlap across platforms", "which of
these are universal?", "how does this keyword perform on Google vs. YouTube?"

Invoke directly (shortcut from seo-keywords) when a keyword list already exists. Invoke from
creator-core when request classification is `keyword_research` and the phrasing includes
comparison language.

Do NOT use for keyword discovery — use `keyword-cluster` or `long-tail-expand` to build the
keyword list first, then pass the results here. Do NOT use for a full SEO strategy — use the
`seo-keywords` spoke, which orchestrates this atom alongside intent, competitor, and title work.

## Inputs

Required:
- `keywords`: list of 1 to 10 keyword strings. If more than 10 are provided, take the first 10
  and flag in retrieval_gaps.

Optional:
- `platforms`: list of platforms to compare across; defaults to all four if omitted:
  `["youtube", "pinterest", "tiktok", "google"]`
- `season`: one of `fall | holiday | spring | summer | evergreen`. When provided, each keyword
  cell is tagged with `seasonal_relevance` (peak / moderate / off_season / evergreen) using
  `seasonal-map` canonical peak windows.
- `check_trend_momentum`: boolean, default false. When true, runs `trend-check` per platform per
  keyword for a live momentum signal. Slow for large inputs — emit a warning in output if
  `keyword_count × platform_count > 20` and recommend reducing scope.

## Core procedure

Follow `shared/method.md`.

### Step 1: Per-platform intent and format classification

For each keyword × platform combination, classify using the intent taxonomy and SERP feature map
from `shared/seo-intelligence-engine.md`:

- `intent`: informational | navigational | commercial | transactional
- `format_fit` (primary): long-form | short-form | reel | pin | blog-post
- `serp_feature`: video_carousel | image_pack | featured_snippet | shopping_ads | local_pack |
  knowledge_panel | blue_link_organic | mixed
- `competition_estimate`: low | medium | high — derived from SERP feature type and niche density
  patterns in seo-intelligence-engine.md. Always labeled `[estimated]`. Never cite a number
  without a source.

Use `shared/platform-engine.md` to ensure platform-specific format conventions (e.g., Pinterest
favors 2:3 visual content; TikTok favors 7-second hook with rewatch design; YouTube long-form
rewards chapter markers).

### Step 2: Seasonal tagging (conditional)

If `season` is provided, call `seasonal-map` logic from the canonical peak windows in
`shared/seo-intelligence-engine.md`:

- Fall peak: September to October. Pinterest lead time 6 to 8 weeks (publish by mid-August).
- Holiday peak: November to December. Pinterest lead time 6 to 8 weeks (publish by late October).
- Spring peak: March to April. Pinterest lead time 6 to 8 weeks (publish by mid-January).
- Summer peak: May to June. Pinterest lead time 6 to 8 weeks (publish by late March).

Set `seasonal_relevance` per cell: peak | moderate | off_season | evergreen.

If `season` is not provided, set `seasonal_relevance: null` for all cells. Do not infer
seasonality from the keyword text alone.

### Step 3: Trend momentum (conditional)

If `check_trend_momentum: true`, retrieve momentum signals via `shared/web-intel-engine.md`
Level 1 (Google Trends proxy, YouTube autocomplete trending indicators) for each keyword × platform
pair. Set `momentum`: rising | flat | declining | unknown.

If retrieval fails or is inconclusive: set `momentum: unknown` and log in retrieval_gaps. Never
infer momentum from keyword text alone.

If `check_trend_momentum: false`: set `momentum: null` for all cells.

### Step 4: Cross-platform verdict per keyword

After building all platform profiles for a keyword, compute `cross_platform_verdict`:

- `universal`: strong format fit (format_fit is appropriate content type for the platform's
  dominant SERP feature) on 3 or more platforms.
- `platform_specific`: strong fit on 1 to 2 platforms, weak or mismatched on others.
- `niche_long_tail`: low competition estimate across all platforms — likely worth targeting
  everywhere even at modest volume.

Set `strongest_platform`: the platform where intent + format fit + SERP feature alignment is
highest. When two platforms tie, prefer YouTube (reaches both YouTube Search and Google video
carousel) over Pinterest, Pinterest over TikTok.

### Step 5: Aggregate output

- `universal_keywords`: keywords where `cross_platform_verdict = universal`.
- `platform_exclusive_opportunities`: keyed by platform, listing keywords where that platform
  shows strong fit but others do not.
- `seasonal_timing_summary`: one-sentence summary of the seasonal window and its implications if
  `season` was provided; null if not.

## Output contract

```json
{
  "keywords_analyzed": ["string"],
  "platforms_analyzed": ["string"],
  "season_context": "fall | holiday | spring | summer | evergreen | null",
  "comparison_matrix": [
    {
      "keyword": "string",
      "cross_platform_verdict": "universal | platform_specific | niche_long_tail",
      "strongest_platform": "youtube | pinterest | tiktok | google",
      "platform_profiles": [
        {
          "platform": "youtube",
          "intent": "informational | navigational | commercial | transactional",
          "format_fit": "long-form | short-form | reel | pin | blog-post",
          "serp_feature": "video_carousel | image_pack | featured_snippet | shopping_ads | local_pack | knowledge_panel | blue_link_organic | mixed",
          "competition_estimate": "low | medium | high [estimated]",
          "seasonal_relevance": "peak | moderate | off_season | evergreen | null",
          "momentum": "rising | flat | declining | unknown | null",
          "recommendation": "one-sentence action for this platform"
        }
      ],
      "notes": "string"
    }
  ],
  "universal_keywords": ["string"],
  "platform_exclusive_opportunities": {
    "youtube": ["string"],
    "pinterest": ["string"],
    "tiktok": ["string"],
    "google": ["string"]
  },
  "seasonal_timing_summary": "string | null",
  "retrieval_gaps": []
}
```

Always honor `protocols/formatting-metadata.md`: no em dashes in any output field; ranges use
"to"; `competition_estimate` always carries `[estimated]` label in the recommendation text or
notes field. All momentum data labeled with source type (Google Trends proxy, autocomplete signal)
when present.

## Engines and protocols loaded

- `shared/seo-intelligence-engine.md` (intent taxonomy, SERP feature map, long-tail methodology,
  seasonal lead times)
- `shared/platform-engine.md` (per-platform format specs, keyword conventions)
- `protocols/no-fabrication.md` (no invented competition figures, no fabricated momentum, null
  and flag when data is unavailable)
- `protocols/formatting-metadata.md` (no em dashes, ranges with "to", [estimated] labels)

## Atoms used

Composes internally (via instruction, not workflow.json — this is a leaf atom):
- `search-intent` logic (per keyword × platform cell)
- `seasonal-map` logic (conditional, when season is provided)
- `trend-check` logic (conditional, when check_trend_momentum is true)

Callable directly as a shortcut from `seo-keywords` spoke (`shortcut_atoms` entry).

## Standalone usability

Produces a complete platform comparison matrix from a keyword list and platform set alone, with
no downstream skill required. The `recommendation` field in each cell gives one concrete action
per platform so the creator can act immediately.

## Failure modes

- More than 10 keywords provided: take the first 10, list the remainder in retrieval_gaps with
  note "truncated to 10-keyword limit."
- `check_trend_momentum: true` with keyword_count × platform_count > 20: emit warning in output
  ("large input — trend retrieval may be slow or incomplete") and set momentum to unknown for
  any cell where retrieval times out.
- Season not provided: set seasonal_relevance to null for all cells. Do not guess from keyword
  text (e.g., "fall mantel" does not automatically get seasonal_relevance: peak without a season
  input).
- Platform-intent combination with no clear SERP feature (e.g., navigational intent on TikTok):
  set serp_feature to "not_applicable" and note in the cell's notes field.
- All keywords produce platform_specific verdicts (no universal keywords): set universal_keywords
  to [] and note in seasonal_timing_summary or a top-level note that keyword-cluster or
  long-tail-expand may surface broader cross-platform candidates.
