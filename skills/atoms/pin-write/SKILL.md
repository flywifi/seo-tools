---
file: skills/atoms/pin-write/SKILL.md
name: pin-write
description: write one Pinterest Pin set (title max 100 chars, description max 500 chars, alt text max 500 chars) for home decor and DIY content. Keyword-front-loaded for Pinterest search discovery. Use when shortform-repurposing, content-calendar, or any spoke needs a ready-to-publish Pinterest Pin. Do NOT use for Instagram captions, TikTok captions, YouTube descriptions, or any non-Pinterest output.
load:
  - shared/platform-engine.md
  - shared/brand-engine.md
  - shared/voice-engine.md
  - protocols/no-fabrication.md
---

# pin-write

Write one Pinterest Pin set per call: a keyword-first title, a keyword-rich description with a CTA, and descriptive alt text for accessibility. Pinterest is a visual search engine; every field is an SEO field. Keywords must appear early and naturally.

## Purpose

Produce a complete, publish-ready Pinterest Pin set scoped to one topic. The title leads with the primary keyword. The description front-loads keywords, delivers value in the body, and closes with a CTA that drives outbound clicks or saves. Alt text describes the image for screen readers and also carries relevant keywords.

Pin specs from `shared/platform-engine.md`: standard Pin 2:3 at 1000x1500px. Titles and descriptions drive discovery; lean on them more than hashtags. Pins compound and drive traffic for months to years after posting, which suits evergreen DIY and decor.

## Inputs

```json
{
  "topic": "string (required: the content topic or working title)",
  "video_url": "optional string (URL to link the Pin to; used for video or tutorial content)",
  "board_name": "optional string (target Pinterest board; informs keyword tone if provided)",
  "keyword_cluster": "optional object (output from keyword-cluster atom; use primary and secondary fields to seed the Pin copy)",
  "persona": "optional string (target persona from shared/brand-engine.md; calibrates specificity and voice)"
}
```

Field notes:
- `topic` is required. Pass the working title or a plain description of the content.
- `video_url` and `board_name` are optional; include either when available to sharpen relevance.
- `keyword_cluster` is optional but strongly recommended. If omitted, the atom derives keywords from the topic alone.
- `persona` is optional; when provided it tightens the vocabulary to that audience segment.

## Output

```json
{
  "tool": "pin-write",
  "pin_title": "string (max 100 chars, keyword-first, specific and action-oriented)",
  "pin_description": "string (max 500 chars, keyword-rich, includes CTA, no hashtag clutter)",
  "alt_text": "string (max 500 chars, descriptive for accessibility, carries relevant keywords)",
  "seo_keywords_used": ["list of keywords woven into the pin set"],
  "character_counts": {
    "pin_title": 0,
    "pin_description": 0,
    "alt_text": 0
  },
  "notes": "string or null (flags, truncation warnings, or keyword sourcing notes)"
}
```

### Character limits (enforced)

| Field | Limit | Notes |
|---|---|---|
| pin_title | 100 chars | Keyword-first; Pinterest shows roughly 40 chars in the feed, so the primary keyword must appear in the first 3 to 5 words |
| pin_description | 500 chars | Front-load keywords in the first sentence; body delivers value; final sentence is the CTA |
| alt_text | 500 chars | Describe what is in the image specifically; weave in 1 to 2 keywords naturally; do not keyword-stuff |

If a draft exceeds the field limit, trim body copy first, preserve the leading keyword phrase and the CTA, and set `notes` to explain what was shortened.

### SEO writing rules for Pinterest

- Titles must open with the primary keyword phrase, not a brand name or article.
- Descriptions must place the most important keyword in the first clause of the first sentence.
- Use specific, concrete vocabulary: "dark moody bedroom with jewel-tone velvet curtains" outperforms "beautiful room ideas."
- CTAs in descriptions are action-oriented and Pinterest-native: "Save this for your next room refresh," "Pin it and shop the look," or "Click through for the full tutorial."
- Do not open with "I" or the brand name; open with the subject keyword.
- No em dashes anywhere in the output.

## Do NOT use for

- Instagram, TikTok, or YouTube Shorts captions (use caption-write with the appropriate platform field).
- Full YouTube video descriptions (use the description-write atom or the relevant spoke).
- Video titles or thumbnail text (use title-generate or thumbnail-concept).
- Batch Pin generation across multiple topics in one call; call once per Pin.
- Fabricating search volume, trend data, or engagement benchmarks; see `protocols/no-fabrication.md`.
- Any output where platform specs have not been loaded; always load `shared/platform-engine.md` before writing.

## Pipeline note

Platform SEO rules and Pin specs (2:3 ratio, 1000x1500px, keyword-forward copy strategy) come from `shared/platform-engine.md`. Voice and persona guidance come from `shared/brand-engine.md` (published-to-audience mode: warm, specific, draws the viewer in; no em dashes). When a `keyword_cluster` is passed from the keyword-cluster atom, use its `primary` field to anchor the Pin title and its `secondary` field to seed the description body. This atom does not fabricate keyword difficulty scores, search volume, or engagement metrics; see `protocols/no-fabrication.md`.
