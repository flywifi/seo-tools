---
name: thumbnail-concept
description: design ONE thumbnail concept for a video (type, composition, and 3 to 6 words of overlay text). Use when video-development needs a thumbnail. Do NOT use to write the title (use title-generate) or to render an image.
---

# thumbnail-concept

Design a single thumbnail concept.

## Input
```json
{
  "concept": "string",
  "type": "before_after_split | pov_hero | face_room"
}
```

## Output
```json
{
  "tool": "thumbnail-concept",
  "type": "string",
  "composition": "what is in frame and where",
  "text_overlay": "3 to 6 words maximum",
  "note": "1280x720, high contrast, text inside a 10 to 15 percent edge margin, aligns with the title"
}
```

## Do NOT use this atom for
- The title (use title-generate).
- More than 6 words of overlay text.
- Rendering the actual image.

## Pipeline note
Follows `shared/method.md`. Thumbnail specs and the face-fill guidance come from
`shared/platform-engine.md`. The concept must align with the title (no overpromising).
