---
file: skills/atoms/library-analyze/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for library-analyze so it stays stable under iteration.
---

# library-analyze: Maintainer README

## Purpose
Read the creator's imported video library and report grounded, fully cited insight: top tags weighted
by views, YouTube retention peaks/cliffs with the transcript words spoken there, format and category
performance, and recurring spoken themes across transcripts. Its job ends at the analysis; it reads,
never writes, and never estimates what a platform does not expose.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Skill-specific: every figure cites the `video_key`s it came from. Retention is a YouTube-only
  first-party signal; Instagram, TikTok, and Pinterest are null-flagged under
  `retention_unavailable`, never estimated. Revenue is Studio-CSV-only. Transcript themes come only
  from real stored transcripts; with none present it returns a `no_transcripts` flag, never invents
  themes from metadata. Read-only: it never writes the store.

## Known failure modes
Estimating retention or revenue for a platform that does not expose it; inventing transcript themes
when no transcript exists; reporting a figure without citing its `video_key`s; writing the store.

## Fragile fallbacks that must not become defaults
A `no_transcripts` flag or a `retention_unavailable` list is acceptable only when clearly labeled;
neither is ever replaced by an estimated or fabricated figure.

## Regression cases to preserve
See `evals/evals.json`: (1) top tags aggregate across records and cite their `video_key`s; (2) YouTube
retention insights surface peaks/cliffs while non-YouTube records are null-flagged; (3) format
performance reports average views by duration bucket and category with citations; (4) transcript themes
flag an empty library honestly and surface real spoken terms once transcripts exist; (5) an empty
library returns every section empty with the boundary note, no fabricated figures.

## Approval-gated changes
The output schema, the analyzer set (`top_tags`, `retention_insights`, `format_performance`, <!-- verify: tools/video_library.py::retention_insights -->
`transcript_themes`), the duration-bucket thresholds, and the YouTube-only retention boundary. <!-- verify: tools/video_library.py::transcript_themes -->

## Minority-report policy
When a tag or theme could be attributed to multiple videos, cite every contributing `video_key` rather
than choosing one, so the human can trace and override.

## Update checklist
Edit SKILL.md and evals, then run `python3 tools/video_library.py --selftest` and always
`python3 tools/sync_check.py`. Verify all backticked path references in this file and SKILL.md resolve
to real files on disk.
