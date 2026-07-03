# Video Editing Engine

Canonical knowledge layer for the Creator OS video-editing bridge (P22). Loaded by the editing
atoms (`edit-timeline-spec`, `fcpxml-parse`, `caption-bridge`, `shorts-edit-spec`, `chapter-map`,
`compressor-preset`, `motion-fill`, `commandpost-macro`, `resolve-drive`) and realized by
`tools/videoedit/`. Internal engine doc; may use em dashes freely.

## The design in one paragraph

Final Cut Pro has no scripting API — the only official surfaces are FCPXML (a file that describes a
timeline), a single "Open Document" Apple event to hand FCP a file to import, and Workflow
Extensions (in-app panels). DaVinci Resolve is the opposite: a real Python API on macOS, Windows,
and Linux, and it reads and writes FCPXML. So Creator OS bridges editors through **one neutral
core** (an editor-agnostic timeline description) exposed as **two lanes**: a universal **file
interchange** lane (generate/parse FCPXML + OpenTimelineIO — just files, any OS, even offline), and
a **Resolve live-control** lane (the Resolve Studio API for renders/markers/queue). Because both
editors read FCPXML, one file targets both.

## The edit-package (the shared artifact every feature reads and writes)

All eight features communicate through this one normalized JSON, never by calling each other. Any
subset works alone; any combination merges into the same package (upsert). Missing pieces are
null-and-flagged (`shared/method.md` honest-gap rule), never invented.

```json
{
  "schema_version": "1.0",
  "title": "string",
  "created_at": "ISO 8601 | null",
  "source": "creator-os | fcpxml-parse | resolve",
  "frame_rate": 30,
  "timeline": {
    "name": "string",
    "duration_seconds": "number | null",
    "markers":  [{"start_seconds": 0.0, "name": "string", "note": "string", "type": "standard|chapter|to-do|completed", "color": "string|null"}],
    "chapters": [{"start_seconds": 0.0, "title": "string", "poster_offset_seconds": 0.0}],
    "titles":   [{"start_seconds": 0.0, "duration_seconds": 4.0, "text": "string", "template": "string|null", "role": "titles"}],
    "clips":    [{"start_seconds": 0.0, "duration_seconds": 10.0, "name": "string", "role": "video", "asset_ref": "string|null", "note": "string|null"}],
    "captions": [{"start_seconds": 0.0, "end_seconds": 2.0, "text": "string"}],
    "keywords": [{"start_seconds": 0.0, "duration_seconds": 5.0, "keyword": "string"}],
    "roles": ["video", "titles", "dialogue", "music"]
  },
  "reframe": {"enabled": false, "aspect": "9:16", "method": "auto_reframe"},
  "export":  {"presets": [], "platform_targets": []},
  "gaps":    [{"gap_type": "string", "description": "string", "impact": "string", "recommended_next_step": "string"}],
  "provenance": {"generated_by": "string", "tool_version": "1.0"}
}
```

`tools/videoedit/otio_core.py` builds/parses this; `fcpxml.py` maps it to and from FCPXML;
`resolve.py` realizes it in a running Resolve project. Time is always seconds in the package; the
FCPXML layer converts to rational time.

## FCPXML mapping (Lane A)

- File: `.fcpxml` (flat) or `.fcpxmld` (a macOS package/bundle, since FCP 10.6 / FCPXML 1.10; needed
  for object-tracking / cinematic sidecar data).
- Version: read the DTD `version` from the installed editor — do NOT hardcode a table. Anchors from
  research (confirm locally): FCP 10.6 → 1.10, FCP 11 → 1.13, FCP 12.x → ~1.14. Resolve exports
  `EXPORT_FCPXML_1_3` … `EXPORT_FCPXML_1_10`.
- Vocabulary used: `fcpxml` → `resources` (`format`, `asset`, `effect`) + `library` → `event` →
  `project` → `sequence` → `spine`. Inside the spine: `gap` (the empty-timeline container that
  carries markers), `title` (editor titles / Motion templates via an `effect` ref + `text`/`param`),
  `asset-clip`/`video`/`audio` (media), `marker`, `chapter-marker`, `keyword`, and `caption`
  (with nested `text`/`text-style`). Roles are `role`/`audio-role`/`video-role` attributes.
- Time format: rational `NUM/DENs` or integer `NUMs`. `tools/videoedit/fcpxml.py` encodes seconds as
  `round(sec * fps * 100)/(fps*100)s` for stable round-trips.
