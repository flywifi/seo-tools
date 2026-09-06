---
name: forecast
atom: true
description: "Performs time-series forecasting for content metrics: projected views, subscriber growth, seasonal revenue, optimal posting schedule. Do NOT use for static keyword comparison (use keyword-compare) or general hypothesis testing (use hypothesis-test)."
load:
  - shared/compute-engine.md
  - shared/seo-intelligence-engine.md
  - protocols/no-fabrication.md
---

# forecast

Project future values of a content metric using time-series methods. Returns point forecasts with
uncertainty bounds, trend direction, and seasonality detection — all anchored to the creator's
planning horizon and content calendar.

## Purpose

The creator needs forward-looking estimates for planning: how many views to expect next month, when
subscriber growth will hit a milestone, whether revenue dips seasonally, and when to publish for
maximum impact. This atom takes historical metric data, selects an appropriate time-series method,
delegates computation to a connected MCP tool (via `shared/compute-engine.md`), and returns
forecasts with explicit uncertainty. It loads `shared/seo-intelligence-engine.md` for seasonal
patterns and platform-specific timing signals.

## When to invoke

- "How many views will I get next month based on my last 6 months?"
- "When will I hit 50K subscribers at this growth rate?"
- "Project my Shorts revenue for Q4."
- "Is my engagement rate trending up or down?"
- "What does my seasonal traffic pattern look like for the next year?"
- Invoke directly or from a spoke that needs a forward-looking metric projection.

## Do NOT use for

- Static keyword comparison across platforms. Use `keyword-compare`.
- General hypothesis testing — comparing groups or testing independence. Use `hypothesis-test`.
- Fitting a regression model to understand predictor relationships. Use `regression-analysis`.
- A/B test design or analysis. Use `ab-test`.
- Querying data files without a time-series question. Use `data-query`.

## Inputs

```json
{
  "metric": "string — the metric to forecast (e.g., 'monthly_views', 'subscriber_count', 'revenue')",
  "historical_data": "csv_path | inline_values",
  "forecast_horizon": "7d | 30d | 90d | 365d",
  "seasonality": "weekly | monthly | yearly | none",
  "confidence_level": 0.95
}
```

- `metric`: required. The name of the metric being forecast. Used for labeling and interpretation.
- `historical_data`: required. Either a path to a CSV file with date and value columns, or inline
  data as an array of `{"date": "YYYY-MM-DD", "value": number}` objects.
- `forecast_horizon`: required. How far ahead to project. Longer horizons produce wider uncertainty
  bounds.
- `seasonality`: optional, defaults to `"none"`. If provided, the model incorporates seasonal
  components. Use `shared/seo-intelligence-engine.md` seasonal patterns to inform the choice:
  - `weekly`: day-of-week effects (posting schedule, viewer habits).
  - `monthly`: monthly cycles (pay periods, seasonal interest shifts).
  - `yearly`: annual patterns (holiday surges, summer dips).
  - `none`: no seasonal component — trend only.
- `confidence_level`: optional, defaults to 0.95. Width of prediction intervals.

## Procedure

### Step 1: validate data and horizon

Check that `historical_data` contains enough observations for the requested model:
- Minimum 10 data points for trend-only forecasting.
- Minimum 2 full seasonal cycles for seasonal models (e.g., 14 days for weekly, 24 months for
  yearly).
- If data is insufficient, emit a warning and either fall back to trend-only or set
  `conclusion` to `"insufficient_data"`.

Check for gaps, duplicates, and outliers in the time series. Note any data quality issues in
`retrieval_gaps`.

### Step 2: check compute-engine tool selection

Read `shared/compute-engine.md` Section 1. Preferred tools for time-series: E2B Python with
statsmodels or Prophet (preferred), Jupyter notebook (alternative).

Check connector availability. Set `computation_source` accordingly.

### Step 3: select and fit the model

Based on the data characteristics and requested seasonality:
- Trend only (`seasonality: "none"`): linear trend model or Holt's exponential smoothing.
- Seasonal: Holt-Winters exponential smoothing or Prophet with the specified seasonality period.
- If the data shows non-linear growth (e.g., subscriber curves), consider log-transform or
  logistic growth model. Note the transformation in the output.

Delegate model fitting and forecasting to the computation tool. Request:
- Point forecasts for each period in the horizon.
- Upper and lower prediction interval bounds at the specified confidence level.
- Trend component (slope or growth rate).
- Seasonal component (if applicable).

### Step 4: fallback to guidance-only if no tool

If no computation tool is connected:
- Set `computation_source` to `"guidance_only"`.
- Compute a simple linear trend using Claude's arithmetic (slope = (last - first) / n_periods).
  Label this `[estimated — verify with computation tool]`.
- Emit runnable Python code using statsmodels or Prophet that the user can execute locally.
- Set `seasonality_detected` to null (cannot verify without a tool).

### Step 5: interpret forecast in creator context

Translate the forecast into actionable planning language:
- State the trend direction and rate: "Your monthly views are growing at approximately {rate}
  per month."
- If seasonal: "You typically see a {peak_pct}% increase in {peak_month} and a {trough_pct}%
  decrease in {trough_month}."
- Highlight the uncertainty: "The 95% prediction interval for {target_date} is {lower} to
  {upper}, meaning the actual value could land anywhere in that range."
- Connect to content strategy using `shared/seo-intelligence-engine.md` seasonal signals:
  if a seasonal peak is approaching, note the content lead time.

## Output

```json
{
  "metric": "monthly_views",
  "forecast": [
    {
      "date": "2026-08-01",
      "predicted_value": 45200,
      "lower_bound": 38100,
      "upper_bound": 52300
    }
  ],
  "trend": "rising | flat | declining",
  "trend_rate": "approximate rate per period with units",
  "seasonality_detected": true,
  "seasonal_pattern": "description of detected seasonal pattern, or null",
  "model_type": "holt_winters | prophet | linear_trend | logistic_growth",
  "interpretation": "plain-language forecast interpretation for the creator",
  "assumption_warnings": [],
  "data_quality_notes": [],
  "computation_source": "e2b | jupyter | guidance_only",
  "runnable_code": null,
  "retrieval_gaps": []
}
```

- `forecast`: array of date/value/bounds objects, one per period in the horizon. Periods match
  the granularity of the input data (daily data produces daily forecasts, monthly data produces
  monthly forecasts).
- `trend`: derived from the trend component. `rising` if slope > 0 with p < 0.1; `declining` if
  slope < 0 with p < 0.1; `flat` otherwise.
- `seasonality_detected`: true if a seasonal component is statistically present, false if tested
  and not found, null if not tested (insufficient data or guidance-only mode).
- `runnable_code`: null when a computation tool produced the result. Contains full Python code
  when `computation_source` is `guidance_only`.

## Fabrication rules

Inherited from `protocols/no-fabrication.md` and `shared/compute-engine.md` Section 4:
- Never invent forecast values, prediction intervals, or trend rates.
- Never present a linear extrapolation as a sophisticated model output.
- If the forecast horizon exceeds the length of the historical data, emit a warning about
  extrapolation risk.
- State all model assumptions (stationarity, no structural breaks, representative history).
- If the model detects a structural break (e.g., a viral video spike), flag it and note that
  the forecast may be unreliable beyond the break.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
