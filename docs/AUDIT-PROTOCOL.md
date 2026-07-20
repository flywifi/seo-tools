# The audit protocol (P64)

How to run a full Creator OS audit so that its COVERAGE is accounted for, not just its findings.
This document exists because two real defects (the missing Cowork surface and the ENAMETOOLONG
traceback class) survived multiple otherwise-thorough audits — not because the audits were sloppy,
but because each one improvised its scope from memory and measured itself by checks-passed, a
numerator with no denominator. Every section below closes one of the root causes recorded in ADR
0047. `docs/PERSONA-AUDIT.md` remains the dedicated protocol for the wizard's GET screens; this
document governs everything else.

## 1. The canonical coverage sets (never enumerate from memory)

An audit's surface list and origin list are DERIVED, never recalled:

- **The surface set IS the ids in `shared/cross-modality/transitions.json`** (eleven surfaces as
  of P64, including `cowork_local` and `cowork_remote`). Drift invariant 32 keeps the json, its
  constant, `docs/TRANSITIONS.md`, and the wizard consistent.
- **The origin set IS `ALLOWED_ORIGINS` in `tools/handoff/queue.py`**
  <!-- verify: tools/handoff/queue.py::ALLOWED_ORIGINS -->, which drift invariant 55
  (`check_surface_origin_completeness` <!-- verify: tools/sync_check.py::check_surface_origin_completeness -->)
  keeps identical to the `shared/schemas/compute-job.json` origin enum and fully claimed by the
  surface model.

The failure this kills: enumerating "the surfaces" from the artifact under test (or from memory)
makes the model's blind spot the audit's blind spot. The two sets above come from artifacts built
for different purposes by different phases, and invariant 55 reconciles them on every build — so
an audit that starts here inherits a machine-checked denominator. If a coverage question is not
answered by these sets, the model is incomplete: fix the MODEL first (a new surface row, a new
origin claim), then audit.

## 2. Input-boundary classes (every CLI exercised gets all of them)

A selftest input that never crosses a boundary cannot find a boundary bug: the ENAMETOOLONG class
was invisible to every short-argument test because `Path.exists()` only raises past NAME_MAX
(255 bytes per path component). Minimum input classes for every CLI an audit exercises — and for
every path-taking CLI's own selftest (the convention `tools/injection_scan.py` established and
invariant 54's whole-path layer now backs for finance/obligations):

1. **Realistic** — a well-formed input the tool is designed for.
2. **Malformed / inline** — a short bad path, inline JSON where a path is expected, wrong shape.
3. **Oversize path (>NAME_MAX)** — a >255-byte argument; must yield the tool's clean error
   envelope, never a raw OSError traceback.
4. **Binary sniff + oversize content** — where the tool reads file contents (the
   `injection_scan.py` precedent: skipped honestly, never guessed at).

A clean pass on classes 1 and 2 alone is NOT a robustness claim; the audit notes must say which
classes ran per tool.

## 3. Per-surface empathy legs (the auditor's own runtime is not a footnote)

Walk the user journey per surface, from setup to deliverable, with the surface set from §1 as the
row list — including both Cowork rows. The pinned scenario suite executes the load-bearing Cowork
model facts on every run (the S10 `cowork-surface-model` leg), so the model cannot silently drift
from what this walkthrough assumes. Honesty rule: legs that this sandbox can only simulate (real
Gatekeeper dialogs, a live Cowork session, real OAuth consent screens) are labeled
`[not exercised on the real surface]` in the notes and land on the hands-on checklist — they are
never reported as exercised. The special trap this section exists for: the auditor itself runs in
a Cowork-class remote sandbox; treating one's own runtime as an edge case inverts the real usage
distribution.

## 4. Harness honesty (a defect is not a defect until re-verified)

Before recording a finding, re-verify it is not an artifact of the audit harness itself: the
wrong function under test, a wrong argument shape, a stale line anchor, an output key the harness
misspelled. The 2026-07-18 sweep produced five such artifacts (a wrong `fetch_retention`
signature, a `| tail` pipe masking an exit code, a legacy three-flag probe, a wrong
`project_docs.check` argument, a nested output key) — each was investigated and reclassified with
a written rationale instead of shipping as a defect. Record reclassified non-defects in the notes
with their rationale; they are evidence of discipline, not noise.

## 5. The mandatory closing step: the unexercised list

An audit deliverable ENDS with a section named "Not exercised", listing every §1 surface, every
§1 origin, and every §2 input class the audit did not exercise, each with a reason. An audit
without this section is incomplete by definition — no matter how many checks passed. This is the
step that converts "117 PASS" from a numerator into a coverage statement, and it is the step
that would have surfaced the Cowork gap on its own: an honest closing list on 2026-07-18 would
have had to say "origin `cowork`: not exercised".

## 6. Deliverable shape (resumable by a cold session)

The notes format proven by `scratchpad/mac-sweep-2026-07-18.md` and
`scratchpad/mac-audit-final-2026-07-18.md`:

1. A remediation-ready summary index FIRST (finding ids, one-line each, severity).
2. Per finding: exact `file:line`, the reproduction (command + observed vs expected), severity,
   and status (confirmed / reclassified-artifact / needs-follow-up).
3. The PASS ledger (what ran clean, so the next audit does not redo it blindly).
4. The §5 unexercised list.
5. Notes live in the scratchpad, never committed; findings that become work get a plan with the
   repo's resume-protocol + change-ledger structure.

## 7. Independent adversarial close-out (claims checked against code, not prose) — P68

Sections 1 to 6 give an audit a machine-checked denominator and an honest unexercised list, and
section 4 makes the auditor re-verify a finding against the harness. What they did NOT require is
the step that would have caught the P67 defects: a check of the phase's own claims against
**ground-truth code**, by a reader who did not write them. The P67-D eval cases asserted output
keys authored from SKILL.md *prose* (`coverage_summary`, `billable_milestones`, `nudge_date`), and
the same-author close-out re-confirmed them against the same mental model; the P67-B auth fail-safe
was reasoned about only through its documented entry point (`--serve-remote`), not the full argv
surface. A green battery and a self-review passed both. Therefore:

- A phase is not "closed" until an **independent** pass — a fresh-context subagent, or a distinct
  reading that deliberately does not trust the phase's prose — re-derives each material claim from
  the authoritative artifact: the tool's actual `return {...}` for an output-shape claim, the real
  argv/branch behavior for an entry-point claim, the emitted keys for an eval assertion. "The docs
  say X" is never the evidence; "the code does X, read here" is.
- Every guard or fail-safe a phase adds must ship with a **red-team proof**: run it against the
  pre-change tree and show it FAILS on the exact defect it targets, then against the fixed tree and
  show it passes. A guard never shown catching its own target is unverified code (the P67-B gated
  path shipped with a "covered by selftest" claim that covered only the pieces that could run).
- This composes with the existing close-out discipline recorded in the ledger — "a proof that
  fails on the pre-change tree, the full battery green after, docs changed in the same commit" —
  and with the runtime analog already in `CLAUDE.md` (every workflow's adversarial verification
  step) and `shared/schemas/verification-envelope.json`. The difference is that section 7 applies
  it to the phase close-out itself, not only to research workflows.

```sources
[]
```
