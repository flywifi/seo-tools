# ADR 0071 — The profile Doc is found by id or name, both mirror engines check content, and every run is stamped

- Status: accepted
- Date: 2026-10-01
- Phase: P99-2
- Amends: ADR 0070 (Decision 2's Doc lane and Decision 3's history)

## Context

ADR 0070's Doc lane looked up the hub's `Creator OS` and `Profile` folders through the Drive API
before it wrote the Doc. The credential has the `drive.file` scope, which reaches files "that you
open with an app or that the user shares with an app" (Google, "Choose Google Drive API
scopes"), and the hub folders are made by Drive for desktop or by hand, so the lookup cannot
succeed and the Doc was never written. The rsync form of the mirror checked file names only,
although `setup-context.local.json`, which it copies, is where the setup template says real
credentials config goes. A run that raised partway left no log line, and `install-agent` judged
the first run by the growth of a run list capped at 20 entries.

## Decision 1: the Doc is resolved without seeing the hub folders

`tools/profile_mirror.py::sync_doc` resolves the Doc in this order:

1. The remembered id, checked with a metadata read on every run. A deleted or trashed Doc is
   replaced (the trashed one is left in the trash); a Doc edited in Drive is rewritten from the
   computer, because the local file wins; a moved Doc is updated where it is.
2. The newest non-trashed Doc of that name the credential can see. The credential sees only Docs
   this app made, so a lost state file does not create a second Doc.
3. A new Doc in `Creator OS/Profile` when the API can see that folder, else in My Drive with no
   parent, with a one-time note to move it; a move keeps the id.

Rejected: creating the hub folders through the API, which would place a second "Creator OS"
folder beside the one Drive for desktop syncs; and the Google Picker, a browser flow the localhost
wizard does not run.

## Decision 2: the Doc renders what Drive holds

The Doc is rendered from the text accepted on this run, and for any other allowlisted file from
its copy in `Profile/`. A file missing or refused on the computer keeps its Drive copy, so it keeps
its Doc section too. A Drive copy that cannot be read, or that is itself refused, holds the Doc
for that run rather than writing it without the section.

## Decision 3: one content check for both engines

`refuse()` decodes the JSON and reads every key and scalar value: the `secret_scan` credential
patterns, vendor formats `secret_scan` states it does not read, keys named like credentials, and
credentials written in prose with a value shaped like a secret. `tools/profile-mirror.sh` calls it
through `profile_mirror.py check-file`, with the Python that `install-agent` writes into the plist;
a file it refuses, or cannot check, is not copied. The forms it does not read are stated in
`docs/PROFILE-MIRROR.md`.

## Decision 4: every run leaves a record

Each run of either engine writes one summary line to the shared, rotating log and replaces
`~/Library/Logs/CreatorOS/profile-mirror.last-run` with its time, status (`ok`, `error` or
`eperm`) and engine. The Python engine records the run in the state file in a `finally`, so a run
that raises is still logged and stamped. `install-agent` removes the old stamp before it starts
the first run and waits for a new one; an `eperm` stamp names Full Disk Access as the remedy,
an `error` stamp does not, and a run that leaves no stamp names it only as the remedy if the
launchd log says "Operation not permitted". The state keeps the last run and the last 20 runs that
copied, refused or failed something or did anything to the Doc but leave it unchanged. The plist keeps the venv
interpreter path rather than its resolved binary, sets `HOME`, and carries `--api` and
`--include-contact-profile` when they were chosen.

## Consequences

- The first Doc may land in My Drive; moving it into `Creator OS/Profile` once is a manual step.
- A known Doc costs one metadata read per run.
- The rsync engine now needs a working Python for its content check; without one it copies by
  name only and logs that contents were not checked.
- A text shaped like a credential (a title such as "Password: Season2Finale") stops that file from
  syncing until it is rephrased; the log and `status` name the file.
- Three behaviours depend on the live account and the Mac and are left to a first run there:
  whether Drive changes a Doc's `modifiedTime` after the app's own write, whether `parents` is
  reported for a folder the app cannot see, and which binary macOS privacy settings attribute the
  job to.
