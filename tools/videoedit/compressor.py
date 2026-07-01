#!/usr/bin/env python3
"""Apple Compressor export-preset library + CLI wrapper (feature 5) — run() is a STUB.

Preset selection (which encode spec fits which platform) works everywhere and is knowledge, so
it is available even off macOS. Actually RUNNING an export shells out to the Compressor CLI on
macOS and is gated behind video_editing_enabled + compressor_presets. Preset specs are keyed to
shared/platform-engine.md. Cross-OS alternative: the Resolve render queue (tools/videoedit/resolve.py).
"""
from __future__ import annotations

import json
import sys

COMPRESSOR_BIN = "/Applications/Compressor.app/Contents/MacOS/Compressor"

# Platform export specs (keyed to shared/platform-engine.md). Spec-only until a .compressorsetting
# is authored for each; these describe the target so the right setting can be chosen or built.
PRESETS = {
    "youtube_longform": {"container": "mp4", "resolution": "3840x2160 or 1920x1080", "fps": "match source",
                          "codec": "H.264/HEVC", "aspect": "16:9", "note": "YouTube 4K/1080 long-form"},
    "youtube_short": {"container": "mp4", "resolution": "1080x1920", "fps": "30 or 60",
                      "codec": "H.264", "aspect": "9:16", "note": "YouTube Short, <=60s"},
    "instagram_reel": {"container": "mp4", "resolution": "1080x1920", "fps": "30",
                       "codec": "H.264", "aspect": "9:16", "note": "Instagram Reel"},
    "tiktok": {"container": "mp4", "resolution": "1080x1920", "fps": "30",
               "codec": "H.264", "aspect": "9:16", "note": "TikTok"},
    "pinterest_video": {"container": "mp4", "resolution": "1000x1500 or 1080x1920", "fps": "30",
                        "codec": "H.264", "aspect": "2:3 or 9:16", "note": "Pinterest video pin"},
}


def presets_for(platform_targets: list) -> dict:
    """Return the export specs for the requested platforms (spec-only; always available)."""
    m = {
        "youtube": ["youtube_longform", "youtube_short"],
        "instagram": ["instagram_reel"],
        "tiktok": ["tiktok"],
        "pinterest": ["pinterest_video"],
    }
    out = {}
    for p in platform_targets or list(m):
        for key in m.get(p, []):
            out[key] = PRESETS[key]
    return out


def run(job_path: str, setting_path: str, out_path: str, batch_name: str = "creator-os") -> dict:
    """Would shell out: Compressor -batchname NAME -jobpath SRC -settingpath X.compressorsetting
    -locationpath OUT. Gated; STUB until video_editing_enabled + compressor_presets are on."""
    raise NotImplementedError(
        "Compressor export is not enabled. Turn on video_editing_enabled + compressor_presets on "
        f"macOS with Compressor installed, then run: {COMPRESSOR_BIN} -batchname {batch_name} "
        f"-jobpath {job_path} -settingpath {setting_path} -locationpath {out_path}"
    )


if __name__ == "__main__":
    targets = sys.argv[1:] or ["youtube", "instagram", "tiktok", "pinterest"]
    print(json.dumps(presets_for(targets), indent=2, ensure_ascii=False))
