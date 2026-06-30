---
file: shared/transcription-engine.md
role: Offline-first transcription and captioning pipeline for batch audio/video files. Covers
  local STT library selection, caption format handling, accuracy validation (WER/CER), and
  YouTube-specific caption workflow. Live STT and real-time streaming are out of scope.
  Brand vocabulary and niche-specific terms live in shared/brand-engine.md.
load: on-demand
---

# Transcription Engine

## Design principles

### Offline-first, zero cloud, zero tokens

All speech-to-text work runs on local hardware. Model weights are downloaded once and cached
locally. No audio bytes, transcript text, or caption files leave the machine during STT processing.
No API calls, no cloud endpoints, no token consumption. This keeps costs at zero, keeps creator
content private, and enables batch processing of large video archives without rate limits.

### Model tier guidance

Choose the Whisper model tier based on the use case and available compute time.

| Tier | Model | Best for |
|------|-------|----------|
| 1 | tiny | Fast quality checks, rough draft review, iteration where accuracy is secondary |
| 2 | base | Draft transcripts, early-edit review, speed-sensitive batch jobs |
| 3 | small / medium | Production captions, YouTube uploads, SEO-indexed captions |
| 4 | large-v3 | Accuracy-critical work: broadcast exports, accessibility deliverables, archival |

For Creator OS production caption workflows, default to small or medium unless the content
contains dense niche vocabulary (armoire, patina, wainscoting, decoupage), in which case
prefer large-v3.

### Caption format handling

Three formats are in scope. Each has distinct syntax and use cases.

**SRT (SubRip Text)**
- File extension: `.srt`
- Timestamp format: `HH:MM:SS,mmm` (comma as decimal separator)
- Structure: sequence number, timestamp range, caption text, blank line separator
- Use for: YouTube uploads, most video editors, broadest compatibility
- Note: YouTube indexes SRT caption text for search; creator-uploaded SRT takes priority over
  auto-generated captions

**WebVTT (Web Video Text Tracks)**
- File extension: `.vtt`
- Timestamp format: `HH:MM:SS.mmm` (dot as decimal separator, W3C spec)
- Supports cue metadata (positioning, alignment, region blocks)
- Use for: HTML5 web embeds, web player integrations, web accessibility compliance

**ASS / SSA (Advanced SubStation Alpha)**
- File extension: `.ass` / `.ssa`
- Supports per-cue styling: font, color, position, border, shadow, karaoke timing
- Use for: stylized exports, branded caption overlays, Premiere Pro / DaVinci Resolve imports
- Not required for standard YouTube or web workflows; treat as optional advanced output

### Accuracy validation thresholds

Accuracy is measured as Word Error Rate (WER) and Character Error Rate (CER) against a reference
transcript. The reference is either a golden human-verified transcript or a second-pass large-v3
output used as a proxy reference.

- WER below 0.10 (10 percent): acceptable for most production uses; proceed with light human review
- WER below 0.05 (5 percent): broadcast quality; suitable for accessibility deliverables and
  archival without additional review
- WER at or above 0.10 (10 percent): flag for human review before publishing; re-run with a larger
  model tier if time permits

CER is a secondary signal. Use CER when transcripts contain many compound words, hyphenated
terms, or names where word boundaries are ambiguous.

### Scope boundary

This engine covers batch file-based transcription and caption creation and validation. Live
speech-to-text, real-time caption streaming, and on-the-fly studio monitoring are not in scope.

---

## Offline STT libraries (ranked by production priority)

### 1. faster-whisper (recommended for batch production)

- Backend: CTranslate2, int8 quantized weights
- Performance: fastest on CPU of the three options; also the fastest on CUDA if GPU is available
- Python install: `pip install faster-whisper`
- Model download: automatic on first run, cached to `~/.cache/huggingface/hub/` by default
- Output formats: JSON (with word-level timestamps), SRT, VTT
- License: MIT
- When to use: all standard batch production jobs; the default for Creator OS caption workflows

### 2. whisper.cpp (recommended for no-Python environments)

- Backend: ggml C/C++ inference, no Python dependency
- Binary: tiny (a few MB); builds from source in under five minutes on most systems
- CLI usage: `./main -m models/ggml-medium.bin -f audio.mp3 -osrt -ovtt`
- Model files: GGML format, downloadable from the whisper.cpp repository
- Output formats: SRT, VTT, TXT, JSON, via CLI flags
- License: MIT
- When to use: shell-only environments, scripts that run without a Python runtime, CI pipelines
  where Python dependency weight matters

