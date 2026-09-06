---
name: serp-feature-check
description: Given a keyword and platform, identify which SERP feature dominates for that query
  type (video carousel, image pack, featured snippet, shopping ads, local pack) and return the
  content format and optimization tactics most likely to win that feature. Do NOT use for keyword
  research (use keyword-cluster) or live rank tracking — this atom classifies SERP feature type
  from static pattern knowledge plus optional live fetch; it does not return current ranking
  positions for specific pages.
version: 1.0.0
lane: content
atom: true
load:
  - shared/seo-intelligence-engine.md
  - shared/web-intel-engine.md
  - shared/platform-engine.md
  - protocols/no-fabrication.md
---

# serp-feature-check

## What it does

Classifies the dominant SERP feature type for a given keyword and recommends which content format
and optimization approach wins it. Uses the static SERP feature map in `shared/seo-intelligence-engine.md`
as the primary source. When `check_live: true`, performs a web-intel-engine Level 3 polite crawl
of the live Google search results page for the keyword to confirm what features are present, then
enriches the static classification with observed data.

## Input

```json
{
  "keyword": "string",
  "platform": "google | youtube",
  "check_live": "boolean — default false; set true to retrieve and parse the live SERP"
}
```

## Output

```json
{
  "keyword": "string",
  "dominant_serp_feature": "video_carousel | image_pack | featured_snippet | shopping_ads | local_pack | knowledge_panel | blue_link_organic | mixed",
  "recommended_content_format": "string — e.g. long-form YouTube video with chapters, Pinterest pin with keyword-rich description",
  "optimization_tactics": ["string — 2 to 4 specific actionable tactics for this feature"],
  "secondary_features_present": ["string"],
  "live_check_performed": "boolean",
  "live_check_notes": "string or null — what was observed if live check ran",
  "confidence": "high | medium | low",
  "confidence_note": "string — explains confidence rating",
  "retrieval_gaps": []
}
```

## Rules

- When `check_live: false`, confidence is medium unless the keyword clearly matches a well-documented
  pattern (tutorial query = video carousel is high confidence; ambiguous query = low).
- When `check_live: true` and retrieval fails (robots.txt blocked, CAPTCHA wall), fall back to
  static classification with `confidence: medium` and note the retrieval gap.
- Never report a ranking position for a specific page or URL. The output is feature type and
  format recommendation, not "your video is ranked #3."
- `optimization_tactics` must be specific (e.g. "Add chapter timestamps in description with exact
  keyword in chapter titles") not generic (e.g. "optimize your video").

## Engines and protocols loaded

- shared/seo-intelligence-engine.md (SERP feature map, query type patterns)
- shared/web-intel-engine.md (live SERP crawl via Level 3 when check_live is true)
- shared/platform-engine.md (platform-specific format constraints)
- protocols/no-fabrication.md (no invented ranking positions or volume figures)

## Cross-modality
Inherits its calling spoke's class (Class B); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
