#!/usr/bin/env python3
"""Creator OS first-time setup.

Run once after cloning the repository. Creates local data files from their
committed templates, builds the FTS5 keyword cache, and verifies the drift guard.

Usage:
    python3 tools/setup.py

Nothing is overwritten if it already exists.
"""
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import env_paths  # sibling in tools/: venv-aware interpreter + brew-PATH resolution

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


# ── Default dependency install (P50, item 11) ───────────────────────────────
# The free, cross-platform, no-key pip sets. tools/setup.py --install-deps installs all of
# them so the accelerated paths are on by default. Everything still degrades if a set fails;
# base function is stdlib-only. Keyed/paid/native-runtime deps stay opt-in (see docs/DEPENDENCIES.md).
REQUIREMENTS_SETS = [
    ("requirements-crawl.txt", "Web fetch (requests, charset-normalizer)"),
    ("requirements-scraper.txt", "HTML parsing (beautifulsoup4)"),
    ("requirements-render.txt", "Headless browser (playwright)"),
    ("requirements-mcp.txt", "Claude Desktop tool surface (mcp)"),
    ("requirements-videoedit.txt", "Video analysis (scenedetect, av, moviepy, numpy)"),
    ("requirements-transcribe.txt", "Local transcription (faster-whisper, jiwer)"),
    ("requirements-tools.txt", "Tooling accelerators (python-dateutil, sqlite-vec, PyYAML)"),
]


def _pip_install(args: list, python: str | None = None, allow_break_system: bool = False) -> tuple:
    """Run pip with the given args in the target interpreter. Returns (ok, detail). Never raises.
    On a PEP 668 externally-managed interpreter, retries once with --break-system-packages only when
    allow_break_system is set. The .venv path avoids PEP 668 entirely, so it never needs the override."""
    py = python or PYTHON
    try:
        r = subprocess.run(
            [py, "-m", "pip", "install", *args],
            capture_output=True, text=True, timeout=1800,
        )
        if r.returncode == 0:
            return True, ""
        detail = (r.stderr or r.stdout or "").strip()
        if allow_break_system and "externally-managed-environment" in detail:
            r2 = subprocess.run(
                [py, "-m", "pip", "install", "--break-system-packages", *args],
                capture_output=True, text=True, timeout=1800,
            )
            if r2.returncode == 0:
                return True, "installed with --break-system-packages (no .venv available)"
            return False, (r2.stderr or r2.stdout or "").strip()[-400:]
        return False, detail[-400:]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def ensure_venv() -> tuple:
    """Create or locate the repo .venv (the 'private toolbox'). Returns (python_path|None, note).
    Isolating deps in .venv sidesteps PEP 668 on a Homebrew Python and gives the launcher and the
    Claude MCP config a stable absolute interpreter. Creating a venv is allowed even from an
    externally-managed base (PEP 668 only blocks pip into the base). If creation fails (e.g. a
    stripped-down CLT-shim interpreter), returns (None, reason) and the caller does a system install."""
    existing = env_paths.venv_python()
    if existing:
        return str(existing), "using existing .venv"
    venv_dir = ROOT / ".venv"
    try:
        subprocess.run([PYTHON, "-m", "venv", str(venv_dir)],
                       capture_output=True, text=True, timeout=300)
    except Exception as exc:  # noqa: BLE001
        return None, f"could not create .venv ({exc}); using the system Python"
    created = env_paths.venv_python()
    if created:
        return str(created), "created .venv (private toolbox)"
    return None, "could not create .venv; using the system Python"


