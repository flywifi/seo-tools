# Open-Source Video Tooling Evaluation (P26)

Status: evaluation only. Nothing in this document changes flags, dependencies, or gap status.
G9 (transcript-to-chapters/cuts) and G10 remain open; the scenario suite's probes still observe
them. This report produces a scored shortlist that a future integration phase can implement.

Companion artifacts:
- `docs/video-tooling-scores.json` — machine-readable scored matrix with per-cell sources.
- `docs/video-tooling-spike-evidence.json` — empirical spike evidence (commands, deltas, hashes).
- `ledger/ledger.json` — shortlist decisions recorded under `decisions[]`.

## Method

The scoring axis is the videoedit engine's two-lane architecture (`shared/videoedit-engine.md`):

- **Lane A (file interchange)**: universal, offline, ungated. A tool fits Lane A when it reads or
  writes edit artifacts (FCPXML, MLT XML, SRT, cut lists) with no app running.
- **Lane B (app driving)**: flag-gated automation of a running application. Every Lane B path must
  degrade to a Lane A artifact when the app or flag is absent.

Any adopted tool must be an optional dependency, runtime-detected (`shutil.which` for binaries,
try-import for wheels), degrading to stdlib behavior — the `otio_core.py` pattern. The integration
bar is the edit-package `timeline.*` contract (markers, chapters, captions, clips, keywords,
titles, reframe, gaps).

Fifteen candidates were assessed: 9 criteria (weights summing to 100), hard gates (headless
operation, no GUI interaction, every maintenance/license cell sourced or marked unverified per
`protocols/no-fabrication.md`), plus time-boxed hands-on spikes for the G9-critical candidates.
Four read-only research agents gathered web evidence (official sites, PyPI/npm/Homebrew registry
JSON, license files); a fifth adversarial agent independently attacked the eight load-bearing
claims before aggregation (3 upheld, 5 refined; refinements are folded into the tool sections
below and flagged as adversarially verified where they changed a conclusion). License scoring distinguishes execution models: GPL invoked as a subprocess
scores 4 (no linking), GPL imported/linked scores 2, non-OSI terms score 0 to 1.

### Ground-truth fixture

Spikes ran against synthetic media generated to match the committed S5 fixture
`skills/creator-core/evals/fixtures/workshop-footage.srt`: 420 seconds, five solid-color scenes
with cuts at 60/150/240/330 s, and sine audio muted exactly at the transcript's three authored
inter-segment gaps (92.0 to 104.5, 210.0 to 218.5, 300.0 to 320.0 s). The transcript fixture and
the media fixture therefore share one ground truth.

### Spike results (detail in `docs/video-tooling-spike-evidence.json`)

| Spike | Candidate | Result |
|---|---|---|
| S-0 | stdlib SRT analysis (control) | PASS — all 3 gaps recovered from the transcript alone, 21 ms, zero deps. The degradation floor. |
| S-1 | ffmpeg 7.0.2 static | PASS with caveat — silences within 0.021 s; scene detection frame-exact on 3 of 4 cuts but blind to the isoluminant red-to-green cut (luma-only scoring, verified empirically) |
| S-2 | auto-editor 29.3.1 | BLOCKED — PyPI wheel is a bootstrap that downloads a compiled binary from GitHub releases; unreachable under this container's network policy. Posture finding recorded. |
| S-3 | PySceneDetect 0.7 | PASS — all 4 cuts frame-exact including the isoluminant one; zero false positives; 41x realtime |
| S-4 | PyAV 18.0.0 | PASS — in-process RMS reproduces silencedetect within one 100 ms window, no ffmpeg binary, 790x realtime |
| S-5 | MoviePy 2.2.1 | PASS — 9:16 center-crop encoded and ffprobe-verified; fully self-contained (imageio-ffmpeg bundles its own ffmpeg) |
| S-6 | OTIO 0.18.1 + adapters | PASS — core ships no format adapters (plugin split confirmed); the dormant fcpx_xml plugin still reads our FCPXML 1.10 output |

---

## Group A — probe, analysis, cut detection (G9 core)

### 1. FFmpeg / ffprobe (recommended G9 silence backbone)

- Install: `brew install ffmpeg` on macOS (8.1.2); static single-binary builds for CI/containers.
  Detection: `shutil.which("ffmpeg")`.
