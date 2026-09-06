#!/usr/bin/env python3
"""Creator OS MLT XML writer/parser: the second Lane A interchange format (P29).

MLT XML is Shotcut's native project format and the substrate Kdenlive builds on; emitting it
means Shotcut/Kdenlive users get a native project the same way FCP/Resolve users get FCPXML.
Sibling of fcpxml.py: same edit-package in, same edit-package out, stdlib-only. Markers and
chapter candidates are carried as Shotcut marker properties (MLT itself has no chapter concept;
recorded honestly in gaps[]). Rendering an .mlt is a separate, gated concern: `render` checks
the media_render flag (an APP_DRIVING feature requiring the video_editing_enabled master gate)
and walks melt -> ffmpeg single-asset cut-list encode -> an honest no-render handoff, which is
the shipped pre-P29 behavior (give the file to the human editor).

Usage:
  python3 tools/videoedit/mltxml.py build <edit-package.json>
  python3 tools/videoedit/mltxml.py parse <file.mlt> [--json]
  python3 tools/videoedit/mltxml.py validate <file.mlt>
  python3 tools/videoedit/mltxml.py render <file.mlt|pkg.json> --out OUT [--backend auto|melt|ffmpeg]
  python3 tools/videoedit/mltxml.py selftest        (or --selftest)
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import videoedit_validate as _gate  # noqa: E402
from fcpxml import _infer_duration  # noqa: E402

DEFAULT_VERSION = "7.0.0"
SUBPROCESS_TIMEOUT = 1800


def sec_to_clock(sec):
    sec = max(0.0, float(sec or 0.0))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def clock_to_sec(val, fps=30.0):
    val = str(val or "0").strip()
    if ":" in val:
        parts = val.split(":")
        out = 0.0
        for p in parts:
            out = out * 60 + float(p)
        return out
    try:  # bare number = frames
        return float(val) / float(fps)
    except ValueError:
        return 0.0


def build(pkg, version=None):
    """Edit-package -> MLT XML string (Shotcut-native, Kdenlive-readable substrate)."""
    tl = pkg.get("timeline", {}) or {}
    fps = float(pkg.get("frame_rate", 30) or 30)
    title = escape(str(pkg.get("title") or tl.get("name") or "Creator OS timeline"))
    duration = float(tl.get("duration_seconds") or _infer_duration(tl) or 0.0)
    ver = version or DEFAULT_VERSION

    clips = tl.get("clips", []) or []
    assets = []
    for c in clips:
        ref = c.get("asset_ref")
        if ref and ref not in assets:
            assets.append(ref)

    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             f'<mlt LC_NUMERIC="C" version="{escape(ver)}" title="{title}" producer="tractor0">',
             f'  <profile description="automatic" frame_rate_num="{int(round(fps))}" '
             'frame_rate_den="1" progressive="1"/>']
    for i, ref in enumerate(assets):
        lines.append(f'  <producer id="producer{i}">')
        lines.append(f'    <property name="resource">{escape(str(ref))}</property>')
        lines.append('  </producer>')

    lines.append('  <playlist id="playlist0">')
    cursor = 0.0
    for c in sorted(clips, key=lambda c: float(c.get("start_seconds", 0) or 0)):
        ref = c.get("asset_ref")
        if ref is None:
            continue
        start = float(c.get("start_seconds", 0) or 0)
        dur = float(c.get("duration_seconds", 0) or 0)
        if start > cursor + 0.0005:
            lines.append(f'    <blank length="{sec_to_clock(start - cursor)}"/>')
        pid = f"producer{assets.index(ref)}"
        src_in = float(c.get("source_in_seconds", start) or start)
        lines.append(f'    <entry producer="{pid}" in="{sec_to_clock(src_in)}" '
                     f'out="{sec_to_clock(src_in + dur)}"/>')
        cursor = start + dur
    lines.append('  </playlist>')

    lines.append(f'  <tractor id="tractor0" title="{title}" in="{sec_to_clock(0)}" '
                 f'out="{sec_to_clock(duration)}">')
    markers = list(tl.get("markers", []) or [])
    for ch in tl.get("chapters", []) or []:
        markers.append({"start_seconds": ch.get("start_seconds", 0),
                        "name": ch.get("title", ""), "type": "chapter"})
    if markers:
        lines.append('    <properties name="shotcut:markers">')
        for i, m in enumerate(markers):
            start = sec_to_clock(m.get("start_seconds", 0))
            lines.append(f'      <properties name="{i}">')
            lines.append(f'        <property name="text">{escape(str(m.get("name") or ""))}</property>')
            lines.append(f'        <property name="start">{start}</property>')
            lines.append(f'        <property name="end">{start}</property>')
            lines.append('        <property name="color">#008000</property>')
            lines.append('      </properties>')
        lines.append('    </properties>')
    lines.append('    <track producer="playlist0"/>')
    lines.append('  </tractor>')
    lines.append('</mlt>')
    return "\n".join(lines) + "\n"


def parse(src):
    """MLT XML (string or path) -> edit-package dict, mirroring fcpxml.parse's shape."""
    text = src
    if "<mlt" not in str(src):
        text = Path(src).read_text(encoding="utf-8")
    root = ET.fromstring(text)
    prof = root.find("profile")
    fps = 30.0
    if prof is not None:
        num = float(prof.get("frame_rate_num", 30) or 30)
        den = float(prof.get("frame_rate_den", 1) or 1)
        fps = num / den if den else 30.0

    resources = {}
    for p in root.findall("producer"):
        res = p.find("./property[@name='resource']")
        resources[p.get("id")] = res.text if res is not None else None

    clips = []
    cursor = 0.0
    playlist = root.find("playlist")
    if playlist is not None:
        for el in playlist:
            if el.tag == "blank":
                cursor += clock_to_sec(el.get("length"), fps)
            elif el.tag == "entry":
                cin = clock_to_sec(el.get("in"), fps)
                cout = clock_to_sec(el.get("out"), fps)
                dur = max(0.0, cout - cin)
                ref = resources.get(el.get("producer"))
                clips.append({"start_seconds": round(cursor, 3),
                              "duration_seconds": round(dur, 3),
                              "name": Path(ref).name if ref else "clip",
                              "role": "video", "asset_ref": ref,
                              "note": None})
                cursor += dur

    markers = []
    tractor = root.find("tractor")
    title = tractor.get("title") if tractor is not None else root.get("title")
    if tractor is not None:
        mprops = tractor.find("./properties[@name='shotcut:markers']")
        if mprops is not None:
            for m in mprops.findall("properties"):
                text_el = m.find("./property[@name='text']")
                start_el = m.find("./property[@name='start']")
                markers.append({
                    "start_seconds": round(clock_to_sec(
                        start_el.text if start_el is not None else "0", fps), 3),
                    "name": (text_el.text or "") if text_el is not None else "",
                    "note": None, "type": "standard", "color": None})

    duration = clock_to_sec(tractor.get("out"), fps) if tractor is not None else cursor
    return {
        "schema_version": "1.0",
        "title": title,
        "created_at": None,
        "source": "mltxml-parse",
        "frame_rate": fps,
        "timeline": {"name": title, "duration_seconds": round(duration or cursor, 3),
                     "markers": markers, "chapters": [], "titles": [], "clips": clips,
                     "captions": [], "keywords": [], "roles": ["video"]},
        "reframe": {"enabled": False, "aspect": "9:16", "method": "auto_reframe"},
        "export": {"presets": [], "platform_targets": []},
        "gaps": [{"gap_type": "mlt_no_chapter_concept",
                  "description": "MLT has no chapter track; chapters ride as Shotcut markers",
                  "impact": "chapter/marker distinction is lost on round-trip",
                  "recommended_next_step": "treat chapter-typed markers as chapters downstream"}],
        "provenance": {"generated_by": "tools/videoedit/mltxml.py", "tool_version": "1.0"},
    }


