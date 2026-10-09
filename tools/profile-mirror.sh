#!/bin/bash
# One-way copy of the profile files from the repo into the Drive hub's Profile folder.
# Usage: tools/profile-mirror.sh <repo>/pipeline/user-context "<Drive hub>/Profile" [python]
# Only the names on ALLOWLIST are copied (the same list as tools/profile_mirror.py
# PROFILE_ALLOWLIST; its selftest compares them). Credential files are refused by name, and each
# file's content is checked with `profile_mirror.py check-file` run by the Python given as the
# third argument (install-agent always gives it); a file the check refuses, or cannot check, is
# not copied. Without a Python only the names are checked, and the run says so.
# Nothing is deleted from Drive: a file missing locally keeps its last copy there.
# Log: ~/Library/Logs/CreatorOS/profile-mirror.log, rotated at 512000 bytes keeping .1 to .3 like
# the Python engine, one summary line per run; profile-mirror.last-run beside it holds the run's
# time, status (ok, error, eperm) and engine, which install-agent reads. Docs: docs/PROFILE-MIRROR.md.
set -euo pipefail

SRC="${1:?usage: profile-mirror.sh <source dir> <Drive Profile dir> [python]}"
DEST="${2:?usage: profile-mirror.sh <source dir> <Drive Profile dir> [python]}"
PY="${3:-}"
# The selftest points ROOT and RSYNC at its own copies; launchd runs the repo's and the system's.
ROOT="${PROFILE_MIRROR_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
RSYNC="${PROFILE_MIRROR_RSYNC:-/usr/bin/rsync}"
LOG_DIR="${HOME:?HOME is not set}/Library/Logs/CreatorOS"
LOG="${LOG_DIR}/profile-mirror.log"
STAMP="${LOG_DIR}/profile-mirror.last-run"
MAX_LOG_BYTES=512000

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
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
# Rotate like the Python engine's RotatingFileHandler: past MAX_LOG_BYTES the log becomes .1 and
# .1 to .3 shift down, so both engines can share one file.
if [ -f "$LOG" ] && [ "$(( $(wc -c < "$LOG") ))" -ge "$MAX_LOG_BYTES" ]; then
  rm -f "$LOG.3"
  if [ -f "$LOG.2" ]; then mv -f "$LOG.2" "$LOG.3"; fi
  if [ -f "$LOG.1" ]; then mv -f "$LOG.1" "$LOG.2"; fi
  mv -f "$LOG" "$LOG.1"
fi
log() { printf '%s %s %s\n' "$(now)" "$1" "$2" >> "$LOG"; }
stamp() { printf '%s %s rsync\n' "$(now)" "$1" > "$STAMP.tmp" && mv -f "$STAMP.tmp" "$STAMP"; }

if [ ! -d "$DEST" ]; then
  why=$(ls -d "$DEST" 2>&1 || true)
  case "$why" in
    *"Operation not permitted"*)
      log ERROR "macOS blocked access to $DEST (Operation not permitted)"; st=eperm ;;
    *)
      log ERROR "Drive folder not found: $DEST (is Google Drive for desktop running?)"; st=error ;;
  esac
  log INFO "run $st: the Drive folder could not be read"
  stamp "$st"
  exit 1
fi
if [ -z "$PY" ]; then
  log WARNING "file contents are not checked (no Python given); names are"
fi

copied=0; unchanged=0; missing=0; refused=0; errors=0; eperm=0
for f in "${ALLOWLIST[@]}"; do
  for bad in "${REFUSED[@]}"; do
    if [ "$f" = "$bad" ]; then
      log WARNING "refused $f: a credential file"; refused=$((refused + 1)); continue 2
    fi
  done
  if [ ! -f "$SRC/$f" ]; then
    log INFO "missing locally, Drive copy kept: $f"; missing=$((missing + 1)); continue
  fi
  if [ -n "$PY" ] && ! why=$("$PY" "$ROOT/tools/profile_mirror.py" check-file "$SRC/$f" 2>&1); then
    log WARNING "refused $f: $why"; refused=$((refused + 1)); continue
  fi
  if [ -f "$DEST/$f" ] && cmp -s "$SRC/$f" "$DEST/$f"; then
    unchanged=$((unchanged + 1)); continue
  fi
  if out=$("$RSYNC" -t "$SRC/$f" "$DEST/$f" 2>&1); then
    log INFO "copied $f"; copied=$((copied + 1))
  else
    log ERROR "could not copy $f: $out"; errors=$((errors + 1))
    case "$out" in *"Operation not permitted"*) eperm=1 ;; esac
  fi
done

if [ "$eperm" = 1 ]; then st=eperm; elif [ $((errors + refused)) -gt 0 ]; then st=error; else st=ok; fi
log INFO "run $st: copied $copied, unchanged $unchanged, missing $missing, refused $refused, errors $errors, Doc off"
stamp "$st"
if [ "$st" = ok ]; then exit 0; fi
exit 1