- Backend: self-contained CLI; six release branches concurrently maintained (8.1.2, 8.0.3, 7.1.5,
  7.0.3, 6.1.6, 5.1.10 all updated mid-2026).
- Automation surface: `silencedetect` (unstructured stderr, regex parsing required), `scdet` /
  `select='gt(scene,t)'` scene scoring, ffprobe with clean `-print_format json`.
- License: LGPL-2.1-or-later by default; GPL when built with `--enable-gpl` (the Homebrew bottle is
  a GPL build). Subprocess invocation keeps the repo unencumbered either way.
- Maintenance: exemplary; large community, corporate backing.
- Edit-package fit: silence and scene events map to `clips[]` boundaries and `markers[]`; ffprobe
  fills duration/fps for `timeline` headers.
- Measured caveat (S-1, adversarially source-verified): for YUV inputs (the default decode path)
  both `select`-scene and `scdet` compute SAD on the luma plane only (`nb_planes = is_yuv ? 1 :
  all`, per f_select.c / vf_scdet.c), so an isoluminant cut scores ~0 — the fixture's red-to-green
  cut was invisible at every threshold. The filters do score all planes for RGB formats, so
  inserting `format=rgb24` before the filter detects such cuts at extra decode cost. A
  default-configuration blind spot, not an absolute one.
- When to use: the default media probe and silence detector; the degradation target every other
  media tool falls back to.

### 2. auto-editor (highest-leverage G9 candidate, changed dependency posture)

- Install: `brew install auto-editor` (31.1.0, depends on ffmpeg). The PyPI path is NOT equivalent:
  the 29.3.1 wheel is a 6 KB launcher that downloads a per-platform compiled binary from GitHub
  releases at first run — tag-pinned to the wheel's own version (verified from the bootstrap
  source) but with no hash or signature verification — and PyPI lags two major versions behind.
- Backend: core rewritten in Nim (GitHub language bar 99.8% Nim); distributed as a single binary.
  Treat its posture as ffmpeg-like (binary + `shutil.which`), not as a Python import.
- Automation surface: headless CLI; edit methods audio loudness/motion/expressions; exports
  premiere, resolve, final-cut-pro, shotcut, kdenlive, clip-sequence.
- License: Unlicense (public domain), verified in the wheel's LICENSE file, PyPI metadata, GitHub,
  and Homebrew.
- Maintenance: solo lead (WyattBlue), very fast release cadence (10 releases May to June 2026) —
  active but with CLI-churn and bus-factor risk.
- Edit-package fit: potentially the single best bridge — it emits the exact formats Lane A speaks.
  Its FCPXML output parsing through `tools/videoedit/fcpxml.py` could NOT be exercised in this
  container (S-2 blocked) and is the number one open validation item before adoption.
- When to use: silence-cut lists and rough-cut FCPXML/MLT generation, once the round-trip is
  validated on a machine with brew or direct binary access.

### 3. PySceneDetect (recommended G9 scene/chapter detector)

- Install: `pip install scenedetect opencv-python-headless` (or the PyAV backend). Pure wheels.
- Backend: Python over OpenCV/PyAV/MoviePy; detectors ContentDetector, AdaptiveDetector,
  ThresholdDetector, HistogramDetector, HashDetector.
- Automation surface: three-line Python API (S-3) plus a CLI; scene list maps directly to
  `chapters[]`.
- License: BSD-3-Clause (PyPI metadata).
- Maintenance: solo lead (Brandon Castellano), steady 2 to 4 releases/year; 0.7 (2026-05-03) is an
  explicitly breaking release two months old — pin carefully.
- Measured result (S-3): all four fixture cuts frame-exact with zero false positives, including the
  isoluminant cut ffmpeg missed (HSV-based scoring). 41x realtime.
- When to use: chapter/scene detection wherever visual accuracy matters more than raw speed.

### 4. PyAV (the no-binary degradation path)

- Install: `pip install av`. Wheels statically bundle FFmpeg (18.0.0 bundles FFmpeg 8.1.2); macOS
  arm64 and x86_64 wheels published. No system ffmpeg needed.