- Validation: `xmllint --noout --dtdvalid <DTD> file.fcpxml`. When no editor DTD is present, fall
  back to well-formedness (`xmllint --noout`) plus a structural check, and report which level ran.
- Import trigger: the Open Document Apple event (AppleScript only *delivers* the file; it cannot edit).

## Captions (feature 2)

FCP imports/exports **CEA-608 (.scc)**, **iTT (.itt)**, and **SRT (.srt)**; only CEA-608 embeds into
the media. Reuse `shared/docintel/transcripts.py` (already parses/emits SRT/VTT) for the transcript
↔ caption conversion; convert its segments to the edit-package `captions[]` and back. Realized by
`tools/videoedit/captions.py` (`to_editor` / `from_editor`): SRT/VTT via docintel, iTT (Apple TTML)
added here, CEA-608 deferred and flagged (never faked).

## Chapters (feature 8)

One chapter list, fanned out by `tools/videoedit/chapters.py:fan_out`: the `geo-optimize` input shape
(`{timestamp_seconds, chapter_topic}`), a paste-ready YouTube description block (`0:00 Title`, MM:SS
then H:MM:SS past an hour, first line forced to 0:00), and scheduling metadata for the content
calendar / scheduling queue. YouTube's Key Moments rules (first at 0:00, at least 3 chapters, each at
least 10 seconds) are validate-and-flag in `gaps[]`, never silently fixed or invented.

## Media analysis: silence and scenes (P29)

`tools/videoedit/mediaprobe.py` measures raw media locally with optional, runtime-detected
backends and honest degradation. No capability flag gates it (read-only local analysis, like
chapter fan-out); availability is a function of what is installed, reported by preflight.

- Silence chain: `ffmpeg silencedetect` -> PyAV windowed RMS -> the transcript floor
  (`shared/docintel/transcripts.gap_metrics`).
- Scene chain: PySceneDetect `ContentDetector` -> `ffmpeg scdet` -> the transcript floor
  (`shared/docintel/transcripts.suggest_chapters`). The scdet fallback scores luma only, so cuts
  between isoluminant colors can be missed; that caveat rides on every scdet result as a note
  (verified in the P26 evaluation, `docs/VIDEO_TOOLING_EVAL.md`).

Provenance contract: every result carries `computed_by` (the backend that actually ran),
`backend_chain` (each link tried, with the reason it was skipped or failed), and the echoed
`parameters`. Chapter candidates never carry invented titles (`suggested_title` is null until a
human or the model names them from real content). `mediaprobe.to_edit_package` folds results
into the shared edit-package as markers; pending titles are recorded in `gaps[]`. Atoms:
`silence-scan`, `scene-scan`; `footage-analysis` composes them when media is present.

## Compressor (feature 5)

macOS batch encoder: `/Applications/Compressor.app/Contents/MacOS/Compressor -batchname NAME
-jobpath SRC -settingpath PRESET.compressorsetting -locationpath OUT`. Presets are keyed to
`shared/platform-engine.md` specs (YouTube 4K/1080, Shorts/Reels 1080x1920, Pinterest, TikTok). The
cross-OS alternative is the Resolve render queue (Lane B).

## Motion templates (feature 6)

Brand titles/lower-thirds live in `~/Movies/Motion Templates/{Titles,Effects,Transitions,Generators}/`.
FCPXML references a template via an `effect` resource and sets its published parameters (including
text) on the `title` clip — how `motion-fill` injects generated copy. macOS + FCP only.

## CommandPost (feature 7)

macOS Lua automation (open source, active) for finishing chores FCPXML cannot reach. `commandpost.py`
emits/triggers macros. Spec/snippet generation works everywhere; execution needs macOS + CommandPost.

## On-device ML (Auto Reframe, Transcribe to Captions, Magnetic Mask, Object Tracker)

UI-only in FCP — cannot be triggered by FCPXML or a script. The edit-package can *request* a step
(e.g. `reframe.method = "auto_reframe"`) and the *results* ride back in on export; the trigger itself
is manual (or a `commandpost-macro`). Never claim these ran automatically.

## DaVinci Resolve Scripting API (Lane B)

Canonical source: the `README.txt` shipped at `Developer/Scripting/` inside every Resolve install
(no public web reference exists). **External scripting requires Resolve Studio (paid)**; the free
version loads the module but Studio-only calls return False. `preflight.py` detects Studio vs free
and degrades Lane B to Lane A (FCPXML/OTIO file import) when unavailable. Pin Python 3.10 to 3.12
(3.13+ can crash the fusionscript bridge on older builds).

Bootstrap (set by `resolve.py` if absent), per OS, from the README:

