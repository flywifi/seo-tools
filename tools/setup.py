#!/usr/bin/env python3
"""Creator OS first-time setup.

Run once after cloning the repository. Creates local data files from their
committed templates, builds the FTS5 keyword cache, and verifies the drift guard.

Usage:
    python3 tools/setup.py

Nothing is overwritten if it already exists.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def _say(msg: str) -> None:
    print(msg, flush=True)


def _ok(label: str) -> None:
    print(f"  [ok] {label}", flush=True)


def _created(label: str) -> None:
    print(f"  [new] {label}", flush=True)


def _skip(label: str) -> None:
    print(f"  [skip] {label} — already exists", flush=True)


def _run(cmd: list) -> int:
    result = subprocess.run(cmd, cwd=str(ROOT))
    return result.returncode


def check_python() -> None:
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 11):
        _say(f"ERROR: Python 3.11 or later required (you have {major}.{minor}).")
        sys.exit(1)
    _ok(f"Python {major}.{minor}")


def create_local_copy(source_path: Path, dest_path: Path, label: str) -> None:
    if dest_path.exists():
        _skip(label)
        return
    shutil.copy2(source_path, dest_path)
    _created(label)


def create_config_local() -> None:
    """Create creator-os-config.local.json with all capabilities false."""
    dest = ROOT / "creator-os-config.local.json"
    if dest.exists():
        _skip("creator-os-config.local.json")
        return
    stub = {
        "_comment": "Your local capability flags. These win over creator-os-config.json defaults.",
        "_hint": "Set any capability to true after completing its setup step. git pull never touches this file.",
        "capabilities": {
            "mcp_server": False,
            "competitor_snapshots": False,
            "keyword_cache": False,
            "playwright": False,
            "youtube_api": False,
            "instagram_api": False,
            "tiktok_api": False,
            "voice_profile": False,
            "channel_context": False,
        },
    }
    dest.write_text(json.dumps(stub, indent=2) + "\n", encoding="utf-8")
    _created("creator-os-config.local.json")


def create_voice_profile_local() -> None:
    source = ROOT / "pipeline" / "user-context" / "voice-profile.json"
    dest = ROOT / "pipeline" / "user-context" / "voice-profile.local.json"
    if dest.exists():
        _skip("pipeline/user-context/voice-profile.local.json")
        return
    # Create a clean copy with empty arrays
    stub = {
        "_comment": "Your real phrases and voice patterns. voice-engine.md loads this file first.",
        "_gitignore_note": "This file is gitignored. Add as many phrases as you like — git pull never overwrites it.",
        "actual_phrases": [],
        "opening_hooks": [],
        "cta_patterns": [],
        "signing_off_phrases": [],
        "phrases_to_avoid": [],
        "last_updated": None,
        "notes": "Add real phrases as content is produced. Pull from approved captions, pinned comments, and first-person writing. Even 5 to 10 entries improve authenticity significantly.",
    }
    dest.write_text(json.dumps(stub, indent=2) + "\n", encoding="utf-8")
    _created("pipeline/user-context/voice-profile.local.json")


def create_content_calendar_local() -> None:
    dest = ROOT / "pipeline" / "user-context" / "content-calendar.local.json"
    if dest.exists():
        _skip("pipeline/user-context/content-calendar.local.json")
        return
    stub = {
        "_comment": "Your real content calendar entries. calendar-slot checks this file first.",
        "_gitignore_note": "This file is gitignored. git pull never overwrites it.",
        "entries": [],
        "last_updated": None,
        "notes": "Each entry: { title, pillar, publish_target_date (ISO 8601), stage (idea/scripted/filmed/edited/scheduled/published), platform_targets (array), linked_deal_id (null if organic) }",
    }
    dest.write_text(json.dumps(stub, indent=2) + "\n", encoding="utf-8")
    _created("pipeline/user-context/content-calendar.local.json")


def create_channel_context_local() -> None:
    source = ROOT / "pipeline" / "user-context" / "channel-context.json"
    dest = ROOT / "pipeline" / "user-context" / "channel-context.local.json"
    create_local_copy(source, dest, "pipeline/user-context/channel-context.local.json")


def create_setup_context_local() -> None:
    source = ROOT / "pipeline" / "user-context" / "setup-context.json"
    dest = ROOT / "pipeline" / "user-context" / "setup-context.local.json"
    create_local_copy(source, dest, "pipeline/user-context/setup-context.local.json")


def build_cache() -> None:
    cache_script = ROOT / "shared" / "cache" / "cache.py"
    if not cache_script.exists():
        _say("  [warn] shared/cache/cache.py not found — skipping cache build.")
        return
    db = ROOT / "shared" / "cache" / "index.local.db"
    if db.exists():
        _skip("keyword cache (index.local.db already built)")
        return
    _say("  Building FTS5 keyword cache (this takes a few seconds)...")
    rc = _run([PYTHON, str(cache_script), "--build"])
    if rc == 0:
        _ok("keyword cache built")
    else:
        _say("  [warn] Cache build exited with errors. Run manually: python3 shared/cache/cache.py --build")


def run_drift_guard() -> None:
    sync_script = ROOT / "tools" / "sync_check.py"
    if not sync_script.exists():
        _say("  [warn] tools/sync_check.py not found — skipping drift check.")
        return
    rc = _run([PYTHON, str(sync_script)])
    if rc == 0:
        _ok("drift guard clean")
    else:
        _say("  [warn] Drift guard reported issues. Review the output above and fix before using the system.")


def print_next_steps() -> None:
    _say("""
Next steps:
  1. Fill in your local data files (all gitignored — never committed):
       pipeline/user-context/channel-context.local.json   — subscriber count, avg views
       pipeline/user-context/voice-profile.local.json     — add real phrases as you produce content
       pipeline/user-context/content-calendar.local.json  — add upcoming video entries

  2. Enable capabilities as you set them up:
       Edit creator-os-config.local.json and set "keyword_cache": true after building the cache.
       Set "mcp_server": true after configuring Claude Desktop.
       Each flag's "requires" field in creator-os-config.json explains what to install.

  3. For Claude Projects (no install needed):
       Follow docs/DEPLOYMENT.md Option B — upload the 8 files from
       implementation/claude/project/knowledge/ and paste the system prompt.

  4. To pull future updates:
       python3 tools/update.py
       (or: git pull origin main && python3 tools/sync_check.py)

  Setup complete.
""")


def main() -> None:
    _say("Creator OS — first-time setup")
    _say("=" * 40)

    check_python()

    _say("\nCreating local data files...")
    create_config_local()
    create_voice_profile_local()
    create_content_calendar_local()
    create_channel_context_local()
    create_setup_context_local()

    _say("\nBuilding keyword cache...")
    build_cache()

    _say("\nRunning drift guard...")
    run_drift_guard()

    print_next_steps()


if __name__ == "__main__":
    main()
