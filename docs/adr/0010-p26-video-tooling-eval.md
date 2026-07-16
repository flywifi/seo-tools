# 10. P26 Video Tooling Eval

- Date: 2026-07-02
- Status: Accepted (shortlist)

## Context

G9 (transcript-to-chapters/cuts) and the flagged-off shorts_reframe and render/export slots need a vetted shortlist before any integration work. Empirical spikes ran against synthetic media sharing ground truth with the committed workshop-footage.srt fixture, so tool accuracy is measured against known-authored cuts and silences.

## Decision

Completed the open-source video tooling evaluation: 15 candidates scored against the two-lane videoedit architecture, 7 hands-on spikes (6 passed, 1 blocked by container network policy), 4 research agents plus 1 adversarial verification agent (3 of 8 load-bearing claims upheld, 5 refined).

## Consequences

**Explicitly not done:** No integration, no flag changes, no requirements changes; G9 and G10 remain open and the scenario suite's probes still observe them.

**Verified by:**
- docs/VIDEO_TOOLING_EVAL.md
- docs/video-tooling-scores.json
- docs/video-tooling-spike-evidence.json

Ledger status at record time: `shortlisted`. Source: `ledger/ledger.json` id `P26-video-tooling-eval`.
