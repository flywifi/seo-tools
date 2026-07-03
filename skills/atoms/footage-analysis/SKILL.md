---
name: footage-analysis
description: "break raw footage into proposed chapters and cut points from its timecoded transcript using local silence/pause and words_per_minute analysis. Use when the user has raw or lightly edited footage plus a transcript or caption file and asks what the chapters should be or what to cut. Do NOT use for repurposing finished long-form into Shorts (short-extract) or for formatting an authored chapter list (chapter-map)."
---

# footage-analysis

Turn a raw-footage transcript into evidence-backed chapter and cut suggestions. All timing math
runs locally in `shared/docintel/transcripts.py` (zero tokens, no network); the model only names
the chapters and explains the cuts.

## When to use this skill
- "here's raw footage, break it down", "what should the chapters be", "what should I cut",
  "find the dead air", "where are the pauses in this recording".
- Routed from the hub as `footage_breakdown` (Content lane, `video-development` spoke).

Do NOT use for:
- Extracting Shorts/Reels/TikToks from a finished video (use `short-extract`).
- Fanning out an already-authored chapter list to YouTube/scheduling formats (use `chapter-map`).
- Live audio transcription (that is `shared/transcription-engine.md`; this atom consumes an
  existing transcript or caption file).

## Input
```json
{
  "transcript_path": "path to an SRT, VTT, JSON, or plain-text transcript",
  "min_gap_seconds": 8.0,
  "min_chapter_seconds": 30.0
}
```

## Core procedure
1. Parse the transcript: `python3 shared/docintel/transcripts.py <file> --json`.
2. Compute silences: `python3 shared/docintel/transcripts.py <file> --gap-metrics
   [--min-gap-seconds N]`. Each silence is a cut candidate (dead air between segments).
3. Compute chapter boundary candidates: `python3 shared/docintel/transcripts.py <file>
   --suggest-chapters`. Boundaries come from long silences and words_per_minute drops; the tool
   never invents titles (`suggested_title` is always null).
4. Name each proposed chapter from the transcript text around its boundary; never invent content
   that is not in the transcript. If a plain-text transcript has no timecodes, report that
   timing analysis is unavailable and degrade to a topic-only outline, flagged as such.
5. Hand the confirmed chapter list to `chapter-map` for YouTube description timestamps and
   scheduling fan-out when the user wants those artifacts.

## Output contract
```json
{
  "tool": "footage-analysis",
  "cut_candidates": [
    { "after_segment": 5, "gap_seconds": 12.5, "from_end": 92.0, "to_start": 104.5,
      "why": "dead air between takes" }
  ],
  "proposed_chapters": [
    { "start_seconds": 0.0, "title": "named from transcript text", "basis": "silence | wpm_drop | both" }
  ],
  "timing_source": "shared/docintel/transcripts.py (local, zero tokens)",
  "human_review_required": true,
  "notes": "every suggestion cites the segment or gap it came from; nothing is fabricated"
}
```
Honor `protocols/formatting-metadata.md` (no em dashes in user-facing output, ranges with "to")
and `protocols/no-fabrication.md` (null and flag missing timecodes; never invent timings).

## Engines and protocols loaded
- `shared/videoedit-engine.md` (edit-package contract downstream)
- `shared/platform-engine.md` (YouTube chapter rules: first at 0:00, 3 or more, 10s minimum)
- `protocols/no-fabrication.md`, `protocols/formatting-metadata.md`

## Standalone usability
Even with no downstream skill, this atom produces a cut-candidate list and a proposed chapter
outline with exact timecodes the creator can apply by hand in any editor.

## Failure modes
- Transcript has no timecodes (plain text): timing analysis skipped; output flags
  `timing_unavailable: true` and degrades to a topic outline.
- No silences at or above the threshold: `cut_candidates` is empty and the note says so; the
  atom does not lower the threshold silently.
- Fewer than 3 proposed chapters: flagged against the YouTube Key Moments minimum rather than
  padded with invented boundaries.
