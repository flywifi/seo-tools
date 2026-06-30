---
file: skills/competitor-analysis/MAINTAINER_README.md
purpose: keep competitor-analysis honest about unverified data and scoped to the moody/vintage home decor and DIY niche.
---

# competitor-analysis: Maintainer README

## Purpose
Research competitors in the moody/vintage home decor and DIY niche, surface content gaps, and produce a differentiation report. Never fabricates competitor data.

## Non-negotiable invariants
- All unverified competitor data (channel names, subscriber counts, view figures) carries [unverified] labels.
- confidence reflects actual retrieval quality (low when thin results).
- Scope is the moody/vintage home decor and DIY niche; off-niche results are labeled as peripheral.

## Known failure modes
- Stating a competitor's subscriber count as fact without [unverified] label.
- Returning high confidence when retrieval returned thin results.
- Drifting to off-niche competitors without noting the scope deviation.

## Regression cases to preserve
1. Zero retrieval results: confidence is low; no fabricated competitors; gap-record emitted.
2. Competitor URL not found: url field is null; not invented.

## Approval-gated changes
- The competitor pool and the niche scope definition.

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
