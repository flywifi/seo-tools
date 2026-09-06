# edit-timeline-spec — maintainer notes

**Feature:** P22 feature 1 (script -> timeline scaffold). Realized by `tools/videoedit/fcpxml.py`
(build) and, live, by `tools/videoedit/resolve.py`. Knowledge layer: `shared/videoedit-engine.md`.

## Invariants
- Output is a valid edit-package per `shared/videoedit-engine.md` (times in seconds; `source`,
  `frame_rate`, `timeline{}` present).
- Never invents beats, chapter titles, or copy. Missing inputs go to `gaps[]`.
- Pure spec: no file writes, no app calls. That is the realization step's job and is gated by
  `video_editing_enabled`.

## Composition
Independent by design. Its output is the shared artifact consumed by `fcpxml-parse` (round-trip),
`caption-bridge`, `shorts-edit-spec`, `chapter-map`, etc. Merge behavior lives in
`tools/videoedit/otio_core.py:merge` (union by start+key, no clobber).

## Regression cases
See `evals/evals.json`: (1) full input round-trips through `tools/videoedit/fcpxml.py`; (2) minimal
input (title only) yields a valid empty timeline + a gap note; (3) missing chapters/titles are
flagged, not invented.

## Update checklist
- Keep the output shape in sync with `shared/videoedit-engine.md` and `pipeline/editing/edit-package.template.json`.
- If you add a timeline field, update `tools/videoedit/fcpxml.py` (build+parse) and `otio_core.merge`.
- Run `python3 tools/sync_check.py`.
