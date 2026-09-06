# 2. Atoms Compose Into Spokes

- Date: 2026-06-01
- Status: Accepted

## Context

Spokes that each re-implemented single operations (keyword clustering, hook writing, invoice drafting) would duplicate logic and drift apart.

## Decision

Factor every single-operation capability into an `atom` under `skills/atoms/`. Spokes compose atoms via a `workflow.json`; an atom is independently callable and independently testable (its own `evals/evals.json`).

## Consequences

Reuse across spokes with one definition per operation; the drift guard enforces that every atom a workflow names is installed. Cost: more skill directories to maintain, mitigated by the scaffolder (`tools/new_skill.py`) and the drift guard.
