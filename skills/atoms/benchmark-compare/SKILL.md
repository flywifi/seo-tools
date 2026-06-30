---
file: skills/atoms/benchmark-compare/SKILL.md
name: benchmark-compare
description: "compares a provided channel or post metric against industry benchmark ranges from canonical-sources/rate-benchmarks/benchmarks.json; does NOT fabricate the creator's metrics or access live analytics."
load:
  - canonical-sources/rate-benchmarks/benchmarks.json
  - protocols/no-fabrication.md
  - shared/platform-engine.md
---

# benchmark-compare

Compare one channel or post metric against industry benchmark ranges for the creator's niche and platform.

## Purpose

This atom looks up the benchmark range for a named metric from
`canonical-sources/rate-benchmarks/benchmarks.json` and, if a real value for the creator is supplied by
the caller, computes how that value sits relative to the range. All benchmark ranges in that file
are industry estimates for the home-decor-diy niche; they are not the creator's personal historical data.

Key constraint: this atom never fetches, infers, or fabricates the creator's actual analytics. If
`alex_value` is not passed in, `alex_value` is null and `gap_assessment` is "unknown". The caller
is responsible for supplying a real number when a comparison is needed.

## Inputs

```json
{
  "metric_name": "ctr | avd | engagement_rate | views | subscribers | rpm",
  "alex_value": "number | null (optional; real number provided by caller)",
  "platform": "youtube | instagram | tiktok | pinterest",
  "niche": "string (optional; defaults to home-decor-diy)"
}
```

- `metric_name`: required. One of the six supported metrics. See `canonical-sources/rate-benchmarks/benchmarks.json` for the full schema.
- `alex_value`: optional. A real number the caller passes in (for example, from a screenshot or manually entered analytics). Do not supply a guessed or fabricated value.
- `platform`: required. Determines which benchmark row is loaded from the file.
- `niche`: optional. Defaults to `home-decor-diy`. If the benchmarks file does not contain the requested niche, return `benchmark_range: null` and flag the gap rather than inventing a range.

## Output

```json
{
  "tool": "benchmark-compare",
  "metric": "string",
  "benchmark_range": {
    "low": "number",
    "high": "number",
    "unit": "string (percent | count | usd | seconds)"
  },
  "benchmark_source": "canonical-sources/rate-benchmarks/benchmarks.json",
  "alex_value": "number | null",
  "gap_assessment": "above | below | within | unknown",
  "interpretation": "string (one to two sentences explaining what the range means for the niche)",
  "recommendation": "string | null (actionable next step if gap_assessment is above or below; null if within or unknown)",
  "data_source": "industry-estimate-home-decor-diy"
}
```

Field rules:

- `benchmark_range`: pulled verbatim from `canonical-sources/rate-benchmarks/benchmarks.json`. If the metric or niche is not found, set to null and note the gap in `interpretation`.
- `gap_assessment`: "above" if `alex_value` exceeds `benchmark_range.high`; "below" if it falls under `benchmark_range.low`; "within" if it sits between low and high (inclusive); "unknown" if `alex_value` is null or `benchmark_range` is null.
- `data_source`: always the literal string `"industry-estimate-home-decor-diy"` to make clear these are estimates, not the creator's measured history.
- `recommendation`: omit fabricated targets. Recommendations must be directional and tied to the gap (for example, "test a tighter hook in the first 30 seconds to lift AVD toward the high end of the range"), never invented metric promises.

## Do NOT use for

- Fabricating the creator's CTR, AVD, RPM, or any other personal analytics value when none is supplied.
- Accessing live YouTube Studio, Instagram Insights, or any analytics API. This atom is offline and reads only from the local benchmarks file.
- Producing final public-facing reports. Output is a draft signal for spokes to interpret and present.
- Metrics not listed in `benchmarks.json`. If a caller requests an unsupported metric, return null for `benchmark_range` and flag it.
- Benchmarks for niches outside the file. Do not extrapolate or borrow from adjacent niches.

## Pipeline note

Follows `shared/method.md`. Platform-specific context (audience size tiers, content format norms)
comes from `shared/platform-engine.md`. Fabrication rules are governed by
`protocols/no-fabrication.md`: if any field would require inventing a number, set it to null and
surface a flag instead. Benchmark ranges in the source file are expressed as low-to-high pairs
with a unit label; always echo both ends of the range and the unit in output so downstream spokes
can format them correctly for the creator.
