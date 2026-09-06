# 30. P45 Content Import

- Date: 2026-07-12
- Status: Accepted

## Context

See the decision below; recorded in the build ledger.

## Decision

Built the content-import lane: import, complete, and analyze the creator's OWN past videos + metadata across YouTube/Instagram/TikTok/Pinterest, entirely on the creator's machine, proposal-only. Grounded in verified 2026-07-12 API/CSV/export field shapes (Appendix A of the approved plan). Two corrected premises are load-bearing: YouTube snippet.tags are PUBLIC (not owner-only), and a solo creator CANNOT pull revenue via the YouTube Analytics API (content-owner reports only), so revenue enters ONLY via the YouTube Studio CSV. STORE: tools/video_library.py is a local gitignored SQLite+FTS5 store (upsert by video_key; each stat wrapped in a freshness envelope; retention null off YouTube; no committed summary export) plus a read-only analysis layer (top tags, YouTube retention peaks/cliffs, format performance, transcript themes; every figure cites video_keys; unavailable data null-flagged). PARSERS: tools/import_parse.py reads the four platforms' export bundles (revenue only from the Studio CSV). LIVE TIER: tools/importers/* is a flag-gated OAuth REST client (content_import_live master + per-platform read flag + own creds; injected-getter selftests; the YouTube importer builds no monetary URL and skips ASR captions). COMPLETION: tools/transcribe.py is an OS/backend-aware on-device STT runner (whisper.cpp on Apple Silicon via select_backend, faster-whisper elsewhere; RAM-tiered model floor; run_local_stt gap with the per-OS install when no backend, never a fabricated transcript); tools/library_complete.py matches downloaded media to records, drives per-video completion, and joins the YouTube retention curve to the transcript so each most-watched moment carries the words spoken there (elapsed_ratio x duration_s). SKILLS: video-import, transcript-import, library-complete, library-analyze atoms + the content-library spoke (Class C with the invariant-32 Cross-modality Fallback and per-surface re-route). WIRING: hub routes import_past_videos/analyze_back_catalog/most_watched_parts; MCP video_library_query + video_library_import_status; the wizard /import guided flow with per-OS STT install + macOS Gatekeeper/Python notes. GOVERNANCE: drift invariant 34 (video-library starters are pure null shape), scenario S9 (import Studio CSV + IG DYI -> analyze; most-watched from retention, revenue CSV-only, IG retention null-flagged), docs/CONTENT-IMPORT.md + SETUP_MAC.md STT section + DEPLOYMENT.md matrix rows. Boundaries: retention YouTube-only, revenue Studio-CSV-only, transcripts on-device or uploaded caption (ASR not downloaded, no scraping), all data gitignored, importer proposes and the human saves.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P45-content-import`.
