# 8. P26 Slot Shorts Reframe

- Date: 2026-07-02
- Status: Accepted (shortlist)

## Context

S-5 produced an ffprobe-verified 9:16 crop with a fully self-contained pip install (imageio-ffmpeg bundles its own ffmpeg). Maintenance is the watch item: no release since 2025-05, no commits since 2025-09 (adversarially verified).

## Decision

shorts_reframe slot: shortlist MoviePy v2 for the mechanical crop/trim/encode half (ffmpeg crop filter as runner-up), degrading to emitting crop parameters into the edit package without rendering.

## Consequences

**Explicitly not done:** No integration; the shorts_reframe flag stays off.

**Verified by:**
- docs/video-tooling-spike-evidence.json#S-5
- docs/video-tooling-scores.json

Ledger status at record time: `shortlisted`. Source: `ledger/ledger.json` id `P26-slot-shorts-reframe`.
