# ADR 0078 — On Windows the Drive hub may be a folder inside a Google Drive for desktop drive

- Status: accepted
- Date: 2026-10-07
- Phase: P102

## Context

Every folder the wizard takes from a text field passes `wizard._confined_folder`, which resolves it
and requires it to lie inside the user's home folder (P57), so a browser form cannot point the
import glob or the filesystem server's root at `/` or `C:\Windows`. On a Mac, Google Drive for
desktop mounts under `~/Library/CloudStorage`, inside the home folder. On Windows it mounts a drive
letter, with `My Drive` and `Shared drives` at its root, so the rule refused every Drive folder and
the hub could not be connected from the wizard. `watcher.detect_mirror_candidates` looked only
under `~/Library/CloudStorage`, so no candidate was offered either.

## Decision

- `_confined_folder` removes surrounding spaces and double quotes on every route (Explorer's "Copy
  as path" adds the quotes).
- Only the `/api/set-drive-hub` route (`wizard._drive_hub_folder`) passes `allow_drive`. With it,
  on Windows, a folder outside the home folder is accepted when `on_google_drive` reads it as a
  folder inside `<letter>:\My Drive` or `<letter>:\Shared drives` and that root folder exists.
  The root folder itself is refused (`drive_root`), as the home folder is. The paths are read with
  Windows rules, so the selftest runs the Windows cases on any system.
- The import folder and the storage folder keep the home-only rule.
- On Windows, `detect_mirror_candidates` offers `<letter>:\My Drive\Creator OS` for each drive
  that has it (`os.listdrives()` on Python 3.12 and later, else each letter whose root exists).

## Consequences

- A folder named `My Drive` at the root of any drive passes the rule, not only Drive for
  desktop's. The person confirms the path on the screen, and the hub holds only Creator OS's own
  files, so the widening is limited to the hub route. Volume labels and Drive's registry keys were
  considered as signals and not used, because they are not documented interfaces.
- Detection checks each drive letter; a disconnected network drive can make the hub screen slow to
  list candidates, never the rule itself.
