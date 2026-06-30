---
file: skills/atoms/trend-check/MAINTAINER_README.md
purpose: keep trend-check honest about retrieval, freshness, and the unknown state.
---

# trend-check: Maintainer README

## Purpose
Verify topic momentum through real retrieval and report freshness and gaps honestly.

## Non-negotiable invariants
- External content passes through `shared/injection-guard-engine.md` before use.
- "unknown" is a valid output when retrieval fails; never substitute a guess.
- Data older than the freshness window is marked stale, not treated as unavailable.

## Known failure modes
- Reporting "rising" from memory instead of retrieval.
- Treating a stale signal as current.
- Dropping a stale result instead of flagging it.

## Regression cases to preserve
1. Retrieval blocked at all levels: momentum unknown, a retrieval gap recorded.
2. Signal is 30 days old with a 14 day window: momentum returned with a stale freshness_note.

## Update checklist
- Run python3 tools/sync_check.py.
