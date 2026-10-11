# Install scope: user-only by default (P93)

Everything Creator OS asks a person to download or install lands inside their own user
account -- under the home folder. Nothing goes to `/Applications`, `/opt/homebrew`,
`/usr/local`, or anywhere `sudo` is needed. Machine-wide installation is always a labeled
choice a person makes deliberately, never a default this repo hands out. The exceptions register
below names the machine-level installs this repo's path can involve; on Windows that includes
Microsoft's Visual C++ runtime, which the setup wizard installs when the person confirms.
Drift invariant 59 enforces this over every tracked guidance file (an unlabeled machine-wide instruction fails
the build), and the code enforces its own half: no Creator OS tool ever writes into a
machine-wide site-packages. The repo `.venv` is the only install target, so when it cannot be
created the installer refuses with the remedy instead of falling back to the base interpreter
(`tools/setup.py::install_dependencies`, `tools/wizard.py::_install_uv`). A PEP 668 marker is
not what protects you -- a plain machine-wide interpreter carries no such marker and pip would
have accepted the write.

## Approved locations (where Creator OS installs things)

| Location | What goes there | Evidence |
|---|---|---|
| the repo's `.venv/` | every Python package (`python3 tools/setup.py --install-deps`) | `tools/setup.py::ensure_venv`; PEP-668-immune by design |
| `~/.local/bin` | single-binary tools: `claude`, `uv` | the Claude Code and uv installers' documented targets |
| `~/Applications` | GUI apps -- Claude Desktop goes HERE (`mkdir -p ~/Applications`, then drag the app in), not `/Applications` | macOS per-user Applications folder |
| `~/Library/...` | app config (`Application Support/Claude/`), caches (pip, Playwright's browser) | written by the apps/tools themselves, always per-user |
| `~/.creator-os/` | downloaded whisper models | `tools/transcribe.py::model_dir` default |
| the repo folder | wizard state, staged bundles, `dist/` builds -- all gitignored | `.gitignore` |
| `~/Library/LaunchAgents` | the optional profile-mirror agent (`com.creatoros.profile-mirror.plist`) | `tools/profile_mirror.py::build_plist`; loaded into your own `gui/<uid>` domain |
| `~/Library/Logs/CreatorOS` | the profile mirror's run log and its last-run stamp (`profile-mirror.last-run`) | `tools/profile_mirror.py::LOG_DIR` |

## User-scoped defaults (what to install when something is missing)

| Need | User-scoped default | Notes |
|---|---|---|
| Python 3.12 to 3.14 | the interpreter already on the machine; missing or too old: `curl -LsSf https://astral.sh/uv/install.sh | sh` then `uv python install 3.12` | uv installs to `~/.local/bin`, its Pythons to `~/.local/share/uv`; "No sudo is required" per its docs |
| Node.js (Microsoft 365 lane only) | nvm, per its README install script | nvm "clones the nvm repository to `~/.nvm`" and is "designed to be installed per-user"; its README adds "When using `nvm` you do not need `sudo` to globally install a module with `npm -g`" |
| Speech-to-text | `faster-whisper` -- already inside the repo `.venv` after `--install-deps` | the package itself is user-scoped on macOS, Linux and Windows; on Windows its engine also loads Microsoft's Visual C++ runtime, a machine-wide install (see the exceptions register) |
| GitHub access | none needed -- the repository is public; `git clone` works anonymously | auth only if a machine must PUSH |

## The exceptions register (stated, not hidden)

- **git via the Apple Command Line Tools** is machine-level and has no user-scoped
  equivalent worth recommending. It is usually preinstalled; when it is not, the CLT prompt
  is a machine-level install this repo's path may involve on a Mac.
- **The Microsoft Visual C++ Redistributable on Windows** is machine-wide (it affects the whole
  computer). faster-whisper's engine loads it, and pip does not install system libraries. It is
  often present already; when it is missing, the setup wizard's Check my setup screen offers to
  install it, under a heading labeled machine-wide. The wizard downloads Microsoft's permalink
  after the person ticks a confirmation box, and runs it
  once Windows reports a Valid signature from Microsoft Corporation chained to Microsoft's
  code-signing root (ADR 0079, `tools/transcribe.py::install_vc_runtime`). The same screen
  keeps the manual route: Microsoft's download, or
  `winget install --exact --id Microsoft.VCRedist.2015+.x64`.
- **Using existing machine tools is allowed; adding to them is not.** Creator OS detects and
  uses an already-installed Homebrew binary (ffmpeg, whisper-cli) happily -- `env_paths`
  even searches the Homebrew prefixes. The policy governs what gets INSTALLED and what the
  docs INSTRUCT, not what already exists.
- **Machine-wide alternatives stay available, labeled.** Every remaining `brew install` in
  the guidance sits under a "machine-wide alternative (affects the whole computer)" label.
  Choosing it is legitimate; defaulting to it is not.

## Verifying an install stayed user-only

Before setup: `ls /opt/homebrew/bin 2>/dev/null | wc -l` and note the count; `ls /Applications`.
After setup, run both again and compare them with your notes. The user-scoped locations this
page names are `~/.local`, `~/.nvm`, `~/Applications`, `~/Library`, `~/projects/<repo>` and
`~/.creator-os`. A PATH check from a second user account on the same machine: there,
`command -v uv node` should not print a path inside the first account's home folder. `git`
from the Apple Command Line Tools is machine-level (see the exceptions register above), so that
account finds it.

## On Windows

On Windows the defaults stay inside the user's account too; the machine-wide installs the path
can involve are listed under the table.

| Location | What goes there | Evidence |
|---|---|---|
| the repo's `.venv\` | the Python packages (`py -3 tools/setup.py --install-deps`) | `tools/setup.py::ensure_venv` |
| the account's Python | the Python install manager's runtimes; its shortcuts go in `%LocalAppData%\Python\bin` | the Python documentation: the install manager "does not support installing runtimes per-machine" |
| `%LOCALAPPDATA%\Programs\Git` | Git for Windows installed from a standard account | the installer's script falls back to the user's Programs folder when `C:\Program Files` is not writable; tested in Windows Sandbox |
| `%USERPROFILE%\scoop` | Scoop, and Node.js for the Microsoft 365 lane from it (`scoop install nodejs-lts`, the wizard's Windows Node.js step) | Scoop's README: run from a regular (non-admin) PowerShell, it installs to `C:\Users\<YOUR USERNAME>\scoop`; tested on Windows in Windows Sandbox, whose account runs elevated (Scoop's installer allows that there), not yet from a standard account |
| `%USERPROFILE%\.creator-os\whisper-models` | downloaded whisper.cpp models | `tools/transcribe.py::model_dir` (HOME, else USERPROFILE); the folder choice checked by transcribe's selftest with HOME unset and USERPROFILE set, which the Windows CI job runs; a download there not yet tested on Windows |
| `%USERPROFILE%\AppData\Local\ms-playwright` | Playwright's browser, which `--install-deps` downloads | Playwright's documentation (Managing browser binaries) |
| `%APPDATA%\Claude\`, or the packaged app's `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\` | the Claude Desktop settings file the wizard writes | `tools/wizard.py::_claude_config_targets` |

Machine-wide on Windows, labeled where the guidance names it:

- The Microsoft Visual C++ Redistributable (the exceptions register above).
- Machine-wide alternative (affects the whole computer): the Git for Windows installer run as an
  administrator installs to `C:\Program Files\Git` and adds Git to the computer's PATH
  (`docs/SETUP_WINDOWS.md`, Step 1).
- Machine-wide alternative (affects the whole computer): the Node.js installer from nodejs.org,
  which the wizard's Windows Node.js step names after the Scoop route, installs to a `nodejs`
  folder under Program Files and adds it to the computer's PATH (its WiX source leaves the
  package's install scope at the WiX default, per machine, and marks its PATH entry as a system
  one; its SetInstallScope action keeps an earlier per-user Node.js install per-user when it
  upgrades it).
- The traditional python.org installer's machine-wide py launcher option and Anthropic's full
  Claude Desktop install, both labeled in `docs/SETUP_WINDOWS.md`.

To check that an install stayed per-user on Windows, run these four lines in PowerShell before
setup and again after it, and compare the output:

    Get-ChildItem $env:ProgramFiles | Select-Object -ExpandProperty Name
    Get-ChildItem ${env:ProgramFiles(x86)} | Select-Object -ExpandProperty Name
    [Environment]::GetEnvironmentVariable('Path', 'Machine')
    Test-Path "$env:SystemRoot\py.exe"

They list the folders at the top of Program Files and Program Files (x86), print the computer's
PATH, and say whether the py launcher's machine-wide option put `py.exe` in the Windows folder. They
do not show a change inside a folder that was already there, in ProgramData or in the registry. A
per-user install changes the account's own PATH,
`[Environment]::GetEnvironmentVariable('Path', 'User')`, and leaves the four as they were.
Installing the Visual C++ runtime from the wizard is a machine-wide change by design (the
exceptions register above). *(the four lines tested on Windows in Windows PowerShell 5.1; the
before-and-after comparison not yet tested)*

```sources
[
  {"id": "uv-installer-docs", "name": "uv installation (Astral docs)",
   "url": "https://docs.astral.sh/uv/getting-started/installation/",
   "category": "software-dependency", "tier": "T1"},
  {"id": "nvm-readme", "name": "nvm README (per-user Node version manager)",
   "url": "https://github.com/nvm-sh/nvm",
   "category": "software-dependency", "tier": "T1"},
  {"id": "python-using-on-windows", "name": "Python docs - Using Python on Windows",
   "url": "https://docs.python.org/3/using/windows.html",
   "category": "os-platform", "tier": "T1"},
  {"id": "git-for-windows-installer-script",
   "name": "Git for Windows installer script (install.iss, git-for-windows/build-extra)",
   "url": "https://github.com/git-for-windows/build-extra/blob/main/installer/install.iss",
   "category": "software-dependency", "tier": "T1"},
  {"id": "playwright-python-browsers", "name": "Playwright for Python - Browsers (Managing browser binaries)",
   "url": "https://playwright.dev/python/docs/browsers",
   "category": "software-dependency", "tier": "T1"},
  {"id": "nodejs-msi-product-wxs", "name": "Node.js Windows installer source (product.wxs, nodejs/node)",
   "url": "https://github.com/nodejs/node/blob/main/tools/msvs/msi/nodemsi/product.wxs",
   "category": "software-dependency", "tier": "T1"},
  {"id": "wix-package-element", "name": "WiX Toolset schema - Package element (install scope)",
   "url": "https://docs.firegiant.com/wix/schema/wxs/package/",
   "category": "software-dependency", "tier": "T1"},
  {"id": "scoop-readme", "name": "Scoop README (installs programs for the current Windows account)",
   "url": "https://github.com/ScoopInstaller/Scoop",
   "category": "software-dependency", "tier": "T1"},
  {"id": "scoop-nodejs-lts-manifest", "name": "Scoop Main bucket - nodejs-lts manifest",
   "url": "https://github.com/ScoopInstaller/Main/blob/master/bucket/nodejs-lts.json",
   "category": "software-dependency", "tier": "T1"}
]
```
