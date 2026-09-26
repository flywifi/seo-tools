# ADR 0066 — A claim about this repo's own behavior ships with its executed proof

- Status: accepted
- Date: 2026-09-21
- Phase: P94 (claim-proof pass)

## Context

P93 pushed three commits. Two headline claims were false, and the
guard built to enforce the third shared a blind spot with the work it was checking:

- the commit subject `P93-1: no code path installs machine-wide.` shipped in the same commit as
  `setup.py:138`, which still read `target = venv_py or PYTHON`. A machine-wide interpreter
  carrying no PEP 668 marker took all seven requirements sets, and the installer reported
  success;
- `docs/INSTALL-SCOPE.md` asserted that every remaining `brew install` in the guidance sat under
  a machine-wide label while three live files did not;
- drift invariant 59 was described as enforcing the policy across the guidance, but scanned a
  hardcoded sixteen-file list, almost all of them files the phase had just edited, so the guard
  largely confirmed work already done.

Three gaps let them ship:

1. **Sequencing.** Section 7 attached verification to the word "closed", while section 8's
   persistence contract requires claims to be committed and pushed per stage and CLAUDE.md
   requires doc prose to land in the same change as the code. Doctrine mandated that claims be
   written and pushed at stage time and separately mandated they be checked at phase close. The
   false commit message and the false doc sentence both lived in that window.
2. **Scope.** No protocol governed a claim about this repo's own behavior. `no-fabrication.md`
   is scoped to creator data, `quality-gates.md` to creator artifacts, `COMPLETENESS-CONTRACT.md`
   to chat surfaces. CLAUDE.md set the "executed and shown to pass" bar on a *plan*, never on a
   report. "Documentation truth" was defined as paths, symbols, counts, URLs and hashes — a
   universal sentence names none of those, so by the model's own definition it was never checked.
3. **A rule already on the books was broken.** `AUDIT-PROTOCOL.md` section 1 requires coverage
   sets to be derived, never recalled, and ADR 0051 explicitly rejected "a hand-maintained
   list… a memorized denominator" for invariant 58 — one invariant earlier, for the same reason.

This is not a single incident. `ledger/ledger.json` already records seven stale selftest
pass-counts drifting across six finance atom docs with nothing catching them.

## Decisions

1. **A universal claim about repo behavior names its executed proof, or is narrowed to what was
   tested.** "no", "never", "every", "all", "only", "nothing", "always", "none", "cannot" (the
   last two and bare "no" detected since P95) in a commit subject, a doc sentence, a CHANGELOG
   entry or a report to the owner. Test the PROPERTY claimed, not the
   mechanism changed.
2. **The independent pass runs before the claim is reported or merged** (`AUDIT-PROTOCOL.md`
   section 7.1), not only at phase close, closing the seam between when a claim is written and
   when it is checked.
3. **A guard's denominator is derived, never recalled** — now written as a precondition for
   shipping a guard rather than a lesson the repo learns once per invariant. Remediation that
   touches the same guard earns a second pass (the P70 case, previously unwritten).
4. **Proofs are named and executed, not gestured at.** `tools/claim-proof-manifest.json` binds
   each promise to either an enforced drift invariant (`invariant:N`, resolved by AST against
   the checks actually registered in `main()`) or a named selftest pin
   (`tools/x.py::selftest::<label>`, resolved by AST and required to live in a module
   `selftest_sweep.discover()` actually runs). A universal that no code can prove — a standing
   instruction to the agent — is recorded as an exemption with a written reason, because
   "nothing proves this" should be a deliberate act rather than a silence.
5. **A route we recommend must be a route we can find.** Route records bind an install route the
   docs recommend to the code that detects it, resolved through the prober's *symbol* rather
   than the path appearing anywhere in the file. A text match is too weak: after `USER_BIN`
   moves, the old path left in a comment would keep the gate silent.
6. **The corpus is bounded and the sweep is reverse.** Guarding every absolute in the repo would
   mean annotating 2,846 lines across 417 files — an annotation project nobody maintains. The
   guarded corpus is CLAUDE.md's non-negotiables and `docs/INSTALL-SCOPE.md`, and the sweep
   fails when a universal claim *joins* that corpus bound to nothing, so the promise list cannot
   grow unproven.
7. **The coverage proof is shared, and the branch set is pinned.** `_coverage_proof()` asserts
   every detector branch has a fixture and every fixture fires its own branch, and is used by
   invariants 59 and 60. Fixture agreement alone only catches a half delete, so the branch names
   are also recorded in the manifest: removing a branch together with its fixture still fails.
   All 22-plus coverage proofs in the repo were previously hand-rolled with no two sharing code.

