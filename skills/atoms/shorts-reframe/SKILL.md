---
name: shorts-reframe
atom: true
standalone: true
description: "Computes the 9:16 (or any target aspect) crop geometry for a chosen clip range and optionally renders the cropped clip locally. Geometry is pure math via tools/videoedit/reframe.py and is always available; the render half runs only when the shorts_reframe flag is on and MoviePy or ffmpeg is present, otherwise the crop parameters ride in the edit-package for the editor to apply. Use when a selected clip needs to become a vertical Short/Reel/TikTok frame. Do NOT use to choose which moments become clips (short-extract), to write captions or hooks (caption-write, hook-write), or for batch platform export (compressor presets or media_render)."
engines_required:
  - shared/videoedit-engine.md
  - shared/platform-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# shorts-reframe

Turn a chosen clip range into a vertical frame. One operation: source dimensions in, crop
rectangle out, with an optional flag-gated local render.

## When to use this skill
- "make this clip vertical", "crop it for Shorts/Reels/TikTok", "give me the 9:16 version of
  this range", after `short-extract` has picked the moments.

Do NOT use for:
- Choosing which moments become clips (use `short-extract`).
- Captions, hooks, or hashtags for the clip (use `caption-write`, `hook-write`, `hashtag-set`).
- Batch export of finished deliverables (Compressor presets or the `media_render` flag path).

## Input
```json
{
  "source_width": 1280,
  "source_height": 720,
  "aspect": "9:16",
  "x_center": null,
  "media_path": "optional; required only for a local render",
  "start_seconds": null,
  "end_seconds": null,
  "out_path": "optional; where the rendered clip goes"
}
```

## Core procedure
1. Geometry (always): `python3 tools/videoedit/reframe.py geometry --width W --height H
   [--aspect 9:16]`. Center crop by default; `x_center`/`y_center` shift the window and are
   clamped in frame. Even-rounded dimensions are returned alongside the exact ones because
   H.264 encoders require even sizes.
2. Package: `reframe.py package` emits the edit-package `reframe` block
   (`{enabled, aspect, method: center_crop, crop, ffmpeg_filter, computed_by}`) which merges via
   `otio_core.merge` without clobbering an existing enabled directive.
3. Render (optional, flag-gated): `reframe.py render` checks
   `realization_allowed("shorts_reframe")` first. Backend chain: MoviePy when installed, then
   the ffmpeg crop filter, else an honest refusal whose `gaps[]` entry says the crop parameters
   are still valid and the editor applies them. Subject tracking is out of scope; this is
   center-crop math only.

## Output contract
Geometry output (always present):
```json
{
  "source": {"width": 1280, "height": 720},
  "aspect": "9:16",
  "crop_exact": {"width": 405.0, "height": 720.0},
  "crop": {"width": 404, "height": 720, "x": 438, "y": 0},
  "ffmpeg_filter": "crop=404:720:438:0",
  "computed_by": "reframe.crop_geometry"
}
```
Render output adds `{rendered, renderer, out_path, backend_chain, gaps}`. All numbers come from
the tool; the model never computes crop rectangles by hand.

## Standalone usability
With no downstream skill and the flag off, the crop rectangle and ffmpeg filter string are
directly usable in any editor or command line.

## Failure modes
- Flag off: render refuses with the degraded_behavior pointer; geometry still returned.
- No MoviePy and no ffmpeg: render refuses with `gaps[]` naming both missing backends.
- Subject not centered: center crop can miss it; pass `x_center` explicitly or apply the crop
  in the editor with Auto Reframe (a UI-only editor feature, per the engine).

## Cross-modality
Inherits its calling spoke's class (the calling spoke's class); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
