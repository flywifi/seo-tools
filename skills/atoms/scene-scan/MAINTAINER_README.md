---
file: skills/atoms/scene-scan/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for scene-scan so it stays stable under iteration.
---

# scene-scan: Maintainer README

## Purpose
Single-operation scene-change detection over raw media or a transcript. All measurement is
delegated to `tools/videoedit/mediaprobe.py` `detect_scenes()`; this atom's job ends at the
boundary candidate list with null titles. Naming and narrative belong to `footage-analysis`;
formatting belongs to `chapter-map`.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- `suggested_title` is always null in tool output; only the model or human names chapters, and
  only from transcript or footage content.
- The scdet fallback always carries the luma-only caveat note; it is never stripped.
- The backend chain order is fixed: PySceneDetect ContentDetector, ffmpeg scdet, transcript
  floor (`shared/docintel/transcripts.suggest_chapters`).
- No capability flag gates this atom (local read-only analysis).

## Known failure modes
- scdet misses isoluminant cuts (verified: the 60s red-to-green cut in the P26 fixture); the
  caveat note is the mitigation, not a fix.
- Slow dissolves can register late or not at all at default thresholds.
- PySceneDetect 0.7 renamed `get_seconds()` to the `seconds` property; mediaprobe handles both.

## Fragile fallbacks that must not become defaults
- scdet standing in for ContentDetector without its caveat.
- The transcript floor's pause/pace boundaries being presented as visual scene cuts.

## Regression cases to preserve
1. scdet fixture stderr parses to cuts at exactly 150/240/330 with the 60s cut absent
   (mediaprobe selftest, committed fixtures).
2. Live PySceneDetect finds all four authored cuts [60, 150, 240, 330] at threshold 27.0
   (recorded in the P29 integration evidence JSON under docs/).
3. Transcript floor proposes 3 boundaries on `workshop-footage.srt`, all titles null, with the
   pinned `computed_by`.
4. No inputs at all returns empty results plus one `gaps[]` entry.
5. Unknown forced backend is refused honestly (no partial output).
Mapped to evals/evals.json and `python3 tools/videoedit/mediaprobe.py --selftest`.

## Approval-gated changes
Backend chain order, default thresholds (27.0 ContentDetector, 10.0 scdet), output schema, the
null-title rule, and any new backend.

## Minority-report policy
When two backends are run deliberately and disagree on a boundary, keep both results with their
`computed_by` labels and record the disagreement; never merge into one unattributed list.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/videoedit/mediaprobe.py --selftest` passes 17 of 17.
3. `python3 tools/sync_check.py` exits 0.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
