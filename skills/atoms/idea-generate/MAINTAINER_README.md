---
file: skills/atoms/idea-generate/MAINTAINER_README.md
purpose: keep idea-generate scoped to a small, on-brand idea batch, never a calendar and never invented trends.
---

# idea-generate: Maintainer README

## Purpose
Generate a few pillar-aligned ideas for one persona and format. Single operation.

## Non-negotiable invariants
- Ideas are anchored to the five pillars and the aesthetic in `shared/brand-engine.md`.
- Every idea names the persona it serves (`shared/audience-engine.md`).
- No trend or search claim is asserted here; that is trend-check and keyword-cluster.

## Known failure modes
- Drifting off aesthetic (bright farmhouse instead of home decor).
- Returning a calendar instead of a small batch.
- Asserting "this is trending" without trend-check.

## Regression cases to preserve
1. Pillar thrifting, persona The Vintage Hunter: ideas serve sourcing and authenticity, not generic hauls.
2. No persona given: ideas still name which persona each serves, chosen from the request, not assumed demographics.
3. count 3: exactly three ideas, each with scale set.

## Update checklist
- Output still validates against the Input/Output contract in SKILL.md.
- Run python3 tools/sync_check.py.
