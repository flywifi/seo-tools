# Windows Setup Guide

Creator OS runs on Windows with Python 3.12 or newer. This guide covers what differs from
`docs/SETUP_MAC.md`; the parts of that guide that do not depend on the computer (Claude Projects,
Claude Desktop, the Google Drive hub model) apply as written.

Steps marked *(tested on Windows)* were run on a Windows 11 computer with Python installed for one
account and Git for Windows. Steps marked *(not yet tested on Windows)* follow the vendors'
documentation.

---

## Quick start (no terminal)

1. **Install Python for your account.** The Python documentation recommends the **Python install
   manager**, from the Microsoft Store or as the identical download from python.org. It adds the
   `python`, `py` and `python3` commands and updates itself. Then, in a terminal, run
   `py install 3.14` *(tested on Windows, on a clean install)*. It may say its global shortcuts
   directory (`%LOCALAPPDATA%\Python\bin`) is not on PATH; Creator OS does not need it, since
   `py`, `python` and `python3` work without it. With the install manager, `python3` is a real
   command, not the Microsoft Store stand-in *(tested on Windows: `py -3` and `python3` run the
   installed Python)*. Creator OS needs Python 3.12 or newer and is tested on 3.12 to 3.14.
   - Alternative: the traditional python.org installer, for Python 3.12 or newer; the Python
     documentation marks it deprecated since 3.14 and says it is not produced for 3.16 or later (the 3.12 floor is unchanged).
     On its first screen, tick **Add python.exe to PATH**. Machine-wide note (affects the whole
     computer): the same screen ticks the py launcher's all-users option by default, which needs
     administrator rights; untick it to install Python for your account alone. If SmartScreen says
     "Windows protected your PC", choose **More info**, then **Run anyway**. *(tested on Windows:
     an install for one account gives working `py -3` and `python` commands)*
2. **Put the repository under your user folder**, for example `%USERPROFILE%\CreatorOS\seo-tools`,
   and not inside OneDrive or the Google Drive folder. Setup warns about both other places: a
   synced folder syncs the credential files in `pipeline/user-context/`, and on Windows a folder
   outside your user folder takes the drive's permissions, which by default let other accounts on
   the computer read its files <!-- verify: tools/env_paths.py::windows_outside_home -->.
   *(tested on Windows: a fresh clone in a folder whose path has spaces)*
3. **Double-click `Start Creator OS Setup.bat`.** It tries `py -3`, then `python`, checks for
   Python 3.12 or newer and opens the setup wizard in your browser. When the wizard stops with an
   error, the window stays open so you can read it. *(tested on Windows)*

## Full setup (terminal)

Use PowerShell, Command Prompt or Git Bash. The commands below use forward slashes, which work in
all three; `py -3` and `python` run the same Python when both are installed.

### Step 1: Git and line endings

- Git: Git for Windows, or `scoop install git` (Scoop installs under your user folder).
  *(Git for Windows tested; Scoop not yet tested on Windows)*
- Line endings are set by the repository: `.gitattributes` checks text files out with LF and
  `.bat` files with CRLF, whatever `core.autocrlf` says. *(tested on Windows on a fresh clone)*
- A clone made before that rule may report hash drift. On a clean tree (nothing uncommitted), run
  these two commands once to check it out again *(tested on Windows)*:

      git rm -r --cached -q .
      git reset -q --hard

### Step 2: Clone

In PowerShell:

    git clone https://github.com/flywifi/seo-tools.git "$env:USERPROFILE\CreatorOS\seo-tools"

In Command Prompt, write the folder as `"%USERPROFILE%\CreatorOS\seo-tools"` instead.

### Step 3: First-time setup

    py -3 tools/setup.py

It creates the private `*.local.json` files, builds the keyword cache and runs the drift guard.
It installs no packages; Step 4 does. *(tested on Windows on a fresh clone; no tracked file
changed)*

### Step 4: Optional dependency sets (private `.venv`)

    py -3 tools/setup.py --install-deps

It creates the repository's `.venv` and runs pip and Playwright inside it. The first run needs
about 1.4 GB of disk for the `.venv` and Playwright's browsers. *(tested on Windows)* On Python
3.14 the timeline interchange packages (OpenTimelineIO and its two adapters) are skipped, because
OpenTimelineIO publishes no 3.14 wheels yet; the video tools report them as absent and keep working.

Local transcription runs on the computer's CPU: `py -3 tools/transcribe.py doctor` checks it, and
the first `py -3 tools/transcribe.py run` downloads the speech model into the Hugging Face cache
(or `HF_HOME` when set). *(tested on Windows)*

### Step 5: The setup wizard

    py -3 tools/wizard.py

- **Ports.** The wizard binds `8765`, then `8775`, then `8785`. Windows can reserve single ports
  for Hyper-V, WSL or Docker; `netsh interface ipv4 show excludedportrange protocol=tcp` lists
  them. The wizard says when its first port is reserved and uses the next. *(tested on Windows)*
- **Addresses.** The wizard prints `http://127.0.0.1:<port>/` links. If you type an address
  yourself, use that form rather than `localhost`: Windows tries IPv6 `::1` first for
  `localhost`, and the wizard listens on IPv4, so each request can wait about two seconds.
  *(tested on Windows)*
