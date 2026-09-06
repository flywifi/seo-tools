---
file: skills/content-library/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for content-library so it stays stable under iteration.
---

# content-library: Maintainer README

## Purpose
Import, complete, and analyze the creator's OWN past videos across YouTube, Instagram, TikTok, and
Pinterest, entirely on the creator's machine. It composes video-import, library-complete,
transcript-import, and library-analyze. Its job ends at proposals and analysis; the human saves. It
never publishes (that is content-distributor) and never scans competitors (that is competitor-analysis).

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Skill-specific: the export bundle (or pasted stats) is the retrieval floor; the live OAuth pull is
  optional, gated behind `content_import_live` plus a per-platform read flag and the creator's own
  credentials, and builds no monetary URL (revenue is Studio-CSV-only). Retention and
  most-watched-parts are YouTube-only; off-YouTube they are null-flagged, never estimated. Transcripts
  come from a creator-uploaded caption or on-device STT (zero cloud, zero tokens); absent a backend they
  are flagged `run_local_stt`, never fabricated; ASR captions are not downloaded (403); no platform is
  scraped. All imported data stays local and gitignored. Untrusted title/description/transcript run
  through `shared/injection-guard-engine.md`. Class C: needs a local runtime and the creator's files.
  The importer proposes; the human saves.

## Known failure modes
Fabricating a transcript when STT is unavailable; estimating retention or revenue for a platform that
does not expose it; posting or scheduling (out of scope); writing the store directly; trying to
transcribe an API-only import with no downloaded file.

## Fragile fallbacks that must not become defaults
A metadata-only library with transcripts flagged `run_local_stt`, or a null-flagged retention off
YouTube, are acceptable only when clearly labeled; neither is ever replaced by invented content.

## Regression cases to preserve
See `evals/evals.json`: (1) a YouTube export builds records with retention and Studio-CSV revenue; (2)
an Instagram export builds records with retention null-flagged; (3) library-complete fills a missing
transcript on-device and joins it to retention; (4) with no STT backend the library is metadata-only and
transcripts carry the `run_local_stt` gap; (5) analysis cites video_keys and null-flags unavailable data.

## Approval-gated changes
The workflow.json step order, the output schema, the engine loading, the Class-C Cross-modality block,
and the tiered-retrieval / revenue-never boundaries.

## Minority-report policy
When the export bundle and the live API disagree on a stat, prefer the more authoritative source per the
connectors evidence ladder, record both, and flag the conflict for the human.

## Update checklist
Edit SKILL.md, workflow.json, and evals, then run `python3 tools/video_library.py --selftest`,
`python3 tools/library_complete.py --selftest`, and always `python3 tools/sync_check.py`. Verify all
backticked path references in this file and SKILL.md resolve to real files on disk, and that every atom
named in workflow.json is installed.
