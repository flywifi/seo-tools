# Setup Wizard

`tools/wizard.py` is a browser-based guided setup wizard for Creator OS. It walks you through
installing the Creator OS tools into Claude Desktop (and **verifying they actually answer** before
saying done), connecting Google and Microsoft services to Claude, setting up **publishing** to
YouTube, Instagram, TikTok, and Pinterest, importing your past videos, and choosing your Creator OS
folder -- all without any command-line configuration.

---

## For Alex (no terminal needed -- claude.ai path)

If you use Claude at **claude.ai** (not Claude Desktop), you do not need the wizard. Since
2026-09-16 Claude chat and Cowork are one Claude (rolling out in stages from Pro and Max), so
skills, plugins, and connectors work from any conversation. Get Creator OS there one of four
ways, best first (full steps: `docs/DEPLOYMENT.md` Option B and the wizard's own claude.ai
screen):

1. **The plugin** (paid plans): Customize > Plugins, add the repository's marketplace link --
   everything in one step. (Private-repository marketplace links on personal plans are not yet
   verified; fall back to door 2.)
2. **A Project fed straight from GitHub**: New Project, paste
   `implementation/claude/project/system-prompt.md` as the project instructions, then connect
   this repository's `implementation/claude/project/` folder to the Project's knowledge
   ("Sync now" after updates).
3. **A Project fed by uploads** (any plan, including Free): upload the nine knowledge files or
   the single combined file.
4. **Individual skill ZIP uploads** (any plan; self-contained skills only).

Then connect Google Workspace, which is a built-in connector:

