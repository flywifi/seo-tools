#!/usr/bin/env python3
"""Shared gate + validation helper for the Creator OS video-editing bridge.

Both the atom/MCP surface (which reports) and the local realization tools (which enforce)
import this. It answers two questions:

  1. Is a given realization ALLOWED right now? File/spec generation is always allowed;
     driving an editor app needs the master flag `video_editing_enabled` plus the feature/lane
     flag. `realization_allowed(feature, config)` returns (ok, reason).
  2. Is a generated FCPXML VALID? `validate_fcpxml(...)` delegates to tools/videoedit/fcpxml.py
     (DTD-valid when a DTD is found, else well-formed) and returns the ok/level/errors contract.

Stdlib only. No network. Config reading matches the rest of Creator OS (object-form flag in the
committed creator-os-config.json, bare-bool override in the gitignored .local.json).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "creator-os-config.json"
CONFIG_LOCAL_PATH = ROOT / "creator-os-config.local.json"

sys.path.insert(0, str(Path(__file__).resolve().parent / "videoedit"))
import fcpxml as _fcpxml  # noqa: E402

# App-driving features (need the master gate). Pure file/spec features are not listed —
# they are always allowed.
APP_DRIVING = {
    "resolve_scripting",
    "compressor_presets",
    "commandpost_macros",
    "motion_template_fill",
}


def load_config() -> dict:
    base: dict = {}
    try:
        base = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    if CONFIG_LOCAL_PATH.exists():
        try:
            local = json.loads(CONFIG_LOCAL_PATH.read_text(encoding="utf-8"))
            for k, v in local.get("capabilities", {}).items():
                base.setdefault("capabilities", {})[k] = v
        except (OSError, json.JSONDecodeError):
            pass
    return base


def flag_enabled(config: dict, name: str) -> bool:
    caps = config.get("capabilities", {}) if isinstance(config, dict) else {}
    meta = caps.get(name)
    if isinstance(meta, dict):
        return bool(meta.get("enabled", False))
    return bool(meta)


def video_editing_enabled(config: dict | None = None) -> bool:
    return flag_enabled(config if config is not None else load_config(), "video_editing_enabled")


def realization_allowed(feature: str, config: dict | None = None) -> tuple[bool, str]:
    """Can `feature` be REALIZED (file written / app driven) right now?

    Spec generation is always allowed and does not call this. File generation (FCPXML/OTIO)
    is allowed whenever the feature flag is on. Driving an editor app additionally needs the
    master `video_editing_enabled` gate.
    """
    cfg = config if config is not None else load_config()
    if not flag_enabled(cfg, feature):
        return False, (
            f"{feature} is off. The spec is still produced; enable {feature} to realize it "
            f"(see degraded_behavior.{feature}_disabled)."
        )
    if feature in APP_DRIVING and not flag_enabled(cfg, "video_editing_enabled"):
        return False, (
            f"{feature} needs the master gate video_editing_enabled, which is off. Nothing "
            f"launches or scripts an editor app until it is on."
        )
    return True, "allowed"


def validate_fcpxml(src: str, dtd_path: str | None = None) -> dict:
    """Delegate to tools/videoedit/fcpxml.validate; returns {ok, level, errors, tool, dtd}."""
    return _fcpxml.validate(src, dtd_path)


def _main(argv) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="video-editing gate + validation helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate")
    g.add_argument("feature")
    vv = sub.add_parser("validate")
    vv.add_argument("file")
    vv.add_argument("--dtd")
    a = ap.parse_args(argv)
    if a.cmd == "gate":
        ok, reason = realization_allowed(a.feature)
        print(json.dumps({"feature": a.feature, "ok": ok, "reason": reason}, indent=2))
    elif a.cmd == "validate":
        print(json.dumps(validate_fcpxml(a.file, a.dtd), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
