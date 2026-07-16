# 13. P29 Media Tool Integration

- Date: 2026-07-03
- Status: Accepted

## Context

Ships the P26 per-slot recommendations with the exact degradation chains the evaluation specified, keeping the repo's optional-dependency posture: nothing new is required, every path degrades to the P28 transcript floor or an honest refusal, and provenance makes fabricated timings structurally impossible. Explicitly NOT integrated or unverified: auto-editor (binary bootstrap still 403-blocked through the proxy; conditionally shortlisted only), melt render execution (no melt in the build container; gate-tested only), macOS paths, editor-side .mlt opening, and otio-kdenlive-adapter reading our Shotcut-flavored MLT (adapter expects Kdenlive docproperties; recorded as failed bonus check). Evidence: docs/video-tooling-integration-evidence.json.

## Decision

Integrated the P26 shortlist as optional, runtime-detected backends over the P28 stdlib floor. Silence/cut slot: tools/videoedit/mediaprobe.py detect_silence (ffmpeg silencedetect -> PyAV windowed RMS -> transcripts.gap_metrics). Scene/chapter slot: detect_scenes (PySceneDetect ContentDetector -> ffmpeg scdet with the luma caveat attached -> transcripts.suggest_chapters; titles always null). shorts_reframe slot: tools/videoedit/reframe.py (crop geometry pure math always available; render gated on shorts_reframe walking MoviePy -> ffmpeg crop -> refusal-with-valid-params). render/export slot: tools/videoedit/mltxml.py (MLT XML build/parse/validate as the second Lane A format; render gated on the new media_render flag, added to APP_DRIVING so it also requires video_editing_enabled, walking melt -> ffmpeg cut-list -> honest handoff). Every result carries computed_by, backend_chain, and parameters. Three new atoms (silence-scan, scene-scan, shorts-reframe), two new flags (mlt_timeline_export, media_render), four MCP tools, preflight detection for all backends, requirements-videoedit.txt (optional only). otio_core.merge fixed to union incoming gaps[] and adopt an enabled reframe directive (both were silently dropped). Live-verified against P26 goldens: ffmpeg silencedetect within 0.003s, PyAV exact, PySceneDetect all 4 cuts including the isoluminant one, scdet 3 of 4 with caveat, MoviePy and ffmpeg renders ffprobe-verified 404x720.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P29-media-tool-integration`.
