---
file: skills/atoms/mediakit-section/MAINTAINER_README.md
purpose: keep mediakit-section honest about data sources; benchmark ranges are labeled and real data is never fabricated.
---

# mediakit-section: Maintainer README

## Purpose
Write one section of the creator's media kit. Subscriber counts, engagement rates, and CPMs are null when real data is absent; benchmark ranges are labeled as industry benchmarks, not personal data.

## Non-negotiable invariants
- data_source field in the output is always set (real/benchmark/placeholder) and accurate.
- placeholders_to_fill lists every field that needs real data before the section is shared externally.
- Voice is professional and brand-facing (published-to-audience mode, not planning-to-the creator).

## Known failure modes
- Presenting a benchmark engagement rate as the creator's personal rate.
- Omitting placeholders_to_fill when real subscriber data is unknown.
- Using planning-to-the creator voice in external-facing media kit copy.

## Regression cases to preserve
1. No channel_data provided: placeholders_to_fill includes all metric fields; no fabricated numbers.
2. Brand name provided: the section is personalized to that brand, not generic.

## Update checklist
- Run python3 tools/sync_check.py.
