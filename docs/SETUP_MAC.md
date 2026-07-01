# macOS Setup Guide (M2 / Apple Silicon)

Creator OS works on Apple Silicon (M2, M3, arm64) natively. All dependencies ship arm64 wheels
and Playwright auto-downloads the arm64 Chromium binary. No Rosetta required.

---

## Quick start for Alex (no terminal needed)

**Option B -- Claude Projects** is the recommended path for non-technical users.

1. Go to [claude.ai](https://claude.ai) and sign in.
2. Click **Projects** in the left sidebar, then **New Project**. Name it **Creator OS**.
3. Open `implementation/claude/project/system-prompt.md`, copy the full text, paste it into the
   Project Instructions field, and save.
4. Click **Add content** and upload each file from `implementation/claude/project/knowledge/`.
5. Start a conversation: "Plan a seasonal home decor project makeover video."

See `docs/DEPLOYMENT.md` Option B for the full walkthrough. No Homebrew, no Python, no git needed.

---

## Full setup for Matt (Claude Desktop + MCP, full capability)

This enables the competitor intelligence extraction, offline keyword cache, source staleness
detection, and deterministic quality scoring via the MCP server.

### Step 1 -- Install Homebrew

If not already installed:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

On M2, Homebrew installs to `/opt/homebrew/`. Add it to your shell profile if prompted:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### Step 2 -- Install Python 3.11 and Git

```bash
brew install python@3.11 git
```

Verify:

```bash
python3 --version   # should show 3.11.x or later
git --version
```

If `python3` still points to the system Python (3.9 on older macOS), use the full path:
`/opt/homebrew/bin/python3`.

### Step 3 -- Clone the repository

```bash
git clone https://github.com/flywifi/seo-tools.git
cd seo-tools
```

Note the absolute path to this folder (needed for the MCP config):

```bash
pwd
# example: /Users/matt/projects/seo-tools
```

### Step 4 -- Run first-time setup

```bash
python3 tools/setup.py
```

This creates your gitignored local data files, builds the FTS5 keyword cache, and verifies the
drift guard. Expected output ends with `[ok] drift guard clean`.

### Step 5 -- Install the fetch stack (competitor intelligence)

```bash
pip3 install -r requirements-crawl.txt -r requirements-scraper.txt
```

### Step 6 -- Install Playwright (optional, for JavaScript-rendered snapshots)

Playwright enables full competitor HTML rendering, including YouTube `ytInitialData` extraction
from pages that require JavaScript. Without it, the fetch stack still works via browser-header
requests (prong 1) -- Playwright adds prong 2.

```bash
pip3 install -r requirements-render.txt
python3 -m playwright install chromium   # downloads arm64 Chromium (~170 MB, one-time)
```

### Step 7 -- Install the MCP server

```bash
pip3 install -r requirements-mcp.txt
```

Smoke test (should return 8 tool definitions):

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 tools/mcp_server.py
```

### Step 8 -- Run the setup wizard

The wizard opens in your browser and handles Claude Desktop configuration, and optionally
connects Google Workspace (Gmail, Calendar, Drive/Docs/Sheets) and Microsoft 365 (Outlook,
Calendar, Excel, OneDrive):

```bash
python3 tools/wizard.py
```

A browser window opens automatically at `http://localhost:8765`. Follow the on-screen steps.
The wizard:
- Configures the Creator OS MCP server in Claude Desktop's config file
- Optionally connects Google Workspace (requires Google Cloud credentials -- the wizard walks
  you through getting them; takes about 5 minutes)
- Optionally connects Microsoft 365 (requires Node.js 20+; the wizard checks and advises if
  missing; uses device code flow -- visit a URL, enter a code, done)

When the wizard says "Restart Claude Desktop," quit and reopen the Claude Desktop app.

After restarting, test: ask Claude "run a drift check" -- expected reply: "DRIFT GUARD: clean".

**Manual alternative:** Merge `implementation/claude/desktop/claude_desktop_config_snippet.json`
into `~/Library/Application Support/Claude/claude_desktop_config.json` by hand, replacing
`REPLACE_WITH_ABSOLUTE_PATH` with the output of `pwd` from the seo-tools directory.

See `docs/WIZARD.md` for full wizard documentation.

---

## M2-specific notes

- Homebrew on M2 installs to `/opt/homebrew/` (not `/usr/local/`). Make sure
  `/opt/homebrew/bin` is on your `$PATH` (the setup script above handles this).
- All Python packages in this project (`requests`, `charset-normalizer`, `beautifulsoup4`,
  `playwright`, `mcp`) ship native arm64 wheels. No Rosetta emulation needed.
- `playwright install chromium` auto-detects your architecture and fetches the arm64 binary.
- The competitor snapshot SQLite database (`pipeline/competitor-snapshots/index.local.db`) and
  keyword cache (`shared/cache/index.local.db`) work identically on M2 as on Linux.
- If you see `python3 -m playwright install` fail with a proxy or certificate error, check
  `/root/.ccr/README.md` -- not applicable on your personal Mac (no proxy is configured there).

---

## Regular updates

Pull code updates without touching your local data files:

```bash
python3 tools/update.py
```

Or manually:

```bash
git pull origin main
python3 tools/sync_check.py
python3 shared/cache/cache.py --build   # only if canonical-sources/ changed
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `python3: command not found` | `brew install python@3.11` then add `/opt/homebrew/bin` to PATH |
| `pip3: command not found` | Use `/opt/homebrew/bin/pip3` or `python3 -m pip` |
| `playwright install` hangs | Check network; retry with `python3 -m playwright install chromium --force` |
| `drift guard` reports issues after `git pull` | Run `python3 tools/sync_check.py` and read the report |
| MCP tools not appearing in Claude Desktop | Restart Claude Desktop; check that the path in `claude_desktop_config.json` is absolute |
| `setup.py` says "running under Rosetta" | Install arm64 Python: `brew install python@3.11` then use `/opt/homebrew/bin/python3` |
