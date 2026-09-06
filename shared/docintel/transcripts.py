#!/usr/bin/env python3
"""Creator OS document intelligence: local, offline, zero-token transcript and caption tool.

Reads transcripts and captions in any common form (SRT, WebVTT, JSON, or plain text) into a single
normalized segment list, and writes them back out as SRT, VTT, or plain text. Also provides
silence/pause detection and chapter suggestion from timecoded transcripts. Runs on the client with
no internet and no tokens, so the model reasons over the normalized output instead of raw caption
files. This is the "grab and parse transcripts in any form" path; live audio transcription is the
job of shared/transcription-engine.md.

Usage:
  python3 shared/docintel/transcripts.py <file>                        # parse and summarize
  python3 shared/docintel/transcripts.py <file> --json                 # normalized JSON
  python3 shared/docintel/transcripts.py <file> --emit srt             # convert to SRT
  python3 shared/docintel/transcripts.py <file> --emit vtt             # convert to WebVTT
  python3 shared/docintel/transcripts.py <file> --emit text            # plain transcript
  python3 shared/docintel/transcripts.py <file> --gap-metrics          # inter-segment silences
  python3 shared/docintel/transcripts.py <file> --suggest-chapters     # chapter suggestions
  python3 shared/docintel/transcripts.py <file> --normalize            # ONE combined object:
                                                                       #   segments + silences + chapters
                                                                       #   (what transcript_normalize jobs use)
  python3 shared/docintel/transcripts.py --selftest                    # offline self-checks
"""
import argparse
import json
import re
import sys
from pathlib import Path

TIME = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{3})")
CUE = re.compile(
    r"(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3})"
)


def to_seconds(stamp):
    m = TIME.search(stamp)
    if not m:
        return 0.0
    h, mn, s, ms = (int(x) for x in m.groups())
    return h * 3600 + mn * 60 + s + ms / 1000.0


def from_seconds(sec, sep=","):
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    mn = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{mn:02d}:{s:02d}{sep}{ms:03d}"


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def parse_srt_vtt(text):
    segments = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip() and ln.strip() != "WEBVTT"]
        cue_line = next((ln for ln in lines if CUE.search(ln)), None)
        if not cue_line:
            continue
        start, end = CUE.search(cue_line).groups()
        idx = lines.index(cue_line)
        body = " ".join(lines[idx + 1:]).strip()
        if body:
            segments.append({"start": to_seconds(start), "end": to_seconds(end), "text": body})
    return segments


def parse_json(text):
    data = json.loads(text)
    if isinstance(data, dict) and isinstance(data.get("segments"), list):
        rows = data["segments"]
    elif isinstance(data, list):
        rows = data
    else:
        return [{"start": 0.0, "end": 0.0, "text": str(data.get("text", "")).strip()}]
    out = []
    for r in rows:
        if isinstance(r, dict) and r.get("text"):
            out.append({
                "start": float(r.get("start", 0) or 0),
                "end": float(r.get("end", 0) or 0),
                "text": str(r["text"]).strip(),
            })
    return out


def parse(path):
    ext = Path(path).suffix.lower().lstrip(".")
    text = read_text(path)
    if ext == "json" or text.lstrip().startswith(("{", "[")):
        fmt, segments = "json", parse_json(text)
    elif ext in ("srt", "vtt") or CUE.search(text):
        fmt = "vtt" if (ext == "vtt" or "WEBVTT" in text[:32]) else "srt"
        segments = parse_srt_vtt(text)
    else:
        fmt = "text"
        segments = [{"start": 0.0, "end": 0.0, "text": line.strip()}
                    for line in text.splitlines() if line.strip()]
    duration = max((s["end"] for s in segments), default=0.0)
    plain = " ".join(s["text"] for s in segments)
    return {
        "format": fmt,
        "segment_count": len(segments),
        "duration_seconds": round(duration, 3),
        "plain_text": plain,
        "segments": segments,
        "ran_locally": True,
        "tokens_spent_on_parse": 0,
    }


