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
  original features.
- `mlt_timeline_export` (feature 9) — emit the timeline as MLT XML, Shotcut's native project
  format and the Kdenlive substrate. `media_render` (feature 10) — render an .mlt or cut list
  locally via melt or ffmpeg; app-driving tier, so it also needs `video_editing_enabled`.

Silence and scene detection (P29) have no switch at all: they are local read-only analysis whose
availability is just which tools are installed (see `requirements-videoedit.txt`), degrading to
the transcript floor.

With everything off, the system still writes out the *plan* (markers, chapters, captions, export
specs); it just does not touch an app. Each switch has a `*_disabled` note in
`creator-os-config.json` explaining the fallback.

## What runs where

| Capability | Claude Desktop | Claude Projects | GPT API | ChatGPT Web | Gemini |
|---|---|---|---|---|---|
| Edit spec generation (markers, chapters, captions, presets) | Yes | Yes | Yes | Yes | Yes |
| Build/parse FCPXML + OTIO files | Yes (local) | No | No | No | No |
| Build/parse MLT XML (Shotcut/Kdenlive) | Yes (local) | No | No | No | No |
| Silence/scene detection over raw media | Yes (local; degrades to transcript floor) | Transcript floor only | Transcript floor only | Transcript floor only | Transcript floor only |
| Shorts crop geometry | Yes | Yes | Yes | Yes | Yes |
| Shorts local render (MoviePy/ffmpeg) | Yes (local + flag) | No | No | No | No |
| DaVinci Resolve live control | Yes (local + Studio) | No | No | No | No |
| Compressor export (macOS) | Yes (local + Mac) | No | No | No | No |
| melt render of .mlt | Yes (local + flags) | No | No | No | No |

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
- `python3 tools/videoedit/mediaprobe.py silence --media raw.mp4` — find the dead air (or
  `--transcript captions.srt` with no media tools installed).
- `python3 tools/videoedit/mediaprobe.py scenes --media raw.mp4` — find the scene cuts.
- `python3 tools/videoedit/reframe.py geometry --width 1920 --height 1080` — the 9:16 crop.
- `python3 tools/videoedit/mltxml.py build edit-package.json > timeline.mlt` — a Shotcut project.
- `python3 tools/videoedit/mltxml.py validate timeline.mlt` — check it.
- `python3 tools/sync_editing.py --status` — list the edit artifacts.

## Status

Phase 1 delivered the neutral core and the script -> timeline -> parse round-trip (features 1 and 4).
Phase 2 added captions (feature 2: transcript <-> SRT/VTT/iTT, via
`tools/videoedit/captions.py` and the `caption-bridge` atom) and chapters (feature 8: one chapter
list fanned out to YouTube timestamps, the geo-optimize outline, and scheduling, via
`tools/videoedit/chapters.py` and the `chapter-map` atom).
Phase 3 (P29, this release) integrates the P26 media-tool shortlist as optional, runtime-detected
backends: silence and scene detection (`tools/videoedit/mediaprobe.py`, atoms `silence-scan` and
`scene-scan`, degrading to the P28 transcript floor), shorts reframe geometry plus optional
MoviePy/ffmpeg render (`tools/videoedit/reframe.py`, atom `shorts-reframe`, feature 3), and MLT
XML as the second Lane A format with a gated melt/ffmpeg render path
(`tools/videoedit/mltxml.py`, features 9 and 10). Nothing became a required dependency; every
path degrades honestly and labels its backend. The melt render path is implemented but not yet
exercised on any machine (no melt was available in the build environment; macOS headless melt is
likewise unverified). OTIO note: since 0.18, the FCPXML and Kdenlive adapters are separate pip
plugins (`otio-fcpx-xml-adapter`, `otio-kdenlive-adapter`), not part of the core package. The
live DaVinci Resolve lane and Compressor/Motion/CommandPost (5, 6, 7) remain feature-flagged off
with wiring in place.

Try Phase 2 features:
- `python3 tools/videoedit/captions.py to-editor transcript.srt --fmt itt` -- transcript to iTT.
- `python3 tools/videoedit/chapters.py edit-package.json` -- YouTube timestamps + rule flags.