- **OAuth.** TikTok and Pinterest need the exact return address, so register all three:
  `http://127.0.0.1:8765/oauth/<platform>/callback`, and the same with `8775` and `8785`
  (`docs/WIZARD.md`). *(not yet tested on Windows against the platform consoles)*
- **A second copy** started by mistake says the wizard is already running instead of sharing the
  port. *(tested on Windows)*

### Claude Desktop

- Machine-wide alternative (affects the whole computer): Anthropic's full Windows install, with
  the agentic tasks on this computer that Claude Cowork used to run, asks for administrator rights
  (a UAC prompt). Without them Claude Desktop still installs, and Anthropic says those desktop
  agentic tasks are not available. *(not yet tested on Windows)*
- The packaged (MSIX) build keeps its settings under
  `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\`, not in
  `%APPDATA%\Claude\`, and an install that had the older app can keep reading
  `%APPDATA%\Claude\`. Claude Desktop's log (`%LOCALAPPDATA%\Claude\logs\main.log`, or the
  packaged app's own `logs` folder) names the file it reads. The wizard's Claude Desktop step
  writes the file that log names and the packaged app's file, and also
  `%APPDATA%\Claude\claude_desktop_config.json` when that file exists beside a packaged app; a file
  saved with a byte-order mark (Notepad, PowerShell 5.1) is read as it is. The screen names each
  file it wrote
  <!-- verify: tools/wizard.py::_claude_config_targets -->. *(the log line seen on Windows; the
  guided first run tested on Windows with stand-in settings folders in both layouts)*
- After the wizard writes the settings, quit Claude Desktop from its icon in the notification
  area by the clock (right-click it, then Quit) and reopen it: closing the window leaves it
  running, and it reads its settings only when it starts
  <!-- verify: tools/wizard.py::_restart_step -->.

### Scheduling Dashboard

    py -3 tools/dashboard/server.py

It binds `8766`, then `8776`, then `8786`. *(tested on Windows)*

## The Google Drive hub (optional)

- Install Google Drive for desktop and sign in. The hub is `<letter>:\My Drive\Creator OS`, where
  the letter is the one Drive for desktop shows in its Preferences (often `G:`).
- Make the `Creator OS` folder inside `My Drive`, then open the wizard's **Drive hub** screen
  (`/drive-hub`). It offers that folder when it finds one on a drive; otherwise paste its path
  (Explorer's "Copy as path" works, quotes included). The wizard accepts a folder inside a Drive
  `My Drive` or `Shared drives` folder, and refuses `My Drive` itself
  <!-- verify: tools/wizard.py::on_google_drive -->.
- Stream files mode *(tested on Windows)*. Mirror files mode *(not yet tested on Windows)*.
- Keep the repository itself out of the Drive folder (Quick start step 2).
- Update Creator OS on every computer that shares the hub before queuing work from Windows: a
  computer on an older version refuses a job queued as `windows` and archives it (ADR 0075).

## Windows notes that trip people up

| Symptom | Why | What to do |
|---|---|---|
| `python3` opens the Microsoft Store | on Windows `python3` can be the Store's alias | use `py -3` or `python` (the `.bat` does) |
| Maintainers: a commit is refused with "no working Python" | the git hooks found no working `python3`, `python` or `py -3` | install Python as above, then run `py -3 tools/install_hooks.py` again; the hooks record the Python that installed them and try the other names after it <!-- verify: tools/install_hooks.py::render --> |
| "Windows cannot find 'Creator'" | the launcher was started from another shell without quotes | double-click it, or quote the full file name |
| `bash` runs WSL instead of Git Bash | `C:\Windows\System32\bash.exe` comes first on PATH | nothing for users; the battery finds Git's bash itself |

Also tested on Windows: Developer Mode is not needed (folder links fall back to junctions), the
battery passed with Microsoft Defender's real-time protection on, and non-ASCII profile text
round-trips through the default cp1252 console.

## For maintainers

- After cloning, run `py -3 tools/install_hooks.py` once (`CLAUDE.md`, Commit and PR hygiene).
- `py -3 tools/battery.py` runs every gate; CI runs it on Windows too (the `windows` job in
  `.github/workflows/ci.yml`).
- The auditor agent's hook in `.claude/settings.json` runs under Git Bash; it tries `python3`,
  `python` and `py -3`, and refuses the auditor's call when none works.

## Declared sources (maintainers)

Every id below must exist in `canonical-sources/source-registry.json` with the same URL
(drift-guard invariant 52); run `python3 tools/source_sync.py check` after editing this block.

```sources
[
  {"id": "claude-desktop-windows-deploy", "name": "Deploy Claude Desktop for Windows (help center)", "url": "https://support.claude.com/en/articles/12622703-deploy-claude-desktop-for-windows", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "claude-desktop-msix-config-path", "name": "Claude Desktop MSIX build reads a different claude_desktop_config.json (claude-code issue 26073)", "url": "https://github.com/anthropics/claude-code/issues/26073", "category": "ai-surface-spec", "tier": "T2"},
  {"id": "python-using-on-windows", "name": "Python docs - Using Python on Windows", "url": "https://docs.python.org/3/using/windows.html", "category": "os-platform", "tier": "T1"}
]
```
