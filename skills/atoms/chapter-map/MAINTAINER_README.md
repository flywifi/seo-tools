# chapter-map — maintainer notes

**Feature:** P22 feature 8 (chapter fan-out). Realized by `tools/videoedit/chapters.py`. Knowledge:
`shared/videoedit-engine.md` + `shared/platform-engine.md`.

## Invariants
- Pure transform: no fabrication. Rule violations are flagged in `gaps[]`, never auto-fixed.
- `chapter_outline` MUST stay in `geo-optimize`'s input shape (`{timestamp_seconds, chapter_topic}`),
  so the two atoms chain without an adapter.
- Timestamp format: MM:SS under an hour, H:MM:SS over; first line always `0:00` when chapters exist.
- YouTube rules encoded: first at 0:00, >= 3 chapters, each >= 10s (constants in chapters.py).

## Composition
Reads `timeline.chapters[]` from the shared edit-package (or a bare list). Feeds `geo-optimize`
(Key Moments), and `content-calendar` + the scheduling queue via `scheduling.description_timestamps`.

## Regression cases
See `evals/evals.json`: (1) compliant chapters -> correct 0:00-first timestamps + geo shape; (2)
first-not-zero / too-few / <10s-gap all flagged, nothing auto-fixed; (3) empty input -> no_chapters gap.

## Update checklist
- If YouTube changes the chapter rules, update MIN_CHAPTERS/MIN_GAP_SECONDS in chapters.py and note it.
- Run `python3 tools/sync_check.py`.
