---
name: title-generate
description: generate a few title options for a video, human readable first and SEO aware second, front-loading the primary keyword. Use when video-development or seo-keywords needs titles. Do NOT use to write the thumbnail text (use thumbnail-concept) or the description.
---

# title-generate

Generate title options for one concept.

## Input
```json
{
  "concept": "string",
  "primary_keyword": "string",
  "style": "the aesthetic style label, for example vintage or modern",
  "platform": "youtube"
}
```

## Output
```json
{
  "tool": "title-generate",
  "titles": [
    {
      "title": "string",
      "chars": 0,
      "keyword_front_loaded": true
    }
  ],
  "note": "human readable first, SEO aware second; balance curiosity with clarity"
}
```

## Do NOT use this atom for
- Thumbnail overlay text (use thumbnail-concept).
- Overpromising beyond what the video delivers.

## Pipeline note
Follows `shared/method.md`. Title length and front-loading guidance come from
`shared/platform-engine.md` (roughly 80 to 100 characters for search and how-to). A useful pattern:
"[Action] My [Space] with [Approach] ([Style] Inspired)."

## Cross-modality
Inherits its calling spoke's class (varies by caller (B/C)); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
