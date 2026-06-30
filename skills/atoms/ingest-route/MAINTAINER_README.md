---
file: skills/atoms/ingest-route/MAINTAINER_README.md
purpose: keep ingest-route as the single entry point for all file ingestion; it classifies, parses, scans, and returns an ingestion record without routing the request.
---

# ingest-route: Maintainer README

## Purpose
Run classify → parse → inject-scan → return ingestion record. Never route the request; creator-core does that from the record.

## Non-negotiable invariants
- All external content (source != trusted_upload) passes through injection-guard-engine; a BLOCK result halts processing and returns the quarantine record.
- ingestion_status uses only the four-state ladder: referenced, metadata_only, content_ingested, local_artifact_saved.
- ran_locally and tokens_spent_on_parse are always set accurately in the returned record.

## Known failure modes
- Skipping the injection-guard scan for cloud-sourced files.
- Returning content_ingested when the parser returned less than PDF_MIN_YIELD chars.
- Routing inside this atom instead of returning the record for creator-core.

## Regression cases to preserve
1. Corrupt PDF: ingestion_status is metadata_only; needs_more_info is populated; no guess at content.
2. External cloud source: injection_scan_result appears in the output; never skipped.
3. Unsupported file type: metadata_only with a needs_more_info explaining the gap.

## Update checklist
- Run python3 tools/sync_check.py.
