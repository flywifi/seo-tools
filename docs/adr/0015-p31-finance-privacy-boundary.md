# 15. P31 Finance Privacy Boundary

- Date: 2026-07-04
- Status: Accepted

## Context

The prior boundary was filename convention only: no gitignore rules for exports, no content scanning, no commit hygiene enforcement. P31 layers accident prevention (allowlist-invert gitignore), force-add detection (invariant 20), content scanning (secret_scan.py, invariant 21, CI), per-clone git hooks, a CI commit-message backstop bounded by a policy SHA, and a written non-negotiable policy. Features then ship with structural safeties: redaction for anything leaving the machine, proposal-only reconciliation with an in-repo non-local CSV refusal, and dunning drafts that are never sent.

## Decision

Ship the four P30 follow-up finance features (cash-flow projection, dashboard AR tab, payment reconciliation, dunning drafts) on a machine-enforced privacy boundary built first.

## Consequences

**Explicitly not done:** No history rewrite; no new dependencies; no entropy scanning; no auto-sent dunning; no bank API integrations.

**Anti-over-share policy:** Commit messages, PR bodies, and issue comments carry no session links, personal emails, real amounts, real counterparty names, credentials, or PII. Author email is the GitHub noreply address. Enforced by the commit-msg hook and the CI backstop; exemptions only via tools/secret-scan-allowlist.json with a written reason. No history rewrite: the policy applies forward of the boundary SHA recorded in the allowlist file.

**Verified by:**
- tools/secret_scan.py --selftest
- tools/finance.py --selftest (71 checks)
- tools/sync_check.py (21 invariants)
- negative tests: gitignore block, force-add trip, hook rejections, CSV refusal

Ledger status at record time: `shipped`. Source: `ledger/ledger.json` id `P31-finance-privacy-boundary`.