1. Sign in to [claude.ai](https://claude.ai).
2. Open **Customize**, then **Connectors** (older builds: Settings > Integrations).
3. Click **Add** next to **Google Workspace**.
4. Sign in with your Google account and click **Allow**.

That is it. Creator OS can now read your Gmail, Google Calendar, and Google Drive (Docs, Sheets)
when you are in a project conversation. No credentials, no downloads, no terminal.

**What it enables:** Creator OS can read brand pitch emails, check your content calendar, pull
analytics from Sheets, and read your Google Docs brand briefs and scripts directly in the
conversation -- just ask.

**Microsoft 365** (Outlook, Calendar, Excel) is not yet available as a native claude.ai
connector. If you need it, see the Claude Desktop path below.

---

## For Claude Desktop users (Mac, Windows, or Linux)

Run one command and follow the browser steps:

```bash
python3 tools/wizard.py
```

A browser window opens automatically. First time? Press the one **"Set everything up"** button:
it chains the free-tools install, the Creator OS install-and-verify step, and the optional
Google/Microsoft connections, with an explicit "Skip this step" on every screen. Progress is
saved locally (a gitignored `creator-os-wizard-state.local.json` holding only step flags), so
closing the window or relaunching resumes where you left off; "Start over" on the welcome
screen clears it. Run on an older Python and the wizard exits with the install instructions
instead of a traceback. The two long steps (installing the free tools, downloading a speech
model) run in the background behind a self-refreshing progress page, so the browser never looks
frozen; pressing the button twice is refused rather than queued, and a crashed install still
lands on an error page with the reason.

The wizard:

1. Detects your operating system (Mac, Windows, or Linux).
2. **Installs the Creator OS tools into Claude Desktop** (the `/creator-os-server` step): it
   writes the one `creator-os` entry into Claude Desktop's settings file with absolute paths,
   never touches your other settings, and then runs a real check -- the full MCP handshake plus a
   tool listing -- before it says done. The check also confirms it is the Creator OS server
   answering (not just any program at that path) and that it actually lists tools; a count that
   cannot be cross-checked against the repo's canonical count is labeled as such rather than
   presented as confirmed. If the check cannot pass yet (for example, the free tools
   are not installed), it says exactly why and where to fix it; a manual-merge fallback is shown
   for the rare case the automatic write cannot work. The Done page reports the verified tool
   count and has a "Check again" button for after you restart Claude Desktop. The check talks
   to the server step by step and never closes the connection before the reply arrives, and it
   quietly tries once more if the server stumbles on its very first start.
3. Asks which services you want to connect (Google, Microsoft, or both).
4. Walks you through each connection step by step.
4. Writes all configuration files automatically -- no JSON editing.
5. Tells you when to fully quit and reopen Claude Desktop (Cmd-Q on macOS, not just closing the
   window) so it reloads the config.

### Google Workspace (Gmail, Calendar, Drive, Docs, Sheets)

The wizard guides you through creating a free Google Cloud project and OAuth credentials
(takes about 5 minutes). You paste two values (Client ID and Client Secret) into the wizard,
and it handles the rest. Once connected, Claude Desktop can read your Gmail, Calendar, and
all Google Drive files.

### Microsoft 365 (Outlook, Calendar, Excel, OneDrive)

The wizard checks whether Node.js 20 or later is installed. If not, it tells you exactly how
to install it for your operating system. Once Node.js is ready, the wizard adds the Microsoft
365 MCP server to your Claude Desktop config. On first use in Claude Desktop, a one-time sign-in
prompt appears: Claude shows you a short code and a URL to visit
(`microsoft.com/devicelogin`). You visit that URL, enter the code, sign in with your Microsoft
account, and you are connected -- no credentials to paste anywhere.

### Publishing setup (YouTube, Instagram, TikTok, Pinterest)

From `/publishing-setup`, the wizard connects each platform with a **Connect** button that runs an
in-browser sign-in (a loopback OAuth flow: the platform redirects back to
`http://127.0.0.1:8765/oauth/<platform>/callback`, the wizard verifies a one-time `state` and stores
the token locally). Each screen states the platform's real limits up front -- YouTube's ~7-day
Testing-mode re-auth, TikTok's private-until-audit, Pinterest's sandbox-only Trial Pins, and
Instagram's public-URL + professional-account requirements. Tokens are saved to
`pipeline/user-context/api-credentials.local.json` (owner-only, gitignored). **Live posting stays off
by default** (`live_publishing_enabled`), and every post needs your explicit confirmation. Full
per-platform playbook: `docs/PUBLISHING.md`.

### The Google Drive hub and the compute hand-off (P60)

Three screens make the cross-surface hub work without a terminal. **`/drive-hub`** explains the
shared Drive folder ("Creator OS": Inbox, Store, Jobs, Knowledge, Profile, Outbox), detects the
Google Drive for desktop synced copy under `~/Library/CloudStorage/GoogleDrive-*`, confines any
typed path to your home tree, creates the missing subfolders, and saves the location locally
(`creator-os-config.local.json`); it also carries a "Refresh the Knowledge folder" button that
copies the claude.ai knowledge pack into the hub's `Knowledge/` folder
(`tools/project_docs.py`, the P60-7 Projects projection; recipe in `docs/DRIVE-HUB.md`). **`/compute`** is the one-click toggle for the
`compute_handoff_enabled` capability (default off): when on, a scheduled watcher pass
(`python3 tools/handoff/watcher.py --once`, snippet in `tools/freshness-scheduler.example`) runs
allowlisted jobs queued in the hub from any surface and writes results back for review. Nothing can
post, publish, or read credentials from a job. **`/inbox`** sorts the drop folder: Scan lists what
is new in the hub's `Inbox/` (the offline scan in `tools/handoff/inbox.py`; transcripts and media
route by format, documents wait for a Claude session, unknowns are flagged in place, and any file
whose text trips the offline injection pattern tier is sealed into `Inbox/Quarantine`). Approve is
a **two-step work order** (P61): the first click files the batch and records it in the ledger, then
a second screen lists the exact follow-up jobs with a checkbox each and an "Anything to change?"
note, and a second click queues only the checked jobs. The note is attached to the work for review
(the ticket `consent_note`); it never changes what runs. A **Background work: ON/OFF** banner on
the work-order screen and beside `/inbox` shows the compute switch state and links to `/compute` to
change it, so queued work that is waiting is never invisible. `/compute` also carries the
default-off **direct saves** toggle (`job_store_writes_enabled`): enabling it requires an
acknowledged risk checkbox, and even then a job writes to the library only when its ticket asks.
Nothing is written or moved until you approve. Full model: `docs/DRIVE-HUB.md`.