def validate(src):
    """Well-formedness check, fcpxml.validate shape. MLT has no DTD, so no dtd_valid level."""
    tmp = None
    if "<mlt" in str(src) and "\n" in str(src):
        tmp = Path(tempfile.mkstemp(suffix=".mlt")[1])
        tmp.write_text(src, encoding="utf-8")
        path = str(tmp)
    else:
        path = str(src)
    xmllint = shutil.which("xmllint")
    try:
        if xmllint:
            proc = subprocess.run([xmllint, "--noout", path], capture_output=True, text=True)
            ok = proc.returncode == 0
            return {"ok": ok, "level": "well_formed" if ok else "invalid",
                    "errors": [] if ok else [ln for ln in proc.stderr.splitlines() if ln.strip()],
                    "tool": "xmllint", "dtd": None}
        text = Path(path).read_text(encoding="utf-8") if Path(path).exists() else str(src)
        ET.fromstring(text)
        return {"ok": True, "level": "well_formed_py", "errors": [], "tool": "ElementTree", "dtd": None}
    except ET.ParseError as exc:
        return {"ok": False, "level": "invalid", "errors": [str(exc)], "tool": "ElementTree", "dtd": None}
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


def _ffmpeg_cutlist_render(pkg, out_path):
    """Single-asset cut-list encode via the concat demuxer. Multi-asset packages are refused."""
    clips = (pkg.get("timeline", {}) or {}).get("clips", []) or []
    refs = {c.get("asset_ref") for c in clips if c.get("asset_ref")}
    if not clips or len(refs) != 1:
        raise LookupError("ffmpeg cut-list encode handles exactly one source asset "
                          f"(package has {len(refs)})")
    ref = refs.pop()
    listfile = Path(tempfile.mkstemp(suffix=".txt")[1])
    lines = []
    for c in sorted(clips, key=lambda c: float(c.get("start_seconds", 0) or 0)):
        src_in = float(c.get("source_in_seconds", c.get("start_seconds", 0)) or 0)
        dur = float(c.get("duration_seconds", 0) or 0)
        lines += [f"file '{ref}'", f"inpoint {src_in}", f"outpoint {src_in + dur}"]
    listfile.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [shutil.which("ffmpeg"), "-hide_banner", "-y", "-f", "concat", "-safe", "0",
           "-i", str(listfile), "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac",
           str(out_path)]
    try:
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT)
    finally:
        listfile.unlink()
    if run.returncode != 0:
        raise RuntimeError(f"ffmpeg exited {run.returncode}: {run.stderr.strip()[-300:]}")


