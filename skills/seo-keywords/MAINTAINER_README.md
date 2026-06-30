---
file: skills/seo-keywords/MAINTAINER_README.md
purpose: keep seo-keywords honest about volume estimates and scoped to the moody/vintage home decor niche.
---

# seo-keywords: Maintainer README

## Purpose
Build a complete SEO strategy for a content topic: keyword cluster, search intent, competitive gap analysis, and a title/description skeleton. Does not write hooks, scripts, or final copy.

## Non-negotiable invariants
- Volume estimates are always ranges labeled "[estimated, unverified]"; exact figures are never asserted.
- Competitor data from competitor-scan carries [unverified] labels where not confirmed by retrieval.
- The keyword vocabulary stays within the moody/vintage home decor and DIY niche.

## Known failure modes
- Asserting an exact search volume figure without [estimated, unverified] label.
- Recommending keywords outside the niche (e.g., generic lifestyle terms).
- Presenting the title skeleton as a finished title rather than a draft for title-generate.

## Fragile fallbacks that must not become defaults
- Skipping competitor-scan when retrieval is slow (gap-record instead of skipping).

## Regression cases to preserve
1. Volume figures: always [estimated, unverified] with a note directing independent verification.
2. Retrieval failure on competitor-scan: gap-record emitted with the missing platform noted; not fabricated.

## Approval-gated changes
- The atom wiring in workflow.json and the volume estimate labeling convention.

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
