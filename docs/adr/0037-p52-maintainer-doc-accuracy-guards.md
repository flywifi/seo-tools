# 37. P52 Maintainer Doc Accuracy Guards

- Date: 2026-07-16
- Status: Accepted

## Context

The drift guard verified that backticked paths resolve and that integer counts are true, but nothing
checked that maintainer/SKILL/docs prose agreed with code behavior, so stale scopes, "stub" claims,
and endpoint drift shipped green. P51 both created an instance of that drift (the publishing
`__init__` docstring) and exposed the gap; the credentialed `tools/` layer had zero maintainer or
guard coverage.

## Decision

Closed the maintainer/doc accuracy blind spot in the drift guard (seo-tools only). Added forward
guards so prose cannot silently diverge from code: extend the path-resolution check to `docs/*.md`
and `README.md`; a symbol-reference invariant (`verify:` markers of the form `path::symbol` resolved
against the AST, with an allowlist for dynamic/optional symbols); a tools-layer maintainer-coverage invariant
(`TOOLS_MAINTAINER_DIRS`); and `tools/doc_freshness.py` content-hash staleness stamping (advisory).
Created `tools/publishing/MAINTAINER_README.md`. Ran a full multi-agent, cite-or-drop content-
accuracy sweep and, after human review, applied only the approved corrections; lowered the
skill-template regression bar to three and backfilled Regression sections on five atoms; retrofitted
61 `verify:` markers across 43 docs. Added process conventions: advisory `.github/CODEOWNERS`
(`@flywifi`), `docs/adr/` (MADR), root `CHANGELOG.md` (Keep a Changelog + SemVer),
`docs/DOC-MAINTENANCE.md`, and a `CLAUDE.md` same-PR docs rule.

## Consequences

**Explicitly not done:** seo-tools only (educator-tools-k12-public excluded entirely, no reads/edits);
no product-code behavior changes (guards are new checks only); dated historical audits annotated, not
rewritten; sweep prose edits applied only after review; staleness stamping labeled emerging-practice,
not a standard; CODEOWNERS advisory (no branch-protection change).

**Verified by:**
- tools/sync_check.py (drift clean; new symbol-ref, tools-maintainer, path-to-docs checks)
- tools/doc_freshness.py --selftest
- tools/count_truth.py (22 spokes / 105 atoms / 129 skills / 51 invariants / 9 scenarios)
- tools/scenario_check.py (9/9)
- regression probe: a bad verify marker and a reintroduced '14 spokes' count each fail sync_check (exit 1); restore -> exit 0

Ledger status at record time: `shipped`. Source: `ledger/ledger.json` id `P52-maintainer-doc-accuracy-guards`.
