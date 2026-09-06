---
file: skills/atoms/library-complete/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for library-complete so it stays stable under iteration.
---

# library-complete: Maintainer README

## Purpose
Complete an already-imported video library by filling the fields the platforms withhold: match each
downloaded media file to its record, run on-device STT for missing transcripts, derive chapters and
spoken keywords, and join the YouTube retention curve to the transcript so each most-watched peak
carries the actual words spoken there. Its job ends at the proposal; the human saves it.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Skill-specific: never fabricates transcripts, chapters, or most-watched words
  (`shared/content-import-engine.md`, `protocols/no-fabrication.md`). All STT is zero-cloud,
  zero-token, on-device (`shared/transcription-engine.md`). When no backend is installed, return the
  `run_local_stt` gap with the per-OS install command, never a guess. Retention exists only on YouTube;
  off-YouTube it is null-flagged, not invented. Media matching never force-fits an unmatched file to a
  record. It proposes completions; the human saves them.

## Known failure modes
Fabricating a transcript when STT is unavailable; force-mapping an unmatched media file to a record;
inventing retention or most-watched words off YouTube; writing the store directly.

## Fragile fallbacks that must not become defaults
A null transcript with a `run_local_stt` gap, or a null-flagged retention on a non-YouTube platform,
are acceptable only when clearly labeled; neither is ever replaced by invented content.

## Regression cases to preserve
See `evals/evals.json`: (1) a downloaded file named with the platform video id is matched to its
record; (2) local STT (injected) fills a missing transcript with recorded provenance; (3) the YouTube
retention peak carries the transcript line spoken there and the cliff line is identified; (4) with no
STT backend the `run_local_stt` gap is returned, no transcript fabricated; (5) an Instagram record has
retention null-flagged while its transcript and topics are still delivered.

## Approval-gated changes
The output schema, the media-match order, the retention x transcript join formula
(`elapsed_ratio x duration_s`), and the transcription-engine loading.

## Minority-report policy
When media matches by both filename id and duration/title, prefer the filename id and record the
alternative so the human can override.

## Update checklist
Edit SKILL.md and evals, then run `python3 tools/library_complete.py --selftest`,
`python3 tools/transcribe.py --selftest`, and always `python3 tools/sync_check.py`. Verify all
backticked path references in this file and SKILL.md resolve to real files on disk.
