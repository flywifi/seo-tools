#!/usr/bin/env python3
"""Caption round-trip for the Creator OS video-editing bridge (feature 2).

Moves captions both ways between Creator OS transcripts and editor caption files, and maps them
to/from the neutral edit-package (shared/videoedit-engine.md). Reuses the offline transcript stack
(shared/docintel/transcripts.py) for SRT/VTT/JSON/text; adds an iTT (Apple TTML) emitter/parser,
since iTT is one of the three formats Final Cut Pro imports. CEA-608 (.scc) is deferred and flagged,
never faked.

No editor and no app scripting: this is pure file work, so it runs on any OS, online or offline.

CLI:
  python3 tools/videoedit/captions.py to-editor   <transcript-or-caption-file> --fmt srt|vtt|itt
  python3 tools/videoedit/captions.py from-editor <caption-file> [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Reuse the offline transcript parser/emitter.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "shared" / "docintel"))
import transcripts as _t  # noqa: E402

SUPPORTED = ("srt", "vtt", "itt", "text")


# ── iTT (Apple TTML) ────────────────────────────────────────────────────────

def _emit_itt(segments: list) -> str:
    """Emit a minimal, well-formed iTT (TTML 1.0) caption document."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tt xmlns="http://www.w3.org/ns/ttml" xml:lang="en">',
        "  <body>",
        "    <div>",
    ]
    for s in segments:
        begin = _t.from_seconds(s.get("start", 0), ".")
        end = _t.from_seconds(s.get("end", 0), ".")
        text = (s.get("text", "") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f'      <p begin="{begin}" end="{end}">{text}</p>')
    lines += ["    </div>", "  </body>", "</tt>", ""]
    return "\n".join(lines)


def _parse_itt(text: str) -> list:
    """Parse iTT/TTML into segments [{start,end,text}]. Handles HH:MM:SS.mmm and HH:MM:SS,mmm."""
    root = ET.fromstring(text)
    segs = []
    for el in root.iter():
        if not el.tag.endswith("}p") and el.tag != "p":
            continue
        begin = el.get("begin")
        end = el.get("end")
        if begin is None:
            continue
        body = "".join(el.itertext()).strip()
        segs.append({
            "start": _t.to_seconds(begin.replace(".", ",", 1) if "." in begin else begin),
            "end": _t.to_seconds((end or "0:0:0,0").replace(".", ",", 1) if end and "." in end else (end or "")),
            "text": body,
        })
    return segs


# ── edit-package mapping ────────────────────────────────────────────────────

def segments_to_captions(segments: list) -> list:
    return [{"start_seconds": s.get("start", 0.0), "end_seconds": s.get("end", 0.0),
             "text": s.get("text", "")} for s in segments]


def captions_to_segments(captions: list) -> list:
    return [{"start": c.get("start_seconds", 0.0), "end": c.get("end_seconds", 0.0),
             "text": c.get("text", "")} for c in captions]


def _load_segments(src) -> list:
    """src is a path (transcript/caption file) or an already-parsed segments list."""
    if isinstance(src, list):
        return src
    p = Path(src)
    if p.suffix.lower() == ".itt":
        return _parse_itt(p.read_text(encoding="utf-8"))
    return _t.parse(src)["segments"]


# ── public API ──────────────────────────────────────────────────────────────

def to_editor(src, fmt: str = "srt") -> str:
    """Transcript/caption file (or segments) -> editor caption text in `fmt`."""
    fmt = fmt.lower()
    if fmt not in SUPPORTED:
        raise ValueError(f"format must be one of {SUPPORTED}")
    segments = _load_segments(src)
    if fmt == "itt":
        return _emit_itt(segments)
    return _t.emit(segments, fmt)


def from_editor(caption_path: str) -> dict:
    """Editor caption file -> edit-package captions[] plus a small envelope."""
    segments = _load_segments(caption_path)
    caps = segments_to_captions(segments)
    return {
        "source": "caption-bridge",
        "caption_count": len(caps),
        "captions": caps,
        "gaps": [] if caps else [{
            "gap_type": "empty_captions",
            "description": "No caption cues found in the file.",
            "impact": "Nothing to import.",
            "recommended_next_step": "Confirm the export contains captions.",
        }],
    }


def _main(argv) -> int:
    ap = argparse.ArgumentParser(description="Caption round-trip (SRT/VTT/iTT)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    te = sub.add_parser("to-editor")
    te.add_argument("src")
    te.add_argument("--fmt", default="srt", choices=list(SUPPORTED))
    te.add_argument("--out")
    fe = sub.add_parser("from-editor")
    fe.add_argument("src")
    fe.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "to-editor":
        out = to_editor(a.src, a.fmt)
        if a.out:
            Path(a.out).write_text(out, encoding="utf-8")
            print(f"wrote {a.out}")
        else:
            sys.stdout.write(out)
    else:
        print(json.dumps(from_editor(a.src), indent=2, ensure_ascii=False))
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
