#!/bin/bash
# Double-click this file to open the Creator OS setup wizard in your web browser.
# No terminal knowledge needed.
#
# First-run note (macOS): a file you got by 'git clone' is NOT blocked and just runs. A file you got
# by downloading a .zip may be blocked by Gatekeeper the first time. To allow it: open
# System Settings > Privacy & Security, scroll to the Security section, and click "Open Anyway",
# then confirm with your admin password. (Right-click > Open no longer bypasses this on macOS
# Sequoia and Tahoe.)

cd "$(dirname "$0")" || exit 1
echo "Starting Creator OS setup..."

# Make the user's own tools AND Homebrew tools visible even under a double-click launch. A
# double-clicked .command runs a non-login shell that loads neither, so both would otherwise look
# "missing." User-scoped dirs go first because user-scoped is the install default (P93,
# docs/INSTALL-SCOPE.md): the uv installer puts uv and `uv python install`'s pythonX.Y in
# ~/.local/bin. Homebrew's prefixes follow, for Apple Silicon (/opt/homebrew) and Intel
# (/usr/local), so an existing machine-wide install keeps working.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Choose an interpreter: prefer the private .venv toolbox (created during setup); otherwise find a
# real, working python3 (the built-in /usr/bin/python3 is only a stub until the Command Line Tools
# are installed). We probe each candidate with a tiny import to confirm it actually works and
# that it is Python 3.12 or newer (the repo floor since P80: numpy 2.5 dropped 3.11, and the
# DaVinci Resolve scripting bridge caps at 3.12, so 3.12 is the one version every lane agrees on).
#
# The .venv is probed like every other candidate, NOT trusted for existing. A Homebrew python
# upgrade (python@3.12 -> python@3.13) relocates the framework the venv symlinks into: the
# interpreter still exists and is still executable, so an -x test passes while the interpreter
# is dead. Trusting -x meant PY was set to a broken interpreter, the working fallbacks were
# never tried, and the user got a dyld / "No module named encodings" traceback instead of the
# install instructions below -- defeating the entire point of this launcher (P73).
PY=""
if [ -x ".venv/bin/python3" ] && .venv/bin/python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)' >/dev/null 2>&1; then
  PY=".venv/bin/python3"
else
  if [ -x ".venv/bin/python3" ]; then
    if venv_v=$(.venv/bin/python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null); then
      echo "Note: the private .venv toolbox runs Python $venv_v, but Creator OS needs 3.12 or newer."
      echo "Falling back to a system Python for this launch."
    else
      echo "Note: the private .venv toolbox is present but its interpreter does not run"
      echo "(usually a Homebrew Python upgrade moved it). Falling back to a system Python."
    fi
    echo "To rebuild it on 3.12: rm -rf .venv && python3.12 tools/setup.py --install-deps"
    echo ""
  fi
  # User-scoped interpreters first (P93). `uv python install 3.12` writes ~/.local/bin/python3.12 --
  # a VERSIONED name, never a bare python3 -- so the versioned candidates are listed explicitly,
  # newest supported first. Without them the route this launcher recommends would dead-end here.
  for c in "$HOME/.local/bin/python3.14" "$HOME/.local/bin/python3.13" \
           "$HOME/.local/bin/python3.12" "$HOME/.local/bin/python3" \
           /opt/homebrew/bin/python3 /usr/local/bin/python3 \
           /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
           "$(command -v python3 2>/dev/null)"; do
    if [ -n "$c" ] && [ -x "$c" ] && "$c" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)' >/dev/null 2>&1; then
      PY="$c"
      break
    fi
  done
fi

if [ -n "$PY" ]; then
  "$PY" tools/wizard.py
else
  echo ""
  echo "Python 3.12 or newer was not found on this Mac (the built-in 'python3' is only a stub,"
  echo "and an older Python is skipped on purpose: Creator OS needs 3.12)."
  echo "Install it once, then double-click this file again."
  echo ""
  echo "Recommended (user-only: everything stays in your account, no admin password):"
  echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "    uv python install 3.12"
  echo "  That puts python3.12 in ~/.local/bin; this launcher looks there."
  echo ""
  echo "Machine-wide alternatives (affect the whole computer, need an admin password):"
  echo "  - the notarized python.org universal2 installer (no security prompt):"
  echo "      https://www.python.org/downloads/macos/"
  echo "  - or install Homebrew (https://brew.sh), then run: brew install python@3.12"
  echo ""
  echo "Details: docs/INSTALL-SCOPE.md"
  echo ""
  read -n 1 -s -r -p "Press any key to close this window."
fi
