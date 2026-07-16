# 6. P26 Slot Render Export

- Date: 2026-07-02
- Status: Accepted (shortlist)

## Context

Group B/D research verified MLT XML as the shared substrate across Shotcut and Kdenlive and melt as the developer-documented headless export path for both. auto-editor emits exactly our Lane A formats but its S-2 spike was network-blocked, so the fcpxml.py round-trip is the top open validation item. LosslessCut failed the headless gate (GUI-bound automation) and is documented as a manual companion only.

## Decision

render/export slot: shortlist MLT XML emission as a second Lane A format (Shotcut native, Kdenlive substrate) with optional melt rendering; ffmpeg direct encode as runner-up; auto-editor conditionally shortlisted pending FCPXML round-trip validation. Kdenlive and Shotcut are interchange targets, not dependencies: both were verified to expose no edit-automation API (project file + melt is the surface), which confirms the two-lane thesis.

## Consequences

**Explicitly not done:** No integration; the render/export flag stays off; no MLT writer is built by this decision.

**Verified by:**
- docs/VIDEO_TOOLING_EVAL.md
- docs/video-tooling-scores.json
- docs/video-tooling-spike-evidence.json#S-2

Ledger status at record time: `shortlisted`. Source: `ledger/ledger.json` id `P26-slot-render-export`.
