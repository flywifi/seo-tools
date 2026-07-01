---
file: skills/seo-keywords/SKILL.md
name: seo-keywords
description: "build a full SEO strategy for a content topic: keyword cluster, search intent, competitive gap analysis, and a recommended title and description skeleton. Optimized for YouTube; also covers Pinterest and TikTok."
load: always
---

# seo-keywords

The SEO strategy spoke for the Content lane. Given a content topic, it produces a verified keyword
cluster, a search intent classification, a competitive gap analysis, and a recommended title and
description skeleton ready for the video-development spoke or direct use.

## Purpose

seo-keywords answers the question: "What keywords should I rank for, who is already ranking, and
what title structure gives the creator the best chance to surface in search and suggested video?" It
is the authoritative SEO input for any Content lane artifact. It does not generate hooks, outlines,
or production packages (use video-development for those). It does not write final copy (it produces
a skeleton). It does not assert exact search volume figures as confirmed fact; all volume signals
are presented as estimated ranges sourced from web-intel retrieval and must be independently
verified before use in an editorial decision.

Platform priority order: YouTube (primary), Pinterest (secondary), TikTok (secondary). The spoke
runs a YouTube-first strategy and adapts signals to Pinterest and TikTok using
`shared/platform-engine.md`. Pinterest and TikTok outputs are labeled as platform-adapted
extensions of the YouTube strategy, not independent SEO studies.

All retrieval passes through `shared/injection-guard-engine.md`. Platform spec freshness window is
3 to 6 months per `protocols/research-citation.md`; specs older than 6 months are marked stale
and flagged for re-verification.

## Inputs

```json
{
  "topic": "string -- the content topic or seed keyword (required)",
  "platform_targets": ["youtube", "pinterest", "tiktok"],
  "persona": "string -- target persona label from shared/audience-engine.md (optional; inferred if omitted)",
  "competitor_count": "integer -- competitors to surface per platform (default: 5, max: 10)"
}
```

