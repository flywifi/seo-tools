# forecast — Maintainer Reference

## What this atom does

Projects future values of a content metric using time-series methods (Holt-Winters, Prophet,
linear trend). Delegates computation to E2B or Jupyter via `shared/compute-engine.md`. Returns
point forecasts with prediction intervals, trend direction, and seasonality detection. Loads
`shared/seo-intelligence-engine.md` for seasonal context.

## Invariants

1. `forecast` array entries always contain `date`, `predicted_value`, `lower_bound`, and
   `upper_bound`. No field is ever null when a computation tool produced the result.
2. `seasonality_detected` is null — not false — when the atom cannot test for seasonality
   (insufficient data or guidance-only mode). False means tested and not found.
3. Prediction intervals widen with forecast horizon. The atom never produces constant-width
   intervals across a multi-period forecast.

## Failure modes

1. **Insufficient historical data.** If data has fewer than 10 points (trend) or fewer than 2
   full cycles (seasonal), the atom emits a warning and either degrades to trend-only or returns
   `insufficient_data`.
2. **Structural break in data.** A viral spike or channel pivot makes history non-representative.
   The atom flags this but cannot automatically correct for it.
3. **No computation tool connected.** Guidance-only mode. The atom computes a simple linear trend
   labeled `[estimated]` and emits Python code for a proper forecast.

## Regression cases (map to evals/evals.json)

| # | Case | Eval ID |
|---|---|---|
| 1 | Monthly views forecast with yearly seasonality | fc-001 |
| 2 | Insufficient data triggers warning | fc-002 |
| 3 | No computation tool — guidance-only with trend estimate | fc-003 |

## Update checklist

1. If `shared/seo-intelligence-engine.md` seasonal patterns change, update Step 5 interpretation.
2. If `shared/compute-engine.md` tool matrix changes, update Step 2.
3. Re-run all evals after any change.
4. Run `python3 tools/sync_check.py`.
