---
name: silence-scan
atom: true
standalone: true
description: "Detects silences (dead air) in raw media or a timecoded transcript and returns cut candidates with exact timings and auditable provenance. Runs locally via tools/videoedit/mediaprobe.py: ffmpeg silencedetect when present, PyAV windowed RMS as the no-binary fallback, degrading to the transcript gap analysis floor. Use when the user has raw footage or a recording and asks where the dead air, pauses, or cut points are. Do NOT use for scene/chapter boundaries (scene-scan), for naming chapters (footage-analysis), or for extracting Shorts clips (short-extract)."
engines_required:
  - shared/videoedit-engine.md
  - shared/platform-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# silence-scan

Find the dead air. One operation: silence spans in, cut candidates out, with the backend that
measured them named on the result.

## When to use this skill
- "find the dead air", "where are the long pauses", "what should I cut out", "trim the silences",
  routed work from `footage_breakdown` when raw media is available.

Do NOT use for:
- Scene or chapter boundaries (use `scene-scan`).
- Naming chapters or producing the full breakdown narrative (use `footage-analysis`).
- Picking Shorts clip ranges (use `short-extract`).

## Input
```json
{
  "media_path": "path to a video or audio file (optional)",
  "transcript_path": "path to an SRT/VTT/JSON transcript (optional; the degradation floor)",
  "noise_db": -50.0,
  "min_silence_seconds": 2.0
}
```
At least one of `media_path` or `transcript_path` is required.

## Core procedure
Run `python3 tools/videoedit/mediaprobe.py silence --media <M> --transcript <T>
[--noise-db N] [--min-silence-seconds S]`. The tool walks the backend chain
(ffmpeg silencedetect, then PyAV windowed RMS, then the transcript floor
`shared/docintel/transcripts.gap_metrics`) and returns the first backend that can run. This is
local analysis: no flag gates it, no app is driven, no network is touched.

## Output contract
The tool's JSON, passed through with an interpretation sentence per silence:
```json
{
  "silences": [{"start_seconds": 92.011, "end_seconds": 104.512, "duration_seconds": 12.501}],
  "computed_by": "ffmpeg.silencedetect | pyav.rms_window | shared/docintel/transcripts.gap_metrics",
  "backend_chain": [{"backend": "ffmpeg", "ok": true}],
  "parameters": {"noise_db": -50.0, "min_silence_seconds": 2.0},
  "gaps": []
}
```
Every timing number comes from the tool; the model never computes or adjusts timecodes. When no
backend can run, `gaps[]` says so and the output contains zero invented numbers. Use
`mediaprobe.to_edit_package` to merge results into the shared edit-package as cut-candidate
markers.

## Standalone usability
With no downstream skill, the silence list with exact timecodes is directly usable in any editor.

## Failure modes
- No media and no transcript: refused with a `gaps[]` entry naming what to provide.
- Media present but no ffmpeg and no av: falls to the transcript floor and says so in
  `backend_chain`; if there is also no transcript, honest empty result.
- Transcript floor measures gaps between caption segments, not audio level; the result labels
  itself via `computed_by` so the two are never conflated.
