---
file: skills/atoms/silence-scan/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for silence-scan so it stays stable under iteration.
---

# silence-scan: Maintainer README

## Purpose
Single-operation silence detection over raw media or a transcript. All measurement is delegated
to `tools/videoedit/mediaprobe.py` `detect_silence()`; this atom's job ends at the labeled cut
candidate list. Chapter naming, breakdown narrative, and clip selection belong to other atoms.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Every timing number comes from the tool. The model never computes, rounds, or adjusts
  timecodes.
- `computed_by` and `backend_chain` are passed through verbatim; provenance is never stripped.
- The backend chain order is fixed: ffmpeg silencedetect, PyAV RMS, transcript floor. The floor's
  `computed_by` string is `shared/docintel/transcripts.gap_metrics` (pinned by scenario S5's
  silence leg; do not change it here without changing it everywhere).
- No capability flag gates this atom (local read-only analysis, chapter-map precedent).

## Known failure modes
- Media without any backend available degrades to the transcript floor, which measures caption
  gaps rather than audio level.
- Aggressive `noise_db` values on noisy footage produce zero silences; report, never lower the
  threshold silently.

## Fragile fallbacks that must not become defaults
- The transcript floor standing in for audio measurement without its `computed_by` label.
- Treating `backend_chain` failures as retryable by inventing a result.

## Regression cases to preserve
1. ffmpeg fixture stderr parses to 3 silences within 0.05s of the authored ground truth
   (mediaprobe selftest, committed fixtures).
2. Transcript floor on `workshop-footage.srt` at 8.0s returns durations 12.5/8.5/20.0 with the
   pinned `computed_by`.
3. Unusable media with a transcript falls through ffmpeg and pyav (reasons recorded) to the floor.
4. No inputs at all returns empty silences plus one `gaps[]` entry.
5. Live backends reproduce P26 goldens (recorded in the P29 integration evidence JSON under docs/).
Mapped to evals/evals.json and `python3 tools/videoedit/mediaprobe.py --selftest`.

## Approval-gated changes
Backend chain order, default thresholds (-50 dB, 2.0s), output schema, the floor's
`computed_by` string, and any new backend.

## Minority-report policy
When media measurement and the transcript floor disagree on a span, report the media result and
note the disagreement; never average the two.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/videoedit/mediaprobe.py --selftest` passes 17 of 17.
3. `python3 tools/scenario_check.py` exits 0 (S5 pins the floor).
4. `python3 tools/sync_check.py` exits 0.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
