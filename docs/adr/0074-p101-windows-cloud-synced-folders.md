# ADR 0074 — On Windows, the cloud-synced repo warning reads OneDrive's variables and Google Drive's drive markers

- Status: accepted
- Date: 2026-10-04
- Phase: P101

## Context

`setup.py` and the wizard's Drive hub screen warn when the repo sits in a folder a sync client
keeps in step with the cloud, because the repo holds its credential files in
`pipeline/user-context/` and a synced repo would upload them (`env_paths.cloud_synced_root`, P99).
The folders it knew were macOS ones: `~/Library/CloudStorage` (Google Drive, OneDrive and Dropbox
under File Provider), `~/Library/Mobile Documents` (iCloud Drive) and `~/Dropbox`. Of these, only
`~/Dropbox` is a folder a Windows sync client uses, so a repo in the OneDrive folder or on Google Drive for desktop's drive was
not warned about.

## Decision 1: OneDrive by its environment variables, iCloud by its folder

`cloud_synced_root` treats as synced the absolute folder named by any of the `OneDrive`,
`OneDriveConsumer` and `OneDriveCommercial` environment variables (on the Windows computer it was
checked on, `OneDrive` named the folder OneDrive syncs), and adds `~/iCloud Drive`, where iCloud for Windows keeps files
by default, and `~/iCloudDrive`, the name earlier versions used. An unset, empty or relative
variable names nothing. The variables are read on every system, so the selftest exercises them on
Linux CI.

## Decision 2: Google Drive by the folder at its drive's root, not by its registry settings

Google Drive for desktop on Windows serves My Drive on a virtual drive, `G:` unless the person
picks another letter or a folder. Its settings live in the registry (`HKCU\Software\Google\DriveFS`
for the user, `HKLM\Software\Google\DriveFS` host-wide, `HKLM\Software\Policies\Google\DriveFS` as
an override), where a `DefaultMountPoint` names a drive letter or a path and each account's
in-app preference sits in the `PerAccountPreferences` JSON. Those values are preferences, not the
current mount: an account that kept the default letter can record none, and the JSON can carry
an entry for an account that is not signed in, so reading them can miss the drive Drive is using
and name a letter that is not Drive's. (`PerAccountPreferences` is not in Google's documentation;
it was read from one computer's registry.)

`cloud_synced_root` instead finds the mount point the path is on (the nearest of the path and its
parents that `os.path.ismount` accepts; a drive root, or a volume mounted in a folder) and treats
it as synced when it holds a `.shortcut-targets-by-id` or a `.file-revisions-by-id` folder,
hidden folders seen at the root of Google Drive for desktop's drive (neither is in Google's
documentation; either is enough, since an account may lack one of them). `My Drive` was not used as
the marker: its
name follows the system language (the `DisableLocalizedVirtualFolders` setting exists to stop
that). The volume label was not used either: it can carry the account's address, cut short.

## Consequences

- A repo in a folder an OneDrive variable names, in `~/iCloud Drive` or `~/iCloudDrive`, or on a
  volume whose root holds one of the two marker folders gets the same warning as on macOS, naming
  that folder or drive.
- A My Drive folder in mirror mode is a folder of the person's choosing with no marker, so a repo
  in it is not detected; `docs/PROFILE-MIRROR.md` says to keep the repo out of it.
- Not detected either: an iCloud folder moved elsewhere (iCloud for Windows 14 and later can
  move it), OneDrive folders no variable names (a further work or school account, SharePoint
  libraries synced beside the OneDrive folder), and a Drive drive whose root holds neither marker.
- A folder of the person's own named `iCloud Drive` or `iCloudDrive` in their user folder, or a
  volume whose root holds a marker folder for another reason, is warned about as synced; the
  warning changes nothing on disk.
- The warning shows the person's own home folder as the example destination and
  `env_paths.python_command()` as the command: `py -3` on Windows when the py launcher is
  installed, else `python`, and `python3` elsewhere.

```sources
[
  {"id": "apple-icloud-windows-drive", "name": "Apple Support - Set up iCloud Drive on your Windows computer", "url": "https://support.apple.com/guide/icloud-windows/set-up-icloud-drive-icw0144825a5/icloud", "category": "os-platform", "tier": "T1", "extraction_hint": "Your files and folders are stored in C:\\Users\\[user name]\\iCloud Drive by default; iCloud for Windows 14 or later can choose a different location."},
  {"id": "google-drive-desktop-advanced-config", "name": "Google Workspace Admin Help - Advanced Drive for desktop configuration", "url": "https://knowledge.workspace.google.com/admin/drive/advanced-drive-for-desktop-configuration", "category": "os-platform", "tier": "T1", "extraction_hint": "Windows settings locations HKLM\\Software\\Google\\DriveFS (host-wide), HKCU\\Software\\Google\\DriveFS (user), HKLM\\Software\\Policies\\Google\\DriveFS (override); in-app user preferences take precedence over host-wide settings and overrides over in-app preferences; DefaultMountPoint is a drive letter or a path on an existing drive."},
  {"id": "google-drive-desktop-settings", "name": "Google Drive Help - Customize Drive for desktop settings", "url": "https://support.google.com/drive/answer/13470231", "category": "os-platform", "tier": "T1", "extraction_hint": "On Windows the Google Drive streaming location is a drive letter or a folder; up to 4 accounts at one time; when switching to mirroring, My Drive files download to the folder you select."}
]
```
