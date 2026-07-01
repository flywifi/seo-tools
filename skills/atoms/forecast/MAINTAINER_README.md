---
file: skills/atoms/forecast/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for forecast so it stays stable under iteration.
---

# forecast: Maintainer README

## Purpose

The forecast atom produces time-series forecasts for creator metrics — subscriber
growth, view counts, revenue, engagement rates — using ARIMA, exponential smoothing,
or linear projection via connected computation tools. It returns point forecasts,
confidence intervals, model fit diagnostics, and a plain-language trend summary
tailored to the moody-vintage home decor and DIY niche. Its job ends at forecast
delivery — it does not test hypotheses (use hypothesis-test) or fit regression
models (use regression-analysis).

## Non-negotiable invariants

1. References the pipeline (`shared/method.md`); self-checks against
   `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
   `protocols/formatting-metadata.md`.
2. All point forecasts must include upper and lower confidence bounds — a bare
   point estimate is never acceptable output.
3. Forecast horizon must not exceed 2x the input data length; requests beyond
   that threshold produce a warning and a truncated horizon.
4. Minimum data-point requirements: 12 for ARIMA, 6 for exponential smoothing,
   3 for linear projection. Requests that fall short trigger a fallback to the
   next simpler model with an explicit note.
5. Never fabricate forecast values, confidence bounds, or model diagnostics.
   Null and flag instead.
6. Model selection rationale must be stated in every response.
7. When no computation tool is connected, output must be clearly labeled
   "guidance-only" and include runnable code the creator can execute elsewhere.

## Known failure modes

1. Forecast delivered without confidence bounds, presenting a point estimate as
   certain — violates invariant 2.
2. Horizon set too long relative to data length, producing misleading precision
   that overstates predictability.
3. Seasonal patterns missed when the caller does not specify periodicity and the
   atom does not probe for it.
4. Trend breaks or regime changes in the data (e.g., a viral video spike) ignored,
   causing the model to project from a distorted baseline.

## Regression cases to preserve

1. 24-month subscriber data with a clear uptrend produces an ARIMA forecast with
   upper and lower confidence bounds and model fit diagnostics.
2. A 4-point data series requesting ARIMA triggers a fallback to linear projection
   with an explicit fallback note explaining the downgrade.
3. A 12-point data series with a 30-period horizon produces a horizon warning and
   truncates the forecast to the 2x maximum (24 periods).
4. No computation tool connected returns guidance-only output with runnable code
   and a clear "guidance-only" label.

## Update checklist

1. Edit the canonical file (`skills/atoms/forecast/SKILL.md` or engine references).
2. Run evals: verify all cases in `evals/evals.json` still pass.
3. Confirm confidence bounds appear in every forecast output path.
4. Check that fallback and horizon-warning paths still trigger correctly.
5. Update `STATE.md` if a phase boundary was crossed.
6. Run `python3 tools/sync_check.py` — must exit 0.
