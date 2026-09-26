# The audit protocol (P64)

How to run a full Creator OS audit so that its COVERAGE is accounted for, not just its findings.
An audit that improvises its scope from memory and measures itself by checks passed has a
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
never reported as exercised. An auditor running in a Cowork-class remote sandbox is itself on one
of the rows; treating one's own runtime as an edge case inverts the real usage distribution.

## 4. Harness honesty (a defect is not a defect until re-verified)

Before recording a finding, re-verify it is not an artifact of the audit harness itself: the
wrong function under test, a wrong argument shape, a stale line anchor, an output key the harness
misspelled. Typical harness artifacts: a wrong function signature, a `| tail` pipe masking an
exit code, a legacy probe, a wrong argument shape, a nested output key. Each is investigated and
reclassified with a written rationale instead of shipping as a defect. Record reclassified non-defects in the notes
with their rationale; they are evidence of discipline, not noise.

## 5. The mandatory closing step: the unexercised list

An audit deliverable ENDS with a section named "Not exercised", listing every §1 surface, every
§1 origin, and every §2 input class the audit did not exercise, each with a reason. An audit
without this section is incomplete by definition — no matter how many checks passed. This is the
step that converts a PASS count from a numerator into a coverage statement: an origin nobody
exercised appears on the list by name ("origin `cowork`: not exercised").

The committed home for the Mac hands-on unexercised list is `docs/MAC-VALIDATION.md` — a local-only,
two-phase runbook with a results-log template in this same shape. Its closing "Not exercised" line
records the deferred real-account tiers (OAuth/publishing, Drive hub, remote-MCP connector) so a
green local pass reads as coverage, not a bare pass.

## 6. Deliverable shape (resumable by a cold session)

An audit's notes carry, in order:

1. A remediation-ready summary index FIRST (finding ids, one-line each, severity).
2. Per finding: exact `file:line`, the reproduction (command + observed vs expected), severity,
   and status (confirmed / reclassified-artifact / needs-follow-up).
3. The PASS ledger (what ran clean, so the next audit does not redo it blindly).
4. The §5 unexercised list.
5. **Audit records stay outside the repository.** The notes, findings, verdicts and change
   ledger live in the working plan outside the repository (section 8) and are reported to the
   owner. What lands in the repository is the change itself: the fix, its docs, an ADR when a
   design decision was made, and the `CHANGELOG.md`, `STATE.md` and `ledger/ledger.json`
   entries, each describing behaviour rather than the audit that led to it.

## 7. Independent adversarial close-out (claims checked against code, not prose) — P68

Sections 1 to 6 give an audit a machine-checked denominator and an honest unexercised list, and
section 4 makes the auditor re-verify a finding against the harness. What they do not require is a
check of the phase's own claims against **ground-truth code**, by a reader who did not write
them. Eval assertions authored from SKILL.md *prose*, and a fail-safe reasoned about only through
its documented entry point rather than the full argv surface, pass a green battery and a
self-review alike. Therefore:

- A phase is not "closed" until an **independent** pass — a fresh-context subagent, or a distinct
  reading that deliberately does not trust the phase's prose — re-derives each material claim from
  the authoritative artifact: the tool's actual `return {...}` for an output-shape claim, the real
  argv/branch behavior for an entry-point claim, the emitted keys for an eval assertion. "The docs
  say X" is never the evidence; "the code does X, read here" is.
- Every guard or fail-safe a phase adds must ship with a **red-team proof**: run it against the
  pre-change tree and show it FAILS on the exact defect it targets, then against the fixed tree and
  show it passes. A guard never shown catching its own target is unverified code.
- This composes with the existing close-out discipline recorded in the ledger — "a proof that
  fails on the pre-change tree, the full battery green after, docs changed in the same commit" —
  and with the runtime analog already in `CLAUDE.md` (every workflow's adversarial verification
  step) and `shared/schemas/verification-envelope.json`. The difference is that section 7 applies
  it to the phase close-out itself, not only to research workflows.

### 7.1 When the pass runs (P94)

The three clauses above say what the independent pass must do; this section says *when*.
Section 8's persistence contract has fixes "committed and pushed per stage", and `CLAUDE.md`'s
documentation-truth rule has doc prose land in the same change as the code, so a claim is written
and pushed at stage time. A pass attached only to the word "closed" checks claims after they have
shipped.

- **The independent pass runs BEFORE the claim is reported or merged**, not only at phase close.
  A universal claim that has not survived it is reported narrowed to what was actually tested,
  or not made. Reporting "X is closed everywhere" on the strength of having tested one case is
  the failure this clause exists to stop.
