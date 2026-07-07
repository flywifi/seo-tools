---
name: caption-bridge
atom: true
standalone: true
description: "Moves captions both ways between Creator OS and a video editor: a transcript becomes an SRT, VTT, or iTT file for Final Cut Pro or DaVinci Resolve, and an editor's exported captions come back as edit-package captions for SEO and repurposing. Reuses the offline transcript stack (shared/docintel/transcripts.py) for SRT/VTT and adds iTT. Do NOT use to transcribe audio (that is shared/transcription-engine.md); do NOT invent timings or caption text; CEA-608 (.scc) is not supported yet and is flagged, not faked."
engines_required:
  - shared/videoedit-engine.md
  - shared/transcription-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# caption-bridge (feature 2)

## When to use
"Give me captions for Final Cut / Resolve," "export this transcript as SRT," "pull my video's
captions back in for SEO," "turn my editor captions into chapters and keywords."

## Inputs
```json
{ "direction": "to_editor | from_editor",
  "source": "path to a transcript/caption file (or a segments list)",
  "format": "srt | vtt | itt   (to_editor only; default srt)" }
```

## Core procedure
- `to_editor`: read the source with `tools/videoedit/captions.py` (which reuses
  `shared/docintel/transcripts.py`), emit SRT/VTT via the shared emitter or iTT via the iTT writer.
  Return the caption file text. File writing drives no app, so it is allowed even while the master
  gate `video_editing_enabled` is off.
- `from_editor`: parse the editor's caption file into edit-package `timeline.captions[]`
  (`{start_seconds, end_seconds, text}`). Empty files return a `gaps[]` note, never fabricated cues.

## Output contract
`to_editor`: the caption file text (SRT/VTT/iTT). `from_editor`: `{captions[], caption_count, gaps[]}`
that merges into the shared edit-package (`shared/videoedit-engine.md`). Round-trips are stable:
transcript -> SRT -> captions[] -> SRT returns the same cues.

## Standalone usability
Fully standalone. Reuses the offline transcript stack; needs no editor and no network. Works on any
AI engine for the spec/text; file output needs local tools.

## Failure modes
- Unsupported request for CEA-608/.scc: return a clear "not supported yet" note; do not emit a
  malformed file.
- Malformed caption input: surface the parse error; never partially guess cues.

## Cross-modality
Inherits its calling spoke's class (the calling spoke's class); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