### Choosing folders (Browse button)

Where the wizard needs a folder path -- the import screen and the "Choose my Creator OS folder" step
-- a **Browse...** button opens your operating system's native folder picker
(`tools/pick_folder.py`: a tkinter dialog, with macOS/Windows/Linux fallbacks). The typed path field
stays as the always-works fallback when no picker is available (e.g. over SSH).

---

## What the wizard does behind the scenes (for Matt's reference)

The wizard is a small Python script (`tools/wizard.py`) that runs a local web server bound to
`http://127.0.0.1:8765` (loopback only, never `0.0.0.0`) and opens your system browser. Nothing
leaves your computer except the OAuth flows to the providers' own servers (Google, Microsoft, and --
during publishing setup -- YouTube/Google, Instagram/Meta, TikTok, and Pinterest).

If port 8765 is already taken, set `CREATOR_OS_WIZARD_PORT` (1024 to 65535; anything unparseable
or out of range falls back to 8765 with a printed note):

```bash
CREATOR_OS_WIZARD_PORT=8790 python3 tools/wizard.py
```

Only do this deliberately. The OAuth redirect URIs you register with each provider embed the
port and are matched exactly, so changing it breaks every already-connected platform until you
update the registered URI in that provider's console. Details in `docs/PUBLISHING.md`.

**Security guards (P57/P58):** every state-changing POST rejects requests whose `Origin`/`Referer`
is not the wizard itself, so a website you merely visit cannot drive the wizard; folder paths you
type (import folder, Creator OS folder) are confined to your home directory after resolving
symlinks; request bodies are size-capped and malformed lengths get a clean error; a corrupt Claude
Desktop config is backed up to `.corrupt.bak` before the wizard writes a fresh one instead of being
silently replaced; and the import scan/approve flow is tied to a single-use token so two open tabs
cannot approve each other's scan.

**Config files the wizard writes:**

| File | What changes |
|---|---|
| `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) | Adds creator-os, google-workspace, and/or microsoft-365 MCP server entries |
| `%APPDATA%\Claude\claude_desktop_config.json` (Windows) | Same |
| `~/.config/Claude/claude_desktop_config.json` (Linux) | Same |
| `creator-os-config.local.json` (repo root) | Sets `google_workspace: true` and/or `microsoft_365: true` in capabilities |

The wizard never commits anything to git. All credential files and config overrides are
gitignored. The committed files in the repo are not touched.

**Google OAuth:** The wizard uses `workspace-mcp` (a community MCP server by Taylor Wilsdon),
which runs via `uvx workspace-mcp`. This is simpler than Google's official MCP servers because
it only needs a standard OAuth Client ID and Secret -- no Google Cloud service account or
complex API setup. The wizard installs `uv` automatically if it is not already present.

**Microsoft device code flow:** The `ms-365-mcp-server` (by Softeria) uses Microsoft's device
code OAuth variant. Instead of a browser redirect, Claude Desktop shows a short code and a URL.
You visit the URL, enter the code, and Microsoft authorizes the connection. This works through
corporate firewalls, does not need a redirect server, and is the same flow used by the official
Microsoft CLI tools.

---

## Screenshots and demo assets

Screenshots and animated GIFs for each wizard screen are in `docs/wizard/`. See
`docs/wizard/screenshot-guide.md` for filenames and descriptions of each screen.
