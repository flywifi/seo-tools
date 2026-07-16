#!/usr/bin/env python3
"""Shared interpreter/PATH helpers for a Mac-friendly launch and install.

Two macOS realities drive this module (see docs/SETUP_MAC.md and the P53 stress test):

1. The "private toolbox": dependencies install into a repo-local ``.venv`` so a Homebrew Python
   (which follows PEP 668 and refuses a global ``pip install``) is never touched. The app's heavy
   tools then run under that venv interpreter. ``app_python()`` returns the venv python when it
   exists and otherwise the current interpreter, so a machine without a ``.venv`` behaves exactly
   as before (no regression).

2. GUI-launch PATH: a double-clicked ``.command`` runs a non-login, non-interactive zsh that
   sources only ``~/.zshenv``, so Homebrew's ``/opt/homebrew/bin`` (Apple Silicon) or
   ``/usr/local/bin`` (Intel) is absent from PATH. ``which()`` prepends both prefixes so
   brew-installed binaries (node, uv, ffmpeg, whisper-cli) are found even under a double-click.

Stdlib only. Pure and injectable so the selftest can simulate a macOS PATH with no real hardware.
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repo root (tools/..)

# Homebrew bin dirs. /opt/homebrew (Apple Silicon) and /usr/local (Intel). Both are listed and
# harmless when absent; we never assume one architecture.
BREW_PREFIXES = ("/opt/homebrew/bin", "/usr/local/bin")


def repo_root() -> Path:
    return ROOT


def venv_python(root=None):
    """Return the repo ``.venv`` interpreter Path if it exists, else None."""
    base = Path(root) if root is not None else ROOT
    for c in (
        base / ".venv" / "bin" / "python3",
        base / ".venv" / "bin" / "python",
        base / ".venv" / "Scripts" / "python.exe",  # Windows
    ):
        if c.exists():
            return c
    return None


def app_python(root=None) -> str:
    """The interpreter the app's heavy tools should run under: the ``.venv`` python when present,
    else the current interpreter (today's behavior, so no ``.venv`` == no change)."""
    vp = venv_python(root)
    return str(vp) if vp else sys.executable


def brew_prefixes() -> list:
    return list(BREW_PREFIXES)


def augmented_path(base=None) -> str:
    """PATH string with the Homebrew prefixes prepended, so ``which()`` finds brew tools under a
    GUI (double-click) launch that has a bare PATH. ``base`` defaults to the current ``$PATH``."""
    base = base if base is not None else os.environ.get("PATH", "")
    parts = list(BREW_PREFIXES)
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

        # Create a fake .venv/bin/python3 -> venv_python + app_python pick it up.
        vbin = root / ".venv" / "bin"
        vbin.mkdir(parents=True)
        vpy = vbin / "python3"
        vpy.write_text("#!/bin/sh\n")
        vpy.chmod(vpy.stat().st_mode | stat.S_IEXEC)
        ok(venv_python(root) == vpy, "venv_python finds .venv interpreter")
        ok(app_python(root) == str(vpy), "app_python returns .venv interpreter when present")

        # augmented_path prepends the brew prefixes ahead of the base.
        ap = augmented_path("/usr/bin:/bin")
        ok(ap.startswith("/opt/homebrew/bin"), "augmented_path prepends Apple-Silicon brew prefix")
        ok("/usr/local/bin" in ap and ap.endswith("/usr/bin:/bin"), "augmented_path keeps base last")

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
