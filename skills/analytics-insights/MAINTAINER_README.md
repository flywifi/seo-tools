---
file: skills/analytics-insights/MAINTAINER_README.md
purpose: keep analytics-insights honest about data sources and returning gap-records when no analytics data is provided.
---

# analytics-insights: Maintainer README

## Purpose
Analyze channel and post metrics against industry benchmarks and surface prioritized recommendations. Returns gap-record if no analytics data is provided.

## Non-negotiable invariants
- Never fabricates analytics data; gap-record fires when analytics_source is null.
- All benchmark comparisons are labeled as industry benchmarks, not Alex's personal data.
- data_quality is always set (real/estimated/partial) in the output.

## Known failure modes
- Fabricating engagement rates when no analytics file is provided.
- Presenting a benchmark as Alex's actual CTR.
- Missing the gap-record path when analytics_source is null.

## Regression cases to preserve
1. No analytics provided: gap-record returned immediately with reason "analytics_data_required."
2. Analytics CSV with partial data: benchmark_compare flags gaps for missing metrics; data_quality is partial.

## Approval-gated changes
- The gap-record trigger condition and the benchmark data source.

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
