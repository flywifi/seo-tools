---
name: regression-analysis
atom: true
description: "Fits regression models (linear, multiple, logistic, polynomial) to creator data. Returns coefficients, R-squared, p-values, and prediction intervals. Do NOT use for hypothesis testing without a regression model (use hypothesis-test) or time-series forecasting (use forecast)."
load:
  - shared/compute-engine.md
  - protocols/no-fabrication.md
---

# regression-analysis

Fit a regression model to creator-supplied data and return coefficients, goodness-of-fit metrics,
p-values per predictor, residual diagnostics, and a plain-language interpretation that connects the
model to the creator's content decisions.

## Purpose

The creator sometimes needs to understand relationships in her data — does video length predict
watch time? Do thumbnail brightness and title word count jointly predict CTR? This atom fits the
appropriate regression model, delegates computation to a connected MCP tool (via
`shared/compute-engine.md`), and translates coefficients into actionable insight. It never
fabricates an R-squared or coefficient.

## When to invoke

- "Does video length predict average view duration?"
- "What predicts my CTR — thumbnail type, title length, or posting day?"
- "Fit a model to my revenue data."
- "Is there a relationship between description length and search impressions?"
- "Predict my engagement rate from these variables."
- Invoke directly or from a spoke that needs regression output.

## Do NOT use for

- Hypothesis testing without a regression model — comparing group means or testing independence.
  Use `hypothesis-test`.
- Time-series forecasting with temporal structure — projecting future views or revenue over time.
  Use `forecast`.
- A/B test analysis — comparing two variants. Use `ab-test`.
- SQL-style queries over data files. Use `data-query`.

## Inputs

```json
{
  "model_type": "linear | multiple | logistic | polynomial",
  "dependent_var": "string — the outcome variable name (e.g., 'avg_view_duration')",
  "independent_vars": ["string — predictor variable names"],
  "data_description": "string — what the data represents and its source",
  "data_source": "csv_path | inline_values",
  "polynomial_degree": 2
}
```

- `model_type`: required. Determines the fitting method:
  - `linear`: single predictor, continuous outcome. OLS.
  - `multiple`: two or more predictors, continuous outcome. OLS.
  - `logistic`: binary outcome (e.g., did a video cross 10K views? yes/no). Logistic regression.
  - `polynomial`: single predictor, continuous outcome, non-linear relationship. Polynomial OLS.
- `dependent_var`: required. The column name or label for the outcome variable.
- `independent_vars`: required. One or more predictor variable names.
- `data_description`: required. Context about what the data represents.
- `data_source`: required. Either a path to a CSV file or inline data values.
- `polynomial_degree`: optional, defaults to 2. Only used when `model_type` is `polynomial`.
  Maximum value: 5 (higher degrees risk overfitting on typical creator datasets).

## Procedure

### Step 1: validate model type and data

Check that `model_type` aligns with the data structure:
- `linear`: exactly 1 independent variable and a continuous dependent variable.
- `multiple`: 2 or more independent variables and a continuous dependent variable.
- `logistic`: dependent variable must be binary (0/1, yes/no, true/false).
- `polynomial`: exactly 1 independent variable and a continuous dependent variable.

Check sample size:
- If n < number of predictors + 10, emit a warning about insufficient observations for reliable
  regression.
- If n < 5, refuse to fit and suggest descriptive statistics only.

If `data_source` is a CSV path, note the path for the computation tool to load. If inline values,
structure them for the computation tool.

### Step 2: check compute-engine tool selection

Read `shared/compute-engine.md` Section 1. Preferred tools for regression: E2B Python with
statsmodels or sklearn (preferred), Jupyter notebook (alternative), R statistics (alternative).

Check connector availability. Set `computation_source` accordingly.

### Step 3: delegate computation

Send the regression task to the selected computation tool:
- For E2B / Jupyter: generate Python code using statsmodels (for OLS with full diagnostics) or
  sklearn (for logistic / polynomial).
- Request: coefficients, standard errors, p-values per coefficient, R-squared, adjusted R-squared,
  residual summary (mean, std, min, max of residuals), and F-statistic (for OLS models).
- For logistic: request coefficients, odds ratios, p-values, pseudo R-squared, and
  classification accuracy on the training data.

Do not round intermediate values.

### Step 4: fallback to guidance-only if no tool

If no computation tool is connected:
- Set `computation_source` to `"guidance_only"`.
- Emit runnable Python code using statsmodels / sklearn that the user can execute locally.
- Include data loading instructions (from CSV path or inline).
- Label output `[guidance-only — no computation engine connected]`.

### Step 5: interpret results in creator context

Translate regression output into plain language:
- State the relationship direction and strength for each significant predictor.
- Interpret R-squared: "This model explains approximately {R-squared * 100}% of the variation
  in {dependent_var}."
- Flag non-significant predictors (p > alpha) and suggest they may not be useful for prediction.
- For logistic: interpret odds ratios ("for each additional minute of video length, the odds of
  crossing 10K views increase by {odds_ratio}x").
- Caveat: correlation is not causation. A regression shows association, not that changing a
  predictor will cause the outcome to change.

## Output

```json
{
  "model_type": "linear | multiple | logistic | polynomial",
  "coefficients": {
    "intercept": 12.5,
    "video_length_min": 0.83
  },
  "standard_errors": {
    "intercept": 2.1,
    "video_length_min": 0.19
  },
  "p_values": {
    "intercept": 0.0001,
    "video_length_min": 0.0003
  },
  "r_squared": 0.62,
  "adjusted_r_squared": 0.59,
  "f_statistic": 18.7,
  "f_p_value": 0.0003,
  "residual_summary": {
    "mean": 0.0,
    "std": 1.42,
    "min": -3.1,
    "max": 2.8
  },
  "interpretation": "plain-language interpretation connecting coefficients to creator decisions",
  "assumption_warnings": [],
  "sample_size_warning": null,
  "computation_source": "e2b | jupyter | r_statistics | guidance_only",
  "runnable_code": null,
  "retrieval_gaps": []
}
```

- For logistic models: `r_squared` is replaced by `pseudo_r_squared`, and `odds_ratios` is added
  alongside `coefficients`.
- `residual_summary`: always present for OLS models. Helps the creator (or a follow-up analysis)
  assess model fit.
- `runnable_code`: null when a computation tool produced the result. Contains full Python code
  when `computation_source` is `guidance_only`.

## Fabrication rules

Inherited from `protocols/no-fabrication.md` and `shared/compute-engine.md` Section 4:
- Never invent coefficients, R-squared, p-values, or standard errors.
- Never round intermediate results.
- State all assumptions (linearity, independence, homoscedasticity, normality of residuals for OLS;
  independence of observations for logistic).
- If the model shows signs of overfitting (polynomial degree too high, R-squared near 1.0 on small
  data), flag it explicitly.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