def _install_playwright_browser(python: str | None = None) -> tuple:
    """Fetch the Chromium binary Playwright needs (only if the package installed in the target
    interpreter). (ok, detail)."""
    py = python or PYTHON
    try:
        probe = subprocess.run(
            [py, "-c", "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('playwright') else 3)"],
            capture_output=True, text=True, timeout=60,
        )
        if probe.returncode == 3:
            return None, "playwright package not installed — skipped browser download"
        r = subprocess.run(
            [py, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, timeout=1800,
        )
        if r.returncode == 0:
            return True, ""
        return False, (r.stderr or r.stdout or "").strip()[-400:]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def install_dependencies() -> list:
    """Install every free, cross-platform pip set + uv + the Playwright browser into a private .venv
    (the 'private toolbox'), so a Homebrew Python's PEP 668 lock never silently blocks the install.
    Returns a list of per-item {item, desc, ok, detail} results; ok=None means skipped. Reports every
    outcome honestly, never silently. System binaries (Node, ffmpeg) are NOT installed here — they need
    the user's shell package manager and are handled by the launcher/doctor."""
    results = []
    venv_py, venv_note = ensure_venv()
    target = venv_py or PYTHON
    allow_break = venv_py is None  # override PEP 668 only when we could not isolate into a .venv
    results.append({"item": ".venv", "desc": "private dependency toolbox",
                    "ok": venv_py is not None, "detail": venv_note})
    for fname, desc in REQUIREMENTS_SETS:
        p = ROOT / fname
        if not p.exists():
            results.append({"item": fname, "desc": desc, "ok": None, "detail": "file not found"})
            continue
        ok, detail = _pip_install(["-r", str(p)], python=target, allow_break_system=allow_break)
        results.append({"item": fname, "desc": desc, "ok": ok, "detail": detail})
    # uv: pip-installable, cross-platform, no sudo. Powers the Google/Wolfram uvx MCP servers.
    venv_uv = Path(target).parent / "uv"
    if venv_uv.exists() or env_paths.which("uv"):
        results.append({"item": "uv", "desc": "uvx runtime", "ok": None, "detail": "already installed"})
    else:
        ok, detail = _pip_install(["uv"], python=target, allow_break_system=allow_break)
        results.append({"item": "uv", "desc": "uvx runtime for Google/Wolfram MCP servers", "ok": ok, "detail": detail})
    # Playwright browser binary (only if the package landed in the target interpreter).
    pw_ok, pw_detail = _install_playwright_browser(target)
    results.append({"item": "playwright chromium", "desc": "Headless browser binary", "ok": pw_ok, "detail": pw_detail})
    return results


def run_install_deps(as_json: bool = False) -> int:
    """CLI entry for --install-deps. Prints per-item results; exit 0 unless a set hard-failed.
    In --json mode stdout carries ONLY the JSON object (the wizard parses it), no preamble."""
    if not as_json:
        _say("Installing Creator OS dependencies (free, cross-platform, no keys)...")
        _say("These install into a private .venv toolbox inside the repo (never committed), so a")
        _say("Homebrew Python's install lock cannot block them. Base function never depends on it.\n")
    results = install_dependencies()
    if as_json:
        print(json.dumps({"results": results}, indent=2))
    else:
        for r in results:
            if r["ok"] is True:
                _ok(f"{r['item']} — {r['desc']}")
            elif r["ok"] is None:
                _skip(f"{r['item']} ({r['detail']})")
            else:
                _say(f"  [fail] {r['item']} — {r['desc']}")
                if r["detail"]:
                    _say(f"         {r['detail']}")
        _say("\nSystem binaries (Node.js, ffmpeg) are NOT installed here — they need your OS package")
        _say("manager. Run 'python3 tools/transcribe.py doctor' for the exact command for your machine,")
        _say("or use the wizard's 'Set up my computer' screen (python3 tools/wizard.py).")
    hard_fail = any(r["ok"] is False for r in results)
    return 1 if hard_fail else 0


def check_python() -> None:
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 11):
        _say(f"ERROR: Python 3.11 or later required (you have {major}.{minor}).")
        sys.exit(1)
    _ok(f"Python {major}.{minor}")


def check_platform() -> None:
    if sys.platform != "darwin":
        return
    arch = platform.machine()
    _ok(f"macOS detected ({arch})")
    if arch == "arm64":
        result = subprocess.run(
            ["sysctl", "-n", "sysctl.proc_translated"],
            capture_output=True, text=True,
        )
        if result.stdout.strip() == "1":
            _say("  [warn] Python is running under Rosetta (x86_64 emulation on arm64 hardware).")
            _say("         For best performance, install a native arm64 Python via Homebrew:")
            _say("           brew install python@3.13")
            _say("         Then rerun: /opt/homebrew/bin/python3 tools/setup.py")
            return
    _say("  macOS tips:")
    _say("    If 'python3' is not found, install the python.org universal2 .pkg (notarized, Tk")
    _say("    bundled), or via Homebrew (https://brew.sh):")
    _say("      brew install python@3.13")
    _say("    After installing requirements-render.txt, run once to fetch arm64 Chromium:")
    _say("      python3 -m playwright install chromium")


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

  2. Install the optional dependencies (free, cross-platform, no keys):
       python3 tools/setup.py --install-deps
       (or use the wizard's "Set up my computer" screen: python3 tools/wizard.py)
       For Node.js / ffmpeg (system binaries), run: python3 tools/transcribe.py doctor

  3. Enable capabilities as you set them up:
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


def _selftest() -> int:
    """Offline checks for the venv-first install mechanism (no network, no real pip install)."""
    import tempfile
    checks = []

    def ok(cond, msg):
        checks.append((bool(cond), msg))

    with tempfile.TemporaryDirectory() as td:
        vd = Path(td) / ".venv"
        r = subprocess.run([PYTHON, "-m", "venv", str(vd)], capture_output=True, text=True, timeout=300)
        vpy = env_paths.venv_python(td)
        ok(r.returncode == 0 and vpy is not None, "python -m venv creates a resolvable .venv (private toolbox)")
        if vpy:
            pv = subprocess.run([str(vpy), "-m", "pip", "--version"], capture_output=True, text=True, timeout=60)
            ok(pv.returncode == 0, "the .venv has pip (a usable install target)")
    # _pip_install never raises on a bad interpreter and reports failure honestly.
    okf, _ = _pip_install(["x"], python="/nonexistent/python/xyz")
    ok(okf is False, "_pip_install returns (False, detail) on a bad interpreter, never raises")

    passed = sum(1 for c, _ in checks if c)
    for c, m in checks:
        if not c:
            print(f"  [FAIL] {m}")
    print(f"setup selftest: {passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


def main() -> None:
    argv = sys.argv[1:]
    if "--selftest" in argv:
        sys.exit(_selftest())
    if "--install-deps" in argv:
        # Standalone dependency install (also used by the wizard's "Set up my computer" screen).
        sys.exit(run_install_deps(as_json="--json" in argv))

    _say("Creator OS — first-time setup")
    _say("=" * 40)

    check_python()
    check_platform()

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
