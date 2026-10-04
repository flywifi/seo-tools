# Profile mirror: your context in Google Drive, your credentials on your computer

Creator OS keeps what it learns about you (your voice, your channel, your setup answers, your
content calendar) in `pipeline/user-context/`, next to the credential files that let it post for
you. The credential files must never enter a synced folder. The profile mirror lets the repo live
outside Google Drive (for example `~/CreatorOS`) and still puts your context where the AI engines
that read your Drive can use it: the hub's `Profile/` folder (see `docs/DRIVE-HUB.md`).

The copy runs one way. Your computer's file wins, the mirror deletes nothing in Drive, and only
the files on the allowlist are copied.

## What is copied, and what is refused

| File in `pipeline/user-context/` | Copied to `Creator OS/Profile/` |
|---|---|
| `voice-profile.local.json` | yes |
| `channel-context.local.json` | yes |
| `setup-context.local.json` | yes |
| `content-calendar.local.json` | yes |
| `creator-profile.local.json` | only with `--include-contact-profile` (it holds contact details) |
| `api-credentials.local.json`, `google-credentials.local.json`, `microsoft-credentials.local.json` | never, by name |
| a context file in which the content check finds a credential | not copied until you fix it |

The allowlist has two copies, `tools/profile_mirror.py::PROFILE_ALLOWLIST`
<!-- verify: tools/profile_mirror.py::PROFILE_ALLOWLIST --> and the `ALLOWLIST` in
`tools/profile-mirror.sh`; the selftest compares them. The script is the macOS agent's job, so
on Windows the selftest's script checks do not run and it says so.

The content check is `tools/profile_mirror.py::refuse`
<!-- verify: tools/profile_mirror.py::refuse -->. Both ways of running the mirror use it (the rsync
recipe calls it through `check-file`). It refuses a file that is not valid JSON, and a file in
which it reads a credential in the raw text or in any key or value:

- a pattern `tools/secret_scan.py` reads (cloud and service keys and tokens, private key blocks,
  and a JSON pair whose key ends in `api_key`, `client_id`, `password`, `passwd`, `secret`,
  `secret_key`, `private_key` or `token` with a value of 8 or more characters);
- a Google OAuth client secret (`GOCSPX-...`), a Google access token (`ya29....`), a Stripe test or
  webhook secret, or an age secret key;
- a key named like a credential (`api_key`, `apiKeys`, `access_token`, `aws_secret_access_key`,
  `clientSecret`, `password`, `pwd`, `passphrase`, `credentials` and similar, matched on the last
  word of the key) holding 8 or more characters with no spaces, or any 8 or more characters under
  a password, passwd, pwd or passphrase key;
