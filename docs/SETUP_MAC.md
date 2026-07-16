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

Smoke test (should return 56 tool definitions):

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

## Local transcription / STT import (content-library)

To import your OWN past videos and have Creator OS transcribe them on this computer (zero cloud, zero
tokens; see `docs/CONTENT-IMPORT.md`), install a speech-to-text engine. Nothing here is required: with
no engine the library is built metadata-only and each transcript is flagged as needing an engine, never
faked.

### Apple Silicon (M1 to M4) and Intel Macs

The recommended engine is **whisper.cpp** (uses the Mac's Metal GPU on Apple Silicon):

```bash
brew install whisper-cpp ffmpeg
```

Homebrew bottles are notarized, so there is no Gatekeeper "unidentified developer" prompt. Download a
model file once (a `ggml-<tier>.bin` from the whisper.cpp repository; tier by RAM: 8GB small, 16GB
medium/turbo, 32GB large-v3) and point Creator OS at it:

```bash
export WHISPER_CPP_MODEL=/path/to/ggml-small.bin
```

Prefer Python instead? Use **faster-whisper**, which needs **no** system ffmpeg (it bundles PyAV):

```bash
brew install python && pip3 install faster-whisper
```

### macOS notes that trip people up

- **`git clone`, don't Download-ZIP.** Files created by `git clone` are not quarantined and the
  `Start Creator OS Setup.command` launcher just runs. A downloaded `.zip`, unzipped in Finder,
  quarantines the launcher and Gatekeeper blocks the first double-click.
- **Clearing a Gatekeeper block (the current flow).** Open System Settings &rarr; Privacy &amp;
  Security, scroll to the Security section, click **Open Anyway**, and confirm with your admin
  password. **Right-click &rarr; Open no longer works** &mdash; that shortcut was removed in macOS 15
  Sequoia and is still gone in the current **macOS 26 (Tahoe)**.
- macOS ships **no usable `python3`** (the built-in one is a stub that pops the "command line
  developer tools" dialog). Install it via the notarized **python.org universal2 `.pkg`** (no
  Gatekeeper prompt, Tk bundled) or Homebrew (`brew install python@3.13`). The setup wizard installs
  Python dependencies into a private `.venv` toolbox, which sidesteps Homebrew Python's PEP 668
  install lock.
- A **downloaded static ffmpeg** hits `com.apple.quarantine` ("cannot be opened because the developer
  cannot be verified"). Clear it with `xattr -dr com.apple.quarantine /path/to/ffmpeg`, or Open Anyway
  as above. `brew install ffmpeg` (a notarized bottle) avoids quarantine entirely.
- faster-whisper needs no system ffmpeg, so it is the escape hatch when a user cannot get a downloaded
  ffmpeg past Gatekeeper.
- **Local setup runs on this computer only.** The wizard, the folder import, transcription, and the
  publishing OAuth loopback need Claude **Desktop** or **Claude Code** on this Mac. Claude in a browser
  (claude.ai) and a remote Cowork session cannot reach your local files or `localhost` services.
- **Dated context (as of 2026-07):** Homebrew disables Gatekeeper-failing casks from **2026-09-01**
  (formula bottles like `ffmpeg`/`whisper-cpp` are unaffected); **macOS 27** (expected fall 2026) drops
  Intel support, so Tahoe 26 is the last Intel release.

### The guided doctor (recommended for non-technical users)

Instead of running the steps by hand, run the doctor. It checks your computer, finds (or explains how
to install) an engine, and downloads a verified model for you:

```bash
python3 tools/transcribe.py doctor                     # green / amber / red verdict + the next command
python3 tools/transcribe.py doctor --fetch-model base.en   # download + checksum-verify one model
```

The download is verified against a known SHA256 (from `canonical-sources/whisper-models.json`); a
corrupt download is deleted rather than used. Models land in `~/.creator-os/whisper-models/` (override
with `WHISPER_MODEL_DIR`). The setup wizard exposes the same flow at `python3 tools/wizard.py` -> **Check
my setup** (`/doctor`), with one-click model downloads.

Verify what was found:

```bash
python3 tools/transcribe.py status          # backend + selection for this machine
python3 tools/videoedit/preflight.py        # transcribe_media lane + probes
```

### Windows (second priority)

Non-technical Windows path uses **faster-whisper** (no separate model step, no system ffmpeg):

1. Install Python from python.org. The installer trips **SmartScreen** ("Windows protected your PC") --
   click **More info -> Run anyway** (the installer is signed by the Python Software Foundation). During
   install, check **"Add python.exe to PATH."**
2. `pip install faster-whisper`. On first transcription it downloads its model automatically to
   `%USERPROFILE%\.cache\huggingface\hub`. A CPU runs it out of the box; an NVIDIA GPU additionally needs
   cuBLAS + cuDNN 9 for CUDA 12.
3. Prefer whisper.cpp? Download `whisper-bin-x64.zip` from the whisper.cpp GitHub releases, extract it,
   and add the folder to PATH (the binary is `whisper-cli.exe`); then fetch a model with the doctor.

The doctor gives the machine-correct command on Windows too.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `whisper.cpp needs a GGML model file` | Download a `ggml-<tier>.bin` and set `WHISPER_CPP_MODEL` to its path |
| ffmpeg "cannot be opened, developer cannot be verified" | `xattr -dr com.apple.quarantine /path/to/ffmpeg`, or use faster-whisper (no ffmpeg needed) |
| No STT backend found on the Import screen | `brew install whisper-cpp ffmpeg` (Apple Silicon) or `pip3 install faster-whisper` |
| `python3: command not found` | `brew install python@3.11` then add `/opt/homebrew/bin` to PATH |
| `pip3: command not found` | Use `/opt/homebrew/bin/pip3` or `python3 -m pip` |
| `playwright install` hangs | Check network; retry with `python3 -m playwright install chromium --force` |
| `drift guard` reports issues after `git pull` | Run `python3 tools/sync_check.py` and read the report |
| MCP tools not appearing in Claude Desktop | Restart Claude Desktop; check that the path in `claude_desktop_config.json` is absolute |
| `setup.py` says "running under Rosetta" | Install arm64 Python: `brew install python@3.11` then use `/opt/homebrew/bin/python3` |
