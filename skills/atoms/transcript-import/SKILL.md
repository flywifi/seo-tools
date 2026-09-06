---
name: transcript-import
atom: true
standalone: true
description: "produces the transcript for ONE of the creator's own videos and attaches it to that video's record, using a creator-uploaded YouTube caption track when one exists, otherwise local on-device speech-to-text on the video file the creator already downloaded; it never fabricates spoken content and never scrapes a platform. Triggers: 'transcribe this video', 'get the transcript for my video', 'add captions text to my library record'. Do NOT use to import stats/metadata (use video-import), to download auto-generated YouTube captions (ASR tracks are not downloadable, 403), to transcribe a file the creator does not have locally (there is nothing to run STT on), or to write the store directly (it proposes the transcript; the human saves it)."
engines_required:
  - shared/transcription-engine.md
  - shared/content-import-engine.md
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# transcript-import

The one field the platforms most consistently withhold, produced honestly and locally. If the creator
uploaded a real caption track to YouTube, use it. Otherwise run speech-to-text on the video file the
creator already downloaded, entirely on their machine. Never guess spoken content, never scrape.

## When to use this skill
- "transcribe my video", "get the transcript for this one", "add the caption text to my library
  record", keyed to a `video_key` already in the video library.

Do NOT use for:
- Importing stats, tags, or metadata (use `video-import`).
- Downloading YouTube auto-generated (ASR) captions: those are effectively not downloadable (403). A
  creator-uploaded track can be downloaded; an ASR-only video must go through local STT instead.
- Transcribing a video whose file the creator does not have locally. STT needs the file; if it is not
  present, return the `run_local_stt` gap and tell the creator to download it first (or, for YouTube,
  to check for an uploaded caption track).
- Writing the store. It proposes the transcript; the human saves it via `video-import` or
  `python3 tools/video_library.py`.

## Inputs
```json
{
  "video_key": "the record to attach the transcript to, e.g. youtube:abc123",
  "media_path": "absolute path to the downloaded video/audio file, or null",
  "caption_track": "a creator-uploaded caption file (srt/vtt), or null",
  "model": "STT model tier, or null (chosen by the runner from the machine's RAM)"
}
```

## Core procedure
Follow `shared/method.md` and `shared/transcription-engine.md`.

1. **Prefer a real caption track.** If `caption_track` is present (a creator-uploaded YouTube SRT/VTT,
   never an ASR track), parse it with `shared/docintel/transcripts.py` into the normalized segment
   array. Done.
2. **Otherwise run local STT.** With `media_path`, run on-device speech-to-text (zero cloud, zero
   tokens; see `shared/transcription-engine.md`). The runner picks the backend for the machine
   (whisper.cpp on Apple Silicon, faster-whisper elsewhere) and seeds a niche-vocabulary prompt from
   `shared/brand-engine.md` plus the video's tags/title to lift accuracy. Output is normalized through
   `shared/docintel/transcripts.py`.
3. **If no backend is installed or no file is available**, return the `run_local_stt` gap with the
   exact per-OS install command. Never fabricate a transcript.
4. **Propose**, do not save. The transcript text and its provenance are returned for the human to attach
   to the `video_key`.

## Output contract
```json
{
  "video_key": "youtube:abc123",
  "transcript_text": "normalized plain transcript, or null",
  "segments": [{"index": 1, "start_ms": 0, "end_ms": 4200, "text": "..."}],
  "source": "uploaded_caption | local_stt",
  "backend": "whisper.cpp | faster-whisper | caption-parse | null",
  "gap": "run_local_stt or null, with the per-OS install command when null-transcript",
  "save_note": "Confirm before saving. Nothing is written automatically; you attach this to your library record yourself. The audio and transcript never leave your machine.",
  "human_review_required": true
}
```

## Standalone usability
A downloaded file (or an uploaded caption) in, one normalized transcript out, with an honest gap when
no backend or file is available, even with no downstream skill.

## Failure modes
- ASR-only YouTube video: the caption download is 403; fall back to local STT on the file, or flag the
  gap. Never present a fabricated transcript.
- No STT backend installed: return the `run_local_stt` gap with the install command; never guess.
- Zero-duration or corrupt file: reported as a gap, not transcribed.

## Cross-modality
Class C (needs a local runtime and the creator's file). On a browser-only surface it re-routes: "run
this transcription on your computer," or use a creator-uploaded YouTube caption where one exists. See
`shared/content-import-engine.md` and `shared/cross-modality-engine.md`.