def render(src, out_path, config=None, backend="auto"):
    """Render an .mlt (or edit-package) to a file. Gated on media_render (APP_DRIVING: also
    needs the video_editing_enabled master gate). melt -> ffmpeg cut-list -> honest no-render."""
    allowed, reason = _gate.realization_allowed("media_render", config)
    result = {"rendered": False, "renderer": None, "out_path": None, "backend_chain": [], "gaps": []}
    if not allowed:
        result["gaps"].append({
            "gap_type": "flag_off", "description": reason,
            "impact": "no local render",
            "recommended_next_step": "enable media_render and video_editing_enabled, or open the "
                                     ".mlt in Shotcut/Kdenlive and render there"})
        return result
    is_pkg = isinstance(src, dict)
    order = ["melt", "ffmpeg"] if backend == "auto" else [backend]
    for b in order:
        try:
            if b == "melt":
                if not shutil.which("melt"):
                    raise LookupError("melt not on PATH")
                if is_pkg:
                    tmp = Path(tempfile.mkstemp(suffix=".mlt")[1])
                    tmp.write_text(build(src), encoding="utf-8")
                    mlt_path = str(tmp)
                else:
                    mlt_path = str(src)
                cmd = [shutil.which("melt"), mlt_path, "-consumer",
                       f"avformat:{out_path}", "vcodec=libx264", "acodec=aac"]
                run = subprocess.run(cmd, capture_output=True, text=True,
                                     timeout=SUBPROCESS_TIMEOUT)
                if run.returncode != 0:
                    raise RuntimeError(f"melt exited {run.returncode}: "
                                       f"{run.stderr.strip()[-300:]}")
            elif b == "ffmpeg":
                if not shutil.which("ffmpeg"):
                    raise LookupError("ffmpeg not on PATH")
                pkg = src if is_pkg else parse(src)
                _ffmpeg_cutlist_render(pkg, out_path)
            else:
                raise LookupError(f"unknown backend '{b}'")
        except Exception as exc:
            result["backend_chain"].append({"backend": b, "ok": False, "reason": str(exc)})
            continue
        result["backend_chain"].append({"backend": b, "ok": True})
        result.update({"rendered": True, "renderer": b, "out_path": str(out_path)})
        return result
    result["gaps"].append({
        "gap_type": "no_backend",
        "description": "no render backend could run (see backend_chain)",
        "impact": "no local render",
        "recommended_next_step": "install melt or put ffmpeg on PATH, or open the .mlt in "
                                 "Shotcut/Kdenlive and render there (the shipped default)"})
    return result


