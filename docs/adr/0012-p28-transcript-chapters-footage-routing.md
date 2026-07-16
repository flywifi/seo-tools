# 12. P28 Transcript Chapters Footage Routing

- Date: 2026-07-03
- Status: Accepted

## Context

P26 shortlisted media tools (PySceneDetect, ffmpeg, auto-editor, PyAV) for a future integration phase but proved the zero-dependency stdlib floor recovers the authored silence structure exactly. Shipping the floor first gives the raw-footage breakdown request an honest, offline, zero-token capability today and preserves the degradation chain the P26 report specified (tool -> ffmpeg-only -> stdlib floor). Media tool integration remains a future phase; no new dependency, flag, or connector was added.

## Decision

Closed scenario-suite gaps G9 and G10. Promoted the stdlib SRT pause analysis (proven in the P26 S-0 spike and previously runner-owned evidence code) into product capability: shared/docintel/transcripts.py gained gap_metrics() (inter-segment silence detection) and suggest_chapters() (chapter boundary proposal from silences plus words_per_minute drops; titles always null, named by the model or human from transcript text). Added the footage_breakdown routing classification to creator-core (Content lane, video-development spoke) and a footage-analysis atom as the realizer. tools/scenario_check.py op_gap_metrics now delegates to the product function; scenario S5 flipped from ambiguous routing with G9/G10 evidence legs to a present-routing product assertion.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P28-transcript-chapters-footage-routing`.
