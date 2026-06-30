---
file: skills/atoms/roi-metric/SKILL.md
name: roi-metric
description: "calculates ROI metrics for a brand partnership deal from pipeline data or provided inputs; clearly labels all estimates; does NOT fabricate metrics or access live analytics without authorization."
load:
  - shared/pipeline-engine.md
  - protocols/no-fabrication.md
---

# roi-metric

A single-operation atom that calculates or estimates ROI metrics for a brand partnership deal. All outputs are clearly labeled as real, estimated, or partial. No metric is invented or inferred without a declared source.

## Purpose

This atom takes deal financials and optional performance inputs and returns a structured ROI breakdown. Its core responsibility is honest labeling: every output field is either sourced from real pipeline data, calculated from provided inputs, or explicitly null with a flag explaining why.

Estimates are allowed and useful. Fabrication is not. Any value that cannot be derived from the provided inputs must be returned as null, not approximated from benchmarks, industry averages, or assumptions unless those assumptions are explicitly passed in as inputs and labeled as such in the output.

The `data_quality` field signals the reliability tier of the entire result set. The `flags` list names every unknown that limits the calculation, so the caller can decide whether the result is actionable or needs more data.

## Inputs

| Field | Type | Required | Description |
|---|---|---|---|
| deal_id | string | No | Pipeline deal identifier. If provided, the atom pulls deal_rate and any stored performance data from pipeline records before applying provided inputs. Provided inputs override pipeline values when both are present. |
| deal_rate | number | Yes | The agreed payment for the partnership, in USD. This is the revenue figure used in all downstream calculations. |
| estimated_views | number | No | Projected or actual view count for the sponsored content. Used to calculate estimated CPM. If omitted, estimated_cpm is null. |
| estimated_clicks | number | No | Projected or actual click count from the sponsored content. Used to calculate estimated CPC. If omitted, estimated_cpc is null. |
| production_hours | number | No | Total creator hours attributed to producing and delivering this deal (scripting, filming, editing, revisions, admin). If omitted, hours_invested and effective_hourly_rate are null. |
| hourly_value | number | No | The creator's self-assigned dollar value per hour of work, in USD. Used only to calculate effective_hourly_rate. If omitted, effective_hourly_rate is null even if production_hours is provided. |

## Output

```json
{
  "revenue": "<deal_rate value in USD>",
  "estimated_cpm": "<(deal_rate / estimated_views) * 1000, or null if estimated_views is unknown>",
  "estimated_cpc": "<deal_rate / estimated_clicks, or null if estimated_clicks is unknown>",
  "hours_invested": "<production_hours value, or null if unknown>",
  "effective_hourly_rate": "<deal_rate / production_hours, or null if production_hours or hourly_value is unknown>",
  "roi_summary": "<plain-language summary of what is known, what is estimated, and what is missing>",
  "data_quality": "<one of: real | estimated | partial>",
  "flags": ["<list of field names or conditions that limited the calculation>"]
}
```

### Field definitions

**revenue** (number, always present): The deal_rate value. This is the only field guaranteed to be non-null, because deal_rate is required.

**estimated_cpm** (number or null): Cost per thousand views, calculated as `(deal_rate / estimated_views) * 1000`. Null when estimated_views is not provided. Always treated as an estimate unless the caller explicitly marks estimated_views as a confirmed final count.

**estimated_cpc** (number or null): Cost per click, calculated as `deal_rate / estimated_clicks`. Null when estimated_clicks is not provided.

**hours_invested** (number or null): The production_hours value passed in. Null when not provided. Reported as-is without adjustment.

**effective_hourly_rate** (number or null): Revenue per hour, calculated as `deal_rate / production_hours`. Null when production_hours is missing. Note: this field uses deal_rate divided by hours, regardless of whether hourly_value is provided. The hourly_value input is reserved for future margin calculations. If hourly_value is provided but production_hours is not, effective_hourly_rate is still null and a flag is emitted.

**roi_summary** (string): A one-to-three sentence plain-language summary. Describes what was calculated, what data quality tier applies, and which fields are null due to missing inputs. No em dashes. Ranges use "to".

**data_quality** (enum: real | estimated | partial):
- `real`: deal_rate came from a confirmed pipeline record and all non-null metrics derive from confirmed actuals.
- `estimated`: one or more non-null metrics derive from projected or estimated inputs rather than confirmed actuals.
- `partial`: one or more output fields are null due to missing inputs. Partial does not mean inaccurate; it means the calculation is incomplete.

**flags** (array of strings): Lists every condition that caused a field to be null or downgraded data_quality. Examples: `"estimated_views not provided: estimated_cpm is null"`, `"production_hours not provided: hours_invested and effective_hourly_rate are null"`, `"estimated_clicks not provided: estimated_cpc is null"`.

## Do NOT use for

- Fetching live analytics from YouTube Studio, Google Analytics, or any external platform. This atom does not have access to live data sources.
- Comparing a deal against benchmark CPM or CPC ranges. Use a benchmarking atom for normative analysis.
- Approving, rejecting, or scoring a deal. Scoring and qualification live in pipeline-engine workflows, not this atom.
- Generating revenue projections for deals that have not yet been agreed upon. This atom reports on an existing deal_rate; it does not forecast.
- Any calculation where deal_rate is zero or negative. Flag and return null for all derived fields if deal_rate is not a positive number.

## Pipeline note

When deal_id is provided, this atom reads from the pipeline store defined in `shared/pipeline-engine.md`. It reads only. It does not write back to pipeline records, update deal stage, or log activity. If the deal_id is not found in the pipeline store, the atom continues using only the inputs provided and adds `"deal_id not found in pipeline: pipeline data not used"` to flags.

All pipeline reads are subject to the no-fabrication protocol (`protocols/no-fabrication.md`). If a pipeline field is missing or ambiguous, the atom returns null for that field rather than interpolating a value.
