---
name: library-complete
atom: true
standalone: true
description: "completes the creator's already-imported video library by filling the fields the platforms withhold: it matches each downloaded video file to its library record, runs on-device speech-to-text for missing transcripts, derives chapters and spoken keywords, and joins the YouTube retention curve to the transcript so each most-watched peak carries the actual words spoken there. Triggers: 'finish building my library', 'what was said at the most-watched parts', 'add transcripts to my imported videos', 'complete my video library'. Do NOT use to import stats/metadata in the first place (use video-import), to transcribe a single video in isolation (use transcript-import), to analyze an already-complete library (use library-analyze), or to write the store directly (it proposes completions; the human saves them)."
engines_required:
  - shared/content-import-engine.md
  - shared/transcription-engine.md
  - shared/cross-modality-engine.md
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# library-complete

Metadata and stats came in through the importers; this atom fills the high-value fields every platform
withholds. It runs the on-device stack over the video files the creator already downloaded, entirely
locally (zero cloud, zero tokens), and proposes the completions for the human to save.

## When to use this skill
- "finish building my library", "complete my imported videos", "add the transcripts to my library".
- "what was actually said at the most-watched parts of my video" (the retention x transcript join).
- After `video-import` has populated records but transcripts/chapters/most-watched are still empty.

Do NOT use for:
- Importing stats, tags, or metadata (use `video-import`); this atom assumes records already exist.
- Transcribing one video in isolation (use `transcript-import`); this atom drives a whole worklist.
- Analyzing an already-complete library (use `library-analyze`).
- Writing the store. It proposes completions; the human saves them via `video-import` or
  `python3 tools/video_library.py upsert` / `python3 tools/library_complete.py complete --write`.

## Inputs
```json
{
  "export_dir": "absolute path to the unzipped export folder holding the downloaded video files",
  "video_keys": "optional subset of library records to complete, or null for all incomplete ones",
  "model": "STT model tier, or null (chosen by the runner from the machine's RAM)"
}
```
Records are read from the local library store (`tools/video_library.py`). Media files are matched from
`export_dir`.

## Core procedure
Follow `shared/method.md`, `shared/content-import-engine.md`, and `shared/transcription-engine.md`.
Runs through `tools/library_complete.py`.

### Step 1: match
`match_media(export_dir, records)` maps each downloaded file to a `video_key` by the platform video id
in the filename, the DYI media uri recorded in provenance, or a title-plus-duration fallback via
`mediaprobe`. Unmatched files and records with no local media are reported honestly, never force-fit.

### Step 2: complete
For each matched record that lacks a transcript, run local STT (`tools/transcribe.py`) on-device. The
runner selects the machine-correct backend (whisper.cpp on Apple Silicon, faster-whisper elsewhere) and
seeds a niche-vocabulary prompt from `shared/brand-engine.md` plus the video's tags/title. Normalize
through `shared/docintel/transcripts.py`, derive chapters (`suggest_chapters`), and extract spoken
keywords/topics (`shared/docintel/parse_text.py` + the scoop cache). If no backend is installed, return
the `run_local_stt` gap with the per-OS install command; never fabricate a transcript.

### Step 3: join retention to transcript (the payoff)
`join_retention_transcript(record, segments)` maps each YouTube retention peak and the steepest-drop
cliff to the transcript line at that absolute timestamp (`elapsed_ratio x duration_s`), so each
most-watched moment carries the actual words spoken there. Off-YouTube (Instagram, TikTok, Pinterest)
retention is null-flagged, and the transcript plus topic themes are still delivered.

## Output contract
```json
{
  "proposals": [
    {"video_key": "youtube:abc123", "filled": ["transcript", "chapters", "most_watched"],
     "transcript_text": "...", "chapters": [], "most_watched_segments": [{"label": "peak", "at_seconds": 42.0, "text": "the words spoken at the peak"}],
     "provenance": {"transcript": {"computed_by": "faster-whisper:small:cpu", "backend_chain": []}},
     "gaps": []}
  ],
  "unmatched_media": [],
  "no_media": ["instagram:reel_9"],
  "save_note": "Confirm before saving. Nothing is written automatically; you save these completions to your library yourself. The video, audio, and transcript never leave your machine.",
  "human_review_required": true
}
```
Honor `protocols/formatting-metadata.md` (no em dashes, ranges with "to") and self-check against
`protocols/quality-gates.md` before handing to `quality-review`.

## Engines and protocols loaded
`shared/content-import-engine.md`, `shared/transcription-engine.md`, `shared/cross-modality-engine.md`;
`protocols/no-fabrication.md`, `protocols/formatting-metadata.md`, `protocols/safety.md`.

## Atoms used
Composes `transcript-import` per video. Feeds `library-analyze`. Callable directly by a user.

## Standalone usability
An export folder plus an imported library in, a set of proposed completions out (transcripts, chapters,
and the retention x transcript join), with honest gaps for missing media or missing STT backends, even
with no downstream skill.

## Failure modes
- No STT backend installed: each affected item returns the `run_local_stt` gap with the per-OS install
  command; nothing is fabricated.
- A record whose media file is not in the export folder: reported under `no_media`, not transcribed.
- An unmatched media file: reported under `unmatched_media`, never force-mapped to a record.
- Off-YouTube retention: null-flagged; the join delivers transcript and topics but no located peaks.

## Cross-modality
Class C (needs a local runtime and the creator's files). On a browser-only surface it re-routes: "run
this completion on your computer," or upload the export to a sandbox that runs the tools on the copy. A
hosted connector runs in the vendor's cloud and cannot see the creator's local export folder. See
`shared/content-import-engine.md` and `shared/cross-modality-engine.md`.
