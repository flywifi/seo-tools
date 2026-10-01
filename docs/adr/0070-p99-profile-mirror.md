# ADR 0070 — The repo stays out of cloud-synced folders; context reaches Drive through a one-way mirror

- Status: accepted
- Date: 2026-09-30
- Phase: P99

## Context

The creator's context (voice profile, channel context, setup answers, content calendar) lives in
`pipeline/user-context/` beside the credential files that let Creator OS post. Google Drive for
desktop syncs everything under its folder and has no ignore list, so a repo placed there would
sync the credential files. The AI engines that read Drive still need the context files.

## Decision 1: the repo lives outside cloud-synced folders, and setup says so

`tools/env_paths.py::cloud_synced_root` names the cloud-synced folder a path sits in
(`~/Library/CloudStorage/`, iCloud Drive, Dropbox). `tools/setup.py` and the wizard's Drive hub
screen print a warning that points at `docs/PROFILE-MIRROR.md`. It is a warning, not a refusal:
setup still runs.

## Decision 2: a one-way, allowlisted mirror carries the context

`tools/profile_mirror.py` copies the files on `PROFILE_ALLOWLIST` into the hub's `Profile/`
folder. The computer's copy wins; nothing in Drive is deleted. The three credential files are
refused by name, and a file a `tools/secret_scan.py` pattern flags is refused by content. An
optional `--api` run writes one Google Doc through the Drive API with the existing
`drive.file` credential. `tools/profile-mirror.sh` offers the same allowlist through rsync.

## Decision 3: scheduling, logs and history are user-scoped

`install-agent` writes a launchd agent into `~/Library/LaunchAgents` and loads it into the
user's own `gui/<uid>` domain, at minutes 7, 22, 37 and 52, without RunAtLoad. Each run logs to
`~/Library/Logs/CreatorOS/` (rotating) and records the last 20 runs, with file hashes, in a
gitignored state file. Drive's own version history is the recovery path for an overwritten file.
(ADR 0071 changes the history to the last 20 runs that changed something, adds a last-run stamp
written by both engines, and extends the content check to the rsync form.)

## Consequences

- The agent stores absolute paths; moving the repo or changing Python means re-running
  `install-agent`.
- The Google Doc needs the hub to be visible to the `drive.file` credential; a hub made by hand
  in Drive gets the files but not the Doc. (Superseded by ADR 0071: the Doc no longer needs the
  hub folders to be visible.)
- Only the allowlisted files leave the computer; a new context file needs an allowlist entry.
