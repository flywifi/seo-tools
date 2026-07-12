---
file: shared/content-import-engine.md
role: >
  How Creator OS imports a creator's OWN past videos and their metadata (stats, ad/revenue,
  audience retention, tags, transcripts) from YouTube, Instagram, TikTok, and Pinterest, and how it
  completes the fields the platforms withhold by running the local media stack on the downloaded
  files. Defines the per-platform availability reality, the tiered retrieval model, the owner
  self-export playbooks, the local-completion (STT) path, and the hard honesty boundaries.
  Live publishing is out of scope (that is the write side, tools/publishing/).
load: on-demand, when a creator wants to import or analyze their back catalog
---

# Content Import Engine

An established creator's back catalog is the richest first-party signal they have: what they titled,
tagged, and said, what was watched and where attention dropped, what earned. This engine brings that
home, honestly. It never fabricates a number the platform did not return, it keeps every imported
value in a gitignored local store with provenance, and it completes the missing pieces (above all,
transcripts) by running the offline media stack on the creator's own downloaded files.

## The reality this engine is built around (verified 2026-07-12)

Availability is wildly uneven by platform and by data type. Two facts correct common assumptions and
are load-bearing for the whole design:

1. **YouTube video tags are public.** `videos.list?part=snippet` returns `snippet.tags` to any caller
   for a public video. Tags are not owner-only. (Only `statistics.dislikeCount`, `fileDetails`,
   `processingDetails`, and `suggestions` are restricted to the authenticated owner.)
2. **A solo creator cannot pull ad/revenue via the YouTube Analytics API.** Estimated-revenue and
   ad-performance metrics are supported only in content-owner (CMS / multi-channel-network) reports,
   not channel reports, and the `yt-analytics-monetary.readonly` scope does not grant monetary data in
   channel reports. A standalone YouTube Partner Program creator gets revenue **only** from the
   YouTube Studio manual CSV export. Creator OS therefore never builds a live-revenue API call.

### Availability matrix

| Data type | YouTube | Instagram | TikTok | Pinterest |
|---|---|---|---|---|
| Video files | Google Takeout (near-original master) | "Download Your Information" (re-encoded copy) | "Download your data" (processed copy) | none |
| View / engagement stats | Data API + Analytics API | Graph API media insights | Display API + Studio CSV | API v5 Pin analytics |
| Ad / revenue stats | **Studio CSV export only** | ads API (separate) | ads / Business Center CSV | ads API |
| Most-watched parts / retention | **API** (`audienceWatchRatio`, `relativeRetentionPerformance`) | **none** (only `reels_skip_rate` + avg watch time) | **in-app UI only** (not in export or creator API) | **none** |
| Tags / hashtags | `snippet.tags` (public) | none as analytics | Display API: none | none |
| Transcripts | captions API for creator-uploaded tracks; **auto (ASR) captions are effectively undownloadable (403)** | none first-party, run local STT | none first-party, run local STT | none |

The single highest-value field, the transcript, is the one the platforms most consistently withhold.
That is what the completion path (below) exists to solve.

## Tiered retrieval (mapped to the connectors evidence-mode ladder)

`shared/connectors/connectors.json` already defines the ladder; this engine uses it verbatim, and
every imported field records which rung produced it (its `source_mode`):

1. **`direct_connector`** (optional, flag-gated, default off): the live REST importers in
   `tools/importers/`, behind the per-platform read flag plus the `content_import_live` master flag,
   using the creator's own OAuth credentials. Best freshness, most setup.
2. **`export_bundle`**: the creator runs a platform export (Takeout / Studio CSV / DYI /
   data-export), and Creator OS parses it (`tools/import_parse.py`) via `ingest-route`. No API keys.
   This is the recommended default for a non-technical creator.
3. **`excerpt_only`**: pasted stats, tags, or a transcript fragment. The floor. Sentence-level
   provenance, missing fields flagged.
4. **`internal_context_only` / `hybrid_reconciliation`**: reconcile across partial sources, surface
   conflicts, never imply retrieval that did not happen.

The importer degrades down this ladder and never presents a lower rung as a higher one.

## Owner self-export playbooks (the export_bundle tier, for a non-technical creator)

Every step below is done by the creator in their own account; Creator OS only reads the resulting
files locally.

- **YouTube, metadata + your video files:** Google Takeout (takeout.google.com), select "YouTube and
  YouTube Music". Yields `video metadata/` (your uploaded files + a metadata file), `playlists/*.csv`,
  `subscriptions/subscriptions.csv`, and history JSON. Takeout contains **no** analytics, views,
  watch-time, or retention. (support.google.com/accounts/answer/3024190)
- **YouTube, stats + retention + revenue:** YouTube Studio to Analytics to **Advanced Mode**, pick the
  report and date range, then Export to CSV or Google Sheets. The .zip holds `Table data.csv` (one row
  per video), `Chart data.csv`, `Totals.csv`. This is the **only** place a solo creator gets revenue
  columns, and the only manual source of the retention report. Note the roughly 500-row cap; for more,
  use the API. (support.google.com/youtube/answer/9002587)
- **Instagram:** Accounts Center to "Download Your Information", choose **JSON**, select your content
  and a date range. Yields your posted media files plus `posts_*.json` / `reels.json` (caption,
  timestamp, media path). Contains **no** insights and **no** transcripts.
  (help.instagram.com/181231772500920)
