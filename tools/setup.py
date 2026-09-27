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


def _pip_install(args: list, python: str) -> tuple:
    """Run pip with the given args in the target interpreter. Returns (ok, detail). Never
    raises. P93: on a PEP 668 externally-managed interpreter this REFUSES with the remedy --
    Creator OS never writes into a machine-wide site-packages; the repo .venv is the only
    install target (docs/INSTALL-SCOPE.md). The interpreter is a required argument with no
    fallback, and it must be the repo .venv interpreter env_paths.venv_python() resolves: an empty
    one or any other (this process's own, a path to another Python) is refused before any process
    starts, so no caller reaches the base interpreter by leaving it out or by passing it."""
    if not python or str(python) != str(env_paths.venv_python() or ""):
        return False, _NO_VENV_REFUSAL
    py = python
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


def _install_playwright_browser(python: str) -> tuple:
    """Fetch the Chromium binary Playwright needs (only if the package installed in the target
    interpreter). (ok, detail). The interpreter is required and must be the repo .venv
    interpreter env_paths.venv_python() resolves: an empty one or any other is skipped before any
    process starts."""
    if not python or str(python) != str(env_paths.venv_python() or ""):
        return None, "skipped: no .venv to install into"
    py = python
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


def _run_as_script(argv: list, subprocess_stand_in, namespace: dict, tty: bool = False,
                   source: str | None = None) -> tuple:
    """Selftest seam: run this file the way a person or the wizard starts it
    (`python3 tools/setup.py <argv>`). Its source is executed in `namespace`, which the caller
    builds with __name__ "__main__", so module-level code and the script block at the bottom of
    the file run, and every `import subprocess` the source makes while it runs gets
    `subprocess_stand_in`. Its stdin, stdout and stderr report a terminal when `tty` is set (a
    person typing the command) and a pipe otherwise (the wizard's subprocess). Returns (exit
    code, stdout); a crash comes back as its repr in place of the exit code. `source`, when
    given, runs in place of the file's text (the selftest's stream probe)."""
    import contextlib
    import io
    class _Stream(io.StringIO):
        def isatty(self):
            return tty

    saved = (sys.argv, sys.modules.get("subprocess"), sys.stdin)
    buf, code = _Stream(), None
    try:
        sys.argv = [str(Path(__file__)), *argv]
        sys.modules["subprocess"] = subprocess_stand_in
        sys.stdin = _Stream()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(_Stream()):
            text = Path(__file__).read_text(encoding="utf-8") if source is None else source
            exec(compile(text, str(Path(__file__)), "exec"), namespace)
    except SystemExit as exc:
        code = exc.code
    except Exception as exc:  # noqa: BLE001 - a crash on this path is a failed pin
        code = repr(exc)
    finally:
        sys.argv = saved[0]
        sys.modules["subprocess"] = saved[1]
        sys.stdin = saved[2]
    return code, buf.getvalue()


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
    # The interpreter is a required argument of both install helpers: a caller that leaves it out
    # fails at the call, and an empty one is refused before any process starts.
    import inspect as _inspect
    _started = []

    class _RefuseStarts:
        def __getattr__(self, name):
            def _rec(*a, **k):
                _started.append(name)
                raise OSError("selftest: process start refused")
            return _rec

    _saved_sp = globals()["subprocess"]
    globals()["subprocess"] = _RefuseStarts()
    try:
        _none_results = (_pip_install(["x"], None), _pip_install(["x"], ""),
                         _install_playwright_browser(None))
    finally:
        globals()["subprocess"] = _saved_sp
    ok(_started == [] and _none_results[:2] == ((False, _NO_VENV_REFUSAL),) * 2
       and _none_results[2][0] is None
       and all(_inspect.signature(_f).parameters["python"].default is _inspect.Parameter.empty
               for _f in (_pip_install, _install_playwright_browser)),
       "_pip_install and _install_playwright_browser take the interpreter as a required argument "
       "and refuse an empty one before any process starts, so no caller reaches the base "
       "interpreter by leaving it out")
    # An interpreter other than the .venv's, this process's own included, is refused the same way,
    # whether a .venv exists or not.
    _saved_vp = env_paths.venv_python
    globals()["subprocess"] = _RefuseStarts()
    _other = []
    try:
        for _vp in (None, ROOT / ".venv-selftest-absent" / "bin" / "python3"):
            env_paths.venv_python = lambda *a, _vp=_vp, **k: _vp
            _other += [_pip_install(["x"], PYTHON), _pip_install(["x"], "/usr/bin/python3"),
                       _install_playwright_browser(PYTHON)]
    finally:
        globals()["subprocess"] = _saved_sp
        env_paths.venv_python = _saved_vp
    ok(_started == [] and len(_other) == 6 and all(_r[0] is not True for _r in _other),
       "_pip_install and _install_playwright_browser refuse any interpreter other than the .venv's "
       "(this process's own included) before any process starts, with or without a .venv")
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
            _saved_vp = env_paths.venv_python
            env_paths.venv_python = lambda *a, **k: fake
            try:
                okp, det = _pip_install(["x"], python=str(fake))
            finally:
                env_paths.venv_python = _saved_vp
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
    _pip_words = ["-m", "pip"]
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
    _venv_pips = [c for c in _rec_venv.calls if c[1:3] == _pip_words]
    ok(len(_venv_pips) == _expected_pips
       and all(c[0] == _fake_venv_py for c in _rec_venv.calls),
       ".venv present: every pip and Playwright subprocess runs the .venv interpreter, never the "
       "base interpreter")
    ok(_rec_none.calls == [[PYTHON, "-m", "venv", str(ROOT / ".venv")]],
       "no .venv: install_dependencies runs only the .venv creation attempt and no pip or "
       "Playwright subprocess, so pip cannot run in the base interpreter")
    # The same property where the wizard and a person start it: the file runs as the script with
    # --install-deps --json and a .venv present, once with every pip and Playwright step
    # succeeding and once with every one failing, so what the entry does after a failed set (a
    # retry, a fallback) is recorded too.
    _entry_calls, _entry_exits = [], []
    _saved_entry = (env_paths.venv_python, env_paths.which)
    try:
        env_paths.which = lambda name: None
        env_paths.venv_python = lambda *a, **k: Path(_fake_venv_py)
        for _rc in (0, 1):
            _rec_entry = _ArgvRecorder()
            _rec_entry.returncode, _rec_entry.stderr = _rc, "selftest: recorded, not run"
            _entry_exits.append(_run_as_script(["--install-deps", "--json"], _rec_entry,
                                               {"__name__": "__main__", "__file__": __file__})[0])
            _entry_calls += _rec_entry.calls
    finally:
        env_paths.venv_python, env_paths.which = _saved_entry
    ok(_entry_exits == [0, 1]
       and len([c for c in _entry_calls if c[1:3] == _pip_words]) == 2 * _expected_pips
       and all(c[0] == _fake_venv_py for c in _entry_calls),
       ".venv present: the --install-deps script entry runs every pip and Playwright subprocess "
       "with the .venv interpreter, whether each step succeeds or fails")
    # The same property at the CLI entry the wizard's "Set up my computer" screen runs
    # (`setup.py --install-deps --json`) and the plain form a person types. The file runs as that
    # script (_run_as_script: its source executed as __main__, so module-level code and the script
    # block at the bottom of the file run, with every `import subprocess` answered by the
    # recorder; the plain form with stdin, stdout and stderr reporting a terminal as a person's
    # do, the --json form with pipes as the wizard's subprocess has) with no .venv obtainable under each way the .venv attempt can fail: it exits 0 and leaves no
    # .venv; it exits 1 with output carrying every string literal in this module, so a branch on
    # that output meets its own operand; and it raises. Every way this process can start another
    # is recorded: this module's `subprocess` name, subprocess.Popen and the fork_exec it runs (so
    # a Popen bound to another name first is seen), os.system and the os exec/spawn/fork family,
    # any name in this module or env_paths bound to one of those, and an import of pip. The only
    # start allowed is the .venv creation attempt, and the entry exits 1 with every requirements
    # set refused. A start made from native code (a C extension, ctypes), or on Windows by a Popen
    # bound to another name in some other module (it reaches _winapi.CreateProcess), is outside
    # what this records, and so is a branch on an environment variable, the platform or the
    # clock, which this pin does not vary.
    import ast as _ast_cli
    import contextlib as _cl
    import io as _io
    import os as _os_proc
    import re as _re_proc
    import subprocess as _sp_mod
    _procs = []
    _all_words = " ".join(sorted({_n.value for _n in _ast_cli.walk(_ast_cli.parse(
        Path(__file__).read_text(encoding="utf-8")))
        if isinstance(_n, _ast_cli.Constant) and isinstance(_n.value, str)}))

    def _argv(cmd):
        return [str(x) for x in cmd] if isinstance(cmd, (list, tuple)) else [str(cmd)]

    def _refuse(tag):
        def _rec(cmd=None, *a, **k):
            _procs.append((tag, _argv(cmd)))
            raise OSError("selftest: process start refused")
        return _rec

    class _ModuleRecorder:
        """Stands in for this module's `subprocess`: every function it is asked for records the
        argv, then raises OSError when `raises` is set and otherwise returns a finished process
        carrying this recorder's returncode, stdout and stderr."""
        returncode, stdout, stderr, raises = 0, "", "", False

        def __getattr__(self, name):
            def _rec(cmd=None, *a, **k):
                _procs.append((name, _argv(cmd)))
                if self.raises:
                    raise OSError(_all_words)
                return self
            return _rec

    class _PipImportRefused:
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in ("pip", "ensurepip"):
                _procs.append(("import", [name]))
                raise ImportError(f"selftest: import of {name} refused")
            return None

    _os_starts = [n for n in dir(_os_proc) if _re_proc.fullmatch(
        r"system|popen|fork|forkpty|posix_spawnp?|(?:exec|spawn)[lv]p?e?", n)]
    _starters = [getattr(_os_proc, n) for n in _os_starts] + [
        f for f in (_sp_mod.Popen, getattr(_sp_mod, "_fork_exec", None)) if f is not None]
    _aliases = [(ns, k) for ns in (globals(), env_paths.__dict__) for k, v in list(ns.items())
                if any(v is f for f in _starters)]
    _cached_pip = {k: v for k, v in sys.modules.items() if k.split(".")[0] in ("pip", "ensurepip")}
    _saved_cli = (globals()["subprocess"], env_paths.venv_python, env_paths.which, sys.argv,
                  _sp_mod.Popen, getattr(_sp_mod, "_fork_exec", None),
                  {n: getattr(_os_proc, n) for n in _os_starts},
                  [(ns, k, ns[k]) for ns, k in _aliases])
    _finder = _PipImportRefused()
    _exits, _outs = [], []
    try:
        env_paths.venv_python = lambda *a, **k: None
        env_paths.which = lambda name: None
        _sp_mod.Popen = _refuse("Popen")
        if _saved_cli[5] is not None:
            _sp_mod._fork_exec = _refuse("fork_exec")
        for _n in _os_starts:
            setattr(_os_proc, _n, _refuse(_n))
        for _ns, _k in _aliases:
            _ns[_k] = _refuse(_k)
        for _k in _cached_pip:
            del sys.modules[_k]
        sys.meta_path.insert(0, _finder)
        for _rc, _text, _raises in ((0, "", False), (1, _all_words, False), (1, "", True)):
            _mod = _ModuleRecorder()
            _mod.returncode, _mod.stdout, _mod.stderr, _mod.raises = _rc, _text, _text, _raises
            globals()["subprocess"] = _mod
            for _cli in (["--install-deps", "--json"], ["--install-deps"]):
                _code, _printed = _run_as_script(_cli, _mod, {"__name__": "__main__",
                                                               "__file__": __file__},
                                                 tty="--json" not in _cli)
                _exits.append(_code)
                _outs.append(_printed)
    finally:
        if _finder in sys.meta_path:
            sys.meta_path.remove(_finder)
        sys.modules.update(_cached_pip)
        (globals()["subprocess"], env_paths.venv_python, env_paths.which, sys.argv,
         _sp_mod.Popen, _fork_saved, _os_saved, _alias_saved) = _saved_cli
        if _fork_saved is not None:
            _sp_mod._fork_exec = _fork_saved
        for _n, _f in _os_saved.items():
            setattr(_os_proc, _n, _f)
        for _ns, _k, _f in _alias_saved:
            _ns[_k] = _f
    _venv_try = ("run", [PYTHON, "-m", "venv", str(ROOT / ".venv")])
    _cli_sets = []
    for _o in _outs[0::2]:
        try:
            _cli_sets.append([r for r in json.loads(_o)["results"]
                              if str(r.get("item", "")).startswith("requirements-")])
        except (ValueError, KeyError, TypeError, AttributeError):
            _cli_sets.append([])
    ok(_procs == [_venv_try] * 6 and _exits == [1] * 6 and len(_cli_sets) == 3
       and all(len(s) == len(REQUIREMENTS_SETS)
               and all(r.get("ok") is False and "never installs into a machine-wide"
                       in str(r.get("detail")) for r in s) for s in _cli_sets),
       "no .venv: the --install-deps CLI entry starts only the .venv creation attempt and exits 1 "
       "with every requirements set refused, so pip cannot run in the base interpreter")
    # _run_as_script's streams: stdin, stdout and stderr report a terminal for the plain form a
    # person types (tty) and a pipe for the --json form the wizard's subprocess runs.
    _probe = "import sys\nprint(sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty())\n"
    ok([_run_as_script([], sys.modules.get("subprocess"), {"__name__": "__main__"}, tty=_t,
                       source=_probe)[1].split() for _t in (True, False)]
       == [["True"] * 3, ["False"] * 3],
       "_run_as_script's stdin, stdout and stderr report a terminal when tty is set and a pipe "
       "otherwise, as the CLI pin's two forms need")
    # Every pip install command in the tree is built in one of two functions, setup.py's
    # _pip_install and wizard.py's _install_uv, and the pins above and in wizard.py's selftest
    # record the interpreter each of them runs. The file set is derived from the tree: every .py
    # under the repo except hidden, build and cache directories (.venv, .git, dist, __pycache__).
    # A site is keyed by its file, qualified name (Class.method, outer.inner) and line, so a
    # nested function, a method or a second definition sharing an install function's name is a
    # site of its own. Within one site (or a module's top level) the census reads every literal
    # an argv can be assembled from: list, tuple and set elements, `+`, `+=` and
    # append/extend/insert operands, names bound to such literals there, in an enclosing function
    # or at module level (plain, chained, annotated, augmented and walrus assignment, and a
    # parameter default), a dict's
    # keys and values reached through a subscript, bytes literals, a constant inside f-string
    # braces, both operands of `or`/`and` and both branches of a conditional, the first
    # positional and every keyword argument of a process call, a string handed to split() (split
    # into words), and an import of pip itself. A pip executable is any name pip, pip3 or pip3.N,
    # bare, at the end of a path or glued to -m. A %-formatted or .format() string is read as its
    # template. A word made by a call (join, chr, decode), read from a file or the environment,
    # returned by another function, held in an attribute, fetched by getattr or captured by a
    # match pattern is outside what this census reads; a fixture per such shape pins that
    # statement.
    import ast as _ast
    import os as _os
    import re as _re
    _pip_exe = _re.compile(r"(?:-m)?(?:.*[/\\])?pip(?:\d+(?:\.\d+)*)?(?:\.exe)?")
    _proc_calls = {"run", "Popen", "call", "check_call", "check_output", "system", "popen",
                   "getoutput", "getstatusoutput", "create_subprocess_exec",
                   "create_subprocess_shell", "run_module", "run_path", "import_module",
                   "__import__", "posix_spawn", "posix_spawnp", "execl", "execlp", "execv",
                   "execvp", "spawnl", "spawnlp", "spawnv", "spawnvp", "split"}

    def _pip_argv_sites(tree, rel, out):
        scopes = (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)
        bound, lines = {}, {}

        def fold(n, fn):
            """(words, is_one_string): the literal words expression `n` is built from."""
            if isinstance(n, _ast.Constant) and isinstance(n.value, (str, bytes)):
                return [n.value if isinstance(n.value, str) else n.value.decode("latin-1")], True
            if isinstance(n, _ast.JoinedStr):
                parts = []
                for v in n.values:
                    inner, one = (([str(v.value)], True) if isinstance(v, _ast.Constant)
                                  else fold(v.value, fn))
                    parts.append(inner[0] if one and len(inner) == 1 else " ")
                return ["".join(parts)], True
            if isinstance(n, _ast.BinOp) and isinstance(n.op, _ast.Mod):
                return fold(n.left, fn)
            if (isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute)
                    and n.func.attr == "format"):
                return fold(n.func.value, fn)
            if isinstance(n, _ast.IfExp):
                return fold(n.body, fn)[0] + fold(n.orelse, fn)[0], False
            if isinstance(n, _ast.BinOp) and isinstance(n.op, _ast.Add):
                (lw, ls), (rw, rs) = fold(n.left, fn), fold(n.right, fn)
                return ([lw[0] + rw[0]], True) if ls and rs else (lw + rw, False)
            if isinstance(n, (_ast.List, _ast.Tuple, _ast.Set)):
                return [w for e in n.elts for w in fold(e, fn)[0]], False
            if isinstance(n, _ast.BoolOp):
                return [w for v in n.values for w in fold(v, fn)[0]], False
            if isinstance(n, _ast.Dict):
                return [w for e in n.keys + n.values if e is not None for w in fold(e, fn)[0]], False
            if isinstance(n, (_ast.Starred, _ast.Subscript)):
                return fold(n.value, fn)[0], False
            if isinstance(n, _ast.NamedExpr):
                return fold(n.value, fn)
            if isinstance(n, _ast.Name):
                scope = fn
                while True:
                    if bound.get((scope, n.id)):
                        return bound[(scope, n.id)]
                    if scope is None:
                        return [], False
                    scope = scope.rpartition(".")[0] or None
            return [], False

        def walk(node, fn, visit):
            if isinstance(node, scopes):
                fn = f"{fn}.{node.name}" if fn else node.name
                lines[fn] = node.lineno
            visit(node, fn)
            for child in _ast.iter_child_nodes(node):
                walk(child, fn, visit)

        def bind(node, fn):
            if isinstance(node, _ast.Assign):
                targets = node.targets
            elif (isinstance(node, (_ast.AnnAssign, _ast.AugAssign, _ast.NamedExpr))
                  and node.value is not None):
                targets = [node.target]
            elif isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.Lambda)):
                a = node.args
                pos = a.posonlyargs + a.args
                for p, d in (list(zip(pos[len(pos) - len(a.defaults):], a.defaults))
                             + [(k, d) for k, d in zip(a.kwonlyargs, a.kw_defaults) if d]):
                    words, one = fold(d, fn)
                    if words:
                        old = bound.get((fn, p.arg), ([], True))[0]
                        bound[(fn, p.arg)] = (old + words, one and not old)
                return
            else:
                return
            words, one = fold(node.value, fn)
            for target in targets:
                if isinstance(target, _ast.Name) and words:
                    old = bound.get((fn, target.id), ([], True))[0]
                    bound[(fn, target.id)] = (old + words, one and not old)

        def read(node, fn):
            words = out.setdefault((rel, fn or "<module>", lines.get(fn, 0)), set())
            if isinstance(node, (_ast.List, _ast.Tuple, _ast.Set)):
                words.update(fold(node, fn)[0])
            elif isinstance(node, _ast.AugAssign) and isinstance(node.op, _ast.Add):
                words.update(fold(node.value, fn)[0])
            elif isinstance(node, (_ast.Import, _ast.ImportFrom)):
                mods = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
                words.update("pip" for m in mods if m.split(".")[0] in ("pip", "ensurepip"))
            elif isinstance(node, _ast.Call):
                f = node.func
                name = f.attr if isinstance(f, _ast.Attribute) else getattr(f, "id", "")
                if name in ("append", "extend", "insert"):
                    for arg in node.args:
                        words.update(fold(arg, fn)[0])
                if name in _proc_calls:
                    first = [f.value] if name == "split" and isinstance(f, _ast.Attribute) else []
                    for arg in first + node.args[:1] + [k.value for k in node.keywords]:
                        for w in fold(arg, fn)[0]:
                            words.update(w.split())

        for _ in range(2):  # twice, so a name bound from another bound name resolves
            walk(tree, None, bind)
        walk(tree, None, read)

    _pip_words_by_site = {}
    for _dir, _subdirs, _files in _os.walk(ROOT):
        _subdirs[:] = sorted(d for d in _subdirs if not d.startswith(".")
                             and d not in ("dist", "node_modules", "__pycache__"))
        for _name in sorted(_files):
            if not _name.endswith(".py"):
                continue
            _p = Path(_dir) / _name
            _rel = _p.relative_to(ROOT).as_posix()
            try:
                _pip_argv_sites(_ast.parse(_p.read_text(encoding="utf-8")), _rel,
                                _pip_words_by_site)
            except (OSError, SyntaxError, UnicodeDecodeError, ValueError, RecursionError):
                _pip_words_by_site[(_rel, "<unreadable>", 0)] = None
    _pip_sites = {site for site, words in _pip_words_by_site.items()
                  if words is None
                  or ("install" in words and any(_pip_exe.fullmatch(w) for w in words))}
    # The census reads each assembly form it names: a fixture per form comes back as a site.
    _fixture_sites = {}
    _fixtures = (
        'def f():\n    c = [sys.executable, "-m", "pip"]\n    c += ["install", "x"]\n',
        'def f():\n    run(["pip3", "install", "x"])\n',
        'P = "pip"\ndef f():\n    run([sys.executable, "-m", P, "install", "x"])\n',
        'def f():\n    c = [py, "-m"]\n    c.append("pi" + "p")\n    c.extend(["install"])\n',
        'def f():\n    run("env pip install x".split())\n',
        'def f():\n    os.system(f"{py} -m pip install x")\n',
        'def f():\n    import pip\n    pip.main(["install", "x"])\n')
    _fixtures += (
        'def f():\n    os.system("%s -m pip install x" % py)\n',
        'def f():\n    run("{} -m pip install x".format(py), shell=True)\n',
        'def f(rm=False):\n    run([py, "-m", "pip", "install" if not rm else "uninstall", "x"])\n',
        'def f():\n    run([py, "-mpip", "install", "x"])\n',
    )
    for _i, _fx in enumerate(_fixtures):
        _pip_argv_sites(_ast.parse(_fx), f"fixture{_i}", _fixture_sites)
    ok({site[0] for site, words in _fixture_sites.items()
        if "install" in words and any(_pip_exe.fullmatch(w) for w in words)}
       == {f"fixture{_i}" for _i in range(len(_fixtures))},
       "pip census self-check: a split argv, pip3, a module-level pip name, an appended "
       "concatenated word, a split string, an f-string command and pip imported in-process "
       "are each read as a pip install site, and so are a %-formatted and a .format() command, "
       "an action word chosen by a conditional and a -mpip flag")
    # The same census over a fixture per form read since sites were keyed by qualified name: a
    # dict value read through a subscript, bytes literals, a walrus, a constant in f-string braces,
    # a keyword argv, annotated and chained assignments, a name bound in an enclosing function and
    # an `or` operand.
    _more = (
        'M = {"module": "pip"}\ndef f():\n    run([py, "-m", M["module"], "install", "x"])\n',
        'def f():\n    run([py, b"-m", b"pip", b"install", b"x"])\n',
        'def f():\n    run([py, "-m", (t := "pip"), "install", "x"])\n',
        'def f():\n    run(f"{py} -m {\'pip\'} install x", shell=True)\n',
        'def f():\n    run(args=f"{py} -m pip install x", shell=True)\n',
        'def f():\n    m: str = "pip"\n    run([py, "-m", m, "install", "x"])\n',
        'def f():\n    a = b = "pip"\n    run([py, "-m", b, "install", "x"])\n',
        'def f():\n    m = "pip"\n    def g():\n        run([py, "-m", m, "install", "x"])\n',
        'def f(o=None):\n    run([py, "-m", o or "pip", "install", "x"])\n',
    )
    _more_sites = {}
    for _i, _fx in enumerate(_more):
        _pip_argv_sites(_ast.parse(_fx), f"more{_i}", _more_sites)
    ok({site[0] for site, words in _more_sites.items()
        if "install" in words and any(_pip_exe.fullmatch(w) for w in words)}
       == {f"more{_i}" for _i in range(len(_more))},
       "pip census self-check: a dict value read through a subscript, bytes literals, a walrus, "
       "a constant in f-string braces, a keyword argv, annotated and chained assignments, a name "
       "bound in an enclosing function and an `or` operand are each read as a pip install site")
    _q_sites = {}
    _pip_argv_sites(_ast.parse(
        "def build():\n    def _pip_install():\n        run([py, '-m', 'pip', 'install', 'x'])\n"
        "class H:\n    def _install_uv(self):\n        run([py, '-m', 'pip', 'install', 'uv'])\n"
        "def _pip_install(a, python):\n    run([python, '-m', 'pip', 'install', *a])\n"
        "def _pip_install(a, python):\n    run([python, '-m', 'pip', 'install', *a])\n"),
        "q.py", _q_sites)
    ok(sorted(site[1:] for site, words in _q_sites.items()
              if "install" in words and any(_pip_exe.fullmatch(w) for w in words))
       == [("H._install_uv", 5), ("_pip_install", 7), ("_pip_install", 9),
           ("build._pip_install", 2)],
       "pip census keys a site by qualified name and line: a nested function or a method named "
       "like an install function, and a second definition of it, are sites of their own")
    _defaults = (
        'def f(m="pip"):\n    run([py, "-m", m, "install", "x"])\n',
        'def f(*, m="pip"):\n    run([py, "-m", m, "install", "x"])\n',
        'g = lambda m="pip": run([py, "-m", m, "install", "x"])\n',
    )
    _default_sites = {}
    for _i, _fx in enumerate(_defaults):
        _pip_argv_sites(_ast.parse(_fx), f"default{_i}", _default_sites)
    ok({site[0] for site, words in _default_sites.items()
        if "install" in words and any(_pip_exe.fullmatch(w) for w in words)}
       == {f"default{_i}" for _i in range(len(_defaults))},
       "pip census self-check: a positional, keyword-only or lambda parameter default is read as "
       "a pip install site")
    _outside = (
        'def f():\n    run([py, "-m", "".join(["p", "i", "p"]), "install", "x"])\n',
        'def f():\n    run([py, "-m", chr(112) + "ip", "install", "x"])\n',
        'def f():\n    run([py, "-m", os.environ["TOOL"], "install", "x"])\n',
        'def w():\n    return "pip"\ndef f():\n    run([py, "-m", w(), "install", "x"])\n',
        'class C:\n    def f(self):\n        self.t = "pip"\n'
        '        run([py, "-m", self.t, "install", "x"])\n',
        'def f():\n    run([py, "-m", getattr(cfg, "tool"), "install", "x"])\n',
        'def f():\n    match "pip":\n        case m:\n            run([py, "-m", m, "install", "x"])\n',
        'def f():\n    run([py, "-m", "%s" % "pip", "install", "x"])\n',
        'def f():\n    with contextlib.nullcontext("pip") as m:\n'
        '        run([py, "-m", m, "install", "x"])\n',
    )
    _out_sites = {}
    for _i, _fx in enumerate(_outside):
        _pip_argv_sites(_ast.parse(_fx), f"outside{_i}", _out_sites)
    ok(not any("install" in words and any(_pip_exe.fullmatch(w) for w in words)
               for words in _out_sites.values()),
       "pip census limit as stated: a word made by join or chr, read from the environment, "
       "returned by another function, held in an attribute, fetched by getattr, carried in a "
       "%-format or with-as value, or bound by a match case is not read")
    _pip_expected = {("tools/setup.py", "_pip_install"), ("tools/wizard.py", "_install_uv")}
    _pip_site_names = sorted(site[:2] for site in _pip_sites)
    if _pip_site_names != sorted(_pip_expected):
        print(f"  [note] pip install commands found at: {sorted(_pip_sites)}")
    ok(_pip_site_names == sorted(_pip_expected),
       "pip census: every pip install command in the tree is built in setup.py::_pip_install or "
       "wizard.py::_install_uv")
    _pip_named = {site for site, words in _pip_words_by_site.items()
                  if words is None or any(_pip_exe.fullmatch(w) for w in words)}
    _pip_others = sorted(
        site for site in _pip_named if site[:2] not in _pip_expected
        and site[:2] != ("tools/readonly_bash_guard.py", "<module>")
        and not (site[0] in ("tools/setup.py", "tools/wizard.py")
                 and site[1].split(".")[0] == "_selftest"))
    if _pip_others:
        print(f"  [note] pip program named at: {_pip_others}")
    ok(not _pip_others,
       "pip census: the pip program is named only in the two install functions, the setup and "
       "wizard selftests with their census helpers, and the Bash guard's refused-module table")
    _syn_map = {}
    _pip_argv_sites(_ast.parse(
        "PREFIX = ('pip',)\n"
        "def split_argv(py):\n    cmd = [py, '-m', 'pip']\n    cmd += ['install', 'x']\n"
        "def pip3_argv():\n    return ['pip3', 'install', 'x']\n"
        "def path_argv():\n    return ['/usr/bin/pip3.12', 'install', 'x']\n"
        "def joined(py):\n    return [py, '-m', 'pip', 'ins' + 'tall', 'x']\n"
        "def in_process():\n    from pip._internal.cli.main import main\n"
        "    return main(['install', 'x'])\n"
        "def prefix(py):\n    return [py, '-m', 'pip']\n"
        "def venv_only(py):\n    return [py, '-m', 'venv', '.venv']\n"),
        "syn.py", _syn_map)
    _syn = {site[:2] for site, words in _syn_map.items()
            if words is not None and "install" in words
            and any(_pip_exe.fullmatch(w) for w in words)}
    _syn_named = {site[:2] for site, words in _syn_map.items()
                  if words is None or any(_pip_exe.fullmatch(w) for w in words)}
    _syn_want = {("syn.py", n) for n in (
        "split_argv", "pip3_argv", "path_argv", "joined", "in_process")}
    ok(_syn == _syn_want,
       "pip census reads an argv split across statements, pip3, a path to pip, literals joined "
       "with + and an in-process pip import, and not a venv command")
    ok(_syn_named == _syn_want | {("syn.py", "prefix"), ("syn.py", "<module>")},
       "pip census names a helper or a module constant that holds the pip program")

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
