---
name: topical-authority-map
description: Given a content pillar and primary keyword cluster, produce a hub-and-cluster content
  architecture — one hub video angle and 3 to 5 satellite video angles — that together build topical
  authority on the subject across YouTube and Pinterest. Tells the caller what to make and in what
  order, not how to make it. Do NOT use for script generation (use script-section), keyword
  research (use keyword-cluster first), or scheduling (use calendar-slot).
version: 1.0.0
lane: content
atom: true
load:
  - shared/seo-intelligence-engine.md
  - shared/brand-engine.md
  - shared/platform-engine.md
  - protocols/no-fabrication.md
---

# topical-authority-map

## What it does

Maps a hub-and-cluster content architecture for one topic. The hub is a comprehensive long-form
video on the broadest version of the keyword. Satellites are specific-angle shorter videos targeting
long-tail variations of the same topic. Together they build topical authority: YouTube rewards the
watch-time chain when viewers move from the hub to satellites, and Pinterest rewards multiple pins
on the same keyword phrase across the same board.

## Input

```json
{
  "pillar": "one of the five content pillars from brand-engine.md",
  "primary_keyword": "string — the broad keyword the hub will target",
  "secondary_keywords": ["string — 2 to 4 secondary terms from keyword-cluster output"],
  "persona_focus": "optional string — persona name from audience-engine.md",
  "cluster_size": "optional integer — number of satellites, default 4, min 3, max 6"
}
```

## Output

```json
{
  "hub": {
    "working_title": "string",
    "angle": "string — one sentence on what makes this the comprehensive anchor piece",
    "format": "long-form",
    "keyword_targeted": "string"
  },
  "satellites": [
    {
      "working_title": "string",
      "angle": "string — one sentence on the specific sub-angle",
      "format": "long-form | short-form",
      "keyword_targeted": "string — the long-tail variant this satellite targets",
      "cross_link_to_hub": true,
      "publish_after_hub": true
    }
  ],
  "cluster_depth": "shallow | medium | deep",
  "build_order_note": "string — recommended publish sequence in one sentence",
  "persona_served": "string or null",
  "retrieval_gaps": []
}
```

## Rules

- Hub is always long-form. Satellites can be short-form if the sub-angle can be demonstrated
  fully in under 60 seconds.
- Every satellite has `cross_link_to_hub: true` and `publish_after_hub: true`. The calling spoke
  ensures the hub URL appears in each satellite's description.
- Never assign `keyword_targeted` to a keyword not present in the caller's input without marking
  it `[inferred]` in the working_title.
- `cluster_depth`: shallow = 3 satellites, obvious angles only; medium = 4 to 5 with at least
  one unexpected long-tail angle; deep = 6 satellites extending the content calendar 6 to 10 weeks.

## Engines and protocols loaded

- shared/seo-intelligence-engine.md (topical authority model, algorithm signals)
- shared/brand-engine.md (aesthetic and pillar guard on working titles)
- shared/platform-engine.md (format decisions: long-form vs short-form satellite)
- protocols/no-fabrication.md (no invented keywords or volume claims)

## Cross-modality
Inherits its calling spoke's class (Class B); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
