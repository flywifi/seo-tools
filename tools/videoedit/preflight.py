#!/usr/bin/env python3
"""Detect what the video-editing bridge can actually do on THIS machine.

Reports OS, Python version, which editors/tools are present, which flags are on, and which
lanes are usable — with honest degrade notes. Mirrors the get_capabilities live-check pattern.
Nothing here launches an app; it only inspects.

CLI: python3 tools/videoedit/preflight.py [--json]
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
import videoedit_validate as gate  # noqa: E402


def _python_ok() -> bool:
    # Resolve's fusionscript bridge is stable on 3.10 to 3.12; 3.13+ can crash older builds.
    return (3, 10) <= sys.version_info[:2] <= (3, 12)


def _otio_available() -> bool:
    try:
        import opentimelineio  # noqa: F401
        return True
    except Exception:
        return False


def _importable(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _resolve_present() -> dict:
    """Best-effort detection of a Resolve install + its fusionscript lib, per OS."""
    plat = sys.platform
    lib = None
    app = None
    if plat == "darwin":
        app = Path("/Applications/DaVinci Resolve/DaVinci Resolve.app")
        lib = Path("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so")
    elif plat.startswith("win"):
        lib = Path(r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll")
    else:
        for cand in ("/opt/resolve/libs/Fusion/fusionscript.so", "/home/resolve/libs/Fusion/fusionscript.so"):
            if Path(cand).exists():
                lib = Path(cand)
                break
        lib = lib or Path("/opt/resolve/libs/Fusion/fusionscript.so")
    return {
        "app_present": bool(app and app.exists()) if app else None,
        "lib_present": bool(lib and lib.exists()),
        "lib_path": str(lib) if lib else None,
        "note": "Studio (paid) required for external scripting; free vs Studio is confirmed only at connect time.",
    }


def preflight(config: dict | None = None) -> dict:
    cfg = config if config is not None else gate.load_config()
    plat = sys.platform
    is_mac = plat == "darwin"

    tools = {
        "xmllint": bool(shutil.which("xmllint")),
        "compressor": is_mac and Path("/Applications/Compressor.app/Contents/MacOS/Compressor").exists(),
        "final_cut_pro": is_mac and Path("/Applications/Final Cut Pro.app").exists(),
        "commandpost": is_mac and Path("/Applications/CommandPost.app").exists(),
        "otio": _otio_available(),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "melt": bool(shutil.which("melt")),
        "auto_editor": bool(shutil.which("auto-editor")),
        "av": _importable("av"),
        "scenedetect": _importable("scenedetect"),
        "moviepy": _importable("moviepy"),
    }
    resolve = _resolve_present()

    flags = {
        name: gate.flag_enabled(cfg, name)
        for name in (
            "video_editing_enabled", "resolve_scripting", "fcpxml_timeline_export",
            "caption_roundtrip", "shorts_reframe", "marker_intel_import",
            "compressor_presets", "motion_template_fill", "commandpost_macros", "chapter_sync",
            "mlt_timeline_export", "media_render",
        )
    }

    lanes = {
        # File interchange always works (just files); it is the universal substrate.
        "file_interchange": True,
        # Live Resolve needs the flag, the lib, and a supported Python.
        "resolve_live": bool(flags["resolve_scripting"] and resolve["lib_present"] and _python_ok()),
        # Compressor run needs macOS + the app + the flag + master gate.
        "compressor_run": bool(is_mac and tools["compressor"] and flags["compressor_presets"] and flags["video_editing_enabled"]),
        # FCP import needs macOS + FCP present.
        "fcp_import": bool(is_mac and tools["final_cut_pro"]),
        # Media analysis lanes (P29): no flag, availability is tool presence; both degrade to
        # the transcript floor which is always available.
        "silence_scan_media": bool(tools["ffmpeg"] or tools["av"]),
        "scene_scan_media": bool(tools["scenedetect"] or tools["ffmpeg"]),
        # Reframe render needs the flag plus a backend; geometry itself is always available.
        "reframe_render": bool(flags["shorts_reframe"] and (tools["moviepy"] or tools["ffmpeg"])),
        # MLT export is a plain file-writing flag; melt render is app-driving (master gate).
        "mlt_export": bool(flags["mlt_timeline_export"]),
        "melt_render": bool(tools["melt"] and flags["media_render"] and flags["video_editing_enabled"]),
    }

    notes = []
    if not tools["xmllint"]:
        notes.append("xmllint not found: FCPXML is checked for well-formedness in pure Python (no DTD validation).")
    if not _python_ok():
        notes.append(f"Python {sys.version_info.major}.{sys.version_info.minor}: pin 3.10 to 3.12 for the Resolve API bridge.")
    if not is_mac:
        notes.append("Non-macOS: Final Cut Pro and Compressor are unavailable; use the Resolve lane or hand off FCPXML files.")
    if flags["resolve_scripting"] and not resolve["lib_present"]:
        notes.append("resolve_scripting is on but no Resolve fusionscript library was found; degrading to file interchange.")
    if not lanes["silence_scan_media"]:
        notes.append("No ffmpeg and no av: silence-scan degrades to transcript gap analysis (the P28 floor).")
    if not lanes["scene_scan_media"]:
        notes.append("No scenedetect and no ffmpeg: scene-scan degrades to transcript chapter heuristics (the P28 floor).")
    if tools["ffmpeg"] and not tools["scenedetect"]:
        notes.append("scene-scan will use ffmpeg scdet (luma-only; isoluminant cuts can be missed). pip install scenedetect for the recommended detector.")
    if flags["shorts_reframe"] and not (tools["moviepy"] or tools["ffmpeg"]):
        notes.append("shorts_reframe is on but no MoviePy or ffmpeg was found; crop parameters are emitted without a local render.")
    if flags["media_render"] and not flags["video_editing_enabled"]:
        notes.append("media_render is on but the video_editing_enabled master gate is off; no render will run.")

    return {
        "os": plat,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "python_ok_for_resolve": _python_ok(),
        "tools": tools,
        "resolve": resolve,
        "flags": flags,
        "lanes": lanes,
        "notes": notes,
    }


def main(argv) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Video-editing preflight")
    ap.add_argument("--json", action="store_true")
    ap.parse_args(argv)
    print(json.dumps(preflight(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
