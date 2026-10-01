#!/bin/bash
# One-way copy of the profile files from the repo into the Drive hub's Profile folder.
# Usage: tools/profile-mirror.sh <repo>/pipeline/user-context "<Drive hub>/Profile"
# Only the names on ALLOWLIST are copied (the same list as tools/profile_mirror.py
# PROFILE_ALLOWLIST; its selftest compares them). Credential files are refused by name.
# Nothing is deleted from Drive: a file missing locally keeps its last copy there.
# Log: ~/Library/Logs/CreatorOS/profile-mirror.log. Docs: docs/PROFILE-MIRROR.md.
set -euo pipefail

SRC="${1:?usage: profile-mirror.sh <source dir> <Drive Profile dir>}"
DEST="${2:?usage: profile-mirror.sh <source dir> <Drive Profile dir>}"
LOG_DIR="${HOME}/Library/Logs/CreatorOS"
LOG="${LOG_DIR}/profile-mirror.log"

ALLOWLIST=(
  voice-profile.local.json
  channel-context.local.json
  setup-context.local.json
  content-calendar.local.json
)
REFUSED=(
  api-credentials.local.json
  google-credentials.local.json
  microsoft-credentials.local.json
)

mkdir -p "$LOG_DIR"
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; }

if [ ! -d "$DEST" ]; then
  log "ERROR: Drive folder not found: $DEST (is Google Drive for desktop running?)"
  exit 1
fi

status=0
for f in "${ALLOWLIST[@]}"; do
  for bad in "${REFUSED[@]}"; do
    if [ "$f" = "$bad" ]; then
      log "REFUSED: $f is a credential file"
      status=1
      continue 2
    fi
  done
  if [ ! -f "$SRC/$f" ]; then
    log "missing locally: $f (Drive copy kept)"
    continue
  fi
  if /usr/bin/rsync -t "$SRC/$f" "$DEST/$f"; then
    log "copied: $f"
  else
    log "ERROR: rsync failed for $f"
    status=1
  fi
done
exit "$status"
