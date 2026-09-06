---
file: skills/atoms/shorts-reframe/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for shorts-reframe so it stays stable under iteration.
---

# shorts-reframe: Maintainer README

## Purpose
Crop geometry and optional local render for one clip range, realized by
`tools/videoedit/reframe.py`. Clip selection is `short-extract`'s job; batch deliverable export
belongs to Compressor presets or the `media_render` path. This atom ends at a crop rectangle
(always) and a rendered file (only when flagged on and a backend exists).

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Geometry is pure math and never gated; the render half always checks
  `realization_allowed("shorts_reframe")` before touching a backend.
- All crop numbers come from `reframe.crop_geometry`; the model never hand-computes rectangles.
- Even-rounded dimensions ship alongside exact ones; the ffmpeg filter string uses the even ones.
- Center-crop only; subject tracking is explicitly out of scope (P26 non-goal).
- A refused or failed render always leaves the crop parameters valid and says so in `gaps[]`.

## Known failure modes
- Center crop misses an off-center subject (mitigation: explicit `x_center`, or editor-side
  Auto Reframe).
- MoviePy import present but broken transitively; the chain records the reason and falls to
  ffmpeg.

## Fragile fallbacks that must not become defaults
- Rendering via ffmpeg without noting MoviePy was tried (backend_chain must show the order).
- Emitting geometry-only output without the `gaps[]` note when a render was requested.

## Regression cases to preserve
1. 1280x720 to 9:16: exact width 405.0, even crop 404x720 at x=438 (P26 S-5 golden;
   reframe selftest).
2. Already-9:16 source is untouched.
3. Off-center x_center clamps inside the frame at both edges.
4. Flag off: render refuses with gap_type flag_off; geometry unaffected.
5. Enabled reframe directive survives `otio_core.merge` without clobbering an existing one.
Mapped to evals/evals.json and `python3 tools/videoedit/reframe.py --selftest`.

## Approval-gated changes
Backend chain order, output schema, the even-rounding rule, aspect parsing, and any move of the
render gate off the `shorts_reframe` flag.

## Minority-report policy
When exact and even-rounded dimensions disagree enough to matter (very small sources), report
both and let the human choose; never silently prefer one for a render.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/videoedit/reframe.py --selftest` passes 12 of 12.
3. `python3 tools/sync_check.py` exits 0.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
