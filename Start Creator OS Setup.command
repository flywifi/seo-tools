#!/bin/bash
# Double-click this file to open the Creator OS setup wizard in your web browser.
# No terminal knowledge needed. macOS may ask you to confirm the first time
# (right-click the file, choose Open, then Open again — or System Settings ->
# Privacy & Security -> Open Anyway). Files from a fresh 'git clone' are not blocked.

cd "$(dirname "$0")" || exit 1
echo "Starting Creator OS setup..."

if command -v python3 >/dev/null 2>&1; then
  python3 tools/wizard.py
else
  echo ""
  echo "Python 3 is not installed on this Mac."
  echo "Install it, then double-click this file again:"
  echo "  - Easiest: install Homebrew (https://brew.sh), then run: brew install python"
  echo "  - Or download the installer from https://www.python.org/downloads/macos/"
  echo ""
  read -n 1 -s -r -p "Press any key to close this window."
fi
