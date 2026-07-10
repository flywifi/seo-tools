---
file: skills/atoms/ingest-route/SKILL.md
name: ingest-route
description: >
  Entry point for all file ingestion. Runs classify then parse then inject-scan in sequence using
  local zero-token scripts, then returns a structured ingestion record that creator-core uses to
  decide the processing lane. Use whenever a file, attachment, or cloud-sourced asset arrives
  before routing. Do NOT use to perform routing, generate content, or act on the ingestion record;
  that is creator-core's responsibility.
load: whenever a file_path or cloud source is provided before lane classification
---

# ingest-route

Single-responsibility entry point for all file and asset ingestion. Runs four steps locally in
sequence (classify, parse, inject-scan, assemble record) and returns one structured ingestion record.
It does not route, generate, or act. creator-core reads the record and decides the lane.

## Purpose

All ingestion passes through this atom before reaching creator-core or any spoke. The four-step
chain is always local and zero-token:

1. Classify: `shared/docintel/classify.py` reads magic bytes and extension to return file_type,
   family, parseable_offline, and a trust hint.
2. Parse: `shared/docintel/parse_text.py` handles text, data, Office, PDF, and spreadsheet formats.
   `shared/docintel/transcripts.py` handles SRT, VTT, JSON transcript, and plain transcript formats.
   For audio and video, the transcription engine produces the transcript first; this atom then ingests
   that transcript. Unreadable or encrypted files yield `metadata_only` plus a `needs_more_info`
   value, never a guess.
3. Inject-scan: untrusted text passes through `shared/injection-guard-engine.md`. The result is one
   of `CLEAN`, `REVIEW`, `QUARANTINE`, or `BLOCK`. A `QUARANTINE` or `BLOCK` result stops ingestion;
   the record is assembled with `ingestion_status: quarantined` and no content reaches routing.
4. Assemble: the atom compiles all step outputs into the ingestion record per the
   `shared/docintel-engine.md` output spec and returns it.

No tokens are spent on classify, parse, or scan. Tokens are spent only on the model step when
creator-core reads the extraction to reason about the content category and routing hint.

## Inputs

```json
{
  "file_path": "absolute local path to the file (mutually exclusive with source)",
  "source": {
    "provider": "onedrive | google_drive | youtube | instagram | tiktok",
    "identifier": "URL, file ID, or platform content ID"
  },
  "artifact_id": "optional caller-supplied ID; atom generates one if omitted",
  "trust_hint": "trusted_upload | untrusted_external (defaults to untrusted_external if omitted)"
}
```

Provide `file_path` for local files. Provide `source` for cloud-sourced assets fetched via
`shared/integrations-engine.md`. Do not provide both.

`trust_hint` of `trusted_upload` allows inject-scan to run with a lower alert threshold. When
omitted, the atom defaults to `untrusted_external`, which runs the full injection guard check.

## Output

Returns one ingestion record per the `shared/docintel-engine.md` output spec.

```json
{
  "artifact_id": "doc_001",
  "source": "upload | onedrive | google_drive | youtube | instagram | tiktok | url | paste",
  "file_type": "docx",
  "family": "document | spreadsheet | presentation | pdf | image | transcript | data | audio | video | archive | unknown",
  "ingestion_status": "content_ingested | metadata_only | quarantined | send_back",
  "extraction": {
    "char_count": 0,
    "summary_for_model": "",
    "tables": [],
    "segments": []
  },
  "injection_scan_result": "CLEAN | REVIEW | QUARANTINE | BLOCK",
  "content_category": "brand_contract | media_kit | analytics | moodboard | transcript | unknown",
  "routing_hint": "deal-pipeline | analytics-insights | content-strategy | document-studio | unknown",
  "needs_more_info": null,
  "ran_locally": true,
  "tokens_spent_on_parse": 0
}
```

`content_category` and `routing_hint` are populated by creator-core after reading
`extraction.summary_for_model`; this atom sets them to `unknown` unless classification is
unambiguous from file type alone.

`needs_more_info` is non-null when the file is unreadable, encrypted, low-yield, or ambiguous. The
value is a structured gap-record prompt for the user, produced via the `gap-record` atom.

`tokens_spent_on_parse` is always 0 because parsing is local and offline. The field exists so
creator-core can log it in the ledger for auditing.

## Do NOT use for

- Routing the request to a lane or spoke. Return the record and let creator-core decide.
- Generating, drafting, or modifying any content artifact.
- Running the injection guard directly on pasted text with no file context; use
  `shared/injection-guard-engine.md` directly for that case.
- Validating transcript accuracy against a reference (use `shared/docintel/wer.py` via the
  transcription spoke for that).
- Fetching from cloud providers; cloud fetch is handled by `shared/integrations-engine.md` before
  this atom is called. The atom receives the downloaded bytes or local path.

## References

- `shared/docintel-engine.md` (output spec, ingestion chain design, file type handling)
- `shared/injection-guard-engine.md` (scan thresholds, CLEAN to BLOCK verdicts)
- `shared/docintel/classify.py` (local classify script)
- `shared/docintel/parse_text.py` (local parse script for text and Office formats)
- `shared/docintel/transcripts.py` (local parse script for transcript formats)
- `shared/integrations-engine.md` (cloud fetch, called upstream of this atom)
- `shared/method.md` (pipeline discipline and evidence standards)

## Cross-modality
Inherits its calling spoke's class (varies by caller (B/C)); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
