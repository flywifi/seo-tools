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

# Make Homebrew tools visible even under a double-click launch. A double-clicked .command runs a
# non-login shell that does NOT load your Homebrew PATH, so brew-installed tools would otherwise
# look "missing." Prepending both prefixes fixes that on Apple Silicon (/opt/homebrew) and Intel
# (/usr/local).
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# Choose an interpreter: prefer the private .venv toolbox (created during setup); otherwise find a
# real, working python3 (the built-in /usr/bin/python3 is only a stub until the Command Line Tools
# are installed). We probe each candidate with a tiny import to confirm it actually works.
#
# The .venv is probed like every other candidate, NOT trusted for existing. A Homebrew python
# upgrade (python@3.13 -> python@3.14) relocates the framework the venv symlinks into: the
# interpreter still exists and is still executable, so an -x test passes while the interpreter
# is dead. Trusting -x meant PY was set to a broken interpreter, the working fallbacks were
# never tried, and the user got a dyld / "No module named encodings" traceback instead of the
# install instructions below -- defeating the entire point of this launcher (P73 D6-F10).
PY=""
if [ -x ".venv/bin/python3" ] && .venv/bin/python3 -c 'import sys' >/dev/null 2>&1; then
  PY=".venv/bin/python3"
else
  if [ -x ".venv/bin/python3" ]; then
    echo "Note: the private .venv toolbox is present but its interpreter does not run"
    echo "(usually a Homebrew Python upgrade moved it). Falling back to a system Python."
    echo "To rebuild it: rm -rf .venv && python3 tools/setup.py --install-deps"
    echo ""
  fi
  for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 \
           /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
           "$(command -v python3 2>/dev/null)"; do
    if [ -n "$c" ] && [ -x "$c" ] && "$c" -c 'import sys' >/dev/null 2>&1; then
      PY="$c"
      break
    fi
  done
fi

if [ -n "$PY" ]; then
  "$PY" tools/wizard.py
else
  echo ""
  echo "Python 3 is not installed on this Mac (the built-in 'python3' is only a stub)."
  echo "Install it once, then double-click this file again:"
  echo "  - Easiest: the notarized python.org universal2 installer (no security prompt):"
  echo "      https://www.python.org/downloads/macos/"
  echo "  - Or install Homebrew (https://brew.sh), then run: brew install python@3.13"
  echo ""
  read -n 1 -s -r -p "Press any key to close this window."
fi
