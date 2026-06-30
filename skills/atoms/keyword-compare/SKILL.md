---
file: skills/atoms/keyword-compare/SKILL.md
name: keyword-compare
atom: true
description: compare 1 to 10 keywords side-by-side across platforms (YouTube, Pinterest, TikTok, Google) and optionally across a seasonal window, producing a structured matrix of intent, SERP feature, format fit, competition estimate, and seasonal relevance per keyword-platform pair plus three cross-platform verdicts (universal, platform-exclusive, niche long-tail). Use when the creator wants to decide which platform to prioritize for a keyword or batch of keywords without running four separate queries. Do NOT use for keyword research from scratch (use keyword-cluster or long-tail-expand first), seasonal planning without existing keywords (use seasonal-trends), or full SEO strategy output (use the seo-keywords spoke).
load:
  - shared/seo-intelligence-engine.md
  - shared/platform-engine.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# keyword-compare

Compare a list of keywords across platforms and optionally across a seasonal window.
Returns a structured matrix plus cross-platform verdicts so the creator can make one
decision about where to focus instead of running and collating four separate queries.

## Purpose

The creator's content decisions are inherently cross-platform: a keyword that drives
YouTube discovery may be a poor fit for Pinterest's visual search model, or it may
be a universal keyword that works everywhere. This atom surfaces the differences in
one structured output, using the SERP feature map and intent model from
`shared/seo-intelligence-engine.md` and platform-specific format rules from
`shared/platform-engine.md`. No volume API is used — competition estimates are labeled
`[estimated]` and derived from SERP feature type and niche density signals.

## When to invoke

- "Which of these keywords works on TikTok vs. YouTube?"
- "Compare this keyword across platforms."
- "Where should I focus for fall — YouTube or Pinterest?"
- "Show me which keywords overlap across platforms."
- "Do these keywords translate to Pinterest?"
- Invoke directly or from `seo-keywords` spoke via `shortcut_atoms`.

## Do NOT use for

- Keyword research from scratch — generate keywords first with `keyword-cluster` or
  `long-tail-expand`, then feed the output here.
- Seasonal content planning without existing keywords — use `seasonal-trends` spoke.
- Full SEO strategy output with titles, descriptions, and posting plan — use `seo-keywords`.
- Cross-platform scheduling with a calendar — use `calendar-slot`.
- Trending topic discovery — use `trend-check`.

## Inputs

```json
{
  "keywords": ["string — 1 to 10 items"],
  "platforms": ["youtube", "pinterest", "tiktok", "google"],
  "season": "fall | holiday | spring | summer | evergreen",
  "check_trend_momentum": false
}
```

- `keywords`: 1 to 10 keyword strings. If more than 10 are provided, the first 10 are
  analyzed and the overflow is noted in `retrieval_gaps`.
- `platforms`: defaults to all four if omitted. Accepts any subset.
- `season`: optional. If provided, each keyword is tagged with seasonal relevance
  (peak / moderate / off_season / evergreen) using the lead times from
  `seo-intelligence-engine.md`. If omitted, `seasonal_relevance` is null for all cells.
- `check_trend_momentum`: when true, calls `trend-check` per platform per keyword to add
  a momentum signal (rising / flat / declining / unknown). Adds latency proportional to
  `len(keywords) x len(platforms)`. Emit a warning in output if the product exceeds 20.
  Defaults to false; static analysis only is fast and sufficient for most decisions.

## Procedure

1. For each keyword x platform pair: call `search-intent` with the platform parameter.
   Collect `intent` label and `format_fit` (primary and secondary).
2. Apply the SERP feature map from `seo-intelligence-engine.md` to each pair: derive
   `serp_feature` (video_carousel / image_pack / featured_snippet / shopping / local_pack)
   and `competition_estimate` (low / medium / high — labeled `[estimated]`).
3. If `season` is provided: apply seasonal lead times from `seo-intelligence-engine.md`
   to tag each keyword with `seasonal_relevance` (peak / moderate / off_season / evergreen).
   Use static data from the engine — do not call a separate atom.
4. If `check_trend_momentum: true`: call `trend-check` per keyword x platform.
   Attach `momentum` to each cell. If trend-check returns null or fails, set
   `momentum: "unknown"` and record a retrieval_gap.
5. Aggregate into comparison matrix. Compute per-keyword `cross_platform_verdict`:
   - `universal`: primary format_fit aligns with the dominant SERP feature on 3 or more platforms.
   - `platform_specific`: strong alignment on 1 to 2 platforms, weak on others.
   - `niche_long_tail`: low `competition_estimate` across all platforms.

## Output

```json
{
  "tool": "keyword-compare",
  "keywords_analyzed": ["string"],
  "keywords_overflow": ["strings beyond the 10-item limit, if any"],
  "platforms_analyzed": ["string"],
  "season_context": "fall | holiday | spring | summer | evergreen | null",
  "trend_momentum_checked": false,
  "comparison_matrix": [
    {
      "keyword": "string",
      "cross_platform_verdict": "universal | platform_specific | niche_long_tail",
      "strongest_platform": "youtube | pinterest | tiktok | google | null",
      "platform_profiles": [
        {
          "platform": "youtube",
          "intent": "informational | navigational | commercial | transactional",
          "format_fit": "long-form | short-form | pin | reel",
          "serp_feature": "video_carousel | image_pack | featured_snippet | shopping | local_pack | mixed",
          "competition_estimate": "low [estimated] | medium [estimated] | high [estimated]",
          "seasonal_relevance": "peak | moderate | off_season | evergreen | null",
          "momentum": "rising | flat | declining | unknown | null",
          "recommendation": "one-sentence action for this keyword on this platform"
        }
      ],
      "notes": "string or null"
    }
  ],
  "universal_keywords": ["string"],
  "platform_exclusive_opportunities": {
    "youtube": ["string"],
    "pinterest": ["string"],
    "tiktok": ["string"],
    "google": ["string"]
  },
  "seasonal_timing_summary": "string or null — only present when season_context is non-null",
  "retrieval_gaps": [],
  "fabrication_flags": []
}
```

## Fabrication rules

- `competition_estimate` is always labeled `[estimated]`. Never cite a specific volume number
  without an attributed API source. Estimates are derived from SERP feature type and niche
  density signals in `seo-intelligence-engine.md`.
- `momentum` is only present when `check_trend_momentum: true` AND trend-check returned a
  non-null result. Never invented.
- `seasonal_relevance` is only present when `season` is provided. Set to null for all cells
  if not provided — do not infer seasonality without the input.
- `recommendation` in each platform profile is one concise, actionable sentence derived from
  intent, format_fit, serp_feature, and seasonal_relevance. No unverified statistics.

## Cross-platform verdict definitions

| Verdict | Definition |
|---|---|
| `universal` | Primary intent and format fit aligns with the dominant SERP feature on 3 or more analyzed platforms. Worth targeting everywhere. |
| `platform_specific` | Strong format fit on 1 to 2 platforms; low alignment on others. Focus on the strong platform(s). |
| `niche_long_tail` | Low competition estimate across all platforms. Specific enough to target everywhere without significant competitive pressure. |

`strongest_platform` is the platform with the best combination of format_fit alignment and
lowest competition estimate. If all are equal, return the first in `platforms_analyzed`.

## Momentum scope warning

If `check_trend_momentum: true` and `len(keywords) x len(platforms) > 20`, emit an advisory
in `retrieval_gaps`:

```
"check_trend_momentum=true with N keywords x M platforms = K calls. Consider reducing scope
or setting check_trend_momentum=false for a faster result."
```

The atom still runs — this is advisory only, not a block.
