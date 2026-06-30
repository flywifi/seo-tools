---
file: skills/partnership-mediakit/MAINTAINER_README.md
purpose: keep partnership-mediakit honest about rate data sources and triggering FTC disclosure notes on every sponsored kit.
---

# partnership-mediakit: Maintainer README

## Purpose
Build brand partnership outreach materials: pitch paragraph, media kit sections, and rate card. Uses labeled benchmark ranges when the creator's rates are not provided.

## Non-negotiable invariants
- rate-card-fill source is always set (personal_rate/benchmark_range) and accurate.
- Benchmark rates are labeled as industry benchmarks, never as the creator's personal rates without explicit labeling.
- FTC disclosure note appears in pitch and media kit sections when content is sponsored.

## Known failure modes
- Presenting a benchmark engagement rate as the creator's measured data in a media kit section.
- Omitting the FTC disclosure note in a sponsored outreach kit.
- A pitch paragraph that is generic and could apply to any creator.

## Regression cases to preserve
1. No alex_actual_rates provided: all rate card lines use benchmark_range source with disclaimer.
2. Sponsored partnership: pitch-paragraph includes FTC disclosure note; mediakit-section includes it as well.
3. Specific brand provided: pitch paragraph anchors to that brand, not a generic template.

## Approval-gated changes
- The rate card line items and the benchmark data source reference.

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
