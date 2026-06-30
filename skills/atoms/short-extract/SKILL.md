---
name: short-extract
description: extract standalone short-form clips from a long-form outline, each with its own hook. Use when video-development or shortform-repurposing needs Shorts, Reels, or TikToks from a long-form piece. Do NOT use to write the long-form outline.
---

# short-extract

Extract self-contained short-form clips from a long-form outline.

## Input
```json
{
  "longform_outline": "string or structured outline",
  "clip_count": 3
}
```

## Output
```json
{
  "tool": "short-extract",
  "clips": [
    {
      "moment": "the specific moment from the process",
      "own_hook": "first 3 seconds, works with no prior context",
      "format": "before_after | micro_tutorial | pov | satisfying",
      "duration_seconds": 30
    }
  ],
  "note": "each clip is standalone content, not an abbreviated version of the video"
}
```

## Do NOT use this atom for
- Writing the long-form outline (that is video-development or script-writer).
- Clips that assume the viewer has seen the full video.

## Pipeline note
Follows `shared/method.md`. Short-form lengths and audio-first guidance come from
`shared/platform-engine.md`. Every video concept yields at least 3 clips (the brand ecosystem ratio).
Each clip carries its own hook.
