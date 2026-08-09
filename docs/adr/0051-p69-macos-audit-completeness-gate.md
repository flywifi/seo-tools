# ADR 0051 — The macOS audit closes with a derived completeness gate, not a signed-off list

- Status: accepted
- Date: 2026-08-09
- Phase: P69 (final adversarial macOS audit)

## Context

Creator OS carries a large macOS surface: the double-click launcher, PATH and venv handling,
Gatekeeper and quarantine copy, TCC, Homebrew, the python.org installer, whisper.cpp and Metal
backend selection, the Claude Desktop MCP config, the Drive-for-desktop mirror, and the
Compressor/Resolve/CommandPost/FCP probes. All of it has only ever been simulated or AST-checked
from Linux, and every Apple, Homebrew, python.org, and whisper source backing it sat at
`last_checked: null`.

Two prior audits (P53, P56) produced hands-on macOS checklists that lived only in session
scratchpad and are now gone. That is the failure mode this ADR addresses: a macOS audit's coverage
claim has never survived the session that produced it. Worse, even a committed findings document
decays immediately, because nothing prevents a new file carrying macOS behavior from landing next
week and never being audited, and nothing prevents an audited file from being rewritten after the
audit signed off on it.

`docs/AUDIT-PROTOCOL.md` section 1 already requires coverage sets to be derived rather than
recalled, and section 5 requires a closing unexercised list. Neither was mechanically enforced for
the macOS surface.

## Decision

The audit closes with a build-enforced gate rather than a document.

1. **The audited set is derived, never memorized.** `tools/mac_surface_manifest.py::derive()`
   sweeps every tracked text file for a macOS signal token set. The denominator is recomputed on
   every run, so it cannot silently fall behind the tree.
2. **Every derived match must carry an explicit decision.** It is either in
   `canonical-sources/mac-surface-manifest.json` under `files`, recorded at the sha256 it was
   audited at, or under `excluded` with a written reason. This mirrors the invariant 46 provenance
   pattern (registry, sidecar, or excluded-by-rule).
3. **Drift invariant 58 enforces both directions and fails closed.** Coverage: a derived match in
   neither map is reported as an unaudited macOS surface. Integrity: an audited file whose bytes
   moved is reported as changed. Either fails the build until a human re-audits and re-blesses.
   Outside a git checkout the guard reports DID-NOT-RUN loudly rather than passing silently, the
   same posture as invariants 19 to 21.
4. **The signal set is tuned against known false positives.** The raw sweep over-matched roughly a
   hundred files on the injection-risk constant `QUARANTINE` and on argparse's `args.command`, so
   neither bare spelling is a signal; `com.apple.quarantine` is. A small `SKIP_PREFIXES` list
   covers append-only history files and the two files whose macOS tokens are the guard machinery
   quoting itself.

## Alternatives considered

- **A one-shot audit script run at close-out.** Rejected: the guarantee decays with the next
  commit, which is precisely the failure this phase exists to fix.
- **A hand-maintained list of macOS files in the manifest.** Rejected: a memorized denominator is
  what AUDIT-PROTOCOL section 1 forbids, and the derivation immediately proved why. An early
  version of the signal set matched only the hyphenated `whisper-cpp` and therefore missed
  `canonical-sources/whisper-models.json`, which spells it `whisper.cpp`. A hand-written list would
  have inherited the same blind spot invisibly.
- **Binding the gate to the doc-freshness manifest.** Rejected: doc-freshness is advisory and
  answers "is this prose stale", not "was this surface ever audited". Coverage needs a hard failure.

## Consequences

- Editing any of the 71 audited macOS files now requires re-blessing the manifest
  (`python3 tools/mac_surface_manifest.py reconcile`). That friction is the point: it forces a
  human decision at exactly the moment a macOS surface changes.
- Adding a file that mentions macOS incidentally will trip the gate once, and is resolved by either
  auditing it or excluding it with a reason. The exclusion map keeps that decision written down.
- The audit's fresh-fetch pass is recorded in the registry stamps rather than in prose, so the next
  re-verification starts from real dates instead of `null`.
- Behaviors that need real Mac hardware (the Gatekeeper dialog, the TCC prompt, Rosetta, live
  post-2026-09-01 Homebrew behavior, a real Desktop MCP spawn, Drive mirror latency) remain
  unexercised and are listed as such in `docs/MAC-VALIDATION.md`. The gate proves the surface was
  reviewed against vendor documentation; it does not claim the surface was run.
