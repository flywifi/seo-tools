---
file: skills/document-studio/references/artifact-types.md
role: the artifact types document-studio produces and the required elements of each.
---

# document-studio artifact types

## Ingestion record
The output of ingest-route for every file processed. Required elements: artifact_id, source (upload/onedrive/google_drive/youtube/instagram/tiktok/url/paste), file_type, family, ingestion_status (referenced/metadata_only/content_ingested/local_artifact_saved), extraction summary, injection_scan_result, content_category, routing_hint, needs_more_info (null if not needed), ran_locally: true, tokens_spent_on_parse: 0.

## Project brief (from document)
A structured project brief derived from an ingested file (e.g., notes, a DOCX, or a PDF). Required elements: all elements of the project-builder project brief artifact, plus a source_file_type and ingestion_record reference.

## Script draft
A section-by-section video script derived from an ingested file. Required elements: section sequence (hook, intro, body steps, transitions, CTA, outro), one section object per entry (section_type, script_text in planning-to-the creator voice, duration_estimate_seconds, broll_suggestion), and a source_file_type reference.

## Caption set (from document)
Captions derived from ingested content for one or more platforms. Required elements: one caption per platform, each within platform character limits, with hook line, body, CTA, FTC disclosure line (if required), character count, and a source_file_type reference.
