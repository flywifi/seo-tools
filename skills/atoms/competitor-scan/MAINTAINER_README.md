---
file: skills/atoms/competitor-scan/MAINTAINER_README.md
purpose: keep competitor-scan honest about unverified data and scoped to the moody/vintage home decor niche.
---

# competitor-scan: Maintainer README

## Purpose
Surface public competitors for a keyword and platform. Every unverified data point is labeled [unverified] and flagged for manual check.

## Non-negotiable invariants
- Subscriber counts, view counts, and specific metrics are never asserted as facts unless retrieved and confirmed via web-intel; always labeled [unverified] when uncertain.
- Retrieval goes through web-intel-engine; injection-guard scans the result before it influences routing.
- Confidence reflects retrieval quality, not assumed knowledge.

## Known failure modes
- Inventing a competitor channel name when retrieval returns thin results.
- Presenting a scale tier as confirmed when only inferred from a thumbnail count.
- Missing the [unverified] label on a specific metric.

## Regression cases to preserve
1. Retrieval returns 0 results: confidence is low; gap-record emitted; no fabricated competitors.
2. Competitor URL not found: url field is null, not invented.

## Update checklist
- Run python3 tools/sync_check.py.