- **TikTok:** Settings and privacy to Account to "Download your data", choose JSON or TXT. Yields your
  posted-video list and your files. The per-video CSV in TikTok Studio (Analytics to Download data)
  covers roughly the last 60 days; the retention curve is shown in the app UI only and is not in the
  export. (support.tiktok.com data-request)
- **Pinterest:** Pin analytics come from the API v5 read side; there is no Takeout-equivalent that
  returns your original video-Pin masters.

## Completing what the export withholds: local, on-device transcription

The exports and APIs deliver metadata and stats but withhold transcripts (off-YouTube entirely;
YouTube auto-captions are 403 on download), and with them the spoken keywords, chapters, and the
meaning behind the retention curve. Because the creator has already downloaded the actual video files,
Creator OS completes those fields by running the existing offline media stack
(`shared/transcription-engine.md`, `shared/docintel/transcripts.py`, `tools/videoedit/mediaprobe.py`)
locally:

- **Local speech-to-text**, zero cloud, zero tokens, on the creator's machine (`tools/transcribe.py`).
  No audio or transcript ever leaves the machine. When no STT backend is installed the tool returns
  the `run_local_stt` gap with the exact per-OS install command; it never fabricates a transcript.
- **Chapters and spoken keywords** derived from the transcript (`transcripts.py --suggest-chapters`,
  `parse_text.py` + the scoop cache).
- **The retention-transcript join (YouTube):** each retention point (`elapsed_ratio`) is mapped to the
  transcript segment at `elapsed_ratio x duration_s`, so "which parts were most watched" is answered
  with the actual words at the peak and the line at the steepest drop. This only labels moments the
  transcript actually contains; it never invents them.

STT backend selection is OS-aware (see `shared/cross-modality-engine.md` and the routing summary
below): whisper.cpp (Metal) on Apple Silicon, faster-whisper (CPU or CUDA) elsewhere; faster-whisper
needs no system ffmpeg, the escape hatch when a creator cannot get a downloaded ffmpeg past macOS
Gatekeeper.

## Where this runs, and how it re-routes (Class C)

Importing and transcribing a creator's own files needs a runtime that can reach those files. There are
exactly two ways to get that, and every surface's guidance says which applies:

1. the tools run on the creator's own computer (Claude Desktop with a local MCP server, Claude Code,
   or a local Cowork session), or
2. the creator uploads the files to a sandbox that runs the tools on the copy.

A hosted connector runs in the vendor's cloud and **cannot see files on the creator's laptop, even the
same laptop**. So browser-only surfaces (claude.ai web and mobile, ChatGPT web / custom GPT / Project /
agent, Gemini and Gems) re-route to either "do this step on your computer" or "upload the files to a
machine that runs the tools." This lane is Class C; the spoke states which fallback rung it used and
never presents reasoning as a verified local result. Full per-surface and per-OS matrices live in
`docs/CONTENT-IMPORT.md`.

## Boundaries (no-fabrication, privacy, safety)

- **Revenue** is Studio-CSV-only for a solo creator; the store's `revenue` field stays null unless a
  Studio export is imported. The live importer builds no monetary endpoint.
- **Retention / most-watched-parts** is YouTube-only first-party. Instagram, TikTok, and Pinterest
  records null-and-flag it. TikTok's in-app retention curve is not scraped.
- **Transcripts** are never fabricated. ASR captions are not downloaded (403). Off-YouTube and
  YouTube-ASR-only transcripts come from local STT on a file the creator legitimately downloaded. No
  platform scraping (each platform's Terms prohibit unauthorized automated collection); operate only on
  the creator's own account and their own downloaded files.
- **Every imported value carries provenance** (source_mode + citation + imported_at) and a freshness
  envelope so a stale stat ages and flags rather than being silently trusted.
- **All imported data is local and gitignored** (`pipeline/video-library/`), never committed. Titles,
  descriptions, and transcripts are untrusted content and pass the injection guard
  (`shared/injection-guard-engine.md`).
- **The importer proposes; the human saves.** Nothing is written to the store without human review.

## Sources (observed 2026-07-12)
- YouTube Data API: developers.google.com/youtube/v3/docs/{channels,playlistItems,videos,captions}
- YouTube Analytics API: developers.google.com/youtube/analytics/{channel_reports,content_owner_reports,metrics,reference/reports/query}
- YouTube Studio export: support.google.com/youtube/answer/9002587 ; Takeout: support.google.com/accounts/answer/3024190
- Instagram Graph API: developers.facebook.com/docs/instagram-platform/reference/instagram-media (+ /insights) ; DYI: help.instagram.com/181231772500920
- TikTok Display API: developers.tiktok.com/doc/tiktok-api-v2-video-{list,query,object} ; data request: support.tiktok.com
- Pinterest API v5: developers.pinterest.com/docs/api/v5/pins-analytics + user_account-analytics-top_video_pins (enums per pinterest/api-description v5/openapi.yaml)
Volatile vendor specifics are tagged [NEEDS VERIFICATION] where they were not confirmable first-party
(exact Studio CSV headers and 500-row cap; IG/TikTok data-export filenames and key casing; whisper.cpp
Homebrew-bottle acceleration defaults).
