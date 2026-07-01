# regression-analysis — Maintainer Reference

## What this atom does

Fits regression models (linear, multiple, logistic, polynomial) to creator-supplied data by
delegating computation to E2B, Jupyter, or R via `shared/compute-engine.md`. Returns coefficients,
R-squared, p-values per predictor, residual diagnostics, and a plain-language interpretation. Falls
back to guidance-only output (runnable Python code) when no computation tool is connected.

## Invariants

1. `computation_source` is always set. Never null, never omitted.
2. `coefficients`, `r_squared`, and `p_values` are never fabricated. If no computation tool is
   connected, they are null and `computation_source` is `guidance_only`.
3. `polynomial_degree` never exceeds 5. Requests for higher degrees are capped with a warning
   about overfitting risk.

## Failure modes

1. **No computation tool connected.** Guidance-only output with runnable statsmodels/sklearn code.
   Labeled `[guidance-only — no computation engine connected]`.
2. **Insufficient sample size.** If n < predictors + 10, a warning is emitted. If n < 5, the
   atom refuses to fit and recommends descriptive statistics.
3. **Model type mismatch.** If user requests `linear` but provides multiple predictors, the atom
   upgrades to `multiple` and notes the change.

## Regression cases (map to evals/evals.json)

| # | Case | Eval ID |
|---|---|---|
| 1 | Simple linear regression with tool connected | ra-001 |
| 2 | Logistic regression returns odds ratios | ra-002 |
| 3 | No computation tool — guidance-only output | ra-003 |
| 4 | Polynomial degree capped at 5 | ra-004 |

## Update checklist

1. If `shared/compute-engine.md` tool matrix changes, update Step 2 in SKILL.md.
2. If statsmodels or sklearn API changes, update the generated code in Step 4.
3. Re-run all evals after any change.
4. Run `python3 tools/sync_check.py`.
