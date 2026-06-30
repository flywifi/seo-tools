# entity-extract — Maintainer Notes

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

## Update triggers
- seo-intelligence-engine.md changes: review this atom's output format for compatibility.
- source-registry.json: if a used_by source is marked changed, review this atom's data sections.
