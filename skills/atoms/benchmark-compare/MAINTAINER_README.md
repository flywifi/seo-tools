---
file: skills/atoms/benchmark-compare/MAINTAINER_README.md
purpose: keep benchmark-compare honest about data source; benchmark ranges are industry estimates, never Alex's personal data.
---

# benchmark-compare: Maintainer README

## Purpose
Compare a metric against industry benchmark ranges from canonical-sources/rate-benchmarks/benchmarks.json. Always labels sources; never presents a benchmark as Alex's personal data.

## Non-negotiable invariants
- data_source is always set to "canonical-sources/rate-benchmarks/benchmarks.json" for benchmark figures.
- alex_value is null when no real data is provided; gap_assessment is unknown in that case.
- benchmark_range reflects the niche (home-decor-diy) when available in the source file; generic range otherwise.

## Known failure modes
- Presenting a benchmark CTR range as "Alex's typical CTR."
- Setting gap_assessment to above/below/within when alex_value is null.
- Using a generic creator benchmark when a niche-specific one exists in the source file.

## Regression cases to preserve
1. alex_value provided and within benchmark range: gap_assessment is within; interpretation is positive.
2. alex_value not provided: gap_assessment is unknown; no interpretation stated.

## Update checklist
- Run python3 tools/sync_check.py.
