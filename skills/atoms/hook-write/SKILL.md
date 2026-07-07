---
name: hook-write
description: write ONE hook for a video or short that lands the promise or problem in the first seconds. Use when video-development, shortform-repurposing, or script-writer needs a hook. Do NOT use to write the full script or outline.
load:
  - shared/brand-engine.md
  - shared/voice-engine.md
---

# hook-write

Write a single hook in the creator's published voice.

## Input
```json
{
  "concept": "string",
  "persona": "the persona this serves",
  "platform": "youtube_longform | shorts | reels | tiktok",
  "duration_seconds": 30
}
```

## Output
```json
{
  "tool": "hook-write",
  "hook": "the spoken or on-screen hook line",
  "promise_or_problem": "what it establishes",
  "first_seconds": "copy for the opening window (3 seconds short-form, up to 30 long-form)",
  "note": "establish the promise or problem before any process content"
}
```

## Do NOT use this atom for
- A full outline or script (use script-section or script-writer).
- A title (use title-generate).

## Pipeline note
Follows `shared/method.md`. Voice comes from `shared/brand-engine.md` (published mode); opening-window
lengths come from `shared/platform-engine.md`. For short-form the hook must work with no prior context.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
