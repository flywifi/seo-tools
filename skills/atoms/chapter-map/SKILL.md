---
name: chapter-map
atom: true
standalone: true
description: "Takes one chapter list (or an edit-package) and fans it out three ways: the geo-optimize chapter outline for YouTube/Google Key Moments, a paste-ready YouTube description timestamp block, and scheduling metadata for the content calendar and scheduling queue. Enforces YouTube's chapter rules (first at 0:00, at least 3 chapters, each at least 10 seconds) by flagging violations, never silently fixing or inventing them. Do NOT use to write SEO copy (pass the outline to geo-optimize); do NOT invent chapter titles or timestamps."
engines_required:
  - shared/videoedit-engine.md
  - shared/platform-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# chapter-map (feature 8)

## When to use
"Turn my chapters into YouTube timestamps," "prep my chapter markers for SEO," "sync my chapters to
the description and schedule." One source of truth, reused everywhere it is needed.

## Inputs
```json
{ "source": "an edit-package, a {chapters:[{start_seconds,title}]} object, or a bare chapter list" }
```

## Core procedure
Call `tools/videoedit/chapters.py fan_out`. It normalizes and sorts the chapters, then returns:
- `chapter_outline` in geo-optimize's exact input shape (`{timestamp_seconds, chapter_topic}`), so it
  drops straight into `geo-optimize`;
- `youtube_description_timestamps`, a paste-ready block (`0:00 Title`, MM:SS under an hour and
  H:MM:SS over, first line forced to `0:00`);
- `scheduling`, a block the content-calendar post / scheduling queue can carry.
It also runs YouTube-rule validation and records any violation in `gaps[]`. Pure transform: no app,
no network, works on every AI engine.

## Output contract
`{chapters, chapter_outline, youtube_description_timestamps, scheduling, feeds, gaps}` (see
`shared/videoedit-engine.md`). The `chapters` field merges back into the shared edit-package.

## Standalone usability
Fully standalone; always available (no flag or tool needed to compute the fan-out).

## Failure modes
- Fewer than 3 chapters, first not at 0:00, or any gap under 10 seconds: emit the artifacts anyway
  and flag each violation in `gaps[]`. Never renumber, drop, or invent chapters to force compliance.
- No chapters: return empty artifacts and a `no_chapters` gap.

## Cross-modality
Inherits its calling spoke's class (the calling spoke's class); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
