# Profile mirror: your context in Google Drive, your credentials on your computer

Creator OS keeps what it learns about you (your voice, your channel, your setup answers, your
content calendar) in `pipeline/user-context/`, next to the credential files that let it post for
you. The credential files must never enter a synced folder. The profile mirror lets the repo live
outside Google Drive (for example `~/CreatorOS`) and still puts your context where every AI
engine can read it: the hub's `Profile/` folder (see `docs/DRIVE-HUB.md`).

The copy runs one way. Your computer's file wins, nothing in Drive is ever deleted by the
mirror, and only the files on the allowlist are copied.

## What is copied, and what never is

| File in `pipeline/user-context/` | Copied to `Creator OS/Profile/` |
|---|---|
| `voice-profile.local.json` | yes |
| `channel-context.local.json` | yes |
| `setup-context.local.json` | yes |
| `content-calendar.local.json` | yes |
| `creator-profile.local.json` | only with `--include-contact-profile` (it holds contact details) |
| `api-credentials.local.json`, `google-credentials.local.json`, `microsoft-credentials.local.json` | never, by name |
| anything a credential pattern in `tools/secret_scan.py` flags | never, by content |

The list lives in one place: `tools/profile_mirror.py::PROFILE_ALLOWLIST`
<!-- verify: tools/profile_mirror.py::PROFILE_ALLOWLIST -->. The refusal is
`tools/profile_mirror.py::refuse` <!-- verify: tools/profile_mirror.py::refuse -->, which checks
the name and then the content, so a credential pasted into a context file is not copied either.

## Two ways to run it

**The Python tool (recommended).** It copies the files, logs every run, remembers what it copied,
and can also write one Google Doc, "About me and my voice", that Gemini Gems, Gemini Notebook and
Claude Projects read as live Knowledge.

```bash
python3 tools/profile_mirror.py check                  # what would be copied; writes nothing
python3 tools/profile_mirror.py sync                   # copy changed files into Profile/
python3 tools/profile_mirror.py sync --api             # also create or update the Google Doc
python3 tools/profile_mirror.py status                 # last runs, from the state file
```

**The rsync recipe.** `tools/profile-mirror.sh` copies the same allowlist with the rsync that
ships with macOS, refuses the credential names, never deletes, and logs to the same folder. Use it
if you prefer a plain script; it cannot write the Google Doc.

```bash
bash tools/profile-mirror.sh "$HOME/Library/CloudStorage/GoogleDrive-<account>/My Drive/Creator OS"
```

The hub path is found automatically from Drive for desktop's folder under
`~/Library/CloudStorage/`. Pass `--hub PATH` when you have more than one Google account signed in.

## Running it on a schedule (macOS)

```bash
python3 tools/profile_mirror.py install-agent                  # the Python tool, every 15 minutes
python3 tools/profile_mirror.py install-agent --engine rsync   # the rsync recipe instead
python3 tools/profile_mirror.py uninstall-agent
```

`install-agent` writes `~/Library/LaunchAgents/com.creatoros.profile-mirror.plist` (your user
only, no admin rights) and loads it with `launchctl bootstrap gui/<your uid>`. It runs at minutes
7, 22, 37 and 52 of each hour. It does not run at login on purpose, so it never races Drive for
desktop while Drive is still starting; a run missed while the Mac slept happens once on wake.
The agent is built by `tools/profile_mirror.py::build_plist`
<!-- verify: tools/profile_mirror.py::build_plist -->.

## After you move or update the repo

The agent stores absolute paths (launchd requires them), so it points at the folder the repo was
in when you installed it. After you move the repo, rename it, or change which Python you use, run
`python3 tools/profile_mirror.py install-agent` again. It replaces the old agent. After a normal
`git pull` nothing needs doing.

## Logs and history

| What | Where |
|---|---|
| Every run, with each file copied, kept or refused | `~/Library/Logs/CreatorOS/profile-mirror.log` (rotates at 500 KB, keeps 3) |
| What launchd itself printed (start-up errors) | `~/Library/Logs/CreatorOS/profile-mirror.launchd.log` |
| The last 20 runs, and the sha256 of each file copied | `pipeline/user-context/profile-mirror-state.local.json` (gitignored) |

A file edited in Drive since the last run is logged as a warning and then overwritten, because
the local file wins. Google Drive keeps the earlier version: open the file in Drive, then
**File information > Manage versions** (or **Version history** for the Google Doc) to get it back.

## The Google Doc and what `--api` can reach

`sync --api` uses the `drive_api_polling` credential you set up in the wizard. That credential
has the `drive.file` scope, so it can only see folders and files this app created or opened. If
the hub was created by hand in Drive, the tool reports that it cannot find `Profile/` through the
API and skips the Doc; the files are still copied. Let the wizard create the hub
(`docs/DRIVE-HUB.md`), or open the folder once from the wizard's Drive screen, and the Doc works.
The Doc is uploaded as Markdown and converted by Drive to a Google Doc.

## Why the repo does not live in Google Drive

Drive for desktop syncs everything under its folder, and it has no ignore list. A repo inside it
would sync `api-credentials.local.json` and the other credential files to the cloud. `setup.py`
and the wizard's Drive hub screen warn when the repo sits under `~/Library/CloudStorage/`, iCloud
Drive or Dropbox (`tools/env_paths.py::cloud_synced_root`
<!-- verify: tools/env_paths.py::cloud_synced_root -->), and point here.

```sources
[
  {"id": "google-drive-desktop-macos", "url": "https://support.google.com/drive/answer/12178485"},
  {"id": "apple-launchd-plist-man", "name": "launchd.plist(5) manual page (Xcode man pages mirror)", "url": "https://keith.github.io/xcode-man-pages/launchd.plist.5.html", "category": "os-platform", "tier": "T1", "extraction_hint": "Program and ProgramArguments paths must be absolute; RunAtLoad defaults to false; StartCalendarInterval events missed during sleep are coalesced into one event on wake."},
  {"id": "apple-launchctl-man", "name": "launchctl(1) manual page (Xcode man pages mirror)", "url": "https://keith.github.io/xcode-man-pages/launchctl.1.html", "category": "os-platform", "tier": "T1", "extraction_hint": "bootstrap and bootout take a domain target; the per-user GUI domain is gui/<uid>."},
  {"id": "apple-openrsync-man", "name": "openrsync(1) manual page (Xcode man pages mirror)", "url": "https://keith.github.io/xcode-man-pages/openrsync.1.html", "category": "os-platform", "tier": "T1", "extraction_hint": "The rsync shipped with recent macOS is openrsync; the include/exclude filter options and -a/-t behaviour the recipe uses."},
  {"id": "google-drive-api-manage-uploads", "name": "Google Drive API - Upload file data", "url": "https://developers.google.com/workspace/drive/api/guides/manage-uploads", "category": "api-changelog", "tier": "T1", "extraction_hint": "Multipart upload; setting mimeType application/vnd.google-apps.document on the metadata converts an uploaded file to a Google Doc."}
]
```