- Backend: Cython bindings to libav*; in-process decode, filter graphs, hwaccel encode.
- Automation surface: library API only. You write the DSP: the S-4 spike reproduced silencedetect
  with ~30 lines of numpy in 0.53 s for 420 s of audio (faster than the ffmpeg binary for
  audio-only work).
- License: BSD-3-Clause.
- Maintenance: PyAV-Org, very active (17 releases in 24 months); aggressive major-version cadence
  tracking FFmpeg. Note: the active lead is also auto-editor's author (shared bus factor).
- Edit-package fit: enabler rather than feature — powers silence/scene analysis where no binary can
  be shipped, and serves as a PySceneDetect backend.
- When to use: environments where a Python wheel is acceptable but a downloaded binary is not.

Staleness note: `ffmpeg-python` (kkroening) last released 0.2.0 on 2019-07-06 — seven years stale;
excluded. Use subprocess + ffprobe JSON directly.

## Group B — interchange and formats (Lane A extensions)

### 5. MLT framework + melt

- Install: `brew install mlt` (7.40.0) — heavy dependency tree (ffmpeg, Qt, OpenCV, frei0r, sox...).
- Backend: the engine under Shotcut and Kdenlive; Meltytech/Dan Dennedy; steady bimonthly releases.
- Automation surface: `melt project.mlt -consumer avformat:out.mp4` renders headlessly; officially
  self-described as a test tool; headless Linux use may need xvfb (Qt linkage).
- License: LGPL-2.1 core (COPYING); GitHub license detection flags additional GPL files; module
  split unverified. Subprocess use only.
- Edit-package fit: MLT XML is the shared substrate of Shotcut (.mlt native) and Kdenlive
  (.kdenlive is MLT XML with app extensions), and it is plain XML writable from stdlib — a natural
  second Lane A emitter next to FCPXML, giving free-editor users what FCPXML gives Alex.
- When to use: emit MLT XML for Shotcut/Kdenlive handoff; render via melt only where the brew tree
  is acceptable.

### 6. OpenTimelineIO (already the repo's optional dep — position confirmed)

- Install: `pip install opentimelineio` (0.18.1); format adapters are now separate plugin packages
  (S-6 verified: core ships only otio_json/otiod/otioz).
