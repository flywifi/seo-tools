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
   denial the import surfaces a plain "Privacy & Security → Files & Folders" message, not a bare
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

## Declared sources
The external authorities the invariants above rest on, declared for the currency system. Every id
below must exist in `canonical-sources/source-registry.json` with the same URL (drift-guard invariant
52, fail-closed); `tools/source_sync.py reconcile` generates a seed file for any id declared here that
is not yet registered, and the human runs `seed-sources` on it. Declaring a NEW source requires the
full seed shape (`id`, `name`, `url`, `category`, `tier`); an already-registered id needs only
`id` + `url`.

```sources
[
  {"id": "pep-668-externally-managed", "url": "https://peps.python.org/pep-0668/"},
  {"id": "homebrew-and-python", "url": "https://docs.brew.sh/Language-Runtimes-and-Packages"},
  {"id": "homebrew-installation", "url": "https://docs.brew.sh/Installation"},
  {"id": "python-using-on-mac", "url": "https://docs.python.org/3/using/mac.html"},
  {"id": "apple-local-network-privacy-tn3179", "url": "https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy"},
  {"id": "apple-local-network-privacy-faq", "url": "https://developer.apple.com/forums/thread/660260"},
  {"id": "homebrew-formula-whisper-cpp", "url": "https://formulae.brew.sh/formula/whisper-cpp"},
  {"id": "homebrew-formula-python-tk", "url": "https://formulae.brew.sh/formula/python-tk@3.13"},
  {"id": "whisper-cpp-ggml-models-hf", "url": "https://huggingface.co/ggerganov/whisper.cpp"},
  {"id": "mcp-connect-local-servers", "url": "https://modelcontextprotocol.io/docs/develop/connect-local-servers"},
  {"id": "claude-desktop-local-mcp", "url": "https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop"},
  {"id": "claude-code-mcp-docs", "url": "https://code.claude.com/docs/en/mcp"},
  {"id": "claude-desktop-vs-web-connectors", "url": "https://support.claude.com/en/articles/11725091-when-to-use-desktop-and-web-connectors"}
]
```

Claim-to-source notes: invariants 1 and 2 (`.venv`) rest on PEP 668 + Homebrew-and-Python; invariant 3
(brew prefixes) on Homebrew Installation; invariant 4 (loopback bind) on TN3179's own definition,
retrieved in full on 2026-08-10: *"A local network is an IP network associated with a
broadcast-capable network interface. Such interfaces include Wi-Fi and Ethernet, but not cellular
(WWAN) or VPN. A local network address is any address on a local network."* Loopback is not a
broadcast-capable interface, so it falls outside that definition by construction. **State this as a
documented-definition inference, never as an Apple statement about loopback:** TN3179 does not use
the words loopback, localhost, or 127.0.0.1 anywhere. Two earlier versions of this note were wrong
and are corrected here. The first attributed an explicit loopback exemption to the DTS forum thread;
that thread addresses BSD-sockets code listening on UDP without sending and says nothing about
loopback. The second said the technote could not be re-fetched; its body is reachable through the
`developer.apple.com/tutorials/data/documentation/...json` endpoint even though the HTML shell
renders client-side. **The invariant does not depend on the inference**: binding 127.0.0.1 is correct
because the wizard has no reason to listen on an external interface, and that stands whatever the
prompt semantics turn out to be; invariant 5 (absolute MCP command) on the MCP
connect-local-servers doc; invariants 6 and 7 (whisper) on the whisper-cpp formula + the GGML model repo;
invariant 9 (TCC folder denial) on the Apple file-access guide, which is where the
"Privacy & Security -> Files & Folders" wording comes from; invariant 10 (python stub) on the
Python-on-macOS doc.

## Re-verification status (P69 to P71, current 2026-08-10)

Every source this document **declares** (the `sources` block above, 13 entries) now carries a
`last_checked` date except the ones named below. That denominator is deliberately the doc's own
declared set, which is reproducible by reading the block; an earlier version cited "23 of 27
macOS-relevant sources", a set no field in the registry marks and no tool derives, and which
`CHANGELOG.md` separately called 26 (P73 D2-1/D2-2).

Of the declared set, only `apple-local-network-privacy-faq` remains unstamped. These are the
mechanical reasons, covering both the declared set and the adjacent dependency entries:

- `apple-local-network-privacy-faq` -- `developer.apple.com/forums/thread/660260` redirects to a
  verify-human challenge, so it cannot be fetched from any headless environment. It is retained as a
  real authority for the fact it does state (UDP listen-without-send), and is explicitly NOT the
  source for the loopback claim it was once miscited for; see the claim-to-source notes above.
- `dep-whisper-cpp` and `dep-faster-whisper` -- GitHub Releases rate-limited the unauthenticated
  check, which `tools/dependency_currency.py` correctly reports as `blocked: true` (blocked is not
  absent, so it refuses to stamp). Re-run with `GITHUB_TOKEN` set to clear these.
- `dep-apple-compressor` -- `upstream_api: manual`, advisory by construction; no tool will ever stamp
  it, and that is the intended design.

**Two corrections to what earlier versions of this section claimed.** Both were wrong in the same
direction, calling an environment limitation a property of the source:

- It said `apple-open-anyway-flow` "was attempted twice and both fetches returned truncated content."
  That was a truncation artifact in the fetch tooling, not the page. Retrieved directly it returns
  ~1.15 MB and states the current flow verbatim: "Open System Settings. Click Privacy & Security,
  scroll down, and click the Open Anyway button." It contains no Control-click or right-click
  instruction, which independently corroborates the removal this guide documents. Now stamped.
- It implied the technote body was unreachable. The HTML shell renders client-side, but the body is
  served as JSON from `developer.apple.com/tutorials/data/documentation/<path>.json`. Now stamped.

**Model integrity pins re-verified 2026-08-10.** All six entries in
`canonical-sources/whisper-models.json` match upstream on both sha256 and byte size. The check is
cheap and does not require downloading the weights: issue a HEAD to the Hugging Face `resolve` URL and
read `X-Linked-Etag` / `X-Linked-Size` from the **302 response itself**. Do not follow the redirect --
the CDN returns a different Xet content hash that will not match the pin and looks like a failure.
Note the guarantee's shape: this confirms the pin equals the LFS object id the repository declares,
which is the same assurance any whisper.cpp user gets, not an independent re-hash of the bytes. An
earlier note claiming these hashes could not be verified without downloading gigabytes was wrong.

## When you change any of this
Update `docs/SETUP_MAC.md` and this file in the same change (the CLAUDE.md docs-in-same-PR rule); keep
the `verify:` markers pointing at real symbols and the `sources` block above in sync with the registry
(`python3 tools/source_sync.py check`); run `python3 tools/wizard.py --selftest`,
`tools/setup.py --selftest`, `tools/env_paths.py --selftest`, and `python3 tools/sync_check.py`.
