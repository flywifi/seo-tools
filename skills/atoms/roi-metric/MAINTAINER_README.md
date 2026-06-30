---
file: skills/atoms/roi-metric/MAINTAINER_README.md
purpose: keep roi-metric clearly labeled (real/estimated/partial) and honest about what cannot be calculated without data.
---

# roi-metric: Maintainer README

## Purpose
Calculate or estimate ROI metrics for a brand deal. Every estimated field is labeled; null when the required input is absent.

## Non-negotiable invariants
- data_quality is always set (real/estimated/partial) and accurate.
- null is used for any calculated field whose required inputs are absent; no estimation without a basis.
- flags lists every unknown that limits the calculation.

## Known failure modes
- Computing effective_hourly_rate when production_hours is null.
- Omitting the data_quality field.
- Presenting an estimated CPM as "the creator's CPM" without a data_quality label.

## Regression cases to preserve
1. Only deal_rate provided, no views: estimated_cpm is null; data_quality is partial; flags includes "views unknown."
2. All inputs provided: data_quality is real; no null calculated fields.

## Update checklist
- Run python3 tools/sync_check.py.
