# ADR 0066 — A claim about this repo's own behavior ships with its executed proof

- Status: accepted
- Date: 2026-09-21
- Phase: P94 (claim-proof pass)

## Context

P93 pushed three commits and reported them as done. Two headline claims were false, and the
guard built to enforce the third shared a blind spot with the work it was checking:

- the commit subject `P93-1: no code path installs machine-wide.` shipped in the same commit as
  `setup.py:138`, which still read `target = venv_py or PYTHON`. A machine-wide interpreter
  carrying no PEP 668 marker took all seven requirements sets, and the installer reported
  success;
- `docs/INSTALL-SCOPE.md` asserted that every remaining `brew install` in the guidance sat under
  a machine-wide label while three live files did not;
- drift invariant 59 was described as enforcing the policy across the guidance, but scanned a
  hardcoded sixteen-file list — exactly the set of files the phase had just edited, so the guard
  could only confirm work already done.

The mandated adversarial pass (`docs/AUDIT-PROTOCOL.md` section 7) caught all three. The
protocol worked. What failed was everything around it:

1. **Sequencing.** Section 7 attached verification to the word "closed", while section 8's
   persistence contract requires claims to be committed and pushed per stage and CLAUDE.md
   requires doc prose to land in the same change as the code. Doctrine mandated that claims be
   written and pushed at stage time and separately mandated they be checked at phase close. The
   false commit message, the false doc sentence, and the report to the owner all lived in that
   window.
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
   tested.** "no", "never", "every", "all", "only", "nothing", "always" in a commit subject, a
   doc sentence, a CHANGELOG entry or a report to the owner. Test the PROPERTY claimed, not the
   mechanism changed: P93 proved a refusal for PEP 668 interpreters and claimed it for every
   machine-wide one.
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
   than the path appearing anywhere in the file. This check's own red-team pass caught that
   weakness: mutating `USER_BIN` left the gate silent because the old path was still mentioned
   in a comment.
6. **The corpus is bounded and the sweep is reverse.** Guarding every absolute in the repo would
   mean annotating 2,846 lines across 417 files — an annotation project nobody maintains. The
   guarded corpus is CLAUDE.md's non-negotiables and `docs/INSTALL-SCOPE.md`, and the sweep
   fails when a universal claim *joins* that corpus bound to nothing, so the promise list cannot
   grow unproven.
7. **The coverage proof is shared, not hand-rolled.** `_coverage_proof()` asserts every detector
   branch has a fixture and every fixture fires its own branch, and is used by invariants 59 and
   60. All 22-plus coverage proofs in the repo were previously hand-rolled with no two sharing
   code.

## Consequences

- A promise in the non-negotiables cannot drift from its proof, lose its pin to a rename, or
  join the list unproven without failing the build.
- A recommended install route that the code stops being able to detect fails the build, which is
  the class that dead-ended the P93 setup path on a real Mac.
- The CI parity step now asserts what its name promises. Turning it on immediately found that CI
  was not running three battery gates; hash audit and source sync were added, and preflight push
  is declared with its reason.
- Exemptions are the honest residue: each one states why no code can prove that sentence, and a
  reviewer can argue with the reason.
- The claims rule binds reports to the owner, not only files. That part is doctrine, because no
  guard sees a chat message.
