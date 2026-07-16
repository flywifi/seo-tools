# macOS maintenance notes (for maintainers)

The non-negotiable macOS invariants and the reasoning behind them, so a future edit does not silently
re-break what the P53 stress test found and P54 fixed. User-facing setup lives in `docs/SETUP_MAC.md`;
this file is the maintainer's "why." A full hands-on verification checklist (the behaviors that can
only be confirmed on real hardware) was produced by the P53 stress test.

**Current target:** macOS 26 (Tahoe), the last Intel release; macOS 15 (Sequoia) is the prior version.
Apple Silicon uses `/opt/homebrew`; Intel uses `/usr/local`. This environment is Linux, so every
macOS behavior below is verified here only at the mechanism level (OS-simulated) — behavioral
confirmation is the hands-on checklist.

## Non-negotiable invariants

1. **Dependencies install into a private `.venv` ("private toolbox").** A Homebrew Python follows
   PEP 668 and refuses a global `pip install`. `setup.py::ensure_venv` creates `.venv/` (gitignored)
   and installs there; `--break-system-packages` is a labeled fallback only when a `.venv` cannot be
   created. Never add a bare `pip install` into the base interpreter.
   <!-- verify: tools/setup.py::ensure_venv -->
2. **The app runs under the `.venv` interpreter when it exists.** `env_paths.app_python()` returns the
   `.venv` python if present, else `sys.executable` (so no `.venv` == today's behavior, no regression).
   The launcher, the Claude MCP snippet, and every wizard subprocess call use it. Do not hardcode
   `python3`/`sys.executable` for a heavy tool.
   <!-- verify: tools/env_paths.py::app_python -->
3. **Resolve system binaries with the Homebrew prefixes prepended.** A double-clicked `.command` runs
   a non-login zsh (only `~/.zshenv`), so `/opt/homebrew/bin` is off PATH and `shutil.which` misses
   brew tools. Use `env_paths.which()` for `node`/`uv`/`ffmpeg`/`whisper-cli`, never bare `shutil.which`
   / a bare command name.
   <!-- verify: tools/env_paths.py::which -->
4. **Bind loopback only (`127.0.0.1`), never `0.0.0.0`.** Loopback is exempt from the macOS Application
   Firewall incoming-connection prompt and the Sequoia/Tahoe local-network permission prompt (Apple
   TN3179). The wizard `_selftest` guards this; do not regress the bind in `main()`.
5. **The Claude Desktop MCP `command` must be an absolute interpreter path.** Claude Desktop launches
   servers with its own narrow PATH; a bare `python3`/`npx`/`uvx` can fail with `ENOENT`. The snippet's
   `creator-os` points at `.venv/bin/python3`; wizard-written entries resolve `npx`/`uvx` via
   `env_paths.which()` (`wizard.py::_mcp_command`). Config is read only at launch → the copy must say
   "**Quit completely (Cmd-Q) and reopen**", and point at `~/Library/Logs/Claude/mcp-server-<name>.log`.
   <!-- verify: tools/wizard.py::_mcp_command -->
6. **whisper.cpp CLI-rename resilience.** The binary has been `whisper-cli`, `whisper-cpp`, and `main`
   across versions; the detector probes all three (`transcribe.py::detect_backends`,
   `wizard._stt_backend_present`). Metal is default-on on Apple Silicon and off on Intel — copy must not
   promise Metal on Intel.
   <!-- verify: tools/transcribe.py::detect_backends -->
7. **STT backend selection is OS/arch aware and injectable.** `transcribe.select_backend` picks
   whisper.cpp (Metal) on Apple Silicon, whisper.cpp (CPU) on Intel, faster-whisper fallback, and an
   honest `run_local_stt` gap when nothing is installed. Keep it pure/injectable so it is testable
   offline.
   <!-- verify: tools/transcribe.py::select_backend -->
8. **The wizard's macOS branches are simulatable.** `wizard._os()`/`_arch()` honor `_OS_OVERRIDE`/
   `_ARCH_OVERRIDE` so the Mac screens render in `--selftest` without hardware. Add new OS branches
   behind these, not bare `platform.system()`.
   <!-- verify: tools/wizard.py::_os -->
9. **The folder picker degrades, and reads fail loudly.** `pick_folder._os_command("mac")` builds the
   `osascript 'choose folder'` command; the chain is tkinter → osascript → text field. On a macOS TCC
   denial the import surfaces a plain "Privacy & Security → Files and Folders" message, not a bare
   "not found."
   <!-- verify: tools/pick_folder.py::_os_command -->
10. **Never assume `python3` works on a fresh Mac.** The built-in `/usr/bin/python3` is a stub that
    triggers the Command Line Tools dialog. The launcher probes for a real, working interpreter and
    steers to the notarized python.org universal2 `.pkg` when only the stub exists.

## Reuse anchors
- `tools/env_paths.py` — `venv_python` / `app_python` / `which` / `augmented_path` (the shared helper).
- `Start Creator OS Setup.command` — venv-prefer + real-python probe + brew-PATH export + Gatekeeper copy.
- `implementation/claude/desktop/claude_desktop_config_snippet.json` + its `README.md` — absolute
  interpreter + Quit/relaunch + logs.
- `tools/videoedit/preflight.py::_resolve_present` — probes both DaVinci Resolve install paths.

## What only a real Mac can confirm (hands-on)
Gatekeeper block on a downloaded `.zip` and the Open-Anyway flow; the CLT dialog on a fresh Mac; the
real PEP 668 error on a Homebrew Python and that `.venv` sidesteps it; brew tools invisible under a
double-click and that the launcher's PATH export fixes it; Claude Desktop spawn-PATH + Quit/relaunch;
TCC folder prompts; Safari HTTPS-Only vs Chrome for the OAuth callback; Rosetta prompts; Metal-vs-CPU
whisper runtimes. These are the P53 hands-on checklist items; the code/copy here is verified by
simulation + selftests.

## When you change any of this
Update `docs/SETUP_MAC.md` and this file in the same change (the CLAUDE.md docs-in-same-PR rule); keep
the `verify:` markers pointing at real symbols; run `python3 tools/wizard.py --selftest`,
`tools/setup.py --selftest`, `tools/env_paths.py --selftest`, and `python3 tools/sync_check.py`.