### 3. openai-whisper (reference implementation)

- Backend: PyTorch
- Performance: slower than faster-whisper (typically 3x to 8x slower on CPU for the same model
  tier)
- Python install: `pip install openai-whisper`
- Output formats: JSON (with segments and word timestamps), SRT, VTT, TXT
- License: MIT
- When to use: debugging, compatibility testing, validating faster-whisper output against the
  reference implementation; not the default for production batch jobs

All three libraries share the same underlying model weights (OpenAI Whisper). Model files are
downloaded once and cached locally. No network access is required after the initial download.

---

## Local scripts

### shared/docintel/transcripts.py

Purpose: parse any SRT, VTT, JSON (Whisper output), or plain text transcript into a normalized
segment list; emit SRT, VTT, or plain text.

Normalized segment schema:
```json
{
  "index": 1,
  "start_ms": 0,
  "end_ms": 4200,
  "text": "Today we are painting this armoire."
}
```

Usage pattern: run locally against the raw Whisper output file; pass the compact JSON segment
array to the model. The model never sees raw audio bytes or unprocessed transcript blobs.

### shared/docintel/parse_text.py

Purpose: ingest transcript text files in TXT, SRT, or VTT format and produce structured output
suitable for downstream processing (search indexing, keyword extraction, chapter generation).

Usage pattern: call before any content skill that needs to reason over transcript text. Strips
timestamp metadata and returns clean paragraph-style text alongside the raw segment array.

### shared/docintel/wer.py

Purpose: compute Word Error Rate (WER) and Character Error Rate (CER) against a reference
transcript. Uses Python standard library only (no third-party dependencies required).

Inputs:
- `--hypothesis`: path to the transcript under evaluation (SRT, VTT, or TXT)
- `--reference`: path to the golden or proxy reference transcript
- `--format`: `wer`, `cer`, or `both` (default: `both`)

Output: JSON with `wer`, `cer`, `substitutions`, `deletions`, `insertions`, `ref_word_count`.

Usage pattern:
```bash
python3 shared/docintel/wer.py \
  --hypothesis output/episode-42.srt \
  --reference reference/episode-42-golden.txt \
  --format both
```

---

## Caption and subtitle creation workflow

This is the standard end-to-end workflow for a Creator OS caption job. Run all steps locally.

### Step 1: transcribe

Run faster-whisper against the source audio or video file. Use the appropriate model tier
(default: medium for production).

```bash
python3 -m faster_whisper \
  --model medium \
  --language en \
  --output_format all \
  --output_dir output/ \
  input/episode-42.mp4
```

Outputs: `episode-42.json`, `episode-42.srt`, `episode-42.vtt`

### Step 2: normalize

Run transcripts.py to produce the canonical segment array and validate that timestamp ranges
are well-formed.

```bash
python3 shared/docintel/transcripts.py \
  --input output/episode-42.srt \
  --emit json \
  > output/episode-42-segments.json
```

### Step 3: validate accuracy

Run wer.py against the normalized output. A golden reference is preferred; if none exists, run
a second pass with large-v3 and use that as the proxy reference.

```bash
python3 shared/docintel/wer.py \
  --hypothesis output/episode-42.srt \
  --reference reference/episode-42-golden.txt \
  --format both
```

Interpret results:
- WER below 0.05: broadcast-ready; proceed to format conversion
- WER 0.05 to 0.10: production-acceptable; light human review recommended
- WER at or above 0.10: flag for human review; consider re-running with a larger model tier

### Step 4: convert to target format

For YouTube: use the SRT output directly (comma decimal separator, SubRip format).
For web embeds: use the VTT output (dot decimal separator, W3C format).
For styled exports: convert to ASS using a subtitle tool (ffmpeg, SubtitleEdit, or a dedicated
converter script).

### Step 5: upload or hand off

YouTube: upload SRT via YouTube Studio (Subtitles tab). Creator-uploaded captions take search
indexing priority over auto-generated captions.

Web embeds: reference the VTT file in the HTML5 `<track>` element with `kind="subtitles"` or
`kind="captions"`.

---

## YouTube caption specifics

### Format requirements

YouTube accepts SRT (SubRip) and VTT. SRT is the safest choice for upload compatibility.
ASS/SSA is not accepted for upload; convert to SRT before uploading styled captions.

### Auto-generated vs. creator-uploaded

YouTube generates automatic captions using its own ASR (automatic speech recognition). Accuracy
varies by accent, background noise, and niche vocabulary. Creator-uploaded SRT is indexed for
search separately and is prioritized in YouTube's caption display logic when available.

