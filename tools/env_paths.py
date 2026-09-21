#!/usr/bin/env python3
"""Shared interpreter/PATH helpers for a Mac-friendly launch and install.

Two macOS realities drive this module (see docs/SETUP_MAC.md and the P53 stress test):

1. The "private toolbox": dependencies install into a repo-local ``.venv`` so a Homebrew Python
   (which follows PEP 668 and refuses global package installs) is never touched. The app's heavy
   tools then run under that venv interpreter. ``app_python()`` returns the venv python when it
   exists and otherwise the current interpreter, so a machine without a ``.venv`` behaves exactly
   as before (no regression).

2. GUI-launch PATH: a double-clicked ``.command`` runs a non-login, non-interactive zsh that
   sources only ``~/.zshenv``, so neither the user's own bin dirs nor Homebrew's
   ``/opt/homebrew/bin`` (Apple Silicon) / ``/usr/local/bin`` (Intel) are on PATH.
   ``which()`` prepends both families so the tools are found even under a double-click.
   P93: the USER-SCOPED dirs come first, because user-scoped is the default install target
   (docs/INSTALL-SCOPE.md). A tool the docs tell someone to install user-only has to be
   findable afterwards, or the recommended route dead-ends: ``uv python install 3.12`` puts
   ``python3.12`` in ``~/.local/bin`` (uv docs, "Installing Python"), and nvm keeps node at
   ``$NVM_DIR/versions/node/<version>/bin`` (nvm.sh ``nvm_version_path``) and is sourced per
   shell, so neither is on a double-click PATH.

Stdlib only. Pure and injectable so the selftest can simulate a macOS PATH with no real hardware.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repo root (tools/..)

# Homebrew bin dirs. /opt/homebrew (Apple Silicon) and /usr/local (Intel). Both are listed and
# harmless when absent; we never assume one architecture.
BREW_PREFIXES = ("/opt/homebrew/bin", "/usr/local/bin")

# P93: the user-scoped bin dirs, searched BEFORE the machine-wide ones. ~/.local/bin is where the
# uv installer puts uv and where `uv python install` puts pythonX.Y; nvm keeps each node under
# $NVM_DIR/versions/node/<version>/bin. Both are per-user by design and neither is on a
# double-click PATH. See docs/INSTALL-SCOPE.md.
USER_BIN = ".local/bin"
NVM_NODE_SUBDIR = "versions/node"

PYTHON_FLOOR = (3, 12)   # THE floor. tools/setup.py imports it; the launcher's probe string embeds it
                         # P91: validated THROUGH 3.14 (battery 13/13 on 3.12/3.13/3.14); the floor
                         # stays 3.12 for the Resolve live-control lane (vendor cap, ADR 0064).
                         # (asserted by _selftest); docs are swept against it by drift invariant 48 (P81 G-1).


def repo_root() -> Path:
    return ROOT


def venv_python(root=None):
    """The repo ``.venv`` interpreter if it exists, RUNS, and meets PYTHON_FLOOR; else None (P81 B-5).
    P80 taught the launcher to refuse an old venv; this function still handed every heavy tool to it,
    so a 3.11 venv produced a wizard on system 3.12 spawning tools on 3.11 that setup.py then refused."""
    base = Path(root) if root is not None else ROOT
    for c in (
        base / ".venv" / "bin" / "python3",
        base / ".venv" / "bin" / "python",
        base / ".venv" / "Scripts" / "python.exe",  # Windows
    ):
        if not c.exists():
            continue
        try:
            r = subprocess.run([str(c), "-c", f"import sys; sys.exit(0 if sys.version_info[:2] >= {PYTHON_FLOOR} else 1)"],
                               capture_output=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return None          # exists but does not run (relocated framework): same as absent
        return c if r.returncode == 0 else None
    return None


def app_python(root=None) -> str:
    """The interpreter the app's heavy tools should run under: the ``.venv`` python when present,
    else the current interpreter (today's behavior, so no ``.venv`` == no change)."""
    vp = venv_python(root)
    return str(vp) if vp else sys.executable


def brew_prefixes() -> list:
    return list(BREW_PREFIXES)


def _nvm_dir(home: Path, env=None) -> Path:
    """nvm's directory: $NVM_DIR when set (nvm.sh honors it), else ~/.nvm (its README's default)."""
    env = env if env is not None else os.environ
    raw = (env.get("NVM_DIR") or "").strip()
    return Path(raw) if raw else home / ".nvm"


def user_prefixes(home=None, env=None) -> list:
    """The user-scoped bin dirs that exist, newest node first. P93: these are searched before the
    machine-wide prefixes, so a tool installed by the route this repo recommends (uv into
    ``~/.local/bin``, node via nvm) is found even under a bare double-click PATH. Returns only
    directories that actually exist, so a machine without them is unaffected. Pure/injectable:
    ``home`` and ``env`` are overridable for the selftest (no real HOME needed)."""
    env = env if env is not None else os.environ
    if home is not None:
        home = Path(home)
    else:
        raw = env.get("HOME") or env.get("USERPROFILE") or ""
        if not raw:
            return []
        home = Path(raw)
    out = []
    local_bin = home / USER_BIN
    if local_bin.is_dir():
        out.append(str(local_bin))
    node_root = _nvm_dir(home, env) / NVM_NODE_SUBDIR
    try:
        versions = [d for d in node_root.iterdir() if (d / "bin").is_dir()]
    except OSError:
        versions = []
    for d in sorted(versions, key=lambda p: _version_key(p.name), reverse=True):
        out.append(str(d / "bin"))
    return out


def _version_key(name: str) -> tuple:
    """Sort key for an nvm version dir name ('v20.11.1'), so the newest node wins. Non-numeric
    parts sort low rather than raising, since nvm also keeps aliases like 'system'."""
    parts = []
    for chunk in name.lstrip("vV").split("."):
        digits = ""
        for ch in chunk:
            if not ch.isdigit():
                break
            digits += ch
        parts.append(int(digits) if digits else -1)
    while len(parts) < 3:
        parts.append(-1)
    return tuple(parts[:3])


def augmented_path(base=None, home=None, env=None) -> str:
    """PATH string with the user-scoped bin dirs prepended FIRST and the Homebrew prefixes after,
    so ``which()`` finds both under a GUI (double-click) launch that has a bare PATH. User-scoped
    leads because user-scoped is the install default (docs/INSTALL-SCOPE.md); brew stays so an
    existing machine-wide install keeps working (using what exists is allowed, adding is not).
    ``base`` defaults to the current ``$PATH``."""
    base = base if base is not None else os.environ.get("PATH", "")
    parts = user_prefixes(home=home, env=env) + list(BREW_PREFIXES)
    if base:
        parts.append(base)
    return os.pathsep.join(parts)


def which(name, path=None):
    """``shutil.which`` with the Homebrew prefixes prepended; falls back to the bare lookup so a
    tool already on PATH is still found. Returns the resolved path string or None."""
    p = path if path is not None else augmented_path()
    return shutil.which(name, path=p) or shutil.which(name)


def _selftest() -> int:
    import tempfile
    import stat

    checks = []

    def ok(cond, msg):
        checks.append((bool(cond), msg))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # No .venv yet -> venv_python None, app_python is the current interpreter.
        ok(venv_python(root) is None, "venv_python None when no .venv")
        ok(app_python(root) == sys.executable, "app_python falls back to sys.executable")

        # P81 B-5: a venv is selected only when it RUNS and meets PYTHON_FLOOR.
        vbin = root / ".venv" / "bin"
        vbin.mkdir(parents=True)
        vpy = vbin / "python3"
        vpy.write_text("#!/bin/sh\nexit 127\n")   # exists but does not run usefully
        vpy.chmod(vpy.stat().st_mode | stat.S_IEXEC)
        ok(venv_python(root) is None, "a broken venv interpreter is rejected (P81 B-5)")
        vpy.unlink()
        vpy.symlink_to(sys.executable)             # a real interpreter
        if sys.version_info[:2] >= PYTHON_FLOOR:
            ok(venv_python(root) == vpy, "venv_python finds a floor-meeting .venv interpreter")
            ok(app_python(root) == str(vpy), "app_python returns .venv interpreter when present")
        else:
            ok(venv_python(root) is None, "a below-floor venv interpreter is rejected (P81 B-5)")
            ok(app_python(root) == sys.executable, "app_python falls back below the floor")
        launcher = ROOT / "Start Creator OS Setup.command"
        if launcher.exists():
            ok(f"sys.version_info[:2] >= {PYTHON_FLOOR}" in launcher.read_text(encoding="utf-8"),
               "the launcher probe embeds PYTHON_FLOOR")

        # augmented_path prepends the brew prefixes ahead of the base. Injected empty home, so a
        # machine with no user-scoped dirs behaves exactly as before P93 (no regression).
        empty_home = root / "emptyhome"
        empty_home.mkdir()
        ap = augmented_path("/usr/bin:/bin", home=empty_home, env={})
        ok(ap.startswith("/opt/homebrew/bin"), "augmented_path prepends Apple-Silicon brew prefix")
        ok("/usr/local/bin" in ap and ap.endswith("/usr/bin:/bin"), "augmented_path keeps base last")
        ok(user_prefixes(home=empty_home, env={}) == [], "no user-scoped dirs -> empty prefix list")

        # P93: the user-scoped dirs this repo tells people to install into must be SEARCHED, or the
        # recommended route dead-ends (the wizard would report an nvm-installed node as missing).
        # This pin fails against the pre-P93 augmented_path, which knew only the brew prefixes.
        uhome = root / "userhome"
        (uhome / USER_BIN).mkdir(parents=True)                       # uv + uv's pythonX.Y land here
        for v in ("v18.20.4", "v20.11.1", "v9.0.0"):                 # nvm layout: versions/node/<v>/bin
            (uhome / ".nvm" / NVM_NODE_SUBDIR / v / "bin").mkdir(parents=True)
        ups = user_prefixes(home=uhome, env={})
        ok(ups and ups[0] == str(uhome / USER_BIN), "user_prefixes leads with ~/.local/bin")
        ok(ups[1].endswith("v20.11.1/bin"), "user_prefixes orders nvm nodes newest first")
        ok(len(ups) == 4, "user_prefixes lists ~/.local/bin + every nvm node bin")
        uap = augmented_path("/usr/bin:/bin", home=uhome, env={})
        ok(uap.startswith(str(uhome / USER_BIN)), "augmented_path puts user-scoped dirs FIRST")
        ok(uap.index(str(uhome / USER_BIN)) < uap.index("/opt/homebrew/bin"),
           "user-scoped dirs outrank the machine-wide prefixes")
        # $NVM_DIR wins over ~/.nvm, the way nvm.sh itself resolves it.
        alt = root / "altnvm"
        (alt / NVM_NODE_SUBDIR / "v22.1.0" / "bin").mkdir(parents=True)
        alt_ups = user_prefixes(home=uhome, env={"NVM_DIR": str(alt)})
        ok(any(p.endswith("v22.1.0/bin") for p in alt_ups), "user_prefixes honors $NVM_DIR")
        ok(not any(".nvm" in p for p in alt_ups), "$NVM_DIR replaces the ~/.nvm default")
        # The functional pin: a node installed the user-only way is findable under a bare PATH.
        fake_node = uhome / ".nvm" / NVM_NODE_SUBDIR / "v20.11.1" / "bin" / "node"
        fake_node.write_text("#!/bin/sh\n")
        fake_node.chmod(fake_node.stat().st_mode | stat.S_IEXEC)
        ok(which("node", path=augmented_path("", home=uhome, env={})) == str(fake_node),
           "which() finds an nvm-installed node (the route the wizard recommends)")

        # which() finds a tool via an injected path, and via augmented_path when the tool sits in a
        # prefix-like dir we inject as base.
        fakebin = root / "fakebin"
        fakebin.mkdir()
        tool = fakebin / "faketool"
        tool.write_text("#!/bin/sh\n")
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
        ok(which("faketool", path=str(fakebin)) == str(tool), "which() resolves via injected path")
        ok(which("definitely_not_a_real_tool_xyz") is None, "which() None for a missing tool")

    passed = sum(1 for c, _ in checks if c)
    for c, m in checks:
        if not c:
            print(f"  [FAIL] {m}")
    print(f"env_paths selftest: {passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    # Plain run: report what this machine resolves (handy for debugging a Mac).
    import json
    print(json.dumps({
        "sys_executable": sys.executable,
        "venv_python": str(venv_python()) if venv_python() else None,
        "app_python": app_python(),
        "brew_prefixes": brew_prefixes(),
        "which_node": which("node"),
        "which_uv": which("uv"),
    }, indent=2))
