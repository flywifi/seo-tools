#!/usr/bin/env python3
"""FCPXML build / parse / validate for the Creator OS video-editing bridge (Lane A).

Converts between the neutral edit-package (see shared/videoedit-engine.md) and FCPXML, the
file both Final Cut Pro and DaVinci Resolve read. Generation and parsing need no editor
installed and no app scripting, so this works on any OS, online or offline.

build(pkg)   -> FCPXML string (a well-formed timeline scaffold: markers, chapter-markers,
                keywords, gap spine, title beats).
parse(src)   -> edit-package dict recovered from an FCPXML string or file path.
validate(src)-> {ok, level, errors} via xmllint (DTD-valid when a DTD is found, else
                well-formed), with a pure-Python well-formedness fallback.
detect_installed_version() -> the FCPXML version of the installed Final Cut Pro, or None.

CLI:
  python3 tools/videoedit/fcpxml.py build   edit-package.json [--out file.fcpxml]
  python3 tools/videoedit/fcpxml.py parse   file.fcpxml [--json]
  python3 tools/videoedit/fcpxml.py validate file.fcpxml [--dtd path]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_VERSION = "1.10"


# ── time helpers ───────────────────────────────────────────────────────────

def _timescale(fps: float) -> int:
    # Stable rational timescale: 1 second = (fps*100)/(fps*100) s; 1 frame = 100/(fps*100) s.
    return int(round(fps * 100))


def sec_to_time(sec: float, fps: float) -> str:
    ts = _timescale(fps)
    return f"{int(round((sec or 0.0) * ts))}/{ts}s"


def time_to_sec(val: str, fps: float) -> float:
    val = (val or "0s").strip()
    if val.endswith("s"):
        val = val[:-1]
    if not val:
        return 0.0
    if "/" in val:
        num, den = val.split("/", 1)
        try:
            return float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0


def _frame_duration(fps: float) -> str:
    ts = _timescale(fps)
    return f"{int(round(ts / fps))}/{ts}s"


# ── build ──────────────────────────────────────────────────────────────────

def _infer_duration(tl: dict) -> float:
    ends = [0.0]
    for m in tl.get("markers", []) or []:
        ends.append(float(m.get("start_seconds", 0) or 0) + 1.0)
    for c in tl.get("chapters", []) or []:
        ends.append(float(c.get("start_seconds", 0) or 0) + 1.0)
    for t in tl.get("titles", []) or []:
        ends.append(float(t.get("start_seconds", 0) or 0) + float(t.get("duration_seconds", 0) or 0))
    for c in tl.get("clips", []) or []:
        ends.append(float(c.get("start_seconds", 0) or 0) + float(c.get("duration_seconds", 0) or 0))
    return max(ends) if ends else 0.0


def build(pkg: dict, version: str | None = None) -> str:
    """Serialize an edit-package to a well-formed FCPXML scaffold string."""
    fps = float(pkg.get("frame_rate", 30) or 30)
    version = version or pkg.get("_fcpxml_version") or DEFAULT_VERSION
    tl = pkg.get("timeline", {}) or {}
    duration = tl.get("duration_seconds") or _infer_duration(tl) or 60.0
    fdur = _frame_duration(fps)

    fcpxml = ET.Element("fcpxml", {"version": version})
    resources = ET.SubElement(fcpxml, "resources")
    ET.SubElement(resources, "format", {
        "id": "r1",
        "name": f"FFVideoFormat1080p{int(round(fps))}",
        "frameDuration": fdur,
        "width": "1920",
        "height": "1080",
    })
    library = ET.SubElement(fcpxml, "library")
    event = ET.SubElement(library, "event", {"name": "Creator OS"})
    project = ET.SubElement(event, "project", {"name": pkg.get("title", "Untitled")})
    sequence = ET.SubElement(project, "sequence", {
        "format": "r1",
        "duration": sec_to_time(duration, fps),
        "tcStart": "0s",
        "tcFormat": "NDF",
    })
    spine = ET.SubElement(sequence, "spine")
    gap = ET.SubElement(spine, "gap", {
        "name": tl.get("name", "Timeline"),
        "offset": "0s",
        "start": "0s",
        "duration": sec_to_time(duration, fps),
    })

    # Markers (standard + to-do/completed) and chapter-markers live on the gap.
    for m in tl.get("markers", []) or []:
        start = sec_to_time(float(m.get("start_seconds", 0) or 0), fps)
        mtype = (m.get("type") or "standard").lower()
        if mtype == "chapter":
            attrs = {"start": start, "duration": fdur, "value": m.get("name", "")}
            po = m.get("poster_offset_seconds")
            if po is not None:
                attrs["posterOffset"] = sec_to_time(float(po), fps)
            ET.SubElement(gap, "chapter-marker", attrs)
        else:
            attrs = {"start": start, "duration": fdur, "value": m.get("name", "")}
            if m.get("note"):
                attrs["note"] = m["note"]
            if mtype == "to-do":
                attrs["completed"] = "0"
            elif mtype == "completed":
                attrs["completed"] = "1"
            ET.SubElement(gap, "marker", attrs)

    # Dedicated chapters[] also render as chapter-markers.
    for c in tl.get("chapters", []) or []:
        attrs = {
            "start": sec_to_time(float(c.get("start_seconds", 0) or 0), fps),
            "duration": fdur,
            "value": c.get("title", ""),
        }
        po = c.get("poster_offset_seconds")
        if po is not None:
            attrs["posterOffset"] = sec_to_time(float(po), fps)
        ET.SubElement(gap, "chapter-marker", attrs)

    # Keyword ranges.
    for k in tl.get("keywords", []) or []:
        ET.SubElement(gap, "keyword", {
            "start": sec_to_time(float(k.get("start_seconds", 0) or 0), fps),
            "duration": sec_to_time(float(k.get("duration_seconds", 0) or 0), fps),
            "value": k.get("keyword", ""),
        })

    # Title beats as connected title clips (Basic Title placeholder; Motion template ref
    # is injected by motion-fill in a later phase).
    for t in tl.get("titles", []) or []:
        title = ET.SubElement(gap, "title", {
            "name": t.get("text", "Title"),
            "offset": sec_to_time(float(t.get("start_seconds", 0) or 0), fps),
            "duration": sec_to_time(float(t.get("duration_seconds", 4) or 4), fps),
            "role": t.get("role", "titles"),
        })
        if t.get("template"):
            title.set("data-template", t["template"])
        text = ET.SubElement(title, "text")
        text.text = t.get("text", "")

    body = ET.tostring(fcpxml, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n' + body + "\n"


# ── parse ──────────────────────────────────────────────────────────────────

def parse(src: str) -> dict:
    """Recover an edit-package from an FCPXML string or file path."""
    text = src
    p = Path(src) if len(src) < 1024 else None
    if p is not None and p.exists():
        # .fcpxmld bundle: read the inner Info.fcpxml
        if p.is_dir():
            inner = next(iter(sorted(p.glob("*.fcpxml"))), None)
            text = inner.read_text(encoding="utf-8") if inner else ""
        else:
            text = p.read_text(encoding="utf-8")

    root = ET.fromstring(text)
    version = root.get("version", DEFAULT_VERSION)
    fmt = root.find(".//format")
    fps = 30.0
    if fmt is not None and fmt.get("frameDuration"):
        fd = time_to_sec(fmt.get("frameDuration"), 1.0)  # frameDuration in seconds
        if fd > 0:
            fps = round(1.0 / fd, 3)

    project = root.find(".//project")
    title = project.get("name") if project is not None else "Untitled"
    gap = root.find(".//spine/gap")
    markers, chapters, keywords, titles = [], [], [], []
    if gap is not None:
        for el in gap:
            tag = el.tag
            if tag == "marker":
                mtype = "standard"
                if el.get("completed") == "0":
                    mtype = "to-do"
                elif el.get("completed") == "1":
                    mtype = "completed"
                markers.append({
                    "start_seconds": time_to_sec(el.get("start"), fps),
                    "name": el.get("value", ""),
                    "note": el.get("note", ""),
                    "type": mtype,
                    "color": None,
                })
            elif tag == "chapter-marker":
                chapters.append({
                    "start_seconds": time_to_sec(el.get("start"), fps),
                    "title": el.get("value", ""),
                    "poster_offset_seconds": time_to_sec(el.get("posterOffset"), fps) if el.get("posterOffset") else 0.0,
                })
            elif tag == "keyword":
                keywords.append({
                    "start_seconds": time_to_sec(el.get("start"), fps),
                    "duration_seconds": time_to_sec(el.get("duration"), fps),
                    "keyword": el.get("value", ""),
                })
            elif tag == "title":
                text_el = el.find("text")
                titles.append({
                    "start_seconds": time_to_sec(el.get("offset"), fps),
                    "duration_seconds": time_to_sec(el.get("duration"), fps),
                    "text": (text_el.text if text_el is not None and text_el.text else el.get("name", "")),
                    "template": el.get("data-template"),
                    "role": el.get("role", "titles"),
                })

    return {
        "schema_version": "1.0",
        "title": title,
        "created_at": None,
        "source": "fcpxml-parse",
        "frame_rate": fps,
        "_fcpxml_version": version,
        "timeline": {
            "name": gap.get("name") if gap is not None else "Timeline",
            "duration_seconds": None,
            "markers": markers,
            "chapters": chapters,
            "titles": titles,
            "clips": [],
            "captions": [],
            "keywords": keywords,
            "roles": sorted({t.get("role", "titles") for t in titles}) or ["video"],
        },
        "gaps": [],
        "provenance": {"generated_by": "fcpxml.parse", "tool_version": "1.0"},
    }


# ── validate ───────────────────────────────────────────────────────────────

def detect_installed_version() -> str | None:
    """Return the FCPXML version of the installed Final Cut Pro (macOS), else None."""
    if sys.platform != "darwin":
        return None
    res = Path("/Applications/Final Cut Pro.app/Contents/Resources")
    if not res.exists():
        return None
    dtds = sorted(res.glob("*.dtd")) + sorted(res.glob("**/FCPXML*.dtd"))
    best = None
    for d in dtds:
        name = d.name.lower()
        # names like FCPXMLv1_10.dtd / fcpxml-1.13.dtd
        import re as _re
        m = _re.search(r"(\d+)[._](\d+)", name)
        if m:
            v = f"{m.group(1)}.{m.group(2)}"
            best = v if best is None or v > best else best
    return best


def _find_dtd() -> str | None:
    if sys.platform != "darwin":
        return None
    res = Path("/Applications/Final Cut Pro.app/Contents/Resources")
    if not res.exists():
        return None
    dtds = sorted(res.glob("*.dtd"))
    return str(dtds[-1]) if dtds else None


def validate(src: str, dtd_path: str | None = None) -> dict:
    """Validate an FCPXML string or path. DTD-valid if a DTD is available, else well-formed."""
    tmp = None
    if "<fcpxml" in src and "\n" in src:
        tmp = Path(tempfile.mkstemp(suffix=".fcpxml")[1])
        tmp.write_text(src, encoding="utf-8")
        path = str(tmp)
    else:
        path = src

    dtd = dtd_path or _find_dtd()
    xmllint = shutil.which("xmllint")
    try:
        if xmllint:
            if dtd:
                cmd = [xmllint, "--noout", "--dtdvalid", dtd, path]
                level = "dtd_valid"
            else:
                cmd = [xmllint, "--noout", path]
                level = "well_formed"
            proc = subprocess.run(cmd, capture_output=True, text=True)
            ok = proc.returncode == 0
            return {
                "ok": ok,
                "level": level if ok else "invalid",
                "errors": [] if ok else [line for line in proc.stderr.splitlines() if line.strip()],
                "tool": "xmllint",
                "dtd": dtd,
            }
        # Pure-Python well-formedness fallback.
        text = Path(path).read_text(encoding="utf-8") if Path(path).exists() else src
        ET.fromstring(text)
        return {"ok": True, "level": "well_formed_py", "errors": [], "tool": "ElementTree", "dtd": None}
    except ET.ParseError as exc:
        return {"ok": False, "level": "invalid", "errors": [str(exc)], "tool": "ElementTree", "dtd": None}
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


# ── CLI ─────────────────────────────────────────────────────────────────────

def main(argv) -> int:
    ap = argparse.ArgumentParser(description="FCPXML build/parse/validate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("pkg")
    b.add_argument("--out")
    b.add_argument("--version")
    pp = sub.add_parser("parse")
    pp.add_argument("file")
    pp.add_argument("--json", action="store_true")
    v = sub.add_parser("validate")
    v.add_argument("file")
    v.add_argument("--dtd")
    a = ap.parse_args(argv)

    if a.cmd == "build":
        pkg = json.loads(Path(a.pkg).read_text(encoding="utf-8"))
        out = build(pkg, version=a.version)
        if a.out:
            Path(a.out).write_text(out, encoding="utf-8")
            print(f"wrote {a.out}")
        else:
            sys.stdout.write(out)
    elif a.cmd == "parse":
        pkg = parse(a.file)
        print(json.dumps(pkg, indent=2, ensure_ascii=False))
    elif a.cmd == "validate":
        print(json.dumps(validate(a.file, a.dtd), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
