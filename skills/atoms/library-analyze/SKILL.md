---
name: library-analyze
atom: true
standalone: true
description: "reads the creator's imported video library and reports what their back catalog actually shows: the most-used tags weighted by views, the YouTube retention peaks and steepest-drop cliffs with the transcript words spoken at each moment, format and category performance, and recurring spoken themes across transcripts. Every number cites the video_keys it came from and any field a platform does not provide is null-flagged, never estimated. Triggers: 'analyze my back catalog', 'what were my most-watched parts', 'which tags perform best', 'what themes run through my videos'. Do NOT use to import videos (use video-import), to complete missing transcripts/chapters (use library-complete), or to invent metrics for a platform that does not expose them (retention off YouTube, revenue without a Studio CSV) which are reported as null, not guessed."
engines_required:
  - shared/content-import-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
  - protocols/quality-gates.md
---

# library-analyze

The read side of the content-import lane. It turns the creator's own imported catalog into grounded,
citable insight and refuses to estimate anything a platform does not actually provide.

## When to use this skill
- "analyze my back catalog", "what patterns run through my videos".
- "which parts of my videos were most watched" (YouTube retention peaks/cliffs with the spoken words).
- "which tags or formats perform best", "what themes come up across my transcripts".

Do NOT use for:
- Importing videos or stats (use `video-import`); this atom reads an already-populated library.
- Completing missing transcripts, chapters, or the retention join (use `library-complete`).
- Producing retention, revenue, or transcript numbers for a platform that does not expose them. Those
  are null-flagged, never estimated (retention is YouTube-only; revenue is Studio-CSV-only).

## Inputs
```json
{
  "platform": "optional filter: youtube | instagram | tiktok | pinterest, or null for all",
  "focus": "optional: tags | retention | format | themes, or null for the full report"
}
```
Reads the local library store via `tools/video_library.py analyze`.

## Core procedure
Follow `shared/method.md` and `shared/content-import-engine.md`. Runs `tools/video_library.py analyze`,
which composes four read-only analyzers, each citing the `video_key`s behind every figure.

### Step 1: tags and formats
`top_tags` ranks the catalog's tags by frequency and total views. `format_performance` reports average
views by duration bucket and by category. Both cite the contributing `video_key`s.

### Step 2: retention (YouTube only)
`retention_insights` surfaces each video's most-watched peaks and its steepest-drop cliff. When
`library-complete` has joined a transcript, each moment carries the actual words spoken there, which is
what answers "which parts were most watched" with what was said. Instagram, TikTok, and Pinterest have
no first-party retention and are listed under `retention_unavailable`, null-flagged, never estimated.

### Step 3: transcript themes
`transcript_themes` surfaces recurring spoken terms across the library's transcripts, each citing its
`video_key`s. When no transcripts exist yet it returns an honest `no_transcripts` flag and points to
`library-complete`, never inventing themes from metadata.

## Output contract
What this skill produces. Always honor `protocols/formatting-metadata.md` (no em dashes, ranges with
"to") and self-check against `protocols/quality-gates.md` before handing to `quality-review`.
```json
{
  "top_tags": [{"tag": "armoire", "count": 12, "total_views": 480000, "video_keys": ["youtube:abc"]}],
  "retention_insights": {"insights": [{"video_key": "youtube:abc", "peaks": [], "cliffs": [{"label": "cliff", "at_seconds": 92.0, "text": "..."}]}], "retention_unavailable": ["instagram:reel_9"]},
  "format_performance": {"by_duration": [], "by_category": []},
  "transcript_themes": {"themes": [{"term": "patina", "count": 30, "video_keys": []}], "flag": null},
  "boundaries": "Retention is YouTube-only; revenue is Studio-CSV-only; unavailable data is null-flagged."
}
```

## Engines and protocols loaded
`shared/content-import-engine.md`; `protocols/no-fabrication.md`, `protocols/formatting-metadata.md`,
`protocols/quality-gates.md`.

## Atoms used
Reads the store built by `video-import` and completed by `library-complete`. Callable directly.

## Standalone usability
An imported library in, a grounded, fully cited analysis out (top tags, retention peaks/cliffs with
spoken words where joined, format performance, transcript themes), with honest null-flags for anything a
platform does not expose, even with no downstream skill.

## Failure modes
- No transcripts imported yet: transcript themes and joined retention words return a `no_transcripts`
  flag pointing to `library-complete`; nothing is invented.
- Non-YouTube records: retention is null-flagged under `retention_unavailable`, never estimated.
- Empty library: every section returns empty with the boundary note; no fabricated figures.

## Cross-modality
Class C (reads the creator's local library store). The analysis runs wherever the store lives: native
on Claude Desktop with a local MCP server or Claude Code. On a browser-only surface it re-routes: "run
this analysis on your computer," since a hosted connector runs in the vendor's cloud and cannot read
the creator's local library. See `shared/content-import-engine.md` and `shared/cross-modality-engine.md`.
