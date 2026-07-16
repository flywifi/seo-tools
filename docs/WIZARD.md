# Setup Wizard

`tools/wizard.py` is a browser-based guided setup wizard for Creator OS. It walks you through
connecting Google and Microsoft services to Claude, setting up **publishing** to YouTube, Instagram,
TikTok, and Pinterest, importing your past videos, and choosing your Creator OS folder -- all without
any command-line configuration.

---

## For Alex (no terminal needed -- claude.ai path)

If you use Claude at **claude.ai** (not Claude Desktop), you do not need the wizard. Google
Workspace is available as a built-in connector:

1. Sign in to [claude.ai](https://claude.ai).
2. Click your profile picture (top right) and go to **Settings**.
3. Click **Integrations** in the left sidebar.
4. Click **Add** next to **Google Workspace**.
5. Sign in with your Google account and click **Allow**.

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

A browser window opens automatically. The wizard:

1. Detects your operating system (Mac, Windows, or Linux).
2. Asks which services you want to connect (Google, Microsoft, or both).
3. Walks you through each connection step by step.
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

### Choosing folders (Browse button)

Where the wizard needs a folder path -- the import screen and the "Choose my Creator OS folder" step
-- a **Browse...** button opens your operating system's native folder picker
(`tools/pick_folder.py`: a tkinter dialog, with macOS/Windows/Linux fallbacks). The typed path field
stays as the always-works fallback when no picker is available (e.g. over SSH).

---

## What the wizard does behind the scenes (for Matt's reference)

The wizard is a small Python script (`tools/wizard.py`) that runs a local web server on
`http://localhost:8765` and opens your system browser. Nothing leaves your computer except
the OAuth flows to the providers' own servers (Google, Microsoft, and -- during publishing setup --
YouTube/Google, Instagram/Meta, TikTok, and Pinterest).

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
