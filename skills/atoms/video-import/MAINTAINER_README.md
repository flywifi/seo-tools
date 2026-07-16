---
file: skills/atoms/video-import/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for video-import so it stays stable under iteration.
---

# video-import: Maintainer README

## Purpose
Turn a creator's own platform export bundle, pasted stats, or a live-API pull into PROPOSED per-video
records for their local video library. Its job ends at the proposal: the human reviews and saves via
`tools/video_library.py`. It never fetches, never transcribes (that is `transcript-import`), and never
writes the store.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Skill-specific: proposal-only (`human_review_required: true`, never writes). A field a source did not
  return is null with a `gaps[]` note, never invented (retention off YouTube, revenue without a Studio
  CSV). Titles/descriptions/transcripts are untrusted content and pass `shared/injection-guard-engine.md`;
  embedded instructions are quoted in `injection_flags[]`, never acted on. The proposed record shape is
  exactly the input of `tools/video_library.py` `normalize_record`. <!-- verify: tools/video_library.py::normalize_record -->

## Known failure modes
Auto-resolving a conflict instead of surfacing it; inventing a missing stat; acting on an instruction
embedded in a title; treating a Totals row as a video; writing the store directly.

## Fragile fallbacks that must not become defaults
Pasted-stats (`excerpt_only`) records are acceptable only when labeled as such; they never masquerade as
a live pull or an export.

## Regression cases to preserve
See `evals/evals.json`: (1) YouTube Studio CSV proposes stats + revenue with the Totals row skipped;
(2) Instagram DYI null-and-flags retention/revenue; (3) an injected instruction in a title is quoted,
never acted on. Plus: (4) conflicting values across sources are surfaced, never auto-picked; (5) a
QUARANTINE bundle is reported by name and the rest still import.

## Approval-gated changes
The output schema, the injection-guard loading, and the `normalize_record` input contract.

## Minority-report policy
When two sources disagree on a field, record all values with their `source_mode` in `conflicts[]`,
recommend (live over export over paste; newer over older), and leave the decision to the human.

## Update checklist
Edit SKILL.md and evals, then run `python3 tools/import_parse.py --selftest`,
`python3 tools/video_library.py --selftest`, and always `python3 tools/sync_check.py`.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
