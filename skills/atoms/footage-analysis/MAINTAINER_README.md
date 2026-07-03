---
file: skills/atoms/footage-analysis/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for footage-analysis so it stays stable under iteration.
---

# footage-analysis: Maintainer README

## Purpose
Turn a raw-footage transcript into chapter and cut suggestions. Timing math (silence detection,
words_per_minute analysis) is delegated to `shared/docintel/transcripts.py` functions
`gap_metrics()` and `suggest_chapters()`; when the media file itself is available, timing
evidence upgrades to `silence-scan`/`scene-scan` (P29, `tools/videoedit/mediaprobe.py`) with the
transcript numbers remaining the floor and every result keeping its own `computed_by`. This
atom's job ends at a named, evidence-cited proposal for human review. Formatting the confirmed
chapters is `chapter-map`'s job.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- All timing numbers come from `shared/docintel/transcripts.py`; the model never computes or
  invents timecodes, gap durations, or words_per_minute values.
- `suggested_title` from the tool is always null; only the model/human names chapters, and only
  from transcript text.
- Output always sets `human_review_required: true`; no cut is applied automatically.
- Degradation is explicit: no timecodes means `timing_unavailable: true`, never silent topic
  guessing presented as timing analysis.

## Known failure modes
- Plain-text transcripts (no timecodes) make silence analysis impossible.
- Uniformly dense speech produces zero boundaries; must be reported, not padded.
- Very short footage yields fewer than 3 chapters (below the YouTube Key Moments minimum).

## Fragile fallbacks that must not become defaults
- Topic-only outlines from untimed transcripts (acceptable only when flagged).
- Lowering `min_gap_seconds` to force cut candidates (never done silently).

## Regression cases to preserve
1. workshop-footage.srt at min_gap_seconds 8.0 yields exactly 3 silences (12.5s, 8.5s, 20.0s);
   pinned by scenario S5 leg `footage-silences` in `skills/creator-core/evals/scenarios.json`.
2. suggest-chapters on the same fixture proposes 3 boundaries, all basis "silence", titles null.
3. Plain-text transcript input flags timing_unavailable and produces no cut_candidates.
4. Zero-silence transcript returns an empty cut_candidates list with an explanatory note.
5. Hub utterance "here's raw footage, break it down" classifies as `footage_breakdown` and
   routes to `video-development` (pinned by scenario S5 routing).
Mapped to evals/evals.json.

## Approval-gated changes
Output schema, the default thresholds (8.0s gap, 30.0s chapter minimum), engine loading, and
any change to the delegation boundary between this atom and `shared/docintel/transcripts.py`.

## Minority-report policy
When silence evidence and words_per_minute evidence disagree on a boundary, keep both candidates
and record the disagreement in the output notes rather than suppressing one.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 shared/docintel/transcripts.py skills/creator-core/evals/fixtures/workshop-footage.srt --gap-metrics --min-gap-seconds 8.0` still returns 3 silences.
3. `python3 tools/scenario_check.py` exits 0 (S5 pins this atom's timing contract).
4. `python3 tools/sync_check.py` exits 0.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
