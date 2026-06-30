---
file: shared/docintel-engine.md
role: offline-first document intelligence. Ingest any file type, parse and extract it with local
  zero-token scripts, scan untrusted content, then hand the compact extraction to the right spoke or
  send it back when more information is needed.
load: whenever a file, document, transcript, or external attachment is provided or fetched
---

# Document Intelligence Engine

## Design principles

Local-first, zero-token compute. Parsing and extraction run as local scripts in `shared/docintel/`
on the client with no internet and no tokens. The model only ever reads the compact structured
output, so tokens are spent on reasoning, not on re-reading raw bytes. This mirrors the scoop cache
in `shared/cache/`.

Detect first, parse second. Classify the file (type, family, trust) before parsing, so the right
local parser runs and unsupported or risky inputs are caught early.

Never overstate extraction. Use the four-state evidence ladder: `referenced`, `metadata_only`,
`content_ingested`, `local_artifact_saved`. A scanned PDF that yielded no text is `metadata_only`,
not `content_ingested`.

Scan untrusted content. Any externally-sourced text (a forwarded email, a fetched page, a brand
attachment) passes through `shared/injection-guard-engine.md` before it influences routing or
analysis.

Honest gaps and send-back. When a file is unreadable, encrypted, low-yield, or ambiguous, return an
explicit `needs_more_info` request (the gap-record atom) rather than guessing.

## The ingestion chain (local scripts do the work)
1. Classify: `shared/docintel/classify.py` returns type, family, magic bytes, parseable_offline, and
   a trust hint.
2. Parse and extract (offline, zero token):
   - `shared/docintel/parse_text.py`: text, data, and Office documents.
   - `shared/docintel/transcripts.py`: SRT, VTT, JSON, and plain transcripts.
   - `shared/docintel/wer.py`: validate a transcript against a reference (Word and Character Error
     Rate), all locally.
3. Scan: untrusted text through `shared/injection-guard-engine.md`.
4. Analyze (model): read the compact extraction and decide what it is (a contract, a media kit, an
   analytics screenshot, a moodboard, a transcript) and the content category.
5. Route or send back: the ingest-route atom hands off to the right lane and spoke, or returns
   `needs_more_info`.

## File type handling (offline, stdlib first)
| Family | Examples | Offline parser | Status it yields |
|---|---|---|---|
| document | docx, txt, md, rtf, html | parse_text.py (docx is zip plus xml) | content_ingested |
| spreadsheet | xlsx, csv, tsv | parse_text.py | content_ingested (rows and cells) |
| presentation | pptx | parse_text.py (slide xml) | content_ingested (slide text) |
| pdf | pdf | parse_text.py best-effort (flate streams); optional local library for hard PDFs | content_ingested or metadata_only |
| image | png, jpg, gif, webp | metadata only without OCR; optional local OCR when installed | metadata_only or content_ingested |
| transcript | srt, vtt, json | transcripts.py | content_ingested (segments) |
| data | json, xml | parse_text.py | content_ingested |
| audio, video | mp3, wav, mp4 | the transcription engine (local STT) produces the transcript | per transcription-engine |
| archive | zip | list members, then parse each member | referenced, then per member |

Where a format needs an optional local dependency (a PDF library, an OCR engine, a local STT model),
the engine prefers it when installed and otherwise returns `metadata_only` plus a send-back, never a
guess.

## Where files come from
- Uploaded by the user from their device: trusted source, parsed locally.
- Cloud storage and platform APIs (OneDrive, Google Drive, YouTube, Meta, TikTok): fetched via
  `shared/integrations-engine.md`, then parsed locally and scanned as untrusted external content.
- Pasted text or a fetched URL: handled via `shared/web-intel-engine.md` Level 5, scanned, then parsed.

## Placement in the workflow
Document intelligence runs as pre-routing middleware, like the injection guard. When a request carries
a file or attachment, the engine ingests and analyzes it first, then feeds the extracted content and
a routing hint to creator-core, which classifies the lane as usual. A quarantined or unreadable source
never reaches routing; it is recorded as a gap or a send-back.

## Output: ingestion record
```json
{
  "artifact_id": "doc_001",
  "source": "upload | onedrive | google_drive | youtube | url | paste",
  "file_type": "docx",
  "family": "document",
  "ingestion_status": "content_ingested",
  "extraction": {"char_count": 0, "summary_for_model": "", "tables": [], "segments": []},
  "injection_scan_result": "CLEAN",
  "content_category": "brand_contract | media_kit | analytics | moodboard | transcript | unknown",
  "routing_hint": "deal-pipeline | analytics-insights | content-strategy | document-studio | unknown",
  "needs_more_info": null,
  "ran_locally": true,
  "tokens_spent_on_parse": 0
}
```