Recommendation: always upload a corrected SRT. Do not rely on auto-generated captions for
SEO-sensitive content.

### Niche vocabulary that trips auto-captions

The following terms appear in the creator's content and are commonly misrecognized by generic
ASR models including YouTube's auto-caption system. Flag these in post-editing review and
consider adding them to a custom Whisper vocabulary prompt if faster-whisper's `initial_prompt`
parameter is used.

- armoire (misread as: "arm war", "arm wah", "arm more")
- patina (misread as: "patena", "pattina", "patient")
- wainscoting (misread as: "wainscotting", "wayne scotting", "wing scoting")
- sconcing (misread as: "sconsing", "scancing")
- bungalow (less common misread; watch for "bungalo")
- decoupage (misread as: "decapod", "decoupled", "de-coupage")
- tartan (occasionally misread as "tarten" or "carton")
- vignette (misread as: "vin-yet", "vinget")

Using faster-whisper with `initial_prompt` set to a short paragraph containing these terms
improves recognition accuracy on large-v3. Example:

```python
segments, info = model.transcribe(
    "episode-42.mp4",
    language="en",
    initial_prompt=(
        "Today on the channel we are working on an armoire with patina hardware, "
        "adding wainscoting, and finishing with a decoupage panel in a vintage bungalow."
    )
)
```

---

## Accuracy validation tools (beyond wer.py)

These are optional local installs that extend accuracy validation beyond the core wer.py script.
None require cloud access. Install only as needed.

### jiwer v4.0.0

- License: Apache-2.0
- Install: `pip install jiwer`
- Backend: RapidFuzz (C++ extension, fast string matching)
- Computes: WER, MER (Match Error Rate), WIL (Word Information Lost), WIP (Word Information
  Preserved) in a single call
- Use when you need richer error decomposition than wer.py provides or when comparing multiple
  model outputs in a benchmark run

```python
from jiwer import process_words
result = process_words(reference, hypothesis)
print(result.wer, result.mer, result.wil)
```

### aeneas

- License: BSD
- Install: `pip install aeneas` (requires espeak and ffmpeg)
- Purpose: forced alignment; maps a known transcript text to audio timestamps word by word
- Use when caption sync is the problem (words are correct but timing is off)
- Output: SMIL or JSON alignment map; useful for validating or correcting segment start/end times

### ffsubsync

- License: MIT
- Install: `pip install ffsubsync`
- Purpose: re-syncs an existing SRT or ASS subtitle file to the audio track of a video; corrects
  temporal drift introduced by export pipeline mismatches or re-encoding
- Use when captions are textually correct but consistently early or late relative to audio

```bash
ffs episode-42.mp4 -i episode-42-draft.srt -o episode-42-synced.srt
```

---

## Error handling and gaps

### No caption source available (audio-only or video with no transcript)

Return:
```json
{
  "status": "metadata_only",
  "gap_reason": "needs_more_info",
  "gap_detail": "No caption or transcript source provided. Run local STT with faster-whisper
    against the audio or video file and pass the output SRT or JSON to this engine.",
  "recommended_action": "run_local_stt"
}
```

Do not fabricate a transcript. Do not guess at spoken content from metadata alone.

### Corrupt or zero-duration file

Return:
```json
{
  "status": "metadata_only",
  "gap_reason": "parse_error",
  "gap_detail": "File could not be parsed or has zero duration. Verify the file is a valid
    audio or video container and that ffprobe reports a nonzero duration.",
  "recommended_action": "verify_source_file"
}
```

### Low-yield transcription (fewer than 50 words)

Flag as low confidence. This typically indicates a silent or near-silent segment, a corrupt
audio track, or a model tier mismatch (tiny model on difficult audio).

Return:
```json
{
  "status": "low_confidence",
  "word_count": "<actual count>",
  "gap_detail": "Transcript contains fewer than 50 words. This may indicate silent audio,
    a corrupt track, or a model tier that is too small for the audio quality.",
  "recommended_action": "re_run_with_larger_model"
}
```

Recommended escalation path: tiny to base to medium to large-v3. Re-run one tier up and compare
word count and WER before escalating further.

### WER at or above threshold

```json
{
  "status": "review_required",
  "wer": "<computed value>",
  "threshold": 0.10,
  "gap_detail": "WER exceeds production threshold. Human review required before publishing.",
  "recommended_action": "human_review_and_optionally_rerun_larger_model"
}
```
