#!/usr/bin/env python3
"""DaVinci Resolve live-control adapter (Lane B) — STUB, feature-flagged off.

External Resolve scripting requires Resolve STUDIO (paid) and Resolve running. This module
holds the bootstrap (env vars / paths per OS from the shipped README) and the operation
surface, but every live method raises NotImplementedError until `video_editing_enabled` +
`resolve_scripting` are on AND a real implementation lands. Until then the system degrades to
file interchange (generate FCPXML/OTIO for manual import). See shared/videoedit-engine.md.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Canonical per-OS bootstrap (from Developer/Scripting/README.txt).
_ENV = {
    "darwin": {
        "RESOLVE_SCRIPT_API": "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting",
        "RESOLVE_SCRIPT_LIB": "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so",
    },
    "win32": {
        "RESOLVE_SCRIPT_API": r"%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting",
        "RESOLVE_SCRIPT_LIB": r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll",
    },
    "linux": {
        "RESOLVE_SCRIPT_API": "/opt/resolve/Developer/Scripting",
        "RESOLVE_SCRIPT_LIB": "/opt/resolve/libs/Fusion/fusionscript.so",
    },
}


def bootstrap_env() -> dict:
    """Set RESOLVE_SCRIPT_API / RESOLVE_SCRIPT_LIB / PYTHONPATH if not already present.
    Returns the resolved values. Does NOT import the API (that needs Resolve running)."""
    key = "linux" if sys.platform.startswith("linux") else sys.platform
    env = _ENV.get(key, _ENV["linux"])
    api = os.environ.get("RESOLVE_SCRIPT_API") or os.path.expandvars(env["RESOLVE_SCRIPT_API"])
    lib = os.environ.get("RESOLVE_SCRIPT_LIB") or os.path.expandvars(env["RESOLVE_SCRIPT_LIB"])
    os.environ.setdefault("RESOLVE_SCRIPT_API", api)
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", lib)
    modules = str(Path(api) / "Modules")
    if modules not in os.environ.get("PYTHONPATH", ""):
        os.environ["PYTHONPATH"] = os.environ.get("PYTHONPATH", "") + os.pathsep + modules
    return {"RESOLVE_SCRIPT_API": api, "RESOLVE_SCRIPT_LIB": lib, "PYTHONPATH_added": modules}


_RECIPE = (
    "Resolve live control is not enabled. Turn on video_editing_enabled + resolve_scripting, "
    "run Resolve Studio, pin Python 3.10 to 3.12, then implement via: "
    "bootstrap_env(); import DaVinciResolveScript as dvr; resolve = dvr.scriptapp('Resolve'); "
    "pm = resolve.GetProjectManager(); project = pm.GetCurrentProject(); "
    "mp = project.GetMediaPool()."
)


def import_edit_package(fcpxml_or_otio_path: str, timeline_name: str = "") -> dict:
    """Would call MediaPool.ImportTimelineFromFile(path, {timelineName})."""
    raise NotImplementedError(_RECIPE)


def add_markers(markers: list) -> dict:
    """Would call Timeline.AddMarker(frameId, color, name, note, duration, customData) per marker."""
    raise NotImplementedError(_RECIPE)


def queue_render(preset: str, out_dir: str) -> dict:
    """Would call Project.LoadRenderPreset / SetRenderSettings / AddRenderJob / StartRendering."""
    raise NotImplementedError(_RECIPE)


def export_timeline(out_path: str, export_type: str = "EXPORT_FCPXML_1_10") -> dict:
    """Would call Timeline.Export(out_path, resolve.<export_type>)."""
    raise NotImplementedError(_RECIPE)


if __name__ == "__main__":
    import json
    print(json.dumps({"bootstrap": bootstrap_env(), "note": "stub; live methods raise NotImplementedError"}, indent=2))
