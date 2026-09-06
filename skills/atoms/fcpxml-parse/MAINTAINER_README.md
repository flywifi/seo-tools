# fcpxml-parse — maintainer notes

**Feature:** P22 feature 4 (marker/keyword/role intelligence import; offline -> online handoff).
Realized by `tools/videoedit/fcpxml.py:parse` + `validate`. Knowledge: `shared/videoedit-engine.md`. <!-- verify: tools/videoedit/fcpxml.py::parse --> <!-- verify: tools/videoedit/fcpxml.py::validate -->

## Invariants
- Emits only what the FCPXML contains. No invented markers, chapter titles, or timestamps.
- Malformed input returns the validator error, not a partial guess.
- Reading is a local file op (not app-driving), so it does not require `video_editing_enabled`.

## Handoff
This is the online-side receiver of the offline artifact. Its edit-package feeds `geo-optimize`
(Key Moments / chapters), `content-calendar` + the scheduling queue (chapter timestamps),
`entity-extract` (keywords), and the audio-stem plan (roles). The MCP tool `import_edit_artifact`
wraps this parse for the dashboard/scheduling side, mirroring `/api/import-report`.

## Regression cases
See `evals/evals.json`: (1) parse an FCPXML built by `edit-timeline-spec` and confirm markers/chapters
match (round-trip); (2) empty timeline -> valid empty package + gap note; (3) malformed input ->
validation error, no fabrication.

## Update checklist
- Keep parse in lockstep with `tools/videoedit/fcpxml.py:build` so round-trips stay lossless.
- Run `python3 tools/sync_check.py`.
