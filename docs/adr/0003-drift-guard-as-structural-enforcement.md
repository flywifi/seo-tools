# 3. Drift Guard As Structural Enforcement

- Date: 2026-06-01
- Status: Accepted

## Context

Conventions stated only in prose (path references, counts, agent contracts, data-at-rest rules) rot silently as the repo grows.

## Decision

Encode every non-negotiable as a machine-checked invariant in `tools/sync_check.py` (the drift guard), run it in CI, and fail the build on violation. Each invariant is catalogued (contiguous numbering, header list, docstring label) and self-consistency is itself an invariant.

## Consequences

The repo's guarantees are executable, not aspirational; a violation blocks merge. Cost: new structure must ship with its invariant, and the catalog must stay self-consistent (enforced by the catalog-integrity invariant).
