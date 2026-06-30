---
file: skills/analytics-insights/references/artifact-types.md
role: the artifact types analytics-insights produces and the required elements of each.
---

# analytics-insights artifact types

## Analytics insights report
A comparison of provided channel metrics against industry benchmarks with prioritized recommendations. Required elements: list of metrics analyzed, benchmark comparison per metric (benchmark_range from canonical-sources, gap_assessment, interpretation), top performers list, underperformers list, prioritized recommendations with rationale, data_quality label (real/estimated/partial), retrieval gaps list, and a govern-artifact gate result.

## Benchmark comparison
A single metric comparison against a benchmark range. Required elements: metric name, benchmark_range (from canonical-sources/rate-benchmarks/benchmarks.json, labeled as industry benchmark), alex_value (null if not provided), gap_assessment (above/below/within/unknown), data_source, and recommendation.

## Gap record (no analytics)
Returned when no analytics data is provided. Required elements: gap_type (analytics_data_required), description, impact, recommended_next_step (e.g., "export analytics from YouTube Studio as a CSV and re-submit").
