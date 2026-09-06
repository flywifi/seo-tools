# 38. P54 macOS Venv And Path Fixes

- Date: 2026-07-16
- Status: Accepted

## Context

The P53 stress test confirmed two HIGH macOS defects — a Homebrew Python's PEP 668 lock made the
dependency installer silently install nothing, and a double-clicked `.command` runs a non-login zsh
whose PATH lacks `/opt/homebrew/bin`, so brew tools (node, uv, whisper-cli, ffmpeg) read as missing
even when installed — plus the Claude Desktop requirement that an MCP `command` be an absolute path
resolvable on its narrow GUI PATH, and a set of copy/handling gaps (stale Gatekeeper flow, port
traceback, Safari OAuth, TCC folder denials, Intel-vs-Metal). This environment is Linux, so the fixes
are verified at the mechanism level (OS-simulation + selftests); behavioral confirmation stays the P53
hands-on checklist.

## Decision

Adopt a repo-local, gitignored `.venv` ("private toolbox") as the single mechanism that resolves the
PEP 668 install break, the double-click interpreter-discovery problem, and the MCP absolute-command
requirement together. `tools/env_paths.py` centralizes it: `app_python()` returns the `.venv`
interpreter when present (else `sys.executable`, so no `.venv` == prior behavior), and `which()`
prepends the Homebrew prefixes so brew tools resolve under a bare PATH. `setup.py::ensure_venv` creates
`.venv` and installs into it (`--break-system-packages` is a labeled fallback). The launcher, the
Claude MCP snippet, and every wizard subprocess use these helpers. Companion fixes: an injectable
`_os()/_arch()` seam, a friendly busy-port exit, `_mcp_command` absolute npx/uvx resolution +
Quit/relaunch/log copy, a real-python-probe launcher, arch-aware STT copy, a TCC folder-denial message,
DaVinci multi-path detection, and a Safari OAuth caveat.

## Consequences

**Explicitly not done:** cannot change macOS itself — real Gatekeeper/TCC/Homebrew-PEP668/Safari/Rosetta
behavior stays the P53 hands-on checklist, verified here only by simulation + selftests. `.venv`
degrades to prior behavior when absent (no regression). No product-logic change beyond the
launch/install/detect plumbing and copy. seo-tools only.

**Verified by:**
- tools/env_paths.py --selftest (8/8); tools/setup.py --selftest (venv creation + pip target, offline)
- tools/wizard.py --selftest (macOS render seam, port-collision, loopback-127.0.0.1 guard G1, whisper 3-name guard G2)
- sync_check.py clean; scenario_check 9/9; projection_manifest --check clean; full selftest battery green

Ledger status at record time: `shipped`. Source: `ledger/ledger.json` id `P54-macos-fixes-venv-and-path`.
