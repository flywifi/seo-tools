# The Completeness Contract

One page naming, in one place, the honesty machinery that already runs across Creator OS. The rule is
simple: **outputs say what they cover and what they do not.** Nothing claims to be complete when it is
partial, and nothing is invented to fill a gap (`protocols/no-fabrication.md`). This document is a map of
the mechanisms that enforce that rule; it does not add new behavior.

## The evidence ladder (how a value earns its confidence)

Every externally-sourced value carries the rung that produced it. See
`shared/connectors/connectors.md` (the model) and `shared/connectors/connectors.json` (the machine-readable
`evidence_modes` with per-mode `primary_weakness`):

| Rung | `source_mode` | What it means | Weakness recorded |
|---|---|---|---|
| A | `direct_connector` | pulled live from an authenticated API | freshest, but scope-limited |
| B | `export_bundle` | parsed from an official export the user downloaded | complete-ish, point-in-time |
| C | `excerpt_only` | a pasted/quoted fragment | cannot be validated against the whole artifact |
| D | `internal_context_only` | from the user's own profile/records | no external corroboration |
| E | `hybrid_reconciliation` | reconciled across sources | conflicts must be shown, not hidden |

Downgrades are never silent (`connectors.json:evidence_mode_rules.silent_downgrade_forbidden`). The
resolver `shared/connectors/connectors.py` turns the active flags into the provider chain.

## Grading completeness

Every bundle carries `artifact_completeness: minimal | partial | rich`
(`shared/schemas/verification-envelope.json`; referenced by `shared/schemas/deal-review.json` and
`connectors.json:artifact_completeness_values`). A `minimal` bundle is a valid answer that says so.

## Where each field lives (file:line anchors)

- **`source_mode`** — set at import (`tools/importers/youtube_import.py`), persisted with per-field
  provenance (`tools/video_library.py normalize_record`), documented in
  `pipeline/video-library/video-library-schema.json`.
- **Freshness envelope** — every refreshed value is wrapped with `{value, source_citation, publish_date,
  as_of}` (`tools/freshness_overlay.py envelope`), so a stale value ages and flags rather than silently
  going wrong; the knowledge-surface analogue is the freshness stamp (`tools/build_freshness_bundle.py`).
- **Truncation sentinels** — a live importer that hits its page cap returns `truncated: true` +
  `truncation_note` ("your library may be incomplete; N pages capped") rather than a silently short list
  (`tools/importers/youtube_import.py`, `instagram_import.py`, `tiktok_import.py`).
- **Blocked, not gone** — a bot-blocked fetch is reported `blocked` (inconclusive), never demoted to
  stale/changed/gone (`tools/source_currency.py`; `docs/CURRENCY.md`).
- **Retrieval gaps** — when a level cannot deliver, the field is left null and a gap is recorded, never
  synthesized (`shared/web-intel-engine.md` Levels 5 to 6).
- **`metadata_only`** — a connector state that is explicitly "listed, not content-ingested"
  (`shared/connectors/connectors.md`).

## The wording rule (chat surfaces)

User-facing capability descriptions must not promise completeness the tool does not deliver. Prefer the
honest framing the packs already use elsewhere (for example `implementation/gpt/web/custom-instructions.md`
"running in knowledge-only mode ... no platform API data"). Do not write "complete", "full", or
"comprehensive" for an output whose own schema exposes `retrieval_gaps`, `fabrication_flags`, or
`[estimated]` values. GPT Action descriptions were softened accordingly (`seo_keywords.yaml`,
`video_development.yaml`): they now describe what runs and point at the gap/estimate fields instead of
claiming a "complete" or "full" deliverable.
