---
name: edit-timeline-spec
atom: true
standalone: true
description: "Turns a finished script (beats, b-roll notes, chapters, title cards) into a neutral edit-package: a timeline spec with markers per beat, gap clips for b-roll, chapter markers, and empty title clips, ready to become an FCPXML/OTIO timeline for Final Cut Pro or DaVinci Resolve. Produces the SPEC only (works on any AI engine, offline); turning it into an actual file is the realization step (tools/videoedit/fcpxml.py). Do NOT use for parsing an exported timeline (use fcpxml-parse); do NOT use for captions (use caption-bridge); do NOT use to run a render (use compressor-preset or resolve-drive)."
engines_required:
  - shared/videoedit-engine.md
  - shared/method.md
protocols:
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# edit-timeline-spec (feature 1)

## When to use
When a script or content plan is finalized and the creator wants it laid out as an editor timeline
rather than a blank project: "set up my Final Cut / Resolve timeline for this video," "give me a
timeline with markers for each section," "scaffold the edit."

## Inputs
```json
{
  "title": "string",
  "frame_rate": 30,
  "beats": [{"start_seconds": 0.0, "name": "string", "note": "string|null"}],
  "chapters": [{"start_seconds": 0.0, "title": "string"}],
  "titles": [{"start_seconds": 0.0, "duration_seconds": 4.0, "text": "string", "template": "string|null"}],
  "broll": [{"start_seconds": 0.0, "duration_seconds": 10.0, "name": "string"}]
}
```
Any field may be omitted; the atom null-and-flags what is missing rather than inventing beats.

## Core procedure
Map the inputs into the edit-package shape defined in `shared/videoedit-engine.md`: beats become
`timeline.markers`, chapters become `timeline.chapters`, titles become `timeline.titles`, b-roll
notes become placeholder `timeline.clips` (with `note`). Set `frame_rate`, `source: "creator-os"`,
and record any missing inputs in `gaps[]`. Follow `shared/method.md` (honest gaps, no fabrication).

## Output contract
A single edit-package JSON (see `shared/videoedit-engine.md`). It is the shared artifact every other
editing feature reads and writes, so this atom composes with all of them without coupling.

## Standalone usability
Fully standalone. Produces a valid spec on any engine with no editor installed. The realization step
(`tools/videoedit/fcpxml.py build`) turns it into a validated FCPXML file when `video_editing_enabled`
is on; while off, the spec is still the deliverable.

## Failure modes
- No beats/chapters provided: return an empty-but-valid timeline and a `gaps[]` note; never invent
  section names.
- Overlapping/negative times: clamp to 0 and flag; do not silently reorder.
