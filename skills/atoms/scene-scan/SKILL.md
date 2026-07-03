---
name: scene-scan
atom: true
standalone: true
description: "Detects scene changes in raw media and proposes chapter boundary candidates with exact timings and auditable provenance. Runs locally via tools/videoedit/mediaprobe.py: PySceneDetect ContentDetector when installed, ffmpeg scdet as fallback (luma-only, caveat auto-noted), degrading to the transcript chapter-suggestion floor. Never invents chapter titles. Use when the user has raw footage and asks where the scenes or chapter boundaries are. Do NOT use to name chapters or write the breakdown (footage-analysis), to format an authored chapter list (chapter-map), or to find dead air (silence-scan)."
engines_required:
  - shared/videoedit-engine.md
  - shared/platform-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# scene-scan

Find where the picture changes. One operation: scene cuts in, chapter boundary candidates out,
titles always left null for a human or the model to name from real content.

## When to use this skill
- "where do the scenes change", "detect the shots", "find chapter boundaries in this footage",
  routed work from `footage_breakdown` when raw media is available.

Do NOT use for:
- Naming chapters or producing the breakdown narrative (use `footage-analysis`).
- Formatting an already-authored chapter list (use `chapter-map`).
- Dead-air detection (use `silence-scan`).

## Input
```json
{
  "media_path": "path to a video file (optional)",
  "transcript_path": "path to an SRT/VTT/JSON transcript (optional; the degradation floor)",
  "threshold": 27.0,
  "scdet_threshold": 10.0
}
```
At least one of `media_path` or `transcript_path` is required. `threshold` is PySceneDetect's
ContentDetector threshold; `scdet_threshold` applies only on the ffmpeg fallback.

## Core procedure
Run `python3 tools/videoedit/mediaprobe.py scenes --media <M> --transcript <T>
[--threshold N] [--scdet-threshold N]`. The tool walks the backend chain (PySceneDetect
ContentDetector, then ffmpeg scdet, then the transcript floor
`shared/docintel/transcripts.suggest_chapters`). When the scdet fallback runs, the result carries
the luma-only caveat: cuts between equally bright colors can be missed (verified in the P26
evaluation). This is local analysis: no flag gates it, no app is driven, no network is touched.

## Output contract
```json
{
  "scene_cuts": [{"time_seconds": 150.0, "score": 15.625}],
  "proposed_chapters": [{"start_seconds": 0.0, "basis": "scene_start", "suggested_title": null}],
  "computed_by": "pyscenedetect.ContentDetector | ffmpeg.scdet | shared/docintel/transcripts.suggest_chapters",
  "backend_chain": [{"backend": "scenedetect", "ok": true}],
  "notes": ["(luma caveat when scdet ran)"],
  "gaps": []
}
```
`suggested_title` is always null: the tool measures boundaries, the model or human names them
from the transcript or footage. Timing numbers come only from the tool. YouTube chapter rules
(first at 0:00, 3 or more chapters, each 10 seconds or longer) are checked downstream by
`chapter-map`, never silently fixed here.

## Standalone usability
With no downstream skill, the scene-cut list with exact timecodes is directly usable as an
editor marker list or a manual chapter draft.

## Failure modes
- No media and no transcript: refused with a `gaps[]` entry naming what to provide.
- scdet fallback on isoluminant cuts: boundaries can be missed; the caveat note is attached to
  the result rather than hidden.
- Transcript floor proposes boundaries from pauses and pace shifts, not pixels; `computed_by`
  keeps the provenance explicit so the two are never conflated.
