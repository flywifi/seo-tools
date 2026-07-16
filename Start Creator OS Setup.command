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
PY=""
if [ -x ".venv/bin/python3" ]; then
  PY=".venv/bin/python3"
else
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