- Adapter ecosystem: AAF 2.0.0 (2025-11, actively maintained), ALE 1.1.0 (2025-12); FCPXML
  (`otio-fcpx-xml-adapter` 1.0.0), FCP7 XML, CMX3600 EDL all release-dormant since 2023-07 (the
  FCPXML adapter's repo saw compatibility commits until 2024-06); kdenlive adapter 0.0.3 (2026-01)
  immature with placeholder metadata. A maintained third-party alternative exists:
  `otio-fcpx-xml-lite-adapter` (0.2.3, 2025-06), covering basic FCPXML read/write only.
- License: Apache-2.0. Governance: Academy Software Foundation; core cadence ~1 release/year.
- Measured result (S-6): the dormant fcpx_xml adapter still reads our generated FCPXML 1.10.
- When to use: keep as the optional interchange hub; do not assume core can read FCPXML without the
  plugin. Documentation in `docs/VIDEO_EDITING.md` should mention the plugin split at integration
  time.

### 7. LosslessCut (companion tool, fails the headless gate)

- GPL-2.0 Electron GUI; 3.69.0 (2026-06). Its automation (CLI flags, HTTP API on port 8080) drives
  a RUNNING GUI instance — remote control, not headless. Cut lists import via CSV
  (start,end,label); project format .llc is JSON5.
- Position: not scoreable as an automation dependency. Worth one line in creator-facing docs as a
  manual companion: our pipeline can emit its CSV cut-list format for creators who use it by hand.

## Group C — programmatic composition and render

### 8. MoviePy v2 (recommended shorts_reframe backend)

- Install: `pip install moviepy` (2.2.1) — fully self-contained; imageio-ffmpeg wheels bundle a
  static ffmpeg (verified in S-5).
- Automation surface: the cleanest pure-Python composition API. v2 broke v1 names (subclipped,
  cropped, resized, with_*; moviepy.editor removed) — v1 tutorials are stale.
- License: MIT. Maintenance: revived in Nov 2024 by a new maintainer group alongside Zulko; six
  releases in the revival window, then quiet — no release since 2025-05 and no master commits
  since 2025-09 (adversarially verified). Pin and watch.
- Measured result (S-5): 9:16 center-crop of the fixture encoded and ffprobe-verified in 2.26 s for
  a 20 s clip.
- When to use: mechanical reframe crops, trims, and simple title/branding renders where FCP is not
  in the loop.

### 9. Blender VSE headless (documented, not shortlisted)

- GPL-2.0-or-later; Blender Foundation cadence is rock-solid (5.1 current, 4.5 LTS to 2027).
  `blender --background --python` drives the VSE; the 4.4 API renamed Sequence types to Strip,
  breaking older scripts. Hundreds of MB, slow startup, bundled Python (not our venv). Verdict:
  capability exists but the weight/benefit ratio loses to MoviePy + ffmpeg for shorts-style work.

### 10. Remotion (excluded on license)

- Verified from LICENSE.md: source-available, NOT open source. Free tier covers individuals,
  for-profit orgs up to 3 employees, non-profits, evaluation; larger companies require a paid
  license. Extremely active (295 npm versions in 24 months, 4.0.484 current) and technically
  excellent, but a Node/React/Chromium stack with per-company licensing has no place as a Creator
  OS dependency. Excluded from recommendation regardless of score.

### 11. Revideo (dormant, do not adopt)

- MIT fork of Motion Canvas; zero npm publishes since 2025-04-20. The sponsoring company pivoted to
  the commercial Midrender product and states engine improvements are not being upstreamed. The
  repo still receives occasional maintenance commits (deps/docs as of 2026-07), so it is
  release-dormant rather than abandoned — but nothing consumable has shipped in 14 months.

### 12. editly (stalled)

- MIT, solo-maintained; last stable 0.14.2 (2022-12); a lone 0.15.0 release candidate (2025-01)
  never promoted. Effectively stalled; do not build on it.

### 13. GStreamer + GES (documented for completeness)

- LGPL, institutionally healthy (1.28.4, 2026-06), genuinely headless (`ges-launch-1.0`,
  PyGObject). But: enormous brew tree, second-tier macOS support, sparse editing-API documentation.
  Right choice only for LGPL-purity, long-horizon platform work; wrong fit for this repo's
  Python-first macOS-target posture.

## Group D — desktop editor automation surfaces

### 14. Kdenlive and 15. Shotcut (two-lane thesis confirmed)

- Kdenlive: GPL-3.0, KDE release train (26.04.3 current), official macOS dmg (macOS 13+, brew
  cask). No scripting API and no documented DBus automation; the documented automation path is the
  project file plus a generated MLT render script executed by melt.
- Shotcut: GPL-3.0, Meltytech (26.06 current, monthly cadence, brew cask). CLI options are GUI
  startup flags only — no export/render/batch flag; the developer-documented CLI export path is
  melt on the .mlt project file.
- Consequence: for both editors the .kdenlive/.mlt project FILE is the edit-automation surface,
  which is exactly Lane A. There is no Lane B to build for these apps; "support Kdenlive/Shotcut"
  means "emit correct MLT XML", plus optional melt rendering. Two verified nuances: Shotcut does
  have an official QML plugin API, but it adds custom filters/UI, not edit automation; and the
  Kdenlive D-Bus scripting projects circulating on PyPI require a patched Kdenlive build — their
  existence confirms stock Kdenlive exposes none.

## Scored matrix (summary)

Weighted totals (0 to 100) computed from `docs/video-tooling-scores.json`; recompute with
`python3 -c` per the verification section there. Hard-gate failures are unranked.

| Rank | Candidate | Total | Verdict |
|---|---|---|---|
| 1 | PySceneDetect | 90.4 | shortlist: G9 scene/chapters |
| 2 | FFmpeg/ffprobe | 89.2 | shortlist: G9 silence + probe backbone |
| 3 (tie) | auto-editor | 81.6 | conditional shortlist: pending FCPXML round-trip validation |
| 3 (tie) | PyAV | 81.6 | shortlist: no-binary degradation path |
| 5 | OpenTimelineIO | 79.0 | hold position: optional interchange hub |
| 6 | MoviePy v2 | 73.4 | shortlist: shorts_reframe mechanical half |
| 7 | MLT/melt | 65.2 | Lane A emitter target; render optional |
| 8 | Shotcut (via MLT XML) | 62.0 | interchange target, not a dependency |
| 9 | Kdenlive (via MLT XML) | 56.4 | interchange target, not a dependency |
| 10 | Blender VSE | 50.0 | documented only |
| 11 | GStreamer GES | 48.4 | documented only |
| 12 | Remotion | 47.8 | excluded (non-OSI license) |
| 13 | Revideo | 40.8 | release-dormant |
| 14 | editly | 38.4 | stalled |
| gate fail | LosslessCut | 44.0 | manual companion only (not headless) |

## Recommendations per feature slot

### G9 — silence/cut detection
- Top pick: **ffmpeg silencedetect** (subprocess, regex parse, S-1 accuracy 0.021 s).
- Runner-up: **PyAV windowed RMS** (S-4) where no binary can be shipped.
- Degradation chain: ffmpeg -> PyAV -> S-0 stdlib SRT gap analysis (no media needed).
- Integration sketch: a `silence-scan` atom shells `ffmpeg -af silencedetect`, parses stderr into
  edit-package `clips[]`/`markers[]`, falls back to PyAV try-import, then to transcript gaps.

### G9 — scene/chapter detection
- Top pick: **PySceneDetect ContentDetector** (S-3: frame-exact, catches isoluminant cuts).
- Runner-up: **ffmpeg scdet** (faster, luma-blind; acceptable for talking-head footage).
- Degradation chain: PySceneDetect -> ffmpeg scdet -> S-0 transcript topic-shift heuristics.
- Integration sketch: a `scene-scan` atom try-imports scenedetect, maps scene list to
  `chapters[]`, else shells ffmpeg scdet, else derives chapter candidates from transcript pauses
  plus keyword shifts (the existing chapter-map atom's logic).

### shorts_reframe (currently flagged off)
- Top pick: **MoviePy v2** for crop/trim/encode (S-5); **ffmpeg crop filter** as the one-liner
  runner-up.
- Degradation chain: MoviePy -> ffmpeg -> emit reframe crop parameters into the edit package
  without rendering (FCP does the crop).
- Integration sketch: extend the reframe atom to compute crop geometry (already pure math), then
  optionally render via MoviePy when `pip install moviepy` is present; never a required dep.

### render/export (currently flagged off)
- Top pick: **MLT XML emission** (stdlib-writable) so Shotcut/Kdenlive users get native projects;
  optional **melt** render behind the existing flag; **ffmpeg** direct encode for simple cut lists.
- Degradation chain: melt render -> ffmpeg encode -> no render (hand FCPXML/MLT XML to the human
  editor; the current shipped behavior).
- Integration sketch: an `mlt-writer` sibling to `fcpxml.py` implementing the same edit-package
  contract; auto-editor (once round-trip-validated) can generate both formats from raw media.

## Rejected or dormant (evidence in scores JSON)

| Tool | Status | Evidence date |
|---|---|---|
| ffmpeg-python | dormant 7 years (0.2.0, 2019-07-06) | PyPI 2026-07-02 |
| editly | stalled (0.14.2 2022-12; RC abandoned 2025-01) | npm 2026-07-02 |
| Revideo | dormant; company pivoted to Midrender | npm + midrender.com 2026-07-02 |
| Olive | hiatus ("Olive will return"); last stable 2019 | olivevideoeditor.org 2026-07-02 |
| ffmpeg-concat | dead (1.3.0, 2022-10) | npm 2026-07-02 |
| OpenShot | maintained (3.5.1, 2026-04) but libopenshot's Python surface has a documented segfault record; keep pruned | openshot.org + issue tracker 2026-07-02 |
| Remotion | non-OSI license (verified from LICENSE.md) | remotion.dev 2026-07-02 |
| whisper/aeneas/ffsubsync/jiwer | already evaluated in `shared/transcription-engine.md`; interop unchanged | n/a |

## Open validation items for the integration phase

1. auto-editor FCPXML output parsed by `tools/videoedit/fcpxml.py` (S-2 was network-blocked).
2. OTIO kdenlive adapter 0.0.3 against a real .kdenlive file.
3. melt headless render on macOS without a display session.
4. PySceneDetect 0.7 API stability (breaking release, two months old) before pinning.
5. MoviePy text/compositing path (S-5 covered crop/encode only).
