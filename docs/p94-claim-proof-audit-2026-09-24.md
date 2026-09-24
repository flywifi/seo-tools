# P94 claim-proof audit: triage and P95 remediation (2026-09-24)

Dated record, append-only (`docs/*-audit-*.md` is frozen by `tools/doc_freshness.py`). Later facts
go in an `## Addendum <date>` section at the end.

## What was audited

P94 (commits `2084e22` to `9505678`) shipped drift invariant 60 (claim-proof binding), the shared
`_coverage_proof()` helper, and `tools/battery.py --check-parity`. Its mandated pre-report pass
(`docs/AUDIT-PROTOCOL.md` section 7.1) ran four lenses (guard soundness, claim versus code,
regression, completeness) with one adversarial verifier per finding. The run's journal is the
source for every count below.

| Stage | Count |
|---|---|
| Findings REPORTED by the four lenses | 29 (6, 11, 5, 7) |
| VERIFIED (verifier could not refute) | 20 |
| KILLED (verifier refuted) | 9 |
| Distinct issues after deduplicating the 20 | 13 (I1 to I13) |

**The audited tree moved during the audit.** The lenses read `ff28d35`; the verifiers read
`007e235` (P94-4), and one verifier recorded the main loop editing `tools/sync_check.py` mid-run
and discarded its first result for that reason. Six of the nine KILLED findings (#22, #23, #24,
#26, #27, #28) were killed because P94-4 had already fixed them, so KILLED there means "fixed
before verification", not "never real". The other three were judged not defects: #6 (scoped out,
see Residuals), #17 (no shipped sentence overstates the scope) and #21 (wording; see N2).
Auditing a moving tree is a process gap; see Follow-ups.

## The 13 verified issues, with verdicts after P95

FIXED means fixed and checked by the author's own harnesses. Under section 7.2 none of it is
independently verified until the independent pass on P95 returns its verification stage; that
outcome goes in an addendum. The three P94-4 fixes the audit's own verifiers confirmed are marked.

| # | Issue | Audit findings | Verdict | Evidence |
|---|---|---|---|---|
| I1 | A selftest proof can be faked | #1 | FIXED in P95-2 (`3e6c246`) | Re-running the audit's vectors against P94-5 showed three still open: a `selftest_park` counted as an entry by name prefix, an attribute call made a same-named function reachable, and `ok(1 == 1, label)` passed. A pin now needs the live call path, a module-defined helper that tests its condition, and a condition that depends on computed state. 35 vectors behave as required; a fixture module in the drift guard exercises each rule; 11 single-rule reversions each fail the build |
| I2 | An escape clause reverses a bound promise | #2 | PARTLY FIXED | `_CLAIM_ESCAPE_RE` gains "except where", "with the exception of", "provided that", "save for" and related forms; each fails the guard beside a bound promise (P95-2 matrix). A reversal carrying no marker word stays open (Residuals) |
| I3 | The reverse sweep whitelists a whole claim unit | #7, #18 | FIXED (P94-4, then P95-2) | Subtract-and-rescan since P94-4 (that fix confirmed by the audit's own verifier on #23). P95-2 found a second form of the hole in its own work: a binding subtracted EVERY occurrence of its text, so the short phrase P95 bound ("makes no network call") whitelisted any later sentence repeating it. Each binding now covers one occurrence, consumed in document order |
| I4 | `--check-parity` is a substring test | #3, #12, #20, #25 | FIXED in P95-3 | A gate counts only when a BLOCKING step (no `if:` on it or its job beyond always()/success(), no continue-on-error) runs exactly the gate's command as its whole step. 14 vectors (`if: false`, `if: ${{ false }}`, job-level `if:` and continue-on-error, `reconcile` for `check`, `|| true`, a commented step, a `set +e` block, a dropped flag, a stale note) behave as required; 8 single-rule reversions each fail `battery.py --selftest` |
| I5 | The launcher parity note described a step that did not exist | #19 | FIXED (P94-4) | Note removed; the real step is `.github/workflows/ci.yml:31` (`bash -n 'Start Creator OS Setup.command'`) |
| I6 | The detector lacks its documented trigger words | #4, #8 | FIXED in P95-2 | Bare "no", "none", "cannot" added, and `no ... ever` tolerates punctuation. "repo-wide" (zero corpus occurrences) removed from CLAUDE.md; "only", "nothing", "always" now advertised. CLAUDE.md, AGENTS.md, ADR 0066 and the check's docstring list the same words. The five universals the new branches surfaced: two bound, three exempted with reasons |
| I7 | The coverage proof allows symmetric narrowing | #5, #14 | FIXED (P94-4) | `detector_branches` pin in the manifest; the P95-2 matrix vector "branch AND fixture removed" fails the build |
| I8 | `invariant:42` credited with failing the build | #9 | FIXED (P94-4) | No `invariant:42` proof remains in `tools/claim-proof-manifest.json` (grep count 0); the claim is an exemption with a reason. Fix confirmed by the audit's own verifier on #27 |
| I9 | Traversal single-writer bound to invariant 42 | #10 | FIXED (P94-4) | Exempted with the reason that no guard inspects the traversal stores. Fix confirmed by the audit's own verifier on #26 |
| I10 | `default_flag` bound to invariant 53 | #11 | FIXED in P95-2 | Invariant 53 now asserts `default_flag` on every connectors.json entry; the matrix vector that deletes one fails the build. The resolver's comment crediting invariant 53 is now true |
| I11 | The claims-rule self-exemption covered a 1272-character bullet | #13 | FIXED (P94-4) | The exemption text is 65 characters; the bullet's other universals are bound or exempted individually |
| I12 | STATE.md omitted the exemption category | #15, #29 | FIXED (P94-4) | STATE.md states bound and exempted counts |
| I13 | "exactly the sixteen files" was inaccurate | #16 | FIXED (P94-4) | ADR 0066 line 19 and STATE.md line 9 read "almost all of them" |

