---
file: skills/document-studio/SKILL.md
name: document-studio
description: "ingests any file type using the offline docintel pipeline and produces a structured artifact (project brief, script, materials list, caption set, or other); does NOT route without confirming file type first."
load: always
lane: document
---

# document-studio

## Purpose

document-studio is the Document lane spoke. It accepts a local file path or a cloud source, runs
every file through the docintel pipeline for classification, parsing, and injection scanning, and
produces one structured downloadable artifact per invocation.

Before producing any output, document-studio confirms the file type with the caller. This confirmation
step is non-negotiable and is governed by `protocols/formatting-metadata.md`. No artifact is written
until `file_type_confirmed` is true.

All outputs are governed by the Quality Gates before delivery.

## Inputs

| Field | Type | Required | Notes |
|---|---|---|---|
| `file_path` | string | conditional | Local path to the source file. Required if `source` is not provided. |
| `source` | string | conditional | Cloud source: `onedrive`, `google-drive`, `youtube`, or `instagram`. Required if `file_path` is not provided. |
| `artifact_type` | string | required | One of: `project_brief`, `script`, `materials_list`, `caption_set`, `custom`. |
| `output_format` | string | optional | One of: `docx`, `txt`, `json`. Defaults to `docx`. |

Exactly one of `file_path` or `source` must be present.

## Primary outputs

| Field | Description |
|---|---|
| `file_type_confirmed` | Boolean. True only after the caller explicitly confirms the detected file type. |
| `ingestion_record` | From `ingest-route`: raw parse metadata and `injection_scan_result`. |
| `extracted_content_summary` | Structured summary: title, sections, word count, embedded media references. |
| `artifact` | The primary deliverable. Structure depends on `artifact_type`. |
| `quality_gate_result` | Pass or fail from `govern-artifact`. Artifact not delivered if fail. |

## Atoms composed

1. `ingest-route` -- classifies the file, parses content, runs injection scan.
2. `project-snapshot` -- extracts structured project metadata.
3. `materials-list` -- identifies and lists materials when applicable.
4. `step-sequence` -- orders procedural steps when the source has a how-to structure.
5. `script-section` (repeat: per_section) -- drafts each script section when `artifact_type` is `script`.
6. `caption-write` -- produces platform captions when `artifact_type` is `caption_set`.
7. `pin-write` -- produces Pinterest pin copy when platform list includes Pinterest.
8. `govern-artifact` -- runs the Quality Gates checklist.

## Engines required

- `shared/docintel-engine.md` -- document classification, parsing, and structured extraction.
- `shared/injection-guard-engine.md` -- prompt injection scanning on all ingested content.
- `shared/transcription-engine.md` -- audio/video transcription (required when source is audio or video).
- `shared/integrations-engine.md` -- cloud source authentication (required when `source` is provided).

## References

- `protocols/formatting-metadata.md` -- file type confirmation step and output format rules.
- `protocols/safety.md` -- injection scan response handling.
- `protocols/quality-gates.md` -- authoritative pass or fail criteria.

## Do NOT use for

- Content lane generation (ideas, hooks, SEO research) without a file source. Use a Content lane spoke.
- Pipeline CRM writes, deal creation, or contact updates. Use deal-pipeline.
- Bulk file processing (more than one file per invocation). Run one invocation per file.

## Knowledge-only mode note

In Claude Projects (web/mobile) mode, `document-studio` produces structured project snapshots,
materials lists, step sequences, and caption sets directly from the user's description without
requiring a file upload. The `ingest-route` and `transcription-engine` steps are skipped when no
file is provided. The output follows the same artifact schema; `injection_scan_result` is set to
`SKIPPED_NO_FILE`. This is the default behavior in Claude Projects mode.
