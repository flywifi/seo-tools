# 24. P39 Cross Modality Audit

- Date: 2026-07-07
- Status: Accepted

## Context

P39: the P38-7 rollout was fast/heuristic; this makes each declaration evidence-true. The planned adversarial multi-agent audit hit an account session limit after 4 spokes and was completed as a deterministic self-audit incorporating those 4 agent findings; the full adversarial run is resumable when budget resets.

## Decision

Audited and corrected the cross-modality declarations from P38-7 (which were assigned by heuristic). Re-derived each spoke's class from evidence (SKILL.md + workflow.json + composed atoms' tools + mcp_server.py). Two class fixes: analytics-insights B->C (runs roi-metric money math + docintel parsing) and partnership-mediakit A->B (depends on rate-benchmarks data); all other Class-C mechanism lines corrected to name the real tool module. Added an inherited one-line ## Cross-modality declaration to all 96 atoms. Hardened invariant 28 to require Class:/Runs on:/Mechanism:/Fallback: on spokes (no stub) + the line on atoms. Final: A=4, B=6, C=13. docs/CROSS-MODALITY-AUDIT.md records the per-skill verdicts + the packaging-candidate list (one remote-MCP deployment surfaces all Class-C skills; Class-B skills are knowledge-pack candidates).

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P39-cross-modality-audit`.
