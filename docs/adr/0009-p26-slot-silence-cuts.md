# 9. P26 Slot Silence Cuts

- Date: 2026-07-02
- Status: Accepted (shortlist)

## Context

S-1 measured silencedetect within 0.021s of authored silences; S-4 reproduced it in-process within one 100ms window without any binary; S-0 recovered all three authored gaps from the transcript alone in 21ms.

## Decision

G9 silence/cut detection slot: shortlist ffmpeg silencedetect (top pick), PyAV windowed RMS (no-binary runner-up), degrading to the stdlib SRT gap analysis proven in spike S-0.

## Consequences

**Explicitly not done:** No integration, no flags, G9 remains open.

**Verified by:**
- docs/video-tooling-spike-evidence.json#S-1
- docs/video-tooling-spike-evidence.json#S-4
- docs/video-tooling-spike-evidence.json#S-0

Ledger status at record time: `shortlisted`. Source: `ledger/ledger.json` id `P26-slot-silence-cuts`.
