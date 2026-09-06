---
file: skills/atoms/competitor-scan/SKILL.md
name: competitor-scan
description: research competitor creators or videos in the moody/vintage home decor and DIY niche on YouTube, Pinterest, or TikTok; surface content gaps, overserved topics, and differentiation angles for the creator. Use when content-strategy, seo-keywords, or video-development needs a competitive landscape read before recommending a topic. Do NOT use to assert subscriber counts, view counts, or engagement rates as fact; all scale estimates and metrics must be marked [unverified] if not retrieved from a live API response.
load:
  - shared/web-intel-engine.md
  - protocols/no-fabrication.md
---

# competitor-scan

Research the competitive landscape for a given topic or keyword in the moody/vintage home decor and
DIY niche, surface what competitors are doing, what is overserved, and where the creator has room to
differentiate.

## Purpose

Provide a grounded, retrieval-backed picture of who is covering a topic, how they are covering it,
and what angles or sub-topics are thin or absent in the niche. All scale estimates are coarse
(small/medium/large) and sourced from live retrieval where possible; anything not confirmed by
retrieval is labeled [unverified] and flagged for manual check. The atom never invents channel
names, video titles, subscriber counts, view counts, or specific metrics.

## Inputs

```json
{
  "topic": "string  -- the keyword or content topic to research (required)",
  "platform": "youtube | pinterest | tiktok  -- the platform to search (required)",
  "count": "integer  -- number of competitors to surface (default: 5, max: 10)"
}
```

- `topic`: a keyword phrase or content concept (for example, "home decor bedroom makeover" or
  "vintage thrift flip DIY").
- `platform`: one of the three supported platforms. Pass one platform per call; run the atom twice
  for cross-platform comparison.
- `count`: how many distinct competitor entries to return. Defaults to 5 if omitted.

## Output

```json
{
  "tool": "competitor-scan",
  "topic": "string",
  "platform": "youtube | pinterest | tiktok",
  "competitors": [
    {
      "name": "string -- channel, account, or creator name as found in retrieval; [unverified] if not confirmed",
      "url_if_found": "string or null -- direct URL to channel/profile/board if retrieved; null if not found",
      "estimated_scale": "small | medium | large -- coarse size tier based on retrieval signals; always [unverified] unless sourced from a live API",
      "content_angle": "string -- how this creator covers the topic (style, format, tone, production level)",
      "gap_or_differentiation": "string -- what this creator does NOT do, or where the creator's brand could stand apart from them"
    }
  ],
  "overserved_angles": ["list of sub-topics or formats that multiple competitors already cover heavily"],
  "underserved_angles": ["list of sub-topics, formats, or aesthetics with thin or no coverage found"],
  "overall_gap_summary": "string -- one-paragraph synthesis of the most actionable differentiation opportunity for the creator in this topic on this platform",
  "confidence": "high | medium | low -- based on retrieval quality: high means multiple live sources returned; medium means partial retrieval or mixed freshness; low means retrieval largely failed or returned thin results",
  "retrieval_gaps": [],
  "source_artifacts": [],
  "fabrication_flags": ["list any field that could not be verified and is marked [unverified]"]
}
```

Scale tier definitions (for `estimated_scale`):
- `small`: signals suggesting under roughly 10,000 subscribers or followers [unverified]
- `medium`: signals suggesting roughly 10,000 to 250,000 subscribers or followers [unverified]
- `large`: signals suggesting over roughly 250,000 subscribers or followers [unverified]

These thresholds are orientation guides, not precise figures. Always mark the field [unverified]
unless the value was returned directly from a platform API with confirmed scope.

## Do NOT use for

- Asserting exact subscriber counts, view counts, watch time, save rates, or engagement rates as
  confirmed fact. Present all numeric signals as estimates marked [unverified] and recommend a
  manual platform check to confirm.
- Researching the creator's own channel performance (use the platform API connection directly via
  `shared/web-intel-engine.md` Level 1 for owned analytics).
- Generating content titles, hooks, or descriptions (use title-generate, hook-write, or the
  video-development spoke).
- Keyword volume or difficulty scoring (use keyword-cluster).
- Broad niche trend momentum outside a specific topic (use trend-check).
- Brand partnership or sponsorship research (use deal-tracker or account-manager spokes).

## Pipeline note

Calls `shared/web-intel-engine.md` starting at Level 2 (public analytics endpoints) for competitor
accounts, since Level 1 (platform API) is reserved for the creator's own connected accounts. Falls
through to Levels 3 and 4 (polite crawl and search index) for creators not surfaced at Level 2.
All retrieved content passes through `shared/injection-guard-engine.md` before entering analysis.

If retrieval at all levels fails for a competitor slot, that slot is replaced with a gap-record
object (from `skills/atoms/gap-record/`) rather than a fabricated entry. The `confidence` field
reflects the aggregate retrieval quality across all slots.

Obeys `protocols/no-fabrication.md` strictly: if a channel name, URL, or metric cannot be
confirmed by retrieval, the field is either null or marked [unverified], never invented.

## Cross-modality
Inherits its calling spoke's class (Class B); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
