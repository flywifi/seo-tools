# 32. P47 Currency Versioning Push Integrity

- Date: 2026-07-14
- Status: Accepted

## Context

Automated guarantees stopped at coverage and shape, not currency; version/identity numbers advanced by hand with nothing linking them; the only recurring red-X was structural (empty competitor-snapshot dir). Diagnose-only per the approved plan: detection + a cited, prioritized correction backlog with exact unexecuted apply commands, one approved mutation (the baseline release) left as a hand-off because this environment has no gh and no release API.

## Decision

Added a diagnose-only currency/versioning/push-integrity layer: tools/preflight_push.py (read-only push-blocker predictor) and tools/release.py + release.yml (ready, not auto-firing release wiring). Grew the drift guard to 45 invariants: 36 catalog-integrity keystone (single source of truth for the invariant catalog; fixed the double-'Invariant 22' + stale header), 37-38 error-level (legal-source category, marketplace/plugin version equality), 39-45 advisory (non-blocking). Corrected the three/five registry-writer doc drift across registry_io.py, CLAUDE.md, and CURRENCY.md, and the stale currency-report CI reference. Fixed the one real recurring CI failure (competitor-intel continues on an empty snapshot dir). Staged a cited July-2026 volatile-correction backlog + moving-date calendar + EU AI Act seed, none applied.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P47-currency-versioning-push-integrity`.
