# ADR 0064 — Validated through Python 3.14; the floor stays 3.12 for the narrowest lane

- Status: accepted
- Date: 2026-09-20
- Phase: P91 (Python 3.14+ support pass)

## Context

The owner's Mac ships `python3` = 3.14.6 and the owner decided the repo formally supports
Python 3.14 and later. The floor was already a floor (`env_paths.PYTHON_FLOOR = (3, 12)`), so
3.14 passed every gate mechanically -- it had just never been validated. A validation pass on
CPython 3.14.0rc2 (the newest 3.14 the validation container could obtain) found the battery
already at 12 of 13 gates, all seven requirements files installing cleanly (including the
transcription and video lanes), and exactly one real regression class plus two environment
artifacts.

## Decisions

1. **The regression class: CPython 3.14 changed `Path.exists()`/`is_file()`/`is_dir()` to
   swallow errors such as ENAMETOOLONG that 3.12 raised.** Four boundary guards (tasks
   register load, obligations scan payload, the takeout import parser, the seed-sources path)
   relied on the raise to convert an UNPROBEABLE path into their documented clean error
   envelopes; under 3.14 they silently returned empty results instead -- the exact failure
   mode the P64/P66 doctrine ("an unprobeable path is unreadable, not empty") exists to
   prevent. Each boundary now probes through a version-proof `_probe_exists` helper
   (`stat()`; absent reads False; unprobeable raises) whose behavior is identical on every
   supported interpreter. The four pre-existing selftest pins are the detector proof: they
   failed under unfixed 3.14 and pass after, while still passing under 3.12/3.13.
2. **Selftests skip-with-reason what an interpreter BUILD cannot prove; they never silently
   pass it.** The standalone 3.14 rc build in the container has a broken `ensurepip` and
   creates venvs whose own python cannot execute. The setup selftest now prints a note and
   skips the pip and venv-resolvability checks in exactly that situation -- detectable
   because the venv's python fails to run at all, which also means `env_paths` refusing the
   venv is its documented correct behavior (P81 B-5), not a resolver regression. A real
   resolver regression still fails loudly.
3. **The floor stays (3, 12).** Support was added upward, not removed downward: DaVinci
   Resolve's scripting bridge vendor-caps at 3.12 (ADR 0055's constraint is unchanged), so
   the Resolve live-control lane is documented as 3.12-only while everything else runs 3.12
   through 3.14+.
4. **CI pins the two ends of the validated range** (a guard-job matrix on 3.12 and 3.14; 3.13
   stays covered by the local battery convention). The scheduled competitor-intel job is a
   crawler, not a validation gate, and stays on 3.12.
5. **The honest residue**: the mcp SDK could not be import-tested on 3.14 in the container --
   pydantic 2.13.5 targets a `typing._eval_type` keyword that CPython added after rc2, so the
   crash is an rc2-vs-final artifact, expected green on 3.14 finals. Tagged in SETUP_MAC with
   the closing acceptance run (setup + battery + the wizard's install-and-verify on a real
   3.14 Mac); never asserted.

## Consequences

`battery: PASS (13 of 13 gates)` under 3.12, 3.13, and 3.14 in the validation container. A
Mac whose `python3` is 3.14 runs Creator OS without installing anything older, except for the
Resolve live-control lane. 3.15 and later enter the validated set through the same mechanism
when they exist: run the battery under the new interpreter, fix what it finds, extend the CI
matrix.