- **A guard's denominator is DERIVED, never recalled.** Section 1 already says this about an
  audit's coverage sets; it binds a new guard's scan set too. A hand-maintained list of files
  to check is the alternative `docs/adr/0051` already rejected for invariant 58 ("a memorized
  denominator"): a scan list made of the files a change touched mostly confirms work already
  done. If a list is
  genuinely unavoidable, every entry carries a written reason, and the exemption map is the
  list, not the scan set.
- **Remediation that touches the same guard earns a second pass.** A remediation can trade one
  defect for another, and a fix authored by the same reader who found the defect is not
  independently verified.
- **A pass reads one pinned commit.** Every agent in a pass reads the same commit and reports
  the SHA it read (`tools/tree_pin.py`); findings from agents that read different trees are
  not merged into one verdict.
- **A commit pushed before the pass returns states the mechanism changed, not the property.**
  Its subject names what the change does ("refuse the install when no .venv exists"), not the
  property the pass has yet to verify ("nothing installs machine-wide"); `tools/commit_claims.py`
  checks the subject.

### 7.2 When the pass is finished (P95)

Section 7.1 says the independent pass runs before a claim is reported. This section says when the
pass is FINISHED: starting a pass is not finishing it, and a pass that could not run did not
pass.

- **A pass is complete when its verification stage has returned.** A lens finding is REPORTED;
  only the refutation round moves it to VERIFIED or KILLED, which is the status ladder section 8
  item 4 already defines. A claim about what a pass found, or about a fix that closes what it
  found, waits for that round. Reporting off first-stage output is reporting an unverified claim.
- **A pass that could not run is DID NOT RUN, never clean.** A zero from a checker whose agents
  never executed is the same defect as a guard that scans nothing, and it takes the same
  treatment the drift guard gives a non-git copy: report DID NOT RUN to the owner, name what went
  unchecked, and do not let it read as a pass. `CLAUDE.md` already says "never claim a skipped
  step ran"; a pass whose agents did not execute is a skipped step.
- **The adversarial vectors are not chosen by the author.** Mutations the author
  picks confirm the fix the author meant, which is the shape section 7.1 forbids for a guard's
  scan set, applied to its test set. Only vectors the reviewer picks test whether the fix does
  what it claims (a function merely NAMED like a selftest, a tautology written as a comparison,
  a disabled CI step).
- **Report an involuntarily incomplete pass as incomplete.** Section 8 item 6's non-action list
  and the ledger's `explicit_non_action` field both cover what a phase *chose* not to do. A pass
  that stopped partway is not a choice: report it to the owner as incomplete, name what it did not
  cover, and narrow the claim to what was verified firsthand.

```sources
[]
```

## 8. Plan structure (what section 6 item 5 refers to)

A working plan for audit remediation is a single file, kept outside the repository, that is
simultaneously the plan and the record. It carries:

1. **A resume protocol, first.** Where the work is (repo, branch, HEAD at plan time), what the
   task is in two sentences, and the exact first commands a session with zero memory should run.
   State explicitly that the ledger outranks any recollection, and that git outranks the ledger:
   if a row disagrees with the tree, trust the tree and fix the row.
2. **A persistence contract.** What is written where, and when. Findings are written to the plan the
   moment they are confirmed, never batched to the end. Fixes are committed and pushed per stage,
   so an interruption loses at most one stage. The plan and its ledger live outside the
   repository, somewhere that survives the machine; their conclusions reach the owner in a
   report, and the repository receives only the changes (section 6 item 5).
3. **The baseline battery**, with the numbers expected at the start, so a later session can tell a
   regression from a pre-existing state.
4. **A change ledger** (part of the plan, so never committed): an append-only table of findings, one row each, carrying an id, the
   dimension, a severity, the claim with its `file:line`, and a status that moves through
   REPORTED to VERIFIED or KILLED, then FIXED at a commit, then REPLAYED where a guard was
   touched. Strike rows through; never delete them. A killed finding keeps the reproduction
   attempt that killed it.
5. **Remediation rules chosen before the findings arrive**, so severity does not get negotiated
   after the fact: what must be fixed in the same checkpoint, what may be accepted with a written
   reason, and the scope brake that turns a rebuild into a recommendation.
6. **An explicit non-action list.** What the phase deliberately did not do, and why. This is the
   field that is most often lost and least reconstructible from a diff.

The ledger rows and the non-action list are what later phases actually read. A plan that records
only the intended work, and not what happened to each finding, is a to-do list rather than a
change ledger.
