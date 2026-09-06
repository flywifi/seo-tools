# 11. P27 Evidence Governance Patterns

- Date: 2026-07-03
- Status: Accepted

## Context

The patterns operationalize the existing no-fabrication and human-review protocols at finer granularity: silent downgrades, identity laundering via strong claims, and confident-wrong CRM writes were previously discouraged by prose but not structurally named. All changes are additive; no schema field was removed and drift guard invariants 14 to 17 are unaffected.

## Decision

Adopted five governance patterns from the maintainer's prior meeting-evidence system (reviewed offline; source document not committed): (1) a five-mode evidence acquisition ladder (direct_connector / export_bundle / excerpt_only / internal_context_only / hybrid_reconciliation) added to the connector model and registry; (2) a field-level memory safety model (raw / conditional / derived_reviewed / safe write classes) added to the pipeline engine; (3) identity confidence separated from claim confidence in the verification envelope; (4) artifact_completeness (minimal/partial/rich) plus per-item provenance required on evidence bundles; (5) explicit stop conditions as first-class workflow outcomes, implemented in deal-review.js.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P27-evidence-governance-patterns`.
