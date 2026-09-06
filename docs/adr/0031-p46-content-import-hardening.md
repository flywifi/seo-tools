# 31. P46 Content Import Hardening

- Date: 2026-07-13
- Status: Accepted

## Context

See the decision below; recorded in the build ledger.

## Decision

Hardened the P45 content-import lane and added a non-technical onboarding layer after a read-only stress test (simulated MacBook Pro on Claude web/Cowork/Desktop) surfaced 9 defects concentrated in the live importers and the export-ZIP parser. Fixes, each grounded in cited platform behavior: (1) TikTok create_time coerced via _epoch_to_iso (int64 epoch-seconds per the Video Object ref) so a malformed field never aborts the batch; (2+3) YouTube/Instagram/TikTok pagination bounded by a max_pages backstop returning a truncated sentinel instead of a silent partial library, with Instagram terminating on the documented paging.next absence (not the after cursor, which can persist on the final page) and the URL pinned to v25.0; (4) import_parse opens every zip via _safe_zip catching OSError AND zipfile.BadZipFile (verified NOT an OSError subclass) so a corrupt export degrades to []; (5+6) video_library CLI returns a clean JSON error + nonzero exit on malformed upsert/FTS input; (7) derive_most_watched returns [] on a flat retention curve instead of labeling the whole video a peak; (8) library_complete joins whisper-JSON/SRT transcripts to retention and flags an untimed transcript with a no_timing gap; (9) complete --write reports honest per-field write counts. Non-technical layer: tools/transcribe.py doctor gives a green/amber/red readiness verdict + the exact next command per OS, and --fetch-model streams a whisper.cpp GGML model (stdlib urllib, env proxy + CA bundle) verified against a committed sha256 allowlist (canonical-sources/whisper-models.json, captured from Hugging Face git-LFS object ids since whisper.cpp publishes no manifest); the wizard adds a /doctor screen with one-click verified model downloads + corrupt-export recovery copy; docs/SETUP_MAC.md gains doctor + Windows (SmartScreen, Add-to-PATH, faster-whisper, prebuilt whisper.cpp) sections. Drift invariant 35 (check_importer_robustness) AST-checks that the defect class cannot regress: no unbounded while-True pagination, every zipfile.ZipFile inside a try, create_time fromtimestamp inside a try, and a truncation signal preserved.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P46-content-import-hardening`.
