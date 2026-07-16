# Content Import (your past videos + metadata)

Bring your OWN published back catalog into Creator OS, complete the fields the platforms withhold, and
analyze it, entirely on your own computer. This is the `content-library` spoke (P45). Nothing here is
fabricated, nothing leaves your machine, and the importer only proposes; you save what you approve.

See also: `shared/content-import-engine.md` (the spec), `shared/integrations-engine.md` (the API
sections), `shared/transcription-engine.md` (local STT), `docs/PASTE-SAFETY.md` (untrusted text), and
`docs/SETUP_MAC.md` (installing a transcription engine on macOS).

---

## What is available where (and what is not)

Every boundary below is enforced in code (null-and-flag, never estimate).

| Data | YouTube | Instagram | TikTok | Pinterest |
|---|---|---|---|---|
| Video files | Takeout (near-master) | DYI (re-encoded) | data export (processed) | none |
| View / engagement stats | Data + Analytics API | Graph insights | Display API + Studio CSV | v5 Pin analytics |
| Ad / revenue | **Studio CSV only** | ads API | ads/BC CSV | ads API |
| Retention / most-watched | **API** (`audienceWatchRatio`, `relativeRetentionPerformance`) | **none** | **UI-only** (not in API/CSV) | **none** |
| Tags / hashtags | `snippet.tags` (public) | none | none (Display) | none |
| Transcripts | captions API (ASR **undownloadable, 403**) | none -> local STT | none -> local STT | none |

Two load-bearing facts: YouTube `snippet.tags` are **public**, not owner-only; and a solo creator
**cannot** pull revenue from the YouTube Analytics API (monetary metrics are content-owner/CMS only).
Revenue therefore enters only through the YouTube Studio CSV export.

---

## Tiered retrieval (floor first, live API optional)

The connectors evidence ladder is `direct_connector` -> `export_bundle` -> `excerpt_only`
(`shared/connectors/connectors.py`). The always-available floor is your own export bundle (or pasted
stats). The optional live OAuth client (`tools/importers/*`) is gated behind the `content_import_live`
master flag plus a per-platform read flag AND your own credentials, and it builds no monetary URL.

---

## Per-platform export playbooks

### YouTube
- **Google Takeout** (takeout.google.com -> "YouTube and YouTube Music"): your video files and
  metadata. No analytics or retention.
- **YouTube Studio** -> Analytics -> Advanced mode -> Export -> `.zip`: `Table data.csv` carries your
  stats and, if monetized, `Estimated revenue (USD)`. This is the only revenue source.
- Parsed by `tools/import_parse.py` (`parse_youtube_studio_csv` / `parse_youtube_takeout`). <!-- verify: tools/import_parse.py::parse_youtube_takeout --> <!-- verify: tools/import_parse.py::parse_youtube_studio_csv -->

### Instagram
- Accounts Center -> Your information and permissions -> **Download your information** -> your profile,
  JSON format. No analytics, no transcripts, no retention.
- Parsed by `parse_instagram_dyi` (globs `posts_*.json`, `reels.json`).

### TikTok
- Profile -> Settings and privacy -> Account -> **Download your data**. Retention curve is UI-only and
  is never scraped.
- Parsed by `parse_tiktok_dyi` / `parse_tiktok_studio_csv`.

### Pinterest
- Settings -> Privacy and data -> **Request your data**. No retention, no transcript.
- Parsed by `parse_pinterest_export`.

---

## Completing what the export did not send (on-device)

The APIs and exports deliver metadata and stats but withhold the highest-value fields: transcripts,
chapters, spoken keywords, and the meaning behind the YouTube retention curve. Because you downloaded
the actual video files, Creator OS completes each record locally:

- `tools/transcribe.py` selects the machine-correct STT backend (whisper.cpp on Apple Silicon,
  faster-whisper elsewhere) and transcribes on-device (zero cloud, zero tokens). With no backend
  installed it returns the `run_local_stt` gap with the per-OS install command, never a fabricated
  transcript.
- `tools/library_complete.py` matches each downloaded file to its record, drives transcription and
  chapter/keyword derivation, and **joins the YouTube retention curve to the transcript** so each
  most-watched peak and the steepest-drop cliff carry the actual words spoken at that timestamp
  (`elapsed_ratio x duration_s`). Off YouTube, retention is null-flagged and the transcript plus topic
  themes are still delivered.

The easiest path is the guided doctor, which checks your machine, prints the exact next command, and
downloads a checksum-verified model for you (also available in the wizard at **Check my setup**):

```bash
python3 tools/transcribe.py doctor                      # green / amber / red + the next command
python3 tools/transcribe.py doctor --fetch-model base.en   # download + verify one model
```

Then complete the library (`docs/SETUP_MAC.md`, `requirements-transcribe.txt`):

```bash
python3 tools/transcribe.py status                       # backend + selection for this machine
python3 tools/library_complete.py complete --export-dir <unzipped folder>
```

### If something goes wrong (no traceback, just a next step)
- **A download will not open / "not a valid zip":** large platform exports sometimes arrive
  incomplete. Re-download the `.zip` and point Creator OS at the fresh copy; the importer skips an
  unreadable file and tells you rather than stopping.
- **No transcription engine installed:** the library is still built metadata-only, and each transcript
  is flagged `run_local_stt` with the exact per-OS install command, never faked. Run the doctor to fix.
- **A very large TikTok / YouTube / Instagram library:** the live importer stops at a safety page cap
  and reports `truncated: true` (re-run to continue) rather than silently returning a partial library.
- **A transcript with no timestamps** (e.g. a plain-text paste): the retention peaks are still located
  but their words cannot be attached; the completion surfaces a `no_timing` gap. Provide a timed
  transcript (SRT/VTT or whisper JSON) to attach the spoken words.

### Cross-modality / OS reality

This lane is **Class C**: it needs a local runtime AND your files. It runs natively on Claude Desktop
and Claude Code. A hosted connector runs in the vendor's cloud and cannot read your local export
folder, even on the same laptop. Browser-only surfaces re-route: run the tools on your computer, or
upload the export to a sandbox that runs the tools on the copy. Backend selection and the macOS
Python/ffmpeg/Gatekeeper notes are in `docs/SETUP_MAC.md` and the setup wizard's Import screen.

---

## Live-API setup (optional, off by default)

Enable only if you have your own OAuth app and credentials. The master flag is `content_import_live`;
each platform also needs its read flag (`youtube_api`, `youtube_analytics` for retention,
`instagram_api`, `tiktok_api`, `pinterest_api`). Credentials live in the gitignored
`pipeline/user-context/api-credentials.local.json`. The live YouTube importer builds no monetary URL
and skips ASR caption tracks. See `tools/importers/` and the wizard Import screen.

---

## Analyze your library

```bash
python3 tools/video_library.py analyze     # top tags, retention peaks/cliffs with words, format perf, themes
python3 tools/video_library.py status      # what is imported and what still needs completing
python3 tools/video_library.py query "armoire OR wainscoting"
```

Every figure cites the `video_key`s behind it. Retention is YouTube-only; revenue is Studio-CSV-only;
anything a platform does not expose is null-flagged, never estimated.

---

## Privacy and boundaries

All imported data lives only in the gitignored `pipeline/video-library/index.local.db` and `.local`
files; there is no committed summary export. The committed starters
(`pipeline/video-library/*.template.json`) are pure null shape, enforced by drift invariant 34.
Untrusted title/description/transcript text runs through `shared/injection-guard-engine.md`. The
importer proposes; you save. No posting (that is `content-distributor`). No competitor scanning (that
is `competitor-analysis`).
