---
file: skills/content-strategy/MAINTAINER_README.md
purpose: keep content-strategy producing trend-verified idea clusters, never single ideas or invented trends.
---

# content-strategy: Maintainer README

## Purpose
The primary idea-generation spoke. It produces pillar-aligned idea clusters and competitive
positioning, and hands developed work to video-development. It does not build production packages or
downloadable files.

## Non-negotiable invariants
- Shared: self-checks against `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- trend-check is mandatory before any trend or seasonal claim; stale data is marked, not dropped.
- Returns clusters, not single ideas.
- Stays on the moody-vintage aesthetic and names the persona each idea serves.

## Known failure modes
- Recommending a trend from memory without trend-check.
- Returning one idea instead of a cluster.
- Drifting to bright farmhouse aesthetic.
- Presenting niche-typical audience defaults as the creator's measured data.

## Fragile fallbacks that must not become defaults
- Proceeding with stale trend data without the stale flag.

## Regression cases to preserve
1. Thrifting pillar request: a cluster, each idea serving a named persona, on aesthetic.
2. "What is trending" request: trend-check runs first; momentum unknown is acceptable.
3. Trend data 30 days old: returned with a stale freshness note, not dropped.
4. No persona signal: ideas still name a persona served, not assumed demographics.
5. A budget constraint mentioned in passing: reflected in adaptation, not ignored.

## Approval-gated changes
- The atom wiring in workflow.json and the output contract in SKILL.md.

## Minority-report policy
When two pillars or personas fit, record the chosen one, the alternative, why, and what would change it.

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
