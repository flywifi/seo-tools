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


_PEP668_REFUSAL = ("this interpreter refuses global installs (PEP 668) and Creator OS never "
                   "installs machine-wide; run 'python3 tools/setup.py --install-deps' to "
                   "create the repo's private .venv, then retry")

# P93: the .venv could not be created, so there is nowhere user-scoped to install. Creator OS
# refuses rather than falling back to the base interpreter, whose site-packages is shared with
# every other user of the machine (docs/INSTALL-SCOPE.md).
_NO_VENV_REFUSAL = ("refused: the repo's private .venv could not be created and Creator OS never "
                    "installs into a machine-wide site-packages. Install a user-scoped Python "
                    "(curl -LsSf https://astral.sh/uv/install.sh | sh, then uv python install "
                    "3.12) and rerun with that interpreter: python3.12 tools/setup.py "
                    "--install-deps")


def _pip_install(args: list, python: str | None = None) -> tuple:
    """Run pip with the given args in the target interpreter. Returns (ok, detail). Never
    raises. P93: on a PEP 668 externally-managed interpreter this REFUSES with the remedy --
    Creator OS never writes into a machine-wide site-packages; the repo .venv is the only
    install target (docs/INSTALL-SCOPE.md)."""
    py = python or PYTHON
    try:
        r = subprocess.run(
            [py, "-m", "pip", "install", *args],
            capture_output=True, text=True, timeout=1800,
        )
        if r.returncode == 0:
            return True, ""
        detail = (r.stderr or r.stdout or "").strip()
        if "externally-managed-environment" in detail:
            return False, _PEP668_REFUSAL
        return False, detail[-400:]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def ensure_venv() -> tuple:
    """Create or locate the repo .venv (the 'private toolbox'). Returns (python_path|None, note).
    Isolating deps in .venv sidesteps PEP 668 on a Homebrew Python and gives the launcher and the
    Claude MCP config a stable absolute interpreter. Creating a venv is allowed even from an
    externally-managed base (PEP 668 only blocks pip into the base). If creation fails (e.g. a
    stripped-down CLT-shim interpreter), returns (None, reason) and the caller REFUSES to install:
    P93 removed the system-install fallback entirely, because a base interpreter that is merely
    machine-wide (a python.org framework build, /usr/local) is not PEP 668 marked, so pip would
    have succeeded straight into a shared site-packages. The .venv is the only install target
    (docs/INSTALL-SCOPE.md)."""
    existing = env_paths.venv_python()
    if existing:
        return str(existing), "using existing .venv"
    venv_dir = ROOT / ".venv"
    try:
        subprocess.run([PYTHON, "-m", "venv", str(venv_dir)],
                       capture_output=True, text=True, timeout=300)
    except Exception as exc:  # noqa: BLE001
        return None, f"could not create .venv ({exc})"
    created = env_paths.venv_python()
    if created:
        return str(created), "created .venv (private toolbox)"
    return None, "could not create .venv"


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
    results.append({"item": ".venv", "desc": "private dependency toolbox",
                    "ok": venv_py is not None, "detail": venv_note})
    if venv_py is None:
        # P93: no .venv means NO install. There is no base-interpreter fallback: pip into the base
        # would land in whatever site-packages that interpreter owns, which on a python.org or
        # /usr/local build is machine-wide AND not PEP 668 marked, so nothing would have refused it.
        for fname, desc in REQUIREMENTS_SETS:
            results.append({"item": fname, "desc": desc, "ok": False, "detail": _NO_VENV_REFUSAL})
        results.append({"item": "uv", "desc": "uvx runtime", "ok": False, "detail": _NO_VENV_REFUSAL})
        results.append({"item": "playwright chromium", "desc": "Headless browser binary",
                        "ok": None, "detail": "skipped: no .venv to install into"})
        return results
    target = venv_py
    for fname, desc in REQUIREMENTS_SETS:
        p = ROOT / fname
        if not p.exists():
            results.append({"item": fname, "desc": desc, "ok": None, "detail": "file not found"})
            continue
        ok, detail = _pip_install(["-r", str(p)], python=target)
        results.append({"item": fname, "desc": desc, "ok": ok, "detail": detail})
    # uv: pip-installable, cross-platform, no sudo. Powers the Google/Wolfram uvx MCP servers.
    venv_uv = Path(target).parent / "uv"
    if venv_uv.exists() or env_paths.which("uv"):
        results.append({"item": "uv", "desc": "uvx runtime", "ok": None, "detail": "already installed"})
    else:
        ok, detail = _pip_install(["uv"], python=target)
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
    if (major, minor) < env_paths.PYTHON_FLOOR:
        floor = ".".join(map(str, env_paths.PYTHON_FLOOR))
        _say(f"ERROR: Python {floor} or later required (you have {major}.{minor}); numpy 2.5 and the "
             f"video tooling are validated on {floor}, and Resolve's scripting bridge caps at 3.12.")
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
            _say("         For best performance, install a native arm64 Python. User-only route")
            _say("         (docs/INSTALL-SCOPE.md): curl -LsSf https://astral.sh/uv/install.sh | sh")
            _say("         then: uv python install 3.12   (lands in ~/.local, native arm64)")
            _say("         Machine-wide alternative (affects the whole computer):")
            _say("           brew install python@3.12")
            _say("         Then rerun tools/setup.py with the new interpreter.")
            return
    _say("  macOS tips:")
    _say("    If 'python3' is not found: the user-only route (docs/INSTALL-SCOPE.md) is the uv")
    _say("    installer: curl -LsSf https://astral.sh/uv/install.sh | sh, then uv python install 3.12.")
    _say("    Machine-wide alternatives (affect the whole computer): the python.org universal2 .pkg")
    _say("    (notarized, Tk bundled), or Homebrew (https://brew.sh): brew install python@3.12")
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
        pip_expected = True
        if r.returncode != 0 and "ensurepip" in (r.stderr or ""):
            # P91: a build with a broken ensurepip (seen in a standalone 3.14 rc) cannot prove
            # the pip check either way; retry without pip so the RESOLVABILITY and floor-gating
            # checks still run, and say so plainly instead of failing a check this build cannot
            # test. The real installer keeps pip and would fail loudly on such a build.
            print("  [note] ensurepip is broken in this interpreter build; venv retried "
                  "--without-pip and the pip check is skipped here")
            pip_expected = False
            r = subprocess.run([PYTHON, "-m", "venv", "--without-pip", str(vd)],
                               capture_output=True, text=True, timeout=300)
        vpy = env_paths.venv_python(td)
        cand = next((c for c in (vd / "bin" / "python3", vd / "Scripts" / "python.exe")
                     if c.exists()), None)
        cand_runs = False
        if cand is not None:
            cr = subprocess.run([str(cand), "-c", "pass"], capture_output=True, timeout=60)
            cand_runs = cr.returncode == 0
        if r.returncode == 0 and not cand_runs:
            # P91: this interpreter BUILD creates venvs whose own python cannot execute (seen
            # in a standalone 3.14 rc: "Could not find platform independent libraries").
            # env_paths refusing such a venv is its documented behavior ("a venv is selected
            # only when it RUNS", P81 B-5), so resolvability is unprovable here -- skipped
            # with this printed reason, never silently passed. A real resolver regression
            # still fails: its candidate executes fine and vpy would still be None.
            print("  [note] this interpreter build creates venvs whose python cannot run; "
                  "env_paths correctly refuses it and the resolvability check is skipped here")
        elif sys.version_info[:2] >= env_paths.PYTHON_FLOOR:
            ok(r.returncode == 0 and vpy is not None, "python -m venv creates a resolvable .venv (private toolbox)")
        else:
            # P81 B-5: env_paths now refuses a below-floor venv; a venv built from a below-floor
            # interpreter is correctly invisible to the interpreter picker.
            ok(r.returncode == 0 and vpy is None,
               "a below-floor venv is created but refused by the interpreter picker (P81 B-5)")
        if vpy and pip_expected:
            pv = subprocess.run([str(vpy), "-m", "pip", "--version"], capture_output=True, text=True, timeout=60)
            ok(pv.returncode == 0, "the .venv has pip (a usable install target)")
    # _pip_install never raises on a bad interpreter and reports failure honestly.
    okf, _ = _pip_install(["x"], python="/nonexistent/python/xyz")
    ok(okf is False, "_pip_install returns (False, detail) on a bad interpreter, never raises")
    # P93: Creator OS never installs machine-wide. (a) A PEP 668 refusal comes back as the
    # user-scope remedy sentence, never a --break retry -- this pin FAILED against the
    # pre-P93 code, which returned ok=True 'installed with the machine-wide pip override (no
    # .venv available)' (executed detector proof). (b) Source pins in the env_paths launcher-probe
    # style: the override string is gone from this module and the wizard.
    if sys.platform != "win32":
        with tempfile.TemporaryDirectory() as td93:
            fake = Path(td93) / "fakepy"
            fake.write_text("#!/bin/sh\necho 'error: externally-managed-environment' >&2\n"
                            "exit 1\n", encoding="utf-8")
            fake.chmod(0o755)
            okp, det = _pip_install(["x"], python=str(fake))
            ok(okp is False and "never installs machine-wide" in det,
               "PEP 668 refusal carries the user-scope remedy, never a machine-wide retry (P93)")
    _marker = "--break-system-" + "packages"  # split so this pin never matches itself
    _self_src = Path(__file__).read_text(encoding="utf-8")
    _wiz_src = (ROOT / "tools" / "wizard.py").read_text(encoding="utf-8")
    ok(_marker not in _self_src and _marker not in _wiz_src,
       "the machine-wide pip override is gone from setup.py and wizard.py (P93 source pin)")
    # (c) P93-4: the PEP 668 branch above only covers an
    # interpreter that MARKS itself externally-managed. A plain machine-wide interpreter (a
    # python.org framework build, /usr/local) raises no such error, so the old
    # `target = venv_py or PYTHON` fallback installed straight into a shared site-packages with
    # nothing to refuse it. No .venv now means NO install, whatever the base interpreter is.
    # This pin fails against P93-1 code, which returned ok=True for every set here.
    _real_pip_install = _pip_install
    _real_ensure_venv = ensure_venv
    _pip_targets = []
    try:
        globals()["ensure_venv"] = lambda: (None, "could not create .venv")
        globals()["_pip_install"] = lambda a, python=None: (_pip_targets.append(python), (True, ""))[1]
        _res = install_dependencies()
    finally:
        globals()["_pip_install"] = _real_pip_install
        globals()["ensure_venv"] = _real_ensure_venv
    _sets = [r for r in _res if r["item"].startswith("requirements-")]
    ok(_pip_targets == [],
       "no .venv: pip is never invoked at all, so nothing can land machine-wide (P93-4)")
    ok(bool(_sets) and all(r["ok"] is False and "never installs into a machine-wide" in r["detail"]
                           for r in _sets),
       "no .venv: every requirements set is refused with the user-scoped remedy (P93-4)")
    ok(any(r["item"] == "uv" and r["ok"] is False for r in _res),
       "no .venv: the uv step is refused too, not silently installed (P93-4)")

    # Install target, observed where it matters: the argv of every subprocess the install path
    # starts. Only this module's `subprocess` name and env_paths' .venv lookup are swapped (no pip,
    # venv or network runs); ensure_venv, _pip_install and _install_playwright_browser stay real,
    # so a wrong interpreter anywhere on the path (a fallback in ensure_venv or
    # install_dependencies, or `py = PYTHON` inside a helper) shows up as an argv[0] that is not
    # the .venv interpreter.
    class _ArgvRecorder:
        returncode, stdout, stderr = 0, "", ""

        def __init__(self):
            self.calls = []

        def run(self, cmd, *a, **k):
            self.calls.append([str(x) for x in cmd])
            return self

    _fake_venv_py = str(ROOT / ".venv-selftest-absent" / "bin" / "python3")
    _pip_words = "-m pip install".split()
    _rec_venv, _rec_none = _ArgvRecorder(), _ArgvRecorder()
    _saved = (globals()["subprocess"], env_paths.venv_python, env_paths.which)
    try:
        env_paths.which = lambda name: None
        env_paths.venv_python = lambda *a, **k: Path(_fake_venv_py)
        globals()["subprocess"] = _rec_venv
        install_dependencies()
        env_paths.venv_python = lambda *a, **k: None
        globals()["subprocess"] = _rec_none
        install_dependencies()
    finally:
        globals()["subprocess"], env_paths.venv_python, env_paths.which = _saved
    _expected_pips = sum(1 for f, _ in REQUIREMENTS_SETS if (ROOT / f).exists()) + 1
    _venv_pips = [c for c in _rec_venv.calls if c[1:4] == _pip_words]
    ok(len(_venv_pips) == _expected_pips
       and all(c[0] == _fake_venv_py for c in _rec_venv.calls),
       ".venv present: every pip and Playwright subprocess runs the .venv interpreter, never the "
       "base interpreter")
    ok(_rec_none.calls == [[PYTHON, "-m", "venv", str(ROOT / ".venv")]],
       "no .venv: install_dependencies runs only the .venv creation attempt and no pip or "
       "Playwright subprocess, so pip cannot run in the base interpreter")
    # Every pip install command in the tree is built in one of two functions, setup.py's
    # _pip_install and wizard.py's _install_uv, and the pins above and in wizard.py's selftest
    # record the interpreter each of them runs. The file set is derived from the tree: every .py
    # under the repo except hidden, build and cache directories (.venv, .git, dist, __pycache__).
    # A command assembled at run time from non-literal parts is outside what this census reads.
    import ast as _ast
    import os as _os

    def _pip_argv_sites(node, rel, fn, out):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            fn = node.name
        if isinstance(node, (_ast.List, _ast.Tuple)):
            words = {e.value for e in node.elts
                     if isinstance(e, _ast.Constant) and isinstance(e.value, str)}
            if "pip" in words and "install" in words:
                out.add((rel, fn))
        for child in _ast.iter_child_nodes(node):
            _pip_argv_sites(child, rel, fn, out)

    _pip_sites = set()
    for _dir, _subdirs, _files in _os.walk(ROOT):
        _subdirs[:] = sorted(d for d in _subdirs if not d.startswith(".")
                             and d not in ("dist", "node_modules", "__pycache__"))
        for _name in sorted(_files):
            if not _name.endswith(".py"):
                continue
            _p = Path(_dir) / _name
            _rel = _p.relative_to(ROOT).as_posix()
            try:
                _pip_argv_sites(_ast.parse(_p.read_text(encoding="utf-8")), _rel, "<module>",
                                _pip_sites)
            except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
                _pip_sites.add((_rel, "<unreadable>"))
    _pip_expected = {("tools/setup.py", "_pip_install"), ("tools/wizard.py", "_install_uv")}
    if _pip_sites != _pip_expected:
        print(f"  [note] pip install commands found at: {sorted(_pip_sites)}")
    ok(_pip_sites == _pip_expected,
       "pip census: every pip install command in the tree is built in setup.py::_pip_install or "
       "wizard.py::_install_uv")

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
