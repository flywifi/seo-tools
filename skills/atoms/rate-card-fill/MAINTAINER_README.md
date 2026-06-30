---
file: skills/atoms/rate-card-fill/MAINTAINER_README.md
purpose: keep rate-card-fill honest about data source; benchmark ranges are labeled as benchmarks, never as Alex's personal rates.
---

# rate-card-fill: Maintainer README

## Purpose
Fill a rate card for a brand proposal. When Alex's rates are not provided, use labeled industry benchmark ranges from canonical-sources/rate-benchmarks/benchmarks.json.

## Non-negotiable invariants
- source field is always set (personal_rate/benchmark_range) and accurate.
- disclaimer appears in the output whenever source is benchmark_range for any line item.
- Never present a benchmark range as "Alex's rate" without explicit labeling.

## Known failure modes
- Setting source to personal_rate when only benchmark data is available.
- Omitting the disclaimer when benchmark_range rates are in the output.
- Fabricating rates not backed by benchmarks.json or alex_actual_rates.

## Regression cases to preserve
1. alex_actual_rates not provided: all rates use benchmark_range source; disclaimer is present.
2. Mix of real and benchmark rates: each line item has its own source label.

## Update checklist
- Run python3 tools/sync_check.py.
