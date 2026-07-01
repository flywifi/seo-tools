---
file: shared/compute-engine.md
role: Source of truth for selecting and delegating to statistical computation tools. Read by every
  statistical atom (hypothesis-test, regression-analysis, forecast, ab-test, data-query) to determine
  which MCP server to invoke, how to fall back when a tool is unavailable, and how to label outputs.
load: when the request involves statistical testing, regression, forecasting, A/B analysis, or
  analytical SQL queries
---

# Compute Engine

## Purpose

Creator OS does not fabricate statistical results. Every number — p-value, confidence interval,
R-squared, effect size — must come from a real computation tool or be clearly labeled as guidance
only. This engine tells each statistical atom which tool to use, what to do when it is unavailable,
and how to label the result so the creator always knows how the number was produced.

---

## 1. Tool selection matrix

Match the task to the preferred MCP tool. If the preferred tool is connected, use it. If not,
follow the fallback chain in Section 2.

| Task | Preferred tool | Alternatives |
|---|---|---|
| Exact symbolic math, unit conversion | Wolfram Alpha | E2B Python, local code |
| Hypothesis tests (t-test, chi-square, ANOVA, Mann-Whitney U, proportion test) | stats-compass | E2B Python (scipy.stats), R statistics |
| Regression (linear, multiple, logistic, polynomial) | E2B Python (statsmodels / sklearn) | Jupyter notebook, R statistics |
| Time-series forecasting | E2B Python (statsmodels, Prophet) | Jupyter notebook |
| Large dataset SQL queries (CSV, Parquet, exports) | DuckDB analytics | E2B Python (pandas) |
| Monte Carlo / probabilistic modeling | MCS-MCP (Monte Carlo Simulator) | E2B Python |
| ML classification / clustering | scikit-learn MCP | E2B Python (sklearn) |
| Multi-step analysis requiring persistent state | Jupyter notebook | E2B Python with state |

When multiple tools can handle a task, prefer the one higher in the table — it is more specialized
and more likely to produce correct, labeled output.

---

## 2. Fallback chain

When the preferred tool is not connected, walk this chain top to bottom and use the first option
that is available.

### Level 1: specialized MCP connected
Use the preferred tool from the matrix. Label output `[computed via <tool_name>]`.

### Level 2: general compute MCP connected (E2B, Jupyter, R)
If the specialized tool is unavailable but a general compute environment is connected:
- Delegate the computation to the general tool.
- Write explicit, verifiable code (scipy.stats, statsmodels, sklearn, or base R).
- Label output `[computed via <tool_name>]`.

### Level 3: Wolfram Alpha available but specialized tool is not
If the task is reducible to symbolic math or a single statistical function that Wolfram Alpha
supports (e.g., a single t-test), delegate to Wolfram Alpha. Label output
`[computed via wolfram_alpha]`.

### Level 4: no computation MCP connected
- Do NOT compute the result using Claude's own arithmetic for anything beyond trivial addition or
  counting.
- Instead, produce **guidance-only output**: describe the test, the formula, the assumptions, and
  emit runnable Python or R code the user can execute locally.
- Label output `[guidance-only — no computation engine connected]`.
- Set `computation_source` to `"guidance_only"` in the output JSON.

### Special case: Claude's own arithmetic
If the atom only needs simple arithmetic (summing a column, computing a percentage from two known
numbers), Claude may compute it directly. Label the result
`[estimated — verify with computation tool]` and set `computation_source` to `"claude_arithmetic"`.
Never use Claude's own arithmetic for hypothesis tests, regression, forecasting, or any result that
involves iterative computation or floating-point precision.

---

## 3. Output labeling rules

Every statistical result must carry a provenance label. These labels are mandatory in all output
fields that contain a computed number.

| Source | Label |
|---|---|
| Result from a connected MCP tool | `[computed via <tool_name>]` |
| Claude's own simple arithmetic | `[estimated — verify with computation tool]` |
| No computation engine connected | `[guidance-only — no computation engine connected]` |

The `computation_source` field in every atom's output JSON must be set to one of:
`wolfram_alpha`, `e2b`, `stats_compass`, `r_statistics`, `jupyter`, `duckdb`, `mcs_mcp`,
`scikit_learn`, `claude_arithmetic`, `guidance_only`.

---

## 4. Anti-fabrication rules for statistics

These rules extend `protocols/no-fabrication.md` with statistics-specific constraints.

### Never fabricate
- p-values
- Confidence intervals
- R-squared or adjusted R-squared values
- Effect sizes (Cohen's d, eta-squared, odds ratios)
- Test statistics (t, F, chi-square, U, z)
- Regression coefficients
- Forecast point estimates or prediction intervals

### Never round intermediate results
Pass full precision through the computation chain. Round only in the final user-facing
interpretation, and state the rounding (e.g., "p = 0.0312, rounded to p = 0.03").

### State assumptions
If a test requires assumptions (normality, homogeneity of variance, independence), state them
explicitly. If an assumption is violated or untested, flag it in the output:
`"assumption_warnings": ["normality not verified — consider Mann-Whitney U as alternative"]`.

### Sample size warnings
- If n < 30 for a parametric test, emit a warning:
  `"sample_size_warning": "n = <value> is below 30; parametric test assumptions may not hold.
  Consider a non-parametric alternative."`.
- If n < 5, refuse to run a parametric test and suggest descriptive statistics only.
- For proportion tests, check that np >= 10 and n(1-p) >= 10; flag if violated.

### Multiple comparisons
If running more than one hypothesis test on the same dataset, warn about family-wise error rate
and suggest Bonferroni or Holm correction. Do not silently apply corrections — state them.

---

## 5. Connector integration

The compute engine reads connector availability from `shared/connectors/connectors.json` and
`creator-os-config.local.json`. Each statistical MCP tool has a connector entry with an `enabled`
flag. The `configure-stats-tool` atom writes these flags.

When an atom starts:
1. Read the connector registry to determine which compute tools are enabled.
2. Match the task to the tool selection matrix (Section 1).
3. Check whether the preferred tool's connector is enabled.
4. If not, walk the fallback chain (Section 2).
5. Label the output (Section 3).

Do not prompt the user to configure tools mid-analysis. If no tool is available, produce
guidance-only output and note in `retrieval_gaps` which tool would improve the result.
