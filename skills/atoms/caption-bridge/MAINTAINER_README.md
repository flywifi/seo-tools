# caption-bridge — maintainer notes

**Feature:** P22 feature 2 (caption round-trip). Realized by `tools/videoedit/captions.py`. Knowledge:
`shared/videoedit-engine.md` + `shared/transcription-engine.md`.

## Invariants
- SRT/VTT reuse `shared/docintel/transcripts.py` (parse/emit); only iTT is added here. Do not
  duplicate the SRT/VTT logic.
- No fabricated timings or text. Empty input -> `gaps[]`, not invented cues.
- CEA-608 (.scc) is deferred and must be flagged, never emitted as a fake file.
- File writing drives no app, so it is allowed even when `video_editing_enabled` is off.

## Composition
Populates the shared edit-package `timeline.captions[]`; merges via `tools/videoedit/otio_core.py`.
`from_editor` output feeds SEO (keywords/description) alongside `fcpxml-parse`.

## Regression cases
See `evals/evals.json`: (1) transcript -> SRT matches the docintel emitter; (2) transcript -> iTT is
well-formed XML; (3) iTT/SRT -> captions[] -> SRT is stable (lossless round-trip).

## Update checklist
- Keep `captions_to_segments`/`segments_to_captions` aligned with the edit-package schema.
- Run `python3 tools/sync_check.py`.