- `topic`: a keyword phrase or concept (for example, "home decor bedroom on a budget" or "vintage
  thrift flip DIY").
- `platform_targets`: defaults to all three platforms if omitted. YouTube is always included.
- `persona`: if omitted, the spoke infers from the topic and states the inference explicitly in the
  output so the creator can confirm or override.
- `competitor_count`: passed directly to competitor-scan; controls how many competitors are returned
  per platform call.

## Primary outputs

```json
{
  "skill": "seo-keywords",
  "topic": "string",
  "persona_used": "string",
  "keyword_cluster": {
    "primary": ["1 to 2 exact-phrase keywords recommended for the title"],
    "secondary": ["2 to 4 keywords for the description body and tags"],
    "long_tail": ["4 to 8 keywords for the description, chapter titles, and hashtags"],
    "difficulty_note": "which primaries are high-competition for a new or mid-size channel",
    "volume_estimates": {
      "note": "All figures are estimated ranges from web-intel retrieval. Treat as directional only. Verify with YouTube Studio, Google Trends, or a keyword tool before using in an editorial decision.",
      "primary_range": "example: roughly 10,000 to 50,000 monthly searches [estimated, unverified]",
      "long_tail_range": "example: roughly 500 to 5,000 monthly searches [estimated, unverified]"
    }
  },
  "search_intent": {
    "classified_intent": "informational | navigational | transactional | inspirational",
    "platform_intent_notes": {
      "youtube": "string -- what the searcher expects to find on YouTube for this keyword",
      "pinterest": "string -- what the searcher expects to find on Pinterest for this keyword",
      "tiktok": "string -- what the searcher expects to find on TikTok for this keyword"
    },
    "content_format_implication": "string -- format and structure recommendation implied by the intent classification"
  },
  "competitive_gap_analysis": {
    "youtube": {
      "overserved_angles": ["list of angles already covered by multiple competitors"],
      "underserved_angles": ["list of angles with thin or absent coverage"],
      "gap_summary": "string -- most actionable differentiation opportunity for the creator on YouTube",
      "confidence": "high | medium | low"
    },
    "pinterest": {
      "overserved_angles": [],
      "underserved_angles": [],
      "gap_summary": "string",
      "confidence": "high | medium | low"
    },
    "tiktok": {
      "overserved_angles": [],
      "underserved_angles": [],
      "gap_summary": "string",
      "confidence": "high | medium | low"
    }
  },
  "title_skeleton": {
    "recommended_titles": [
      {
        "title": "string -- primary keyword front-loaded; human readable first",
        "chars": 0,
        "keyword_front_loaded": true,
        "platform": "youtube"
      }
    ],
    "description_skeleton": {
      "opening_200_chars": "string -- primary keyword in first sentence; hook the viewer in the first two lines visible before 'show more'",
      "body_structure": ["keyword-rich paragraph 1 outline", "keyword-rich paragraph 2 outline", "chapter timestamps placeholder", "hashtag block placeholder"],
      "pinterest_description_skeleton": "string -- 150 to 300 character Pinterest description adapted from the YouTube description; keyword at the front",
      "tiktok_caption_skeleton": "string -- under 150 characters; primary keyword or hashtag in the first line"
    }
  },
  "retrieval_gaps": ["any keyword or competitor data that could not be retrieved; manual check required"],
  "fabrication_flags": ["any field that could not be confirmed by retrieval and is marked [unverified]"],
  "source_artifacts": [],
  "human_review_required": true
}
```

Key output guarantees:

- Volume figures are always ranges labeled "[estimated, unverified]". Exact numbers are never
  asserted. The output block includes an explicit note directing the creator to verify with a live
  tool before acting.
- Competitor names, URLs, and scale tiers from competitor-scan are passed through unchanged,
  including their [unverified] labels where present.
- The title skeleton is ready to hand to title-generate for final polish; it is a draft, not a
  finished title.
- `human_review_required` is always true. The govern-artifact gate must pass before any output
  from this spoke is used in a published artifact.

## Atoms composed

1. keyword-cluster: builds the primary, secondary, and long-tail keyword lists for YouTube;
   adapts secondary and long-tail lists for Pinterest and TikTok via platform-engine.
2. search-intent: classifies the dominant search intent for the topic on each platform and derives
   a content format implication.
3. competitor-scan: called once per platform (up to three calls); surfaces overserved and
   underserved angles and generates the gap summary.
4. title-generate: generates 2 to 4 title skeleton options with character counts and
   keyword-front-loading flags.
5. govern-artifact: gates the full strategy package through quality-review before release.

## Engines required

- `shared/platform-engine.md`: platform SEO differences, character limits, spec freshness window
  (3 to 6 months).
- `shared/web-intel-engine.md`: live keyword signal retrieval starting at Level 2 (public
  analytics endpoints) and falling through to Levels 3 and 4 if Level 2 returns thin results.
- `shared/seo-intelligence-engine.md`: topical authority model, algorithm signal hierarchy,
  entity SEO rules, long-tail expansion methodology, SERP feature map, seasonal lead times.

## References

- `shared/platform-engine.md`
- `shared/seo-intelligence-engine.md`
- `protocols/research-citation.md` (platform spec freshness window: 3 to 6 months)
- `protocols/no-fabrication.md`
- `shared/web-intel-engine.md`
- `shared/brand-engine.md` (home decor keyword vocabulary and aesthetic guard)
- `protocols/quality-gates.md` (governs the govern-artifact gate at the end of the workflow)

## Do NOT use for

- Generating hooks, outlines, scripts, or thumbnail concepts. Use video-development for those.
- Writing final copy for a description or caption. This spoke produces skeletons; use
  video-development or document-studio for finished copy.
- Asserting exact search volume figures as verified fact. Volume output from this spoke is always
  an estimated range requiring independent verification.
- Researching the creator's own channel analytics or video performance. Use the platform API
  connection via web-intel-engine Level 1 directly.
- Trend momentum research outside a specific keyword. Use trend-check for broad trend signals.
- Brand partnership or sponsorship research. Use deal-tracker or account-manager spokes.
- Any topic outside the home decor and DIY niche. This spoke's keyword vocabulary
  and competitor pool are calibrated to that niche; off-niche results will be unreliable.
