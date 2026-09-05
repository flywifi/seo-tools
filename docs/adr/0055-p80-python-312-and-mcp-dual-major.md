# ADR 0055 — A 3.12 floor set by the narrowest lane, and an MCP server that speaks both SDK majors

- Status: accepted
- Date: 2026-09-05
- Phase: P80 (remediation of the P79 residue)

## Context

P79 left three non-Mac items open. Researching each to primary text changed its shape:

- The dependency checker's docs described a reconciliation the tool never performed. The tool reads
  two registry fields (`validated_version`, `pinned_constraint`); the requirements files and the
  evidence file are hand-transcribed inputs. Thirteen pip entries had an empty registry pin, so
  out-of-pin detection was unreachable for them, and one pin (faster-whisper) already disagreed
  with its requirements line.
- numpy 2.5 dropped Python 3.11, the interpreter the video tooling was validated on. At the same
  time the repo recommended `brew install python@3.13` in twelve places while its own DaVinci
  Resolve gate caps the scripting bridge at 3.12. Python 3.12 is the only version every lane agrees
  on. The Homebrew formula API gives python@3.12 a deprecation date of 2028-11-01 and python@3.13
  2029-11-01: recommending 3.12 costs one year of runway.
- The MCP Python SDK went to 2.x. Two of the four breaks the P79 record listed were not breaks (the
  `mcp.types` alias is permanent and camelCase kwargs still construct; the tool registry internals
  are unchanged). The two real breaks were silent: a swallowed settings assignment made `--host`
  and `--port` no-ops, and the app factory's DNS-rebinding default answers 421 to the proxied Host
  header the documented deployment sends. Executing the port found that the second is not a 2.x
  break at all: 1.28.1 and 1.29.1 enable the same protection in the constructor, so the proxied
  runbook had been failing on the shipped pin since it was written.
- Executing the plan also found two environment-dependent guards: the skill-package manifest hashed
  gitignored `__pycache__` output, and the fcpxml selftest accepted only xmllint's validation levels.
  The second had kept CI red on every run since 2026-08-16 while every machine with xmllint passed.

## Decision

1. The Python floor is 3.12 and the recommended macOS formula is `python@3.12`. The reason is the
   Resolve ceiling, not runway; the runway cost is accepted here. The launcher probes each candidate
   interpreter for 3.12 or newer instead of accepting any interpreter that imports.
2. The dependency checker keeps reading only the registry. The chain the docs described is enforced
   instead: drift invariant 25 fails the build when a requirements specifier and the registry pin
   disagree. The docs say what the tool does, and CURRENCY.md is bound in doc-freshness so the
   contract cannot drift silently again.
3. `tools/mcp_server.py` is dual-capable (MCPServer arm first, FastMCP arm second). The pin moves to
   `mcp>=2,<3` after the live tier and a real bind test passed under both majors and again from a
   fresh venv installed from the flipped requirements. Host and port reach `run()` explicitly. A new
   allowed-hosts surface (`--allowed-host`, `remote_mcp_allowed_hosts`) builds the SDK's transport
   security for proxied deployments in both majors, keeping the SDK loopback entries so direct
   clients keep working. When absent the server warns and names the flag rather than refusing,
   because direct loopback clients still work.
4. Six file-writing tools are serialised behind one lock because 2.x runs synchronous handlers on
   worker threads; `configure_tool`'s local-config write is atomic. Three write-annotated tools need
   no lock: `schedule_post` returns a plan, `launch_setup` spawns a process, `submit_compute_job`
   writes one unique ticket through temp-plus-replace.
5. Guards must hash and assert only what is the same on every machine: the package manifest hashes
   tracked files, and the fcpxml selftest expects the level the installed tool can reach.

## What was deliberately left open, and why

- Python 3.13: Resolve caps at 3.12. `tools/library_complete.py`'s rglob envelope (3.13's pathlib
  swallows the OSError the check relies on) and `tools/videoedit/mediaprobe.py`'s audioop fallback
  (leaves the stdlib at 3.13) are the recorded 3.13 checklist.
- The Resolve ceiling itself is an on-disk README (`Developer/Scripting/README.txt`); re-reading it
  against a current Resolve build is a Mac step. If it has risen, `preflight.py` and the prose copies
  move together.
- Atomic writes inside `tools/obligations.py` and `tools/freshness_overlay.py`: their MCP callers are
  serialised here; making the writers atomic is their own change.
- `mcp-types` is never pinned independently (exact-pinned by mcp, per the SDK migration guide).
- `mcp-stats-compass` stays without a baseline (an MCP server, not importable-testable here).

## Alternatives considered

Docs-only correction (leaves the pin chain unguarded). Making the tool read the requirements and
evidence files (a second source of truth beside the registry). A hard cut to mcp 2.x (breaks every
existing `.venv`). Keeping the 3.11 floor (numpy 2.5 stays uninstallable). Recommending python@3.13
for runway (fails the Resolve gate on the documented path). Refusing to start without an allowed
host (would break direct loopback clients that were never affected).

## Consequences

A requirements pin edit without its registry mirror is a build failure. Fresh installs land on
mcp 2.x; existing 1.x venvs keep working until rebuilt. Proxied remote deployments must declare
their public hostname, and the runbook now says so. The battery runs under both 3.11 and 3.12 until
3.11 installs are gone. CI is green for the first time since 2026-08-16.