- a credential written in a sentence: a word such as password, passcode, secret, secret key,
  API key, access key or token, then a value of 8 or more characters that has a letter, a digit,
  and both letter cases or one of `! @ # $ % ^ & * + = ? ~` ("my instagram password is
  Sunny2024!").

What it does not read: a secret with no digit written in a sentence, a secret under a key named
some other way, and any other phrasing. Two things are refused although they are not secrets:
`{"secret": "<any text of 8 or more characters>"}` (the `secret_scan` rule above), and a title such
as "Password: Season2Finale reveal". Rephrase them. A refused file stops syncing until it is
fixed; the log and `status` say which file and why, and its last good copy stays in Drive.

## Two ways to run it

**The Python tool (recommended).** It copies the files, logs every run, remembers what it copied,
and can also write one Google Doc, "About me and my voice", for the AI engines below.

```bash
python3 tools/profile_mirror.py check                  # what would be copied; writes nothing
python3 tools/profile_mirror.py sync                   # copy changed files into Profile/
python3 tools/profile_mirror.py sync --api             # also create or update the Google Doc
python3 tools/profile_mirror.py status                 # last run, recent activity, the agent
python3 tools/profile_mirror.py check-file pipeline/user-context/voice-profile.local.json
```

**The rsync recipe.** `tools/profile-mirror.sh` copies the same allowlist with the rsync that
ships with macOS, refuses the credential names, runs the content check through the Python you give
it as the third argument, deletes nothing, and logs to the same file. It cannot write the Google
Doc or copy the contact profile.

```bash
bash tools/profile-mirror.sh "$PWD/pipeline/user-context" \
  "$HOME/Library/CloudStorage/GoogleDrive-<account>/My Drive/Creator OS/Profile" "$(command -v python3)"
```

Without the third argument it checks names only, and its log says so.

**Which hub.** The Python tool uses the hub folder you saved on the wizard's Drive hub screen
(`drive_hub.local_mirror` in `creator-os-config.local.json`), or `--hub PATH`
(`tools/handoff/watcher.py::resolve_hub` <!-- verify: tools/handoff/watcher.py::resolve_hub -->).
Neither way of running the mirror searches `~/Library/CloudStorage/` on its own.

## Running it on a schedule (macOS)

```bash
python3 tools/profile_mirror.py install-agent                  # the Python tool, every 15 minutes
python3 tools/profile_mirror.py install-agent --api            # ... and keep the Google Doc current
python3 tools/profile_mirror.py install-agent --include-contact-profile
python3 tools/profile_mirror.py install-agent --engine rsync   # the rsync recipe instead
python3 tools/profile_mirror.py uninstall-agent
```

`install-agent` writes `~/Library/LaunchAgents/com.creatoros.profile-mirror.plist` (your user
only, no admin rights) and loads it with `launchctl bootstrap gui/<your uid>`. It runs at minutes
7, 22, 37 and 52 of each hour. It does not run at login on purpose, so it does not race Drive for
desktop while Drive is still starting; a run missed while the Mac slept happens once on wake.
The `--api` and `--include-contact-profile` choices are written into the agent, so the scheduled
runs do what you chose. The agent is built by `tools/profile_mirror.py::build_plist`
<!-- verify: tools/profile_mirror.py::build_plist -->; it runs the Python of the repo's `.venv`
when there is one, by its path inside the venv.

`install-agent` starts one run at once and waits for it: it reports success only when that run's
stamp says `ok`. If macOS blocked the job (the stamp says `eperm`, "Operation not permitted"), it
tells you so. The fix is to keep the repo out of Desktop, Documents and Downloads, or to allow the
program it names under **System Settings > Privacy & Security > Full Disk Access**. That grant
lets every script the program runs read all your files, so prefer moving the repo.

## Updating and changing things

| When | Do this |
|---|---|
| After `git pull` | `status`; run `install-agent` again only if its agent line shows a program or script path that changed |
| After moving or renaming the repo | `uninstall-agent`, then `install-agent` from the new place |
| After changing Python or recreating `.venv` | `install-agent` |
| To switch between the Python tool and the rsync recipe | `install-agent --engine python` or `--engine rsync` |
| To turn the Google Doc on | `install-agent --api` |
| To stop | `uninstall-agent` (nothing in Drive is touched) |
| To get an older version of a file back | Drive version history (below), then copy it into `pipeline/user-context/`, or the next run puts your computer's copy back |

## Logs and history

| What | Where |
|---|---|
| Every run: each file copied, refused or missing, and one summary line (`run ok: copied 1, unchanged 3, ...`) | `~/Library/Logs/CreatorOS/profile-mirror.log`; both ways of running it rotate it at 512000 bytes and keep `.1` to `.3` |
| The last run's time, status (`ok`, `error`, `eperm`) and engine | `~/Library/Logs/CreatorOS/profile-mirror.last-run` |
| What launchd itself printed (start-up errors) | `~/Library/Logs/CreatorOS/profile-mirror.launchd.log` |
| The last run; the last 20 runs that copied, refused or failed something or wrote, held or failed the Doc; the sha256 of each file copied; and the Doc's id and place | `pipeline/user-context/profile-mirror-state.local.json` (gitignored) |

A file edited in Drive since the last run is logged as a warning and then overwritten, because
the local file wins. Google Drive keeps the earlier version: for the copied files, open the file
in Drive, then **File information > Manage versions**. Drive says "A version might be permanently
deleted after 30 days or if there are 100 newer versions", unless you choose **Keep forever**. The
Google Doc has its own **Version history**, which works differently.

## The Google Doc

`sync --api` uses the `drive_api_polling` credential you set up in the wizard. That credential
has the `drive.file` scope: Google describes it as access to files "that you open with an app or
that the user shares with an app". The hub folders were made by Drive for desktop or by hand, not
by this app, so the API cannot see them. The tool therefore finds the Doc this way
(`tools/profile_mirror.py::sync_doc` <!-- verify: tools/profile_mirror.py::sync_doc -->):

1. By the id it remembers. It checks the Doc on every run: a Doc you deleted or put in the trash
   is left there and a new one is made; a Doc edited in Drive is rewritten from your computer
   (version history keeps the edit); a Doc you moved is updated where it now is.
2. Otherwise, by its name among the Docs this app made, so a lost state file does not make a second
   Doc.
3. Otherwise it creates the Doc: in `Creator OS/Profile` when the API can see that folder, else in
   **My Drive**, and the log and `status` ask you to move it into `Creator OS/Profile` once. Moving
   it keeps its id, so later runs update it there.

The Doc is rendered from what `Profile/` holds, so a file missing or refused on your computer keeps
its section from its Drive copy. If a Drive copy cannot be read, that run holds the Doc instead of
writing it without the section. The Doc is uploaded as Markdown, which Drive converts to a Google
Doc; an update replaces its whole content.

What the AI engines do with it, as their own help pages say:

- **Gemini Gems:** "If you add a file from your Drive, Gemini will use the most recent version of
  the file."
- **Gemini Notebook** (formerly NotebookLM): Drive sources "are auto-updated and will sync every
  few minutes"; a source can also be refreshed with "Click to sync with Google Drive".
- **Claude Projects:** "Google Docs added to chats and projects sync directly from Google Drive";
  the Drive connector works in private projects only.

## Why the repo does not live in Google Drive

Drive for desktop syncs everything under its folder, and it has no ignore list. A repo inside it
would sync `api-credentials.local.json` and the other credential files to the cloud. `setup.py`
and the wizard's Drive hub screen warn when the repo sits under `~/Library/CloudStorage/`, iCloud
Drive or Dropbox (`tools/env_paths.py::cloud_synced_root`
<!-- verify: tools/env_paths.py::cloud_synced_root -->), and point here. On Windows they also warn
for the folder OneDrive names in the `OneDrive`, `OneDriveConsumer` or `OneDriveCommercial`
environment variable, for iCloud for Windows' `iCloud Drive` folder in your user folder (its
default, per Apple) or the older `iCloudDrive`, and for Google Drive for desktop's drive (`G:`
unless you chose another letter): a path whose volume root holds one of the hidden folders
`.shortcut-targets-by-id` or `.file-revisions-by-id` seen there (ADR 0074). Not detected: a My
Drive folder in mirror mode (it sits where you put it, with no marker), a Drive drive whose root
holds neither folder, an iCloud folder you moved, and OneDrive folders no variable names (a further
work account, SharePoint libraries); keep the repo out of them too.

