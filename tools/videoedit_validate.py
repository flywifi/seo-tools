#!/usr/bin/env python3
"""Shared gate + validation helper for the Creator OS video-editing bridge.

Both the atom/MCP surface (which reports) and the local realization tools (which enforce)
import this. It answers two questions:

  1. Is a given realization ALLOWED right now? SPEC generation is always allowed and never calls
     this. FILE generation (FCPXML/OTIO) needs that feature's own flag. Driving an editor app
     additionally needs the master flag `video_editing_enabled`.
     `realization_allowed(feature, config)` returns (ok, reason).
  2. Is a generated FCPXML VALID? `validate_fcpxml(...)` delegates to tools/videoedit/fcpxml.py
     (DTD-valid when a DTD is found, else well-formed) and returns the ok/level/errors contract.

Stdlib only. No network. Config reading matches the rest of Creator OS (object-form flag in the
committed creator-os-config.json, bare-bool override in the gitignored .local.json).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from pathlib import Path as pathlib_Path

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
    "media_render",
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


def _selftest() -> int:
    """Offline proof of the two contracts this module owns (P73 D1-2: it had NO selftest and was
    absent from the sweep, so `fcpxml.validate` had no executed test path anywhere in the repo).
    Stdlib only; temp files; no config writes."""
    import tempfile
    failures = []

    def ok(label, cond):
        print(("ok   " if cond else "FAIL ") + label)
        if not cond:
            failures.append(label)

    # 1) The gate. App-driving features need the master flag; pure file/spec features never do.
    off = {"capabilities": {"video_editing_enabled": False}}
    for feature in sorted(APP_DRIVING):
        allowed, reason = realization_allowed(feature, off)
        ok(f"gate refuses {feature} with the master flag off", allowed is False and bool(reason))
    on_no_master = {"capabilities": {"video_editing_enabled": False, "timeline_spec": True}}
    allowed, _ = realization_allowed("timeline_spec", on_no_master)
    ok("non-app-driving feature realizes on its own flag, master not required", allowed is True)
    refused, why = realization_allowed("timeline_spec", off)
    ok("...but is refused when its own flag is off, with the degraded-behavior pointer",
       refused is False and "timeline_spec" in why)
    unknown, reason = realization_allowed("no_such_feature_xyz", off)
    ok("unknown feature is answered, not crashed", isinstance(unknown, bool) and bool(reason))

    # 2) The validator. Well-formed FCPXML passes; malformed XML fails with errors, never raises.
    with tempfile.TemporaryDirectory() as td:
        good = pathlib_Path(td) / "good.fcpxml"
        good.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<fcpxml version="1.9">'
                        '<resources/><library/></fcpxml>\n', encoding="utf-8")
        res = validate_fcpxml(str(good))
        ok("well-formed fcpxml validates ok", res.get("ok") is True and "level" in res)
        bad = pathlib_Path(td) / "bad.fcpxml"
        bad.write_text("<fcpxml><unclosed></fcpxml>\n", encoding="utf-8")
        res_bad = validate_fcpxml(str(bad))
        ok("malformed fcpxml fails with errors, no exception",
           res_bad.get("ok") is False and bool(res_bad.get("errors")))
        missing = validate_fcpxml(str(pathlib_Path(td) / "absent.fcpxml"))
        ok("missing file is reported, not raised", missing.get("ok") is False)

    print(f"\nvideoedit_validate selftest: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    raise SystemExit(_main(sys.argv[1:]))