- macOS: `RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"`,
  `RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"`,
  add `$RESOLVE_SCRIPT_API/Modules/` to `PYTHONPATH`.
- Windows: `%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting`,
  `C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll`, `...\Modules\` on `PYTHONPATH`.
- Linux: `/opt/resolve/Developer/Scripting` (some packages `/home/resolve`),
  `/opt/resolve/libs/Fusion/fusionscript.so`, `Modules/` on `PYTHONPATH`.

Then `import DaVinciResolveScript as dvr; resolve = dvr.scriptapp("Resolve")` (Resolve must be
running). Object model: `Resolve → ProjectManager → Project → MediaPool/MediaStorage → Timeline →
TimelineItem`, plus the render queue on `Project`.

Operations `resolve.py` exposes (all gated behind `video_editing_enabled` + `resolve_scripting`):

- Import an edit-package: `MediaPool.ImportTimelineFromFile(fcpxml_or_otio, {timelineName})`
  (Resolve imports AAF/EDL/FCP7-XML/FCPXML/DRT/OTIO), or `CreateEmptyTimeline` +
  `CreateTimelineFromClips`.
- Markers: `Timeline.AddMarker(frameId, color, name, note, duration, customData)`.
- Captions from audio: `Timeline.CreateSubtitlesFromAudio()` (Resolve 18.5+).
- Render: `Project.AddRenderJob()` + `SetRenderSettings()` + `LoadRenderPreset()`,
  `Project.StartRendering()`, poll `GetRenderJobStatus()` — feature 5's cross-OS realization.
- Export back to the neutral core: `Timeline.Export(path, resolve.EXPORT_FCPXML_1_10)` or
  `EXPORT_OTIO`.

## OpenTimelineIO (OTIO)

Optional neutral-core enhancement (`pip install OpenTimelineIO OpenTimelineIO-Plugins` +
`otio-fcpx-xml-adapter`). Since OTIO 0.17 adapters are a separate package. The FCPXML adapter
round-trips single/multiple tracks, audio, gaps, markers, nesting, but NOT transitions, effects,
multicam, or fancy speed changes. When OTIO is absent, `otio_core.py` degrades to the edit-package +
`fcpxml.py` serialization (no OTIO dependency required for the core round-trip).

## Scoop storage + offline ↔ online handoff

- `pipeline/editing/`: committed null-schema templates (`edit-package.template.json`,
  `render-manifest.template.json`) + gitignored artifacts (`edit-package.local.json`, generated
  `*.fcpxmld`/`*.drt`, `markers.local.json`, `render-manifest.local.json`).
- Portable bucket manifest via `tools/sync_editing.py` (mirrors `tools/sync_cache.py` L3): sha256 of
  every edit artifact so an offline machine's outputs can be verified before the online side trusts
  them.
- OUT (online → offline): `edit-timeline-spec` / `chapter-map` / `compressor-preset` write files into
  `pipeline/editing/`, ready for FCP import or Resolve `ImportTimelineFromFile`.
- IN (offline → online): the editor exports FCPXML / marker CSV → `fcpxml-parse` → edit-package → an
  import adapter hands markers/chapters/keywords to `entity-extract`, `geo-optimize`,
  `content-calendar`, and the scheduling queue (modeled on the dashboard `POST /api/import-report`;
  MCP tool `import_edit_artifact`).

## Portability matrix (widest reach)

- Spec generation (all features' "WHAT"): every AI engine, offline, any OS — it is text.
- FCPXML/OTIO build + parse + Compressor presets: wherever local Python runs; FCP import and
  Compressor are macOS-only; Resolve import/render is Mac/Win/Linux (Studio).
- Live app control: Claude Desktop + local only.

## Canonical sources (with caveats)

- FCPXML Reference / DTD / "Sending Data Programmatically to FCP" (Open Document event) / Bundle
  Reference — developer.apple.com/documentation/professional-video-applications. Exact FCPXML version
  = read the on-disk DTD in the installed editor.
- Captions / Compressor CLI / Motion templates / Workflow Extensions — support.apple.com guides.
- OpenTimelineIO 0.18.x + `otio-fcpx-xml-adapter` (documented limits above) — github.com/AcademySoftwareFoundation/OpenTimelineIO.
- DaVinci Resolve API — the `Developer/Scripting/README.txt` in the install (canonical); Studio-only;
  per-OS env-vars/paths as above; pin Python 3.10 to 3.12.
- FCP has no editing scripting API (definitive) — Apple "Responding to / Sending Apple Events" docs.
