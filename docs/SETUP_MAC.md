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
4. Click **Add content** and upload each file from `implementation/claude/project/knowledge/`
   (or the single combined file `implementation/claude/project/creator-os-combined.md`, or
   connect this GitHub repository to the Project's knowledge instead of uploading -- see
   `docs/DEPLOYMENT.md` Option B).
5. Start a conversation: "Plan a seasonal home decor project makeover video."

No repo on the computer? Ask the maintainer to send the files or mirror them into the shared
Drive folder's `Knowledge/` subfolder (the wizard's Drive hub screen does it in one click), or
download them from github.com/flywifi/seo-tools.

See `docs/DEPLOYMENT.md` Option B for the full walkthrough. No Homebrew, no Python, no git needed.

---

## Full setup for Matt (Claude Desktop + MCP, full capability)

This enables the competitor intelligence extraction, offline keyword cache, source staleness
detection, and deterministic quality scoring via the MCP server.

### Which macOS you need

Creator OS supports **Python 3.12 to 3.14** (`tools/setup.py` enforces the 3.12 floor; numpy 2.5
dropped 3.11; 3.14 is battery-validated as of P91, ADR 0064). One lane exception: **DaVinci
Resolve's scripting bridge caps at 3.12**, so if you use the Resolve live-control lane, run that
lane's tools with `python3.12`. Two P91 residues only a real 3.14-final machine can close, both
expected to pass: `[NEEDS VERIFICATION: the mcp SDK import on a 3.14 FINAL (the validation
container's 3.14.0rc2 lacks the typing._eval_type keyword pydantic 2.13.5 targets); closed by
the acceptance run below]` -- acceptance run on a 3.14 Mac: `python3 tools/setup.py
--install-deps && python3 tools/battery.py`, then the wizard's install-and-verify step must
report the full tool count. Creator OS
does not check your macOS version. **Install scope (P93): everything on this default path
stays inside your user account** -- home folder only, no admin rights, nothing under
`/Applications` or `/opt/homebrew`. Full policy, approved locations, and the one exception
(Apple's Command Line Tools git): `docs/INSTALL-SCOPE.md`. This guide targets macOS 26
(Tahoe) and 15 (Sequoia).

### Step 1 -- Python and Git (user-only)

Check what you already have:

```bash
python3 --version   # 3.12 to 3.14 all work (P91). Already in range? Nothing to install.
                    # Only the DaVinci Resolve live-control lane needs python3.12 (its bridge caps there).
git --version       # usually preinstalled via Apple's Command Line Tools
```

Python missing or too old? Install a user-only one via uv (lands in `~/.local`, no admin
rights; docs.astral.sh/uv):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
```

That gives you **`python3.12`**, not a bare `python3`, and it lands in `~/.local/bin`. Two
consequences worth knowing before Step 4:

- Type `python3.12` (not `python3`) in the commands below. Every command in this guide works
  with either name.
- If your shell reports `command not found`, `~/.local/bin` is not on your PATH yet. Run
  `uv python update-shell` and open a new Terminal window, or call it by full path:
  `~/.local/bin/python3.12`. The double-click launcher already looks in `~/.local/bin`, so it
  finds this Python without any PATH change.

Git missing? Accept the Apple Command Line Tools prompt (`xcode-select --install`) -- the one
machine-level component on this path, with no user-scoped equivalent (see the exceptions
register in `docs/INSTALL-SCOPE.md`).

**Machine-wide alternative (affects the whole computer):** Homebrew. Its docs support macOS
Sonoma (14) or later; it installs to `/opt/homebrew/` for every user of the machine.

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
# machine-wide: lands in /opt/homebrew for every user of this Mac
brew install python@3.12 git
```

If `python3` still points to Apple's stock interpreter, use the full path:
`/opt/homebrew/bin/python3`. (Apple's `/usr/bin/python3` is described by the Python docs as an older,
incomplete build shipped for Xcode's own use; never modify or remove it, just do not build on it.)

### Step 2 -- Clone the repository

```bash
git clone https://github.com/flywifi/seo-tools.git
cd seo-tools
```

Note the absolute path to this folder (needed for the MCP config):

```bash
pwd
# example: /Users/matt/projects/seo-tools
```

### Step 3 -- Run first-time setup

```bash
python3 tools/setup.py
```

This creates your gitignored local data files, builds the FTS5 keyword cache, and verifies the
drift guard. Expected output ends with `[ok] drift guard clean`.

### Step 4 -- Install every dependency set (one command, into the repo's private .venv)

```bash
python3 tools/setup.py --install-deps
```

One command covers the fetch stack, the HTML parser, Playwright plus its Chromium download
(~170 MB, one-time, cached under `~/Library`), the MCP server package, transcription, video
analysis, and the tooling accelerators -- all into the repo's private `.venv`, never into a
machine-wide Python (P93: on a locked-down PEP 668 interpreter with no `.venv`, the installer
refuses with the remedy instead of overriding). Each set reports its own honest result; a
failed optional set degrades that lane, never the base.

#### Already covered by Step 4

(Playwright and the MCP server used to be separate pip steps of their own; they install into
the `.venv` with everything else now, so there is nothing extra to run.)

Smoke test (should print the tool count; a bare `tools/list` is rejected before the MCP
`initialize` handshake, so the probe sends the full three-message sequence — the wizard's
"Install and verify" button runs the same verification for you, interactively). If it prints
nothing, run it once more: this one-shot pipe can lose the reply to a startup race on newer
MCP SDK versions — the wizard's check speaks the protocol step by step and does not have
this race (P88):

```bash
python3 - <<'EOF'
import json, subprocess
msgs = [
  {"jsonrpc": "2.0", "id": 1, "method": "initialize",
   "params": {"protocolVersion": "2025-06-18", "capabilities": {},
              "clientInfo": {"name": "smoke", "version": "0"}}},
  {"jsonrpc": "2.0", "method": "notifications/initialized"},
  {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
]
r = subprocess.run(["python3", "tools/mcp_server.py"],
                   input="".join(json.dumps(m) + "\n" for m in msgs),
                   capture_output=True, text=True, timeout=90)
for line in r.stdout.splitlines():
    if line.strip().startswith("{"):
        d = json.loads(line)
        if d.get("id") == 2 and "result" in d:
            print(len(d["result"]["tools"]), "tools")
EOF
```

### Step 5 -- Run the setup wizard

The wizard opens in your browser and handles Claude Desktop configuration, and optionally
connects Google Workspace (Gmail, Calendar, Drive/Docs/Sheets) and Microsoft 365 (Outlook,
Calendar, Excel, OneDrive):

```bash
python3 tools/wizard.py
```

A browser window opens automatically at `http://localhost:8765`. Follow the on-screen steps.
The wizard:
- Installs the Creator OS MCP server into Claude Desktop's config file AND verifies it with a
  real handshake check before saying done (the "Install the Creator OS tools" step)
- Optionally connects Google Workspace (requires Google Cloud credentials -- the wizard walks
  you through getting them; takes about 5 minutes)
- Optionally connects Microsoft 365 (requires Node.js 20+; the wizard checks and advises if
  missing; uses device code flow -- visit a URL, enter a code, done)

Installing Claude Desktop itself? Put the app in your per-user folder so even the binary
stays user-only: `mkdir -p ~/Applications`, then drag Claude.app there instead of
`/Applications` (its config and sign-in are per-user either way).

When the wizard says "Restart Claude Desktop," quit and reopen the Claude Desktop app.

After restarting, test: ask Claude "run a drift check" -- expected reply: "DRIFT GUARD: clean".

**A note on the config file's future:** Anthropic's current local-MCP help article (support
article 10949351, updated 2026-06-30) documents only Settings > Extensions with packaged
`.mcpb` bundles and no longer mentions `claude_desktop_config.json`. Current builds still honor
the file (your working install is the evidence) `[NEEDS VERIFICATION: re-confirm after each
Claude Desktop update -- if the entry ever stops loading, the packaged .mcpb path in
docs/UPDATING.md is the successor]`.

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

## The Google Drive hub + overnight compute (optional, P60)

To let this Mac pick up jobs queued from any Claude surface (web, phone, Cowork) and run them
locally (transcription, library analysis, import previews, finance reports):

1. Install **Google Drive for desktop** (google.com/drive/download) and sign in.
2. Create the hub folder in My Drive (the wizard's `/drive-hub` screen walks you through it) and
   prefer **mirror** mode for that folder so it is always fully on disk. Streaming mode (the
   macOS File Provider mount under `~/Library/CloudStorage/`) also works, but a large queued media
   file must download before a job can start.
3. On the wizard `/drive-hub` screen, point Creator OS at the synced folder (it is usually
   detected automatically), then turn the hand-off on at `/compute`.
4. Schedule the watcher with the ready-made cron or launchd snippet in
   `tools/freshness-scheduler.example` ("compute hand-off watcher" section).

The Mac must be **awake** for a pass to run; queued jobs simply wait otherwise. For an overnight
batch, `caffeinate -s` in a Terminal window, or System Settings, then Energy Saver, and a wake
schedule, keeps it available. Only allowlisted read/compute jobs can run; nothing posts, publishes,
or reads credentials from a job, and every result waits for your review (`docs/DRIVE-HUB.md`).

---

## Local transcription / STT import (content-library)

To import your OWN past videos and have Creator OS transcribe them on this computer (zero cloud, zero
tokens; see `docs/CONTENT-IMPORT.md`), install a speech-to-text engine. Nothing here is required: with
no engine the library is built metadata-only and each transcript is flagged as needing an engine, never
faked.

### Apple Silicon (M1 to M4) and Intel Macs

The user-only default is **faster-whisper**: it is already inside the repo's `.venv` after
`python3 tools/setup.py --install-deps` (requirements-transcribe), needs **no** system ffmpeg
(it bundles PyAV), and downloads its model to your user cache on first run. Nothing else to
install.

**Machine-wide alternative (affects the whole computer):** **whisper.cpp** uses the Mac's
Metal GPU on Apple Silicon and is the faster engine, but installs via Homebrew:

```bash
# machine-wide: lands in /opt/homebrew for every user of this Mac
brew install whisper-cpp ffmpeg
```

Homebrew bottles are notarized, so there is no Gatekeeper "unidentified developer" prompt. Download a
model file once (a `ggml-<tier>.bin` from the whisper.cpp repository; tier by RAM: 8GB small, 16GB
medium/turbo, 32GB large-v3) and point Creator OS at it:

```bash
export WHISPER_CPP_MODEL=/path/to/ggml-small.bin
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
  developer tools" dialog). The user-only route is uv (`~/.local`, Step 1); the machine-wide
  alternatives (affect the whole computer) are the notarized **python.org universal2 `.pkg`**
  (no Gatekeeper prompt, Tk bundled) or Homebrew (`brew install python@3.12`). The setup wizard
  installs Python dependencies into a private `.venv` toolbox either way, which sidesteps
  Homebrew Python's PEP 668 install lock.
- A **downloaded static ffmpeg** hits `com.apple.quarantine` ("cannot be opened because the developer
  cannot be verified"). Clear it with `xattr -dr com.apple.quarantine /path/to/ffmpeg`, or Open Anyway
  as above. The machine-wide alternative `brew install ffmpeg` (a notarized bottle) avoids
  quarantine entirely.
- faster-whisper needs no system ffmpeg, so it is the escape hatch when a user cannot get a downloaded
  ffmpeg past Gatekeeper.
- **Local setup runs on this computer only.** The wizard, the folder import, transcription, and the
  publishing OAuth loopback need Claude **Desktop** or **Claude Code** on this Mac. Claude in a browser
  (claude.ai) and a remote Cowork session cannot reach your local files or `localhost` services.
- **Dated context (as of 2026-08):** Homebrew's 5.0.0 announcement says casks that fail Gatekeeper
  are disabled from **September 2026** (the post states the month, not a specific day, and hedges
  the related changes as "September or later"). The same announcement moves **Intel to Tier 3 from
  September 2026 and stops building new Intel bottles**, so on an Intel Mac expect `ffmpeg` and
  `whisper-cpp` to build from source rather than install prebuilt. Separately, **macOS 27**
  (expected fall 2026) drops Intel support, so Tahoe 26 is the last Intel release; that is a later
  and independent cutoff from the Homebrew tier change.

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
2. `python tools\setup.py --install-deps` installs faster-whisper into the repo's private
   `.venv` (user-only). On first transcription it downloads its model automatically to
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
| No STT backend found on the Import screen | `python3 tools/setup.py --install-deps` (installs faster-whisper into the repo `.venv`, user-only); machine-wide alternative: `brew install whisper-cpp ffmpeg` |
| `python3: command not found` | User-only: the uv route in Step 1; machine-wide alternative: `brew install python@3.12` then add `/opt/homebrew/bin` to PATH |
| `pip3: command not found` | Use `python3 -m pip`, or better: `python3 tools/setup.py --install-deps` (the `.venv` route) |
| `playwright install` hangs | Check network; retry with `python3 -m playwright install chromium --force` |
| `drift guard` reports issues after `git pull` | Run `python3 tools/sync_check.py` and read the report |
| MCP tools not appearing in Claude Desktop | Restart Claude Desktop; check that the path in `claude_desktop_config.json` is absolute |
| `setup.py` says "running under Rosetta" | Install an arm64 Python: user-only via uv (Step 1); machine-wide alternative: `brew install python@3.12` then `/opt/homebrew/bin/python3` |

---

## Declared sources (maintainers)

The macOS facts this guide states (Gatekeeper/Open Anyway flow, Rosetta, Tahoe 26, Intel support,
python.org installers, Homebrew, connectors) are tracked for staleness by the currency system. Every id
below must exist in `canonical-sources/source-registry.json` with the same URL (drift-guard invariant
52); run `python3 tools/source_sync.py check` after editing this block.

```sources
[
  {"id": "apple-gatekeeper-runtime", "url": "https://support.apple.com/guide/security/gatekeeper-and-runtime-protection-sec5599b66df/web"},
  {"id": "apple-open-anyway-flow", "url": "https://support.apple.com/en-us/102445"},
  {"id": "apple-gatekeeper-sequoia-change", "url": "https://developer.apple.com/news/?id=saqachfa"},
  {"id": "apple-tcc-file-access", "url": "https://support.apple.com/guide/security/controlling-app-access-to-files-secddd1d86a6/web"},
  {"id": "apple-rosetta", "url": "https://support.apple.com/en-us/102527"},
  {"id": "apple-macos-tahoe-updates", "url": "https://support.apple.com/en-us/122868"},
  {"id": "apple-macos-intel-support", "url": "https://support.apple.com/en-us/122867"},
  {"id": "python-macos-downloads", "url": "https://www.python.org/downloads/macos/"},
  {"id": "homebrew-installation", "url": "https://docs.brew.sh/Installation"},
  {"id": "homebrew-formula-ffmpeg", "url": "https://formulae.brew.sh/formula/ffmpeg"},
  {"id": "claude-google-workspace-connectors", "url": "https://support.claude.com/en/articles/10166901-use-google-workspace-connectors"}
]
```
