# Video Editing Bridge (P22)

Plain-English guide to the video-editing integration. Full engine spec:
`shared/videoedit-engine.md`.

## What it does

Creator OS can hand a finished script to your editor as a labeled timeline, and read markers and
chapters back out of your editor for SEO and scheduling. It works with **Final Cut Pro** and
**DaVinci Resolve** because both read the same interchange file (FCPXML), and it never requires an
editor to be installed to be useful.

## The two lanes

- **File interchange (works everywhere).** The system writes/reads FCPXML and OpenTimelineIO files.
  A file works on any operating system, online or offline, with or without an editor. You import the
  file into Final Cut Pro or DaVinci Resolve.
- **Live Resolve control (power path).** On macOS/Windows/Linux the system can drive DaVinci Resolve
  directly (create timelines, add markers, queue renders) through its Python API. This needs
  **Resolve Studio (the paid version)**; the free version cannot be scripted. If Studio is not
  present, the system quietly falls back to the file lane.

Final Cut Pro has no automation API, so FCP is always reached through files, never live scripting.

## The switches (all off by default)

Two master switches plus one per feature. Turn on only what you want; any combination is safe.

- `video_editing_enabled` — master gate for writing editor files / driving apps.
- `resolve_scripting` — the live DaVinci Resolve lane (Studio only).
- `fcpxml_timeline_export`, `caption_roundtrip`, `shorts_reframe`, `marker_intel_import`,
  `compressor_presets`, `motion_template_fill`, `commandpost_macros`, `chapter_sync` — the eight
  features.

With everything off, the system still writes out the *plan* (markers, chapters, captions, export
specs); it just does not touch an app. Each switch has a `*_disabled` note in
`creator-os-config.json` explaining the fallback.

## What runs where

| Capability | Claude Desktop | Claude Projects | GPT API | ChatGPT Web | Gemini |
|---|---|---|---|---|---|
| Edit spec generation (markers, chapters, captions, presets) | Yes | Yes | Yes | Yes | Yes |
| Build/parse FCPXML + OTIO files | Yes (local) | No | No | No | No |
| DaVinci Resolve live control | Yes (local + Studio) | No | No | No | No |
| Compressor export (macOS) | Yes (local + Mac) | No | No | No | No |

"Spec generation" is just text, so it works on every AI engine. Turning specs into files or driving
an app needs the local tools (Claude Desktop + MCP).

## How offline and online stay in sync

Generated files live in `pipeline/editing/` (gitignored). `tools/sync_editing.py` writes a
sha256-verified manifest of them so a copy made offline can be verified before the online side trusts
it. When you export a timeline from your editor, `fcpxml-parse` (or the `import_edit_artifact` MCP
tool) reads it back and hands the chapters to SEO/scheduling and the keywords to entity analysis, the
same way the scheduling dashboard imports a distribution report.

## Try it (once local tools are set up)

- `python3 tools/videoedit/preflight.py` — what can this machine do?
- `python3 tools/videoedit/fcpxml.py build edit-package.json --out timeline.fcpxml` — make a timeline.
- `python3 tools/videoedit/fcpxml.py validate timeline.fcpxml` — check it.
- `python3 tools/videoedit/fcpxml.py parse timeline.fcpxml` — read it back.
- `python3 tools/sync_editing.py --status` — list the edit artifacts.

## Status

Phase 1 delivered the neutral core and the script -> timeline -> parse round-trip (features 1 and 4).
Phase 2 (this release) adds captions (feature 2: transcript <-> SRT/VTT/iTT, via
`tools/videoedit/captions.py` and the `caption-bridge` atom) and chapters (feature 8: one chapter
list fanned out to YouTube timestamps, the geo-optimize outline, and scheduling, via
`tools/videoedit/chapters.py` and the `chapter-map` atom). The live DaVinci Resolve lane (3 render +
markers) and Compressor/Motion/CommandPost (5, 6, 7) follow in later phases; their wiring is already
in place and feature-flagged off.

Try Phase 2 features:
- `python3 tools/videoedit/captions.py to-editor transcript.srt --fmt itt` -- transcript to iTT.
- `python3 tools/videoedit/chapters.py edit-package.json` -- YouTube timestamps + rule flags.