## What only your Mac can confirm

These depend on macOS and on your Google account, so the selftest cannot show them:

- After `install-agent --api`, run `python3 tools/profile_mirror.py sync --api` twice. The second
  run should report the Doc as `unchanged`; if it says `updated` every time, Drive is changing the
  Doc after each write, and the Doc is being rewritten every 15 minutes.
- If the Doc landed in My Drive, move it into `Creator OS/Profile` and check that `status` reports
  it as `moved` after the next run.
- If `install-agent` reports `eperm`, follow its remedy and run it again.

```sources
[
  {"id": "google-drive-desktop-macos", "url": "https://support.google.com/drive/answer/12178485"},
  {"id": "apple-icloud-windows-drive", "name": "Apple Support - Set up iCloud Drive on your Windows computer", "url": "https://support.apple.com/guide/icloud-windows/set-up-icloud-drive-icw0144825a5/icloud", "category": "os-platform", "tier": "T1", "extraction_hint": "Your files and folders are stored in C:\\Users\\[user name]\\iCloud Drive by default; iCloud for Windows 14 or later can choose a different location."},
  {"id": "apple-launchd-plist-man", "name": "launchd.plist(5) manual page (Xcode man pages mirror)", "url": "https://keith.github.io/xcode-man-pages/launchd.plist.5.html", "category": "os-platform", "tier": "T1", "extraction_hint": "Program and ProgramArguments paths must be absolute; RunAtLoad defaults to false; StartCalendarInterval events missed during sleep are coalesced into one event on wake."},
  {"id": "apple-launchctl-man", "name": "launchctl(1) manual page (Xcode man pages mirror)", "url": "https://keith.github.io/xcode-man-pages/launchctl.1.html", "category": "os-platform", "tier": "T1", "extraction_hint": "bootstrap and bootout take a domain target; the per-user GUI domain is gui/<uid>."},
  {"id": "apple-openrsync-man", "name": "openrsync(1) manual page (Xcode man pages mirror)", "url": "https://keith.github.io/xcode-man-pages/openrsync.1.html", "category": "os-platform", "tier": "T1", "extraction_hint": "The rsync shipped with recent macOS is openrsync; the include/exclude filter options and -a/-t behaviour the recipe uses."},
  {"id": "google-drive-api-manage-uploads", "name": "Google Drive API - Upload file data", "url": "https://developers.google.com/workspace/drive/api/guides/manage-uploads", "category": "api-changelog", "tier": "T1", "extraction_hint": "Markdown converts to a Google Doc; when you upload and convert media during an update request to a Docs file, the full contents of the document are replaced."},
  {"id": "google-drive-api-scopes", "name": "Google Drive API - Choose Google Drive API scopes", "url": "https://developers.google.com/workspace/drive/api/guides/api-specific-auth", "category": "api-changelog", "tier": "T1", "extraction_hint": "drive.file: create new Drive files, or modify existing files, that you open with an app or that the user shares with an app while using the Google Picker API or the app's file picker."},
  {"id": "google-drive-api-search-files", "name": "Google Drive API - Search for files and folders", "url": "https://developers.google.com/workspace/drive/api/guides/search-files", "category": "api-changelog", "tier": "T1", "extraction_hint": "Query string literals escape a single quote and a backslash with a backslash."},
  {"id": "google-drive-file-versions", "name": "Google Drive Help - Check activity and file versions", "url": "https://support.google.com/drive/answer/2409045", "category": "platform-spec", "tier": "T1", "extraction_hint": "A version might be permanently deleted after 30 days or if there are 100 newer versions, unless Keep forever; Google Docs version history is separate."},
  {"id": "gemini-gems-use", "name": "Gemini Apps Help - Use Gems in Gemini Apps", "url": "https://support.google.com/gemini/answer/15146780", "category": "ai-surface-spec", "tier": "T1", "extraction_hint": "A Drive file added to a Gem: Gemini uses the most recent version of the file, and changes are reflected in the Gem."},
  {"id": "gemini-notebook-sources", "name": "Gemini Notebook Help - Add or discover new sources for your notebook", "url": "https://support.google.com/gemininotebook/answer/16215270", "category": "ai-surface-spec", "tier": "T1", "extraction_hint": "Sources imported from Google Drive are auto-updated and sync every few minutes; manual Click to sync with Google Drive; NotebookLM's help now publishes as Gemini Notebook."},
  {"id": "claude-google-workspace-connectors", "url": "https://support.claude.com/en/articles/10166901-use-google-workspace-connectors"}
]
```
