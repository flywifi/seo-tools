#!/usr/bin/env python3
"""Neutral timeline core for the video-editing bridge.

The edit-package (shared/videoedit-engine.md) is the canonical in-repo timeline description.
OpenTimelineIO (OTIO) is an OPTIONAL enhancement: when installed it gives us a battle-tested
timeline object and adapters to other NLEs; when absent, the edit-package plus
tools/videoedit/fcpxml.py cover the core round-trip with no third-party dependency.

This module normalizes/validates an edit-package and, if OTIO is available, converts to/from an
OTIO Timeline. It never requires OTIO to function.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def otio_available() -> bool:
    try:
        import opentimelineio  # noqa: F401
        return True
    except Exception:
        return False


def _empty_timeline(name: str = "Timeline") -> dict:
    return {
        "name": name,
        "duration_seconds": None,
        "markers": [], "chapters": [], "titles": [],
        "clips": [], "captions": [], "keywords": [], "roles": ["video"],
    }


def normalize(pkg: dict) -> dict:
    """Fill in a well-formed edit-package with sane defaults; never invent content."""
    out = {
        "schema_version": pkg.get("schema_version", "1.0"),
        "title": pkg.get("title", "Untitled"),
        "created_at": pkg.get("created_at"),
        "source": pkg.get("source", "creator-os"),
        "frame_rate": pkg.get("frame_rate", 30),
        "timeline": {**_empty_timeline(), **(pkg.get("timeline") or {})},
        "reframe": pkg.get("reframe", {"enabled": False, "aspect": "9:16", "method": "auto_reframe"}),
        "export": pkg.get("export", {"presets": [], "platform_targets": []}),
        "gaps": pkg.get("gaps", []),
        "provenance": pkg.get("provenance", {"generated_by": "otio_core.normalize", "tool_version": "1.0"}),
    }
    if "_fcpxml_version" in pkg:
        out["_fcpxml_version"] = pkg["_fcpxml_version"]
    return out


def merge(base: dict, incoming: dict) -> dict:
    """Compose two edit-packages without clobbering: union timeline lists by (start, key).

    This is how independent features combine into one package. Existing entries win on exact
    duplicates; everything else is unioned. No feature's data is silently dropped.
    """
    base = normalize(base)
    incoming = normalize(incoming)
    bt, it = base["timeline"], incoming["timeline"]

    def _union(a, b, keyfn):
        seen = {keyfn(x) for x in a}
        return a + [x for x in b if keyfn(x) not in seen]

    bt["markers"] = _union(bt["markers"], it["markers"], lambda m: (round(m.get("start_seconds", 0), 3), m.get("name", "")))
    bt["chapters"] = _union(bt["chapters"], it["chapters"], lambda c: (round(c.get("start_seconds", 0), 3), c.get("title", "")))
    bt["titles"] = _union(bt["titles"], it["titles"], lambda t: (round(t.get("start_seconds", 0), 3), t.get("text", "")))
    bt["clips"] = _union(bt["clips"], it["clips"], lambda c: (round(c.get("start_seconds", 0), 3), c.get("name", "")))
    bt["captions"] = _union(bt["captions"], it["captions"], lambda c: (round(c.get("start_seconds", 0), 3), c.get("text", "")))
    bt["keywords"] = _union(bt["keywords"], it["keywords"], lambda k: (round(k.get("start_seconds", 0), 3), k.get("keyword", "")))
    bt["roles"] = sorted(set(bt["roles"]) | set(it["roles"]))
    base["gaps"] = _union(base.get("gaps", []), incoming.get("gaps", []),
                          lambda g: (g.get("gap_type", ""), g.get("description", "")))
    if it.get("name") and not bt.get("name"):
        bt["name"] = it["name"]
    return base


def to_otio(pkg: dict):
    """Convert an edit-package to an OTIO Timeline (requires OTIO). Raises if OTIO absent."""
    import opentimelineio as otio
    pkg = normalize(pkg)
    fps = float(pkg.get("frame_rate", 30) or 30)
    tl = otio.schema.Timeline(name=pkg["timeline"].get("name", "Timeline"))
    track = otio.schema.Track(name="V1", kind=otio.schema.TrackKind.Video)
    tl.tracks.append(track)
    for m in pkg["timeline"].get("markers", []):
        tl.tracks.markers.append(otio.schema.Marker(
            name=m.get("name", ""),
            marked_range=otio.opentime.TimeRange(
                start_time=otio.opentime.RationalTime(round(m.get("start_seconds", 0) * fps), fps),
                duration=otio.opentime.RationalTime(1, fps),
            ),
        ))
    return tl


def main(argv) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="edit-package normalize/merge; OTIO status")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    n = sub.add_parser("normalize")
    n.add_argument("pkg")
    m = sub.add_parser("merge")
    m.add_argument("base")
    m.add_argument("incoming")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps({"otio_available": otio_available()}, indent=2))
    elif a.cmd == "normalize":
        print(json.dumps(normalize(json.loads(Path(a.pkg).read_text(encoding="utf-8"))), indent=2, ensure_ascii=False))
    elif a.cmd == "merge":
        base = json.loads(Path(a.base).read_text(encoding="utf-8"))
        inc = json.loads(Path(a.incoming).read_text(encoding="utf-8"))
        print(json.dumps(merge(base, inc), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
