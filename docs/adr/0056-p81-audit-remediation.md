# ADR 0056 — One writer, one floor, frozen records: closing the 24-hour audit

- Status: accepted
- Date: 2026-09-06
- Phase: P81 (remediation of the audit of P80)

## Context

A read-only audit of the six P80 commits found forty-nine deficiencies. Five were high severity: the
records misdated the CI history by four weeks and named one cause where there were two; the MCP
server answered 421 to every request on a non-loopback bind under the 1.x SDK because FastMCP freezes
its DNS-rebinding settings at construction for the default host; the skill packager zipped every file
on disk while the manifest hashed only tracked files; the launcher refused a 3.11 venv that the
interpreter picker then handed every tool to; and the setup guide still recommended Python 3.13 three
lines under `brew install python@3.12`. The forty-nine reduced to nine classes: proving the named path
and not its neighbours; editing a list of sites instead of sweeping after the edit; writing records from
intent rather than evidence; editing a dated record in place; trusting operator input without a shape
check; copying a pattern without its contract; weakening a validation to make a gate pass; bypassing a
process gate; and applying half of a data change.

## Decision

1. One atomic writer. `tools/atomic_io.py` is the only place a local-config, credential, or register
   file is written: same-directory temp, mode preserved, temp cleaned on failure, cross-process lock.
   Drift invariant 42 fails on any other `write_text` of such a path.
2. The 1.x non-loopback bind mirrors the SDK. When no allow-list is configured and the bind is not
   loopback, the server sets transport security to None under 1.x, which is what FastMCP itself does
   when constructed with that host. Operator input is validated with a reason per rejection; the live
   selftest asserts deny/pass outcomes, not object presence, in both SDK majors.
3. The packager and the manifest share one file set, and an un-added skill is refused rather than
   hashed as empty.
4. The interpreter floor is one constant, `env_paths.PYTHON_FLOOR`; the launcher probe embeds it, setup
   imports it, the interpreter picker enforces it, and invariant 48 sweeps prose against it.
5. Dated records are frozen above an `## Addendum` heading; the P79 record is restored and extended by
   an addendum instead of being edited.
6. Claims about CI cite `tools/ci_history.py` output; the P80 records are corrected through errata and
   a ledger field, not by rewriting history.
7. The gate is `tools/battery.py`: raw exit codes, refusal on unstaged tracked edits.

## What was deliberately left open, and why

- Python 3.13 (Resolve's scripting bridge caps at 3.12; the rglob and audioop items are the recorded
  3.13 checklist), and re-reading the Resolve ceiling itself on a Mac.
- Pinning mcp-types (exact-pinned by mcp) and a baseline for mcp-stats-compass.
- Refusing to start when no allowed host is configured; the server warns and names the flag instead.
- CI still lacks xmllint, so its FCPXML check stops at well-formedness; installing `libxml2-utils` in
  the workflow is a maintainer decision.
- The Windows launcher probe (no cmd.exe in this environment) and the first live `ci_history.py` run
  (api.github.com is proxy-blocked here) are verified on the maintainer's machines.
- `count_truth.py` as a CI step cannot fail (it prints); the comparison lives in invariant 48. Giving it
  a `--check` verb or removing the step is a follow-up; the step is renamed informational meanwhile.
- `dependency_currency.apply_stamps` ignores the `blocked` flag; a rate-limited entry can be stamped.
  Recorded for the next dependency pass, as is `tools/transcribe.py`'s use of `shutil.which` instead of
  `env_paths.which`.
- Tag and PR remain the maintainer's.

## Alternatives considered

Per-site fixes without a shared writer (would leave the next writer bare); asserting `transport_security
is not None` (passes a settings object with empty lists, which denies everything); hashing the zip
instead of the tree (mtimes make it non-reproducible); a new numbered invariant per sweep (the catalog
and every count sentence would move); editing the P79 record in place a second time (the failure being
fixed).

## Consequences

A bare writer of a token file, a stale floor in prose, a missing ADR row, a duplicate changelog heading,
an un-runnable evidence entry, an unstamped map, or an edited dated record is a build failure. The MCP
server behaves identically on both SDK majors for every bind class the selftest names. Records cite
commands. The Windows launcher probe and the live CI-history run are verified on the maintainer's
machines, not here.
