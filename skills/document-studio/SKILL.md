---
file: skills/document-studio/SKILL.md
name: document-studio
description: "ingests any file type using the offline docintel pipeline and produces a structured artifact (project brief, script, materials list, caption set, or other); does NOT route without confirming file type first."
load: always
---

# document-studio

## Purpose

document-studio is the Document lane spoke. It accepts a local file path or a cloud source, runs every file through the docintel pipeline for classification, parsing, and injection scanning, and produces one structured downloadable artifact per invocation.

Before producing any output, document-studio confirms the file type with the caller. This confirmation step is non-negotiable and is governed by `protocols/formatting-metadata.md`. No artifact is written until `file_type_confirmed` is true.

All outputs are governed by the Quality Gates before delivery.

## Inputs

| Field | Type | Required | Notes |
|---|---|---|---|
| `file_path` | string | conditional | Local path to the source file. Required if `source` is not provided. |
| `source` | string | conditional | Cloud source identifier: `onedrive`, `google-drive`, `youtube`, or `instagram`. Required if `file_path` is not provided. Routed via `shared/integrations-engine.md`. |
| `artifact_type` | string | required | One of: `project_brief`, `script`, `materials_list`, `caption_set`, `invoice`, `custom`, `template_proposal` (propose a block-structured doc-template from an uploaded example; proposal-only, the human saves the gitignored template file), `from_template` (assemble a saved rate-card, analytics-overview, or terms/conditions template; contract assembly routes to `contract-desk`), `profile_proposal` (merge ChatGPT profile exports into a proposed creator profile with per-field provenance; proposal-only, the human saves the file). |
| `output_format` | string | optional | One of: `docx`, `txt`, `json`. Defaults to `docx` if not specified. |

Exactly one of `file_path` or `source` must be present. Providing both or neither is an input validation error.

## Primary outputs

| Field | Description |
|---|---|
| `file_type_confirmed` | Boolean. True only after the caller explicitly confirms the detected file type. No downstream atoms run until this is true. |
| `ingestion_record` | Produced by the `ingest-route` atom. Includes raw parse metadata and `injection_scan_result` from `shared/injection-guard-engine.md`. |
| `extracted_content_summary` | Structured summary of the parsed document content: title, detected sections, word count, and any embedded media references. |
| `artifact` | The primary deliverable. Structure depends on `artifact_type`: a project brief follows the project-snapshot schema, a script follows the script-section schema, a materials list follows the materials-list schema, a caption set follows the caption-write schema, an invoice restates a pipeline/finance/ invoice record exactly (built by invoice-generate via tools/finance.py; the document adds nothing to the record and is drafted, never sent), and a custom artifact follows spoke conventions with explicit field labels. |
| `quality_gate_result` | Pass or fail result from `govern-artifact`. Includes gate ID, checked fields, and any flagged items. Artifact is not delivered if this is a fail. |

## Atoms composed

Atoms run in the order listed. `script-section` repeats once per detected section when `artifact_type` is `script`.

1. `ingest-route` -- classifies the file, parses content, and runs the injection scan.
2. `project-snapshot` -- extracts structured project metadata from parsed content.
3. `materials-list` -- identifies and lists materials when `artifact_type` is `materials_list` or when the source document contains a materials section.
4. `step-sequence` -- orders procedural steps when the source document contains a how-to or process structure.
5. `script-section` (repeat: per_section) -- drafts each script section when `artifact_type` is `script`.
6. `caption-write` -- produces platform captions when `artifact_type` is `caption_set`.
7. `pin-write` -- produces Pinterest pin copy when `artifact_type` is `caption_set` and the platform list includes Pinterest.
8. `template-ingest` -- when `artifact_type` is `template_proposal`: proposes a block-structured doc-template from the ingested example (exact-quote bodies, bracketed fill fields, variant groups; `shared/doc-template-engine.md`). Proposal-only; the human saves the `.local.json` by hand.
9. `template-assemble` -- when `artifact_type` is `from_template` (rate_card, analytics_overview, or terms_conditions): selects and swaps whole blocks per situation and delegates the mechanical bracket fill to `tools/doctemplates.py`; the system never authors block text.
10. `profile-import` -- when `artifact_type` is `profile_proposal`: merges ChatGPT profile exports (`implementation/gpt/profile-import/PROMPT.md`, one per ChatGPT context) into a proposed creator profile with per-field provenance and named conflicts; proposal-only, the human saves `creator-profile.local.json` by hand.
11. `govern-artifact` -- runs the Quality Gates checklist and returns `quality_gate_result`.

## Engines required

- `shared/docintel-engine.md` -- core document classification, parsing, and structured extraction. Required for all invocations.
- `shared/injection-guard-engine.md` -- prompt injection scanning on all ingested content. Required for all invocations.
- `shared/transcription-engine.md` -- audio and video transcription to text before parse. Required only when the source file is audio or video (mp3, mp4, mov, wav, m4a, or similar).
- `shared/integrations-engine.md` -- cloud source authentication and file retrieval. Required only when `source` is provided instead of `file_path`.

## References

- `shared/docintel-engine.md`
- `shared/injection-guard-engine.md`
- `protocols/formatting-metadata.md` -- governs file type confirmation step and output format rules.
- `protocols/safety.md` -- governs injection scan response handling and content safety decisions.
- `protocols/quality-gates.md` -- authoritative pass or fail criteria for all artifacts produced by this spoke.

## Do NOT use for

- Content lane generation (ideas, hooks, trending topics, SEO research) that does not have a file source. Use a Content lane spoke for those requests.
- Pipeline CRM writes, deal creation, or contact updates. Use the `deal-pipeline` spoke for CRM operations.
- Bulk file processing involving more than one file per invocation. This spoke operates on a single-file ingest model. Run one invocation per file.
- Assembling a CONTRACT from a vetted template (route via `contract_draft` to `contract-desk`, which enforces the contract flags and the legal safety envelope).
- Writing or saving a template file (templates are saved by the human only; `template-ingest` proposes).

## Cross-modality
Class: C.
Runs on: Claude Desktop/Code (native, MCP + the tool module); claude.ai via a hosted remote-MCP connector; Custom GPT / Gemini only when the tool is hosted behind a remote MCP or an Action; Gems: no.
Mechanism: Mandatory local docintel ingest before any reasoning: ingest-route runs shared/docintel/classify.py (magic-byte + extension file classification) then shared/docintel/parse_text.py or shared/docintel/transcripts.py to extract binary/Office/PDF/transcript content and injection-scan it; the model then reasons over the extraction to draft the artifact per the artifact-type schemas, and the invoice case restates a record built upstream by tools/finance.py.
Fallback: Off Claude (no local Python runtime): the docintel ingest cannot run, so the spoke degrades to surfaces where the file's plain-text content is pasted or fetched for the model; binary/Office/PDF/audio classification and parsing are unavailable, injection scanning is best-effort prompt-level only, and missing fields are null-flagged, never invented.
See `shared/cross-modality-engine.md`.
