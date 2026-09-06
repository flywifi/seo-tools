# topical-authority-map — Maintainer Notes

## Owner
The operator (see pipeline/user-context/creator-profile.local.json).

## Purpose
See SKILL.md description.

## Dependencies
All dependencies are canonical files in shared/ and canonical-sources/. No per-atom copies.
Run python3 tools/sync_check.py after any change to shared/ files this atom loads.

## Testing
Run the eval cases in evals/evals.json. Each case should pass govern-artifact with
quality_gate_result: pass.

## Known limitations
- No direct API access to search volume data. All volume figures must be labeled
  [estimated, unverified].
- Live web checks (where applicable) depend on web-intel-engine Level 3 crawl succeeding.
  If blocked, falls back to static knowledge with retrieval_gap recorded.

## Regression cases to preserve
Mapped to evals/evals.json (at least three):
1. tam-01 — a seasonal keyword yields a basic hub-and-cluster map.
2. tam-02 — a renter-persona DIY-pillar request produces a renter-scoped cluster.
3. tam-03 — a single secondary keyword still produces a minimal (not empty) cluster.

## Update triggers
- seo-intelligence-engine.md changes: review this atom's output format for compatibility.
- source-registry.json: if a used_by source is marked changed, review this atom's data sections.
