#!/usr/bin/env python3
"""Chapter fan-out for the Creator OS video-editing bridge (feature 8).

One chapter list, reused three ways: the editor chapter track (already handled by fcpxml.py),
the YouTube description timestamps, and the scheduling metadata. Pure data transform, so it works
on every AI engine and any OS. Enforces YouTube's Key Moments rules by VALIDATE-AND-FLAG (never
silently fixing or inventing).

Feeds the existing geo-optimize atom (its `chapter_outline` input shape) and content-calendar /
the scheduling queue.

CLI:
  python3 tools/videoedit/chapters.py <edit-package.json | chapters.json> [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MIN_CHAPTERS = 3          # YouTube Key Moments eligibility
MIN_GAP_SECONDS = 10      # YouTube requires each chapter >= 10s


def _fmt_ts(sec: float) -> str:
    sec = int(round(max(0.0, sec)))
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _normalize(obj) -> list:
    """Accept an edit-package, a {chapters:[...]} dict, or a bare list. Return chapters list."""
    if isinstance(obj, list):
        raw = obj
    elif isinstance(obj, dict) and "timeline" in obj:
        raw = obj.get("timeline", {}).get("chapters", []) or []
    elif isinstance(obj, dict) and "chapters" in obj:
        raw = obj["chapters"]
    else:
        raw = []
    out = []
    for c in raw:
        out.append({
            "start_seconds": float(c.get("start_seconds", c.get("timestamp_seconds", 0)) or 0),
            "title": c.get("title", c.get("chapter_topic", "")),
        })
    return sorted(out, key=lambda c: c["start_seconds"])


def validate(chapters: list) -> list:
    """Return a gaps[] list of YouTube-rule violations (empty = compliant)."""
    gaps = []
    if not chapters:
        return [{
            "gap_type": "no_chapters",
            "description": "No chapters provided.",
            "impact": "No chapter track, no Key Moments, no description timestamps.",
            "recommended_next_step": "Provide at least 3 chapters, the first at 0:00.",
        }]
    if chapters[0]["start_seconds"] > 0.001:
        gaps.append({
            "gap_type": "first_not_zero",
            "description": f"First chapter starts at {_fmt_ts(chapters[0]['start_seconds'])}, not 0:00.",
            "impact": "YouTube ignores chapter markers unless the first is at 0:00.",
            "recommended_next_step": "Add a chapter at 0:00 (or shift the first to 0:00).",
        })
    if len(chapters) < MIN_CHAPTERS:
        gaps.append({
            "gap_type": "too_few_chapters",
            "description": f"{len(chapters)} chapter(s); YouTube Key Moments needs at least {MIN_CHAPTERS}.",
            "impact": "Chapters will not appear as Google/YouTube Key Moments.",
            "recommended_next_step": f"Add chapters to reach at least {MIN_CHAPTERS}.",
        })
    for i in range(1, len(chapters)):
        gap = chapters[i]["start_seconds"] - chapters[i - 1]["start_seconds"]
        if gap < MIN_GAP_SECONDS:
            gaps.append({
                "gap_type": "chapter_too_short",
                "description": f"Chapter '{chapters[i]['title']}' is {gap:.0f}s after the previous one (min {MIN_GAP_SECONDS}s).",
                "impact": "YouTube rejects chapter lists with any segment under 10 seconds.",
                "recommended_next_step": "Space chapters at least 10 seconds apart.",
            })
    return gaps


def fan_out(obj) -> dict:
    chapters = _normalize(obj)
    gaps = validate(chapters)

    # geo-optimize input shape.
    chapter_outline = [{"timestamp_seconds": c["start_seconds"], "chapter_topic": c["title"]}
                       for c in chapters]

    # Paste-ready YouTube description block; force the first line to 0:00 if chapters exist.
    lines = []
    for i, c in enumerate(chapters):
        ts = "0:00" if i == 0 else _fmt_ts(c["start_seconds"])
        lines.append(f"{ts} {c['title']}".rstrip())
    description_timestamps = "\n".join(lines)

    return {
        "source": "chapter-map",
        "chapter_count": len(chapters),
        "chapters": chapters,
        "chapter_outline": chapter_outline,
        "youtube_description_timestamps": description_timestamps,
        "scheduling": {
            "description_timestamps": description_timestamps,
            "chapter_count": len(chapters),
            "key_moments_eligible": not gaps,
        },
        "feeds": {
            "geo_optimize": "chapter_outline",
            "content_calendar_and_scheduling": "scheduling.description_timestamps",
        },
        "gaps": gaps,
    }


def _main(argv) -> int:
    ap = argparse.ArgumentParser(description="Chapter fan-out")
    ap.add_argument("path")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    obj = json.loads(Path(a.path).read_text(encoding="utf-8"))
    result = fan_out(obj)
    if a.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["youtube_description_timestamps"])
        if result["gaps"]:
            print("\n-- flags --")
            for g in result["gaps"]:
                print(f"  [{g['gap_type']}] {g['description']}")
    return 0


def main(argv) -> int:
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
    raise SystemExit(main(sys.argv[1:]))
