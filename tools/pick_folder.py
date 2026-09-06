#!/usr/bin/env python3
"""pick_folder.py -- pop a native "choose a folder" dialog and print the chosen path (P51, item 10).

The wizard runs this as a short-lived SUBPROCESS (python3 tools/pick_folder.py). That matters: Tk must
run on the process's main thread, but the wizard's HTTP handler runs on a daemon thread -- a fresh
subprocess owns its own main thread and sidesteps the rule (docs.python.org/3/library/tkinter.html).

Order of attempts:
  1. tkinter.filedialog.askdirectory  (stdlib, but an OPTIONAL module -- absent on some Linux/Homebrew builds)
  2. OS-native fallback: macOS `osascript`, Windows PowerShell FolderBrowserDialog (-STA), Linux zenity/kdialog
Prints the selected POSIX path to stdout, or an empty string on cancel / no available backend. Never
raises; a headless machine (no DISPLAY) degrades silently so the wizard's text field stays the floor.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys


def _os() -> str:
    s = platform.system()
    if s == "Darwin":
        return "mac"
    if s == "Windows":
        return "windows"
    return "linux"


def _has_display() -> bool:
    """A GUI dialog can only appear if there's a display. macOS/Windows always have one for a user
    session; Linux needs X11 or Wayland."""
    if _os() in ("mac", "windows"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _tk_pick():
    """Return the chosen path, '' on cancel, or None if tkinter is unavailable/unusable (fall through)."""
    if not _has_display():
        return None
    try:
        import tkinter
        from tkinter import filedialog
    except Exception:  # noqa: BLE001  (optional module may be missing)
        return None
    try:
        root = tkinter.Tk()
        root.withdraw()
        try:
            root.update()   # macOS: nudge the hidden root so the dialog takes focus
        except Exception:  # noqa: BLE001
            pass
        path = filedialog.askdirectory(mustexist=True)
        try:
            root.destroy()
        except Exception:  # noqa: BLE001
            pass
        return path or ""
    except Exception:  # noqa: BLE001
        return None


def _os_command(osn: str):
    """The native fallback command for this OS, or None if there is no usable backend."""
    if osn == "mac":
        return ["osascript", "-e", 'POSIX path of (choose folder with prompt "Select a folder")']
    if osn == "windows":
        ps = ("Add-Type -AssemblyName System.Windows.Forms; "
              "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
              "if ($f.ShowDialog() -eq 'OK') { [Console]::Out.Write($f.SelectedPath) }")
        # -STA is mandatory: WinForms dialogs need a single-threaded apartment (pwsh 7 defaults to MTA).
        return ["powershell", "-NoProfile", "-STA", "-Command", ps]
    # linux
    if shutil.which("zenity"):
        return ["zenity", "--file-selection", "--directory", "--title=Select a folder"]
    if shutil.which("kdialog"):
        return ["kdialog", "--getexistingdirectory", os.path.expanduser("~")]
    return None


def _run(cmd) -> str:
    """Run a fallback dialog command. Returns the trimmed stdout path, or '' on cancel/error (a
    non-zero exit means the user cancelled)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception:  # noqa: BLE001
        return ""
    if r.returncode != 0:
        return ""
    return (r.stdout or "").strip()


def _os_pick() -> str:
    osn = _os()
    if osn == "linux" and not _has_display():
        return ""
    cmd = _os_command(osn)
    if not cmd:
        return ""
    return _run(cmd)


def pick_folder() -> str:
    """Return the chosen folder path, or '' if cancelled / no dialog backend is available."""
    result = _tk_pick()
    if result is not None:
        return result   # tkinter worked ('' means the user cancelled)
    return _os_pick()


def _selftest() -> int:
    failures: list[str] = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    # Command construction per OS (pure, no dialog shown).
    mac = _os_command("mac")
    check("osascript" in mac[0] and "choose folder" in mac[-1], "mac osascript command wrong")
    win = _os_command("windows")
    check("-STA" in win and any("FolderBrowserDialog" in a for a in win), "windows -STA/FolderBrowserDialog missing")
    # Linux command depends on which() being present; just assert it's a list-or-None without raising.
    lin = _os_command("linux")
    check(lin is None or (lin[0] in ("zenity", "kdialog")), "linux fallback command unexpected")

    # _run returns '' on a non-zero exit (a cancel), never raises.
    rc = _run([sys.executable, "-c", "import sys; sys.exit(1)"])
    check(rc == "", "_run should return '' on non-zero exit")
    rc = _run([sys.executable, "-c", "print('/some/dir')"])
    check(rc == "/some/dir", "_run should return trimmed stdout on success")

    # Headless graceful degrade: no DISPLAY -> tkinter returns None, linux os-pick returns ''.
    saved = {k: os.environ.pop(k, None) for k in ("DISPLAY", "WAYLAND_DISPLAY")}
    try:
        if _os() == "linux":
            check(_tk_pick() is None, "headless tkinter should return None")
            check(_os_pick() == "", "headless linux os-pick should return ''")
        # pick_folder must always return a str and never raise.
        check(isinstance(pick_folder(), str), "pick_folder must return a str")
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v

    if failures:
        print("pick_folder selftest FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("pick_folder selftest OK (per-OS command construction + graceful headless degrade)")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    sys.stdout.write(pick_folder() or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