## Defects found by P95's research that the 20 did not contain

| # | Defect | Status |
|---|---|---|
| N1 | The `staged secret scan` parity note was dead text and the printed count was wrong: the probe dropped arguments, so CI's `--tracked` step matched the `--staged` gate and the note never printed | FIXED in P95-3. With exact-command matching the note is live again; a note whose gate CI runs directly now fails as stale, and a note naming no gate fails too. The parity line reads "CI enforces 11 of 13 battery gates directly; 2 covered differently" |
| N2 | `ci_parity`'s docstring said CI-only commands "are REPORTED"; nothing reported them | This is audit finding #21, KILLED by its verifier as wording rather than a defect. P95-3 implemented the reporting anyway, because the silence was hiding N3 |
| N3 | `version.py --check` runs in CI but not in the battery, and nothing said so | Now printed by `--check-parity` as a CI-only command. Not added to the battery (not in scope) |
| N4 | Exemption maps with no staleness check; `_INSTALL_SCOPE_EXEMPT` narrows invariant 59's denominator | FIXED for that map in P95-3. Measured: 5 of its 13 entries exempted nothing (CHANGELOG.md, ledger/, docs/production-readiness-, the secret-scan allowlist, and docs/AUDIT-, whose one match is the living AUDIT-PROTOCOL filed under "dated audit protocol records"). They are dropped, and invariant 59 now fails on an entry that matches no tracked file or exempts nothing. 8 entries remain |

## Defects P95 found in its own work (author's harness, not an independent pass)

These are recorded because section 7.2 says the author's vectors are not the reviewer's: each was
caught by a harness the author wrote, so none of them counts as independently verified.

- The first tautology rule treated a list bound once (`_pip_targets = []`, later appended to) as a
  constant and refused the real P93-4 pin. Only immutable bindings fold now.
- It also treated module-level constants as fixed and refused three real regression guards
  (`paste_check.py`, `wizard.py` twice). A module-level name is the code under test; only names the
  selftest binds itself can make a check self-fulfilling.
- It conflated "truth is fixed" with "value is fixed", so `not any(<generator>)` read as a tautology.
- The existing dispatch pin checked the returned status only; a gate that returns `gated` after
  calling the client passed it. A recording-client pin now observes zero calls, with a flag-on
  control.
- Binding a short phrase whitelisted its repeats (I3 above).
- Two harness errors: a mutation that changed text but not behaviour (`[] or X`), and a parity
  fixture step appended to the wrong job. The first was caught because the matrix reported a miss
  instead of silently passing; the second because the selftest failed.

## Residuals (named, not claimed closed)

- A bound promise reversed by a clause with no marker word ("..., and ALLOW_SYSTEM installs into
  the shared site-packages").
- Relocating a promise out of the guarded section makes it invisible (audit #6, KILLED because no
  shipped sentence overstates the corpus boundary).
- Pin reachability is static: a call under a branch that is not provably dead still counts; a
  helper that tests its condition but discards the result still counts; a pin can pass while
  testing a different property than its claim.
- Bare "no" detection: recall 0.89 on the labelled set; the one miss ("No real CRM data or PII
  committed to the repo") is already bound verbatim.
- The dashboard's own flag-off branch is not pinned directly; the "makes no network call" claim is
  bound to the dispatch seam, with that scope stated in the manifest.

## Not exercised

- Parity reads `.github/workflows/ci.yml` only; it does not check the `on:` triggers (a guard job
  that stopped running on push would still pass), and does not model `shell:` or
  `working-directory:` overrides.
- Staleness checks for the other five reason-bearing maps (`doc-verify-allowlist`,
  `doc-source-allowlist` including its `_reasons`/`exempt` key divergence, `secret-scan-allowlist`,
  `operational-url-allowlist`, the mac-surface `excluded` map).
- The `verification_verdict` enum (`pass|pass_with_flags|fail`, in two schemas) has no member for
  an incomplete pass; section 7.2's DID NOT RUN has no schema home yet.
- The independent pass on P95 itself: at the time of writing it has not run. Its outcome, once its
  verification stage returns, is recorded as an addendum here.

## Follow-ups

- Audit a fixed commit: the pass reads a pinned SHA and the author does not edit the tree while it
  runs (the gap behind six of the nine KILLED verdicts above).
- The five unguarded exemption maps and the verdict enum listed under Not exercised.
