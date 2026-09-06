---
file: skills/atoms/transcript-import/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for transcript-import so it stays stable under iteration.
---

# transcript-import: Maintainer README

## Purpose
Produce the transcript for one of the creator's own videos and propose it for their library record,
using a creator-uploaded YouTube caption when one exists, otherwise local on-device speech-to-text on
the file the creator already downloaded. Its job ends at the proposal; the human saves it.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Skill-specific: never fabricates spoken content and never scrapes a platform
  (`shared/content-import-engine.md`). YouTube auto (ASR) captions are not downloaded (403); only a
  creator-uploaded track is parsed, otherwise local STT runs. STT is zero-cloud, zero-token, on-device
  (`shared/transcription-engine.md`). When no backend or no file is available, return the
  `run_local_stt` gap with the per-OS install command and a null transcript, never a guess.

## Known failure modes
Presenting a fabricated transcript when STT is unavailable; attempting to download an ASR caption;
transcribing a file that is not local; writing the store directly.

## Fragile fallbacks that must not become defaults
A null transcript with a `run_local_stt` gap is acceptable only when clearly labeled; it is never
replaced by invented text.

## Regression cases to preserve
See `evals/evals.json`: (1) a creator-uploaded caption is parsed (source uploaded_caption, no STT);
(2) local STT runs on a downloaded file (source local_stt, on-device); (3) with no backend the
`run_local_stt` gap is returned with a null transcript. Plus: (4) an ASR-only YouTube video falls back
to local STT rather than a 403 download; (5) a zero-duration file is flagged, not transcribed.

## Approval-gated changes
The output schema, the caption-vs-STT decision order, and the transcription-engine loading.

## Minority-report policy
When both a caption and a file exist, prefer the creator-uploaded caption; record the choice and the
alternative (local STT) so the human can override.

## Update checklist
Edit SKILL.md and evals, then run `python3 tools/video_library.py --selftest` and always
`python3 tools/sync_check.py`. Verify all backticked path references in this file and SKILL.md resolve
to real files on disk.