def _check(label, cond, failures):
    _check.ran += 1
    print(f"  [{'ok' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)


_check.ran = 0


def selftest():
    failures = []
    pkg = {
        "title": "selftest timeline", "frame_rate": 30,
        "timeline": {
            "duration_seconds": 40.0,
            "clips": [
                {"start_seconds": 0.0, "duration_seconds": 10.0, "name": "a", "asset_ref": "a.mp4"},
                {"start_seconds": 15.0, "duration_seconds": 20.0, "name": "b", "asset_ref": "a.mp4"},
            ],
            "markers": [{"start_seconds": 5.0, "name": "silence 2.0s", "type": "to-do"}],
            "chapters": [{"start_seconds": 15.0, "title": "part two"}],
        },
    }
    xml = build(pkg)
    _check("build emits well-formed XML with LC_NUMERIC=C",
           'LC_NUMERIC="C"' in xml and ET.fromstring(xml) is not None, failures)
    _check("build inserts a blank for the timeline gap", '<blank length="00:00:05.000"/>' in xml,
           failures)
    v = validate(xml)
    _check("validate reports ok (well-formed)", v["ok"] and v["level"].startswith("well_formed"),
           failures)
    _check("validate rejects garbage", validate("<mlt>\n<broken")["ok"] is False, failures)

    back = parse(xml)
    _check("round-trip recovers 2 clips with start/duration",
           [(c["start_seconds"], c["duration_seconds"]) for c in back["timeline"]["clips"]]
           == [(0.0, 10.0), (15.0, 20.0)], failures)
    _check("round-trip recovers title and fps",
           back["title"] == "selftest timeline" and back["frame_rate"] == 30.0, failures)
    _check("round-trip carries marker plus chapter as Shotcut markers",
           len(back["timeline"]["markers"]) == 2
           and back["timeline"]["markers"][1]["name"] == "part two", failures)
    _check("chapter flattening is recorded in gaps[]",
           any(g["gap_type"] == "mlt_no_chapter_concept" for g in back["gaps"]), failures)

    fixture = HERE / "fixtures" / "sample-timeline.mlt"
    fx = parse(str(fixture))
    _check("sample fixture parses to 1 clip and 1 marker",
           len(fx["timeline"]["clips"]) == 1 and len(fx["timeline"]["markers"]) == 1, failures)
    _check("clock helpers round-trip 3661.25s",
           abs(clock_to_sec(sec_to_clock(3661.25)) - 3661.25) < 0.001, failures)

    r = render(pkg, "out.mp4", config={"capabilities": {}})
    _check("render refused while media_render is off (default)",
           not r["rendered"] and r["gaps"][0]["gap_type"] == "flag_off", failures)
    r = render(pkg, "out.mp4", config={"capabilities": {"media_render": {"enabled": True}}})
    _check("media_render alone is not enough (APP_DRIVING needs the master gate)",
           not r["rendered"] and r["gaps"][0]["gap_type"] == "flag_off", failures)
    r = render(pkg, "out.mp4", backend="melt",
               config={"capabilities": {"media_render": {"enabled": True},
                                        "video_editing_enabled": {"enabled": True}}})
    _check("gates open: chain runs and reports the missing backend honestly",
           not r["rendered"] and r["backend_chain"][0]["backend"] == "melt"
           and r["backend_chain"][0]["ok"] is False, failures)

    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["parse", "x" * 300])
    _check(">255-byte path arg -> clean envelope, no traceback (P66 boundary)",
           rc == 1 and "next_step" in buf.getvalue(), failures)

    n = _check.ran
    print(f"selftest: {'PASS' if not failures else 'FAIL'} ({n - len(failures)} of {n} checks)")
    return 0 if not failures else 1


def _main(argv):
    if argv and argv[0] == "--selftest":
        argv = ["selftest"]
    ap = argparse.ArgumentParser(description="Creator OS MLT XML writer/parser (Lane A)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build")
    p.add_argument("package")
    p = sub.add_parser("parse")
    p.add_argument("file")
    p = sub.add_parser("validate")
    p.add_argument("file")
    p = sub.add_parser("render")
    p.add_argument("src")
    p.add_argument("--out", required=True)
    p.add_argument("--backend", default="auto")
    sub.add_parser("selftest")
    args = ap.parse_args(argv)
    if args.cmd == "build":
        print(build(json.loads(Path(args.package).read_text(encoding="utf-8"))))
    elif args.cmd == "parse":
        print(json.dumps(parse(args.file), indent=2))
    elif args.cmd == "validate":
        print(json.dumps(validate(args.file), indent=2))
    elif args.cmd == "render":
        src = args.src
        if src.endswith(".json"):
            src = json.loads(Path(src).read_text(encoding="utf-8"))
        print(json.dumps(render(src, args.out, backend=args.backend), indent=2))
    elif args.cmd == "selftest":
        return selftest()
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