8. **The reverse sweep matches claim units, a pin must be reachable, and an escape clause is
   surfaced.** The sweep subtracts each bound claim from its unit and rescans the remainder, so a
   universal claim appended to an already-bound bullet is checked on its own; eleven universals
   that whole-unit matching had absorbed are now accounted for. A selftest pin whose condition is
   a literal does not resolve as a proof, and a pin label parked in a function nothing calls does
   not resolve either (a label is a comment, not a proof, so a pin must be REACHABLE from the
   selftest entry). The CI parity check reads steps rather than raw file text, so a commented-out
   step does not count as coverage. A bound promise reversed by an "except when..." clause
   containing no universal word is caught: an undeclared escape hatch beside a bound promise
   fails on its own, and a declared "unless" elsewhere in the file does not switch the check off.

9. **P95: a pin must be able to fail, and the detector must see the words the docs advertise.**
   P94's reachability rule was incomplete: a
   `selftest_park` counted as an entry by name prefix, an unrelated attribute call made a
   same-named function reachable, and `ok(1 == 1, label)` passed because only a bare literal was
   refused. P95 added three static refusal rules: (a) the call must be on the live call path
   from `selftest`/`_selftest` or a selftest-named function the CLI calls, following uses by
   name and skipping uncalled nested defs and dead `if` branches; (b) the helper it calls must
   be defined in the module and test its condition; and (c) that condition's truth must not be
   fixed. A literal, a local constant, a tuple, `x == x` and `x or True` are refused; a
   known-false condition counts, because `ok(False, label)` after a call that must raise is a
   real should-not-reach assertion; a MODULE-level constant counts, because it is the code under
   test. Measured over all 91 swept modules before shipping: no previously accepted label is
   refused, and 80 more became visible (71 in mcp_server's module-level `_selftest_static`, 9
   should-not-reach pins elsewhere). A fixture module in the drift guard exercises eleven of the
   rules, and reverting any one of those fails the build. Nine
   further rules have no fixture, and some pins that cannot fail are still accepted
   (`ok(x or not x, ...)`, a helper rebound to `print`, a pin under `while False:`).

   The trigger vocabulary did not match its own documentation. CLAUDE.md advertised "repo-wide"
   (no sentence in the guarded corpus used it; its one occurrence was the list itself) and a bare "no" the code could not see,
   and did not mention "only", "nothing" and "always", which it enforced. Bare "no", "none" and
   "cannot" are now branches, and `no ... ever` tolerates punctuation ("no sudo, ever"). The
   bare-"no" pattern misses a past-participle predicate ("No real CRM data or PII committed to
   the repo", already bound verbatim) and other in-vocabulary forms ("There is no fallback to
   the base interpreter"), and it flags "no admin rights needed". It must follow `no_ever`:
   listed before it, it claims "no ... ever" sentences from their own branch and the coverage
   proof fails. The five universals it
   surfaced were resolved on their merits: two bound (one to a new recording-client pin that
   observes zero platform calls with the flag off, one to the existing no-.venv refusal pin) and
   three exempted with reasons. Invariant 53 now asserts `default_flag` on every connector entry;
   before, it only executed a resolver that reads the field with a fallback, so the binding was
   false.

   Residuals, named rather than claimed closed: reachability is static, so a call under a branch
   that is not provably dead still counts; a helper that tests its condition but throws the
   result away still counts; a pin can pass while testing a different property than the claim
   (semantic, and the reviewer's job); and a bound promise reversed by a clause with no marker
   word at all ("..., and ALLOW_SYSTEM installs into the shared site-packages") is invisible to
   the escape check, which now also knows "except where", "with the exception of", "provided
   that" and "save for".

10. **P95: parity reads what CI enforces, and an exemption must still do work.** A gate is
    meant to count only when a blocking step runs exactly its command as the whole step; in the
    forms the line parser reads, a disabled, advisory, conditional or wrong-subcommand step does
    not, and a parity note whose gate CI runs directly fails as stale. Invariant 59's exemption map had no staleness check: five of thirteen entries
    exempted nothing and are dropped, and an entry that exempts nothing now fails the build (the
    selftest-enrolment rule "is BOTH exempt and covered; drop the stale exemption", applied to
    the map that narrows invariant 59's denominator). An over-broad entry still passes, and the
    parity parser misses several valid YAML forms; both are open.

## Consequences

- A promise in the non-negotiables cannot drift from its proof, lose its pin to a rename, or
  join the list unproven without failing the build.
- A recommended install route that the code stops being able to detect fails the build, which is
  the class that dead-ended the P93 setup path on a real Mac.
- The CI parity step now asserts what its name promises. CI runs the hash audit
  and source sync gates, and preflight push is declared with its reason.
- Exemptions are the honest residue: each one states why no code can prove that sentence, and a
  reviewer can argue with the reason.
- The claims rule binds reports, not only files. That part is doctrine, because no guard reads
  a report.
