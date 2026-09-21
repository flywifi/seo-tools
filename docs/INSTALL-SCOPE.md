# Install scope: user-only by default (P93)

Everything Creator OS asks a person to download or install lands inside their own user
account -- under the home folder. Nothing goes to `/Applications`, `/opt/homebrew`,
`/usr/local`, or anywhere `sudo` is needed. Machine-wide installation is always a labeled
choice a person makes deliberately, never a default this repo hands out. Drift invariant 59
enforces this over every tracked guidance file (an unlabeled machine-wide instruction fails
the build), and the code enforces its own half: no Creator OS tool ever writes into a
machine-wide site-packages. The repo `.venv` is the only install target, so when it cannot be
created the installer refuses with the remedy instead of falling back to the base interpreter
(`tools/setup.py::install_dependencies`). A PEP 668 marker is not what protects you -- a plain
machine-wide interpreter carries no such marker and pip would have accepted the write.

## Approved locations (where Creator OS installs things)

| Location | What goes there | Evidence |
|---|---|---|
| the repo's `.venv/` | every Python package (`python3 tools/setup.py --install-deps`) | `tools/setup.py::ensure_venv`; PEP-668-immune by design |
| `~/.local/bin` | single-binary tools: `claude`, `uv` | the Claude Code and uv installers' documented targets |
| `~/Applications` | GUI apps -- Claude Desktop goes HERE (`mkdir -p ~/Applications`, then drag the app in), not `/Applications` | macOS per-user Applications folder |
| `~/Library/...` | app config (`Application Support/Claude/`), caches (pip, Playwright's browser) | written by the apps/tools themselves, always per-user |
| `~/.creator-os/` | downloaded whisper models | `tools/transcribe.py::model_dir` default |
| the repo folder | wizard state, staged bundles, `dist/` builds -- all gitignored | `.gitignore` |

## User-scoped defaults (what to install when something is missing)

| Need | User-scoped default | Notes |
|---|---|---|
| Python 3.12 to 3.14 | the interpreter already on the machine; missing or too old: `curl -LsSf https://astral.sh/uv/install.sh | sh` then `uv python install 3.12` | uv installs to `~/.local/bin`, its Pythons to `~/.local/share/uv`; "No sudo is required" per its docs |
| Node.js (Microsoft 365 lane only) | nvm, per its README install script | nvm "clones the nvm repository to `~/.nvm`" and is "designed to be installed per-user"; no sudo, ever |
| Speech-to-text | `faster-whisper` -- already inside the repo `.venv` after `--install-deps` | works on every platform, fully user-scoped |
| GitHub access | none needed -- the repository is public; `git clone` works anonymously | auth only if a machine must PUSH |

## The exceptions register (stated, not hidden)

- **git via the Apple Command Line Tools** is machine-level and has no user-scoped
  equivalent worth recommending. It is usually preinstalled; when it is not, the CLT prompt
  is the one machine-level install this repo's path may involve.
- **Using existing machine tools is allowed; adding to them is not.** Creator OS detects and
  uses an already-installed Homebrew binary (ffmpeg, whisper-cli) happily -- `env_paths`
  even searches the Homebrew prefixes. The policy governs what gets INSTALLED and what the
  docs INSTRUCT, not what already exists.
- **Machine-wide alternatives stay available, labeled.** Every remaining `brew install` in
  the guidance sits under a "machine-wide alternative (affects the whole computer)" label.
  Choosing it is legitimate; defaulting to it is not.

## Verifying an install stayed user-only

Before setup: `ls /opt/homebrew/bin 2>/dev/null | wc -l` and note the count; `ls /Applications`.
After setup: both unchanged, and everything new sits under `~` (`~/.local`, `~/Applications`,
`~/Library`, `~/projects/<repo>`, `~/.creator-os`). The strongest proof: a second user
account on the same machine sees none of it.

```sources
[
  {"id": "uv-installer-docs", "name": "uv installation (Astral docs)",
   "url": "https://docs.astral.sh/uv/getting-started/installation/",
   "category": "software-dependency", "tier": "T1"},
  {"id": "nvm-readme", "name": "nvm README (per-user Node version manager)",
   "url": "https://github.com/nvm-sh/nvm",
   "category": "software-dependency", "tier": "T1"}
]
```