def emit(segments, fmt):
    if fmt == "text":
        return " ".join(s["text"] for s in segments)
    lines = []
    if fmt == "vtt":
        lines.append("WEBVTT\n")
    sep = "." if fmt == "vtt" else ","
    for i, s in enumerate(segments, 1):
        if fmt == "srt":
            lines.append(str(i))
        lines.append(f"{from_seconds(s['start'], sep)} --> {from_seconds(s['end'], sep)}")
        lines.append(s["text"])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def gap_metrics(segments, min_gap_seconds=5.0):
    """Return inter-segment silence gaps at or above min_gap_seconds.

    A silence (pause) is the dead air between one segment's end and the next segment's
    start. Each entry: {after_segment, gap_seconds, from_end, to_start}.
    """
    min_gap = float(min_gap_seconds)
    silences = []
    for i in range(1, len(segments)):
        gap = round(float(segments[i]["start"]) - float(segments[i - 1]["end"]), 3)
        if gap >= min_gap:
            silences.append({
                "after_segment": i - 1,
                "gap_seconds": gap,
                "from_end": segments[i - 1]["end"],
                "to_start": segments[i]["start"],
            })
    return {"silences": silences, "min_gap_seconds": min_gap}


def suggest_chapters(segments, min_gap_seconds=8.0, min_chapter_seconds=30.0):
    """Propose chapter boundaries from silence gaps and words_per_minute drops.

    A boundary is proposed where a long pause precedes a segment (basis "silence"), where
    the speaking pace falls from above the median words_per_minute to below half of it
    (basis "wpm_drop"), or both. Titles are never invented: suggested_title is always null
    and the model or the human names each chapter from the transcript text.
    Returns [{start_seconds, basis, suggested_title}] sorted by time, with boundaries
    closer than min_chapter_seconds to the previous one dropped.
    """
    if not segments:
        return []

    wpm_vals = []
    for s in segments:
        words = len(str(s["text"]).split())
        dur = float(s["end"]) - float(s["start"])
        wpm_vals.append((words / dur * 60.0) if dur > 0 else 0.0)

    sorted_wpm = sorted(w for w in wpm_vals if w > 0)
    median_wpm = sorted_wpm[len(sorted_wpm) // 2] if sorted_wpm else 0.0
    wpm_threshold = median_wpm * 0.5

    boundaries = {}
    for i in range(1, len(segments)):
        gap = float(segments[i]["start"]) - float(segments[i - 1]["end"])
        if gap >= float(min_gap_seconds):
            boundaries[float(segments[i]["start"])] = "silence"

    for i in range(1, len(segments)):
        if median_wpm > 0 and wpm_vals[i - 1] > median_wpm and wpm_vals[i] < wpm_threshold:
            ts = float(segments[i]["start"])
            boundaries[ts] = "both" if ts in boundaries else "wpm_drop"

    chapters = []
    prev_ts = 0.0
    for ts in sorted(boundaries):
        if ts - prev_ts >= float(min_chapter_seconds):
            chapters.append({"start_seconds": ts, "basis": boundaries[ts], "suggested_title": None})
            prev_ts = ts
    return chapters


def normalize(parsed, min_gap_seconds=None):
    """One combined object for the transcript_normalize job (P63 F-SWEEP-3): the parse payload
    plus silence gaps plus suggested chapters, in a single dict. The single-mode CLI arms below
    stay untouched (the footage-analysis atom runs them as separate calls); this is the additive
    path a headless job uses so its Outbox artifact carries everything the docs promise.
    min_gap_seconds applies to BOTH consumers when given; otherwise each keeps its own default
    (silences 5.0, chapters 8.0 — the same defaults as the standalone modes)."""
    gap_min = 5.0 if min_gap_seconds is None else min_gap_seconds
    chap_min = 8.0 if min_gap_seconds is None else min_gap_seconds
    gm = gap_metrics(parsed["segments"], gap_min)
    return {
        "format": parsed["format"],
        "segment_count": parsed["segment_count"],
        "duration_seconds": parsed["duration_seconds"],
        "segments": parsed["segments"],
        "silences": gm["silences"],
        "min_gap_seconds": gm["min_gap_seconds"],
        "chapters": suggest_chapters(parsed["segments"], chap_min),
        "ran_locally": True,
    }


def _selftest():
    """Offline checks: the combined --normalize payload carries all three analysis products for a
    timecoded fixture, and the single-mode outputs are unchanged by its existence."""
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    srt = ("1\n00:00:01,000 --> 00:00:04,000\nWelcome to the workshop.\n\n"
           "2\n00:00:06,000 --> 00:00:10,000\nFirst we sand the panel.\n\n"
           "3\n00:00:25,000 --> 00:00:30,000\nNow the stain goes on.\n\n"
           "4\n00:01:20,000 --> 00:01:26,000\nThe final reveal.\n")
    with tempfile.NamedTemporaryFile("w", suffix=".srt", delete=False) as fh:
        fh.write(srt)
        path = fh.name
    parsed = parse(path)
    combined = normalize(parsed)
    ok("normalize: segments present and non-empty",
       combined["segments"] and combined["segment_count"] == 4)
    ok("normalize: silences detected (15s and 50s gaps at the 5.0 default)",
       len(combined["silences"]) == 2)
    ok("normalize: chapters suggested for the timecoded fixture",
       isinstance(combined["chapters"], list) and len(combined["chapters"]) >= 1)
    ok("normalize: single-mode outputs unchanged (silences == gap_metrics arm)",
       combined["silences"] == gap_metrics(parsed["segments"], 5.0)["silences"])
    ok("normalize: single-mode outputs unchanged (chapters == suggest_chapters arm)",
       combined["chapters"] == suggest_chapters(parsed["segments"], 8.0))
    ok("normalize: per-mode min-gap defaults preserved (5.0 silences / 8.0 chapters)",
       combined["min_gap_seconds"] == 5.0)
    shared = normalize(parsed, min_gap_seconds=12.0)
    ok("normalize: explicit --min-gap-seconds applies to both consumers",
       shared["min_gap_seconds"] == 12.0
       and shared["silences"] == gap_metrics(parsed["segments"], 12.0)["silences"]
       and shared["chapters"] == suggest_chapters(parsed["segments"], 12.0))

    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["x" * 300])
    ok(">255-byte path arg -> clean envelope, no traceback (P66 boundary)",
       rc == 1 and "next_step" in buf.getvalue())

    passed = sum(1 for _, c in checks if c)
    print(f"selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


def _main(argv):
    ap = argparse.ArgumentParser(description="Creator OS offline transcript and caption tool")
    ap.add_argument("path", nargs="?")
    ap.add_argument("--emit", choices=["srt", "vtt", "text"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gap-metrics", action="store_true")
    ap.add_argument("--suggest-chapters", action="store_true")
    ap.add_argument("--normalize", action="store_true")
    ap.add_argument("--min-gap-seconds", type=float, default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    if not args.path:
        ap.error("path is required (or pass --selftest)")
    parsed = parse(args.path)
    if args.normalize:
        print(json.dumps(normalize(parsed, args.min_gap_seconds), indent=2))
    elif args.gap_metrics:
        min_gap = 5.0 if args.min_gap_seconds is None else args.min_gap_seconds
        print(json.dumps(gap_metrics(parsed["segments"], min_gap), indent=2))
    elif args.suggest_chapters:
        min_gap = 8.0 if args.min_gap_seconds is None else args.min_gap_seconds
        print(json.dumps(suggest_chapters(parsed["segments"], min_gap), indent=2))
    elif args.emit:
        print(emit(parsed["segments"], args.emit))
    elif args.json:
        print(json.dumps(parsed, indent=2))
    else:
        print(f"format={parsed['format']} segments={parsed['segment_count']} "
              f"duration={parsed['duration_seconds']}s\n\n{parsed['plain_text'][:1000]}")
    return 0


def main(argv):
    """Thin CLI boundary (P66): an unhandled filesystem error from a user-supplied path (for
    example a >255-byte component raising ENAMETOOLONG, which Path.exists() does not suppress)
    becomes the clean {"error","next_step"} envelope instead of a raw traceback."""
    try:
        return _main(argv)
    except OSError as exc:
        print(json.dumps({"error": str(exc),
                          "next_step": "pass a readable file path (this one could not be opened)"}))
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
