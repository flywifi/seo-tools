# 5. Local First Privacy Boundary

- Date: 2026-06-01
- Status: Accepted

## Context

The pipeline holds real CRM facts, contacts, and money; none of it may leak into git history or anything that leaves the machine.

## Decision

Keep all real data in gitignored `.local` files; commit only schemas and blank structures. Enforce at rest with allowlist-invert gitignore, force-add detection (invariant 20), a content secret scanner (invariant 21, CI), per-clone git hooks, and a commit-message backstop bounded by a policy SHA.

## Consequences

Real data physically cannot be committed without tripping a guard; commit hygiene (no session links, emails, real amounts, counterparty names, credentials, PII) is machine-enforced. Cost: contributors must install hooks after cloning; verified false positives need an allowlist entry with a written reason.
