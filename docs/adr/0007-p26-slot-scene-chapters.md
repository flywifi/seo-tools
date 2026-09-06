# 7. P26 Slot Scene Chapters

- Date: 2026-07-02
- Status: Accepted (shortlist)

## Context

S-3 found all 4 authored cuts frame-exact with zero false positives, including an isoluminant cut that ffmpeg missed; the adversarial pass source-verified the ffmpeg limitation (YUV path scores luma only) and its format=rgb24 workaround.

## Decision

G9 scene/chapter detection slot: shortlist PySceneDetect ContentDetector (top pick), ffmpeg scdet (runner-up with a documented luma-only default), degrading to transcript-derived chapter heuristics.

## Consequences

**Explicitly not done:** No integration, no flags, G9 remains open.

**Verified by:**
- docs/video-tooling-spike-evidence.json#S-3
- docs/video-tooling-spike-evidence.json#S-1
- docs/video-tooling-scores.json

Ledger status at record time: `shortlisted`. Source: `ledger/ledger.json` id `P26-slot-scene-chapters`.
