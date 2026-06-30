---
file: skills/document-studio/MAINTAINER_README.md
purpose: keep document-studio confirming file type before any downloadable output and scanning all external content through injection-guard.
---

# document-studio: Maintainer README

## Purpose
The Document lane spoke. Ingests any file type using the offline docintel pipeline and produces a structured artifact. All external content is scanned through injection-guard inside ingest-route.

## Non-negotiable invariants
- File type is confirmed before producing any downloadable output (protocols/formatting-metadata.md).
- All files pass through ingest-route (classify + parse + inject-scan); no raw bytes reach the model.
- A BLOCK result from injection-guard halts processing; no artifact is produced.

## Known failure modes
- Producing a downloadable artifact without confirming file type first.
- Skipping injection-guard for uploaded files labeled as "trusted" without running classify.
- Proceeding with content generation when ingest-route returns metadata_only (request more information instead).

## Regression cases to preserve
1. Externally sourced file: inject-scan runs; BLOCK result halts; no artifact produced.
2. Scanned PDF with low text yield: ingestion_status is metadata_only; gap-record returned; no guessed content.

## Approval-gated changes
- The artifact type routing logic in workflow.json.

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
