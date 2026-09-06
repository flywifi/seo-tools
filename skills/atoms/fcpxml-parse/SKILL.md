---
name: fcpxml-parse
atom: true
standalone: true
description: "Reads an FCPXML exported from Final Cut Pro or DaVinci Resolve and turns it back into a neutral edit-package: markers become YouTube Key Moments candidates, chapter markers become description timestamps, keywords become shot logs, and roles map audio stems. This is the offline-to-online handoff that feeds SEO and scheduling. Requires the local parser (tools/videoedit/fcpxml.py) to read the file. Do NOT use to create a timeline (use edit-timeline-spec); do NOT use for captions (use caption-bridge); do NOT invent markers the file does not contain."
engines_required:
  - shared/videoedit-engine.md
  - shared/method.md
protocols:
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# fcpxml-parse (feature 4)

## When to use
After the creator exports an FCPXML/`.fcpxmld` from their editor and wants its markers, chapters,
keywords, and roles pulled back into Creator OS: "import my timeline markers," "turn my chapter
markers into YouTube chapters," "read my edit for SEO."

## Inputs
```json
{ "fcpxml_path": "path to .fcpxml or .fcpxmld (or the FCPXML text)" }
```

## Core procedure
Call `tools/videoedit/fcpxml.py parse` to recover the edit-package (markers, chapters, keywords,
titles, roles, fps). Emit exactly what the file contains; anything absent is null-and-flagged in
`gaps[]`. Downstream: chapters feed `geo-optimize` (Key Moments) and `content-calendar`/scheduling;
keywords feed `entity-extract`; roles inform the audio-stem plan. Never add markers, chapter titles,
or timestamps not present in the file.

## Output contract
An edit-package JSON (`shared/videoedit-engine.md`) with `source: "fcpxml-parse"`, plus a short
`handoff` note listing which downstream consumers each field feeds. This is the same shared artifact
`edit-timeline-spec` produces, so a full round-trip (spec -> FCPXML -> parse) returns the same data.

## Standalone usability
Standalone. Reading + normalizing is a local file operation and does not need `video_editing_enabled`
(no app is driven). The parsed data flows to any downstream atom.

## Failure modes
- Malformed/invalid FCPXML: return the well-formedness/validation error from
  `tools/videoedit/fcpxml.py validate`; do not partially guess.
- Empty timeline: return a valid empty edit-package and a `gaps[]` note; never fabricate markers.

## Cross-modality
Inherits its calling spoke's class (the calling spoke's class); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
