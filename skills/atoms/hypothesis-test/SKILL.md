---
name: hypothesis-test
atom: true
description: "Performs statistical hypothesis testing (t-test, chi-square, ANOVA, Mann-Whitney U, proportion test) on provided data using connected statistical MCP tools. Returns test statistic, p-value, effect size, and plain-language interpretation for the creator. Do NOT use for regression modeling (use regression-analysis) or time-series forecasting (use forecast)."
load:
  - shared/compute-engine.md
  - protocols/no-fabrication.md
  - protocols/research-citation.md
---

# hypothesis-test

Perform a statistical hypothesis test on creator-supplied data and return a structured result with
test statistic, p-value, effect size, confidence interval, and a plain-language interpretation
anchored to the creator's content context.

## Purpose

The creator's content decisions benefit from statistical rigor — knowing whether a difference in
watch time, CTR, or engagement rate is meaningful rather than noise. This atom takes a hypothesis,
selects the correct test, delegates computation to a connected MCP tool (via
`shared/compute-engine.md`), and translates the result into actionable creator language. It never
fabricates a p-value or effect size.

## When to invoke

- "Is the difference in watch time between these two video formats significant?"
- "Did my CTR actually improve after changing thumbnails?"
- "Are engagement rates different across these three content pillars?"
- "Is there a real difference in subscriber conversion between Shorts and long-form?"
- "Test whether my posting time matters for views."
- Invoke directly or from a spoke that needs statistical validation of a comparison.

## Do NOT use for

- Regression modeling — fitting a line or curve to data. Use `regression-analysis`.
- Time-series forecasting — projecting future metrics. Use `forecast`.
- A/B test design or analysis with experiment structure. Use `ab-test`.
- Running SQL queries over data files. Use `data-query`.
- Descriptive statistics only (mean, median, counts) without a hypothesis. Compute inline or
  use `data-query`.

## Inputs

```json
{
  "test_type": "t_test_independent | t_test_paired | chi_square | anova_one_way | mann_whitney_u | proportion_test",
  "data": {},
  "alpha": 0.05,
  "hypothesis": "string describing what the creator expects or wants to test",
  "data_source": "string describing where the data came from (e.g., YouTube Studio export, manual entry)"
}
```

- `test_type`: required. The statistical test to perform. If the user describes the comparison but
  does not name a test, infer the correct test from the data structure:
  - Two independent groups, continuous metric → `t_test_independent`
  - Same group measured twice → `t_test_paired`
  - Counts in categories → `chi_square`
  - Three or more independent groups, continuous metric → `anova_one_way`
  - Two independent groups, non-normal or ordinal data → `mann_whitney_u`
  - Comparing proportions (e.g., CTR) → `proportion_test`
- `data`: required. Structure depends on test type:
  - t-test (independent): `{ "group_a": [numbers], "group_b": [numbers] }`
  - t-test (paired): `{ "before": [numbers], "after": [numbers] }`
  - chi-square: `{ "observed": [[counts]], "labels": { "rows": [...], "cols": [...] } }`
  - ANOVA: `{ "groups": { "group_name": [numbers], ... } }`
  - Mann-Whitney U: `{ "group_a": [numbers], "group_b": [numbers] }`
  - Proportion test: `{ "successes": [n1, n2], "totals": [N1, N2] }`
- `alpha`: optional, defaults to 0.05. Significance level.
- `hypothesis`: required. Plain-language description of what is being tested.
- `data_source`: required. Attribution for the data — where it came from and when.

## Procedure

### Step 1: validate test type and data

Check that `test_type` matches the data structure. If there is a mismatch (e.g., user requests
`anova_one_way` but provides only two groups), either:
- Suggest the correct test and proceed with confirmation, or
- Downgrade to the appropriate test and note the change in the output.

Check sample sizes per group. If any group has n < 5, refuse parametric tests and recommend
descriptive statistics. If any group has n < 30, emit the sample size warning from
`shared/compute-engine.md` Section 4.

Check for assumption violations where detectable:
- Paired t-test: verify group lengths match.
- Chi-square: verify no expected cell count < 5 (if computable from marginals).
- ANOVA: note that homogeneity of variance is assumed but not tested without a computation tool.

### Step 2: check compute-engine tool selection

Read `shared/compute-engine.md` Section 1 to identify the preferred tool for hypothesis testing:
stats-compass (preferred), E2B Python with scipy.stats (alternative), R statistics (alternative).

Check connector availability. Set `computation_source` based on which tool is connected.

### Step 3: delegate computation

Send the test to the selected computation tool:
- Provide the raw data arrays, test type, and alpha level.
- Request: test statistic, p-value, confidence interval, and effect size.
- For stats-compass: use the tool's native test functions.
- For E2B / R: generate and execute code (e.g., `scipy.stats.ttest_ind(group_a, group_b)`).

Do not round intermediate values. Pass full precision from the tool's output.

### Step 4: fallback to guidance-only if no tool

If no computation tool is connected (Level 4 in compute-engine fallback chain):
- Set `computation_source` to `"guidance_only"`.
- Set `conclusion` to `"insufficient_data"` (since no computation was performed).
- Emit runnable Python code using scipy.stats that the user can execute locally.
- Include all input data in the code so it is self-contained.
- Label the output `[guidance-only — no computation engine connected]`.

### Step 5: interpret result in creator context

Translate the statistical result into plain language anchored to the creator's hypothesis:
- If `p_value < alpha`: "The difference is statistically significant. [Restate in creator terms,
  e.g., 'Watch time for tutorial-style videos is meaningfully higher than for vlogs.']"
- If `p_value >= alpha`: "The difference is not statistically significant at the {alpha} level.
  The observed difference could be due to chance."
- Always include effect size interpretation: small, medium, or large (using Cohen's conventions
  for the test type).
- Always caveat: statistical significance does not imply practical significance. State whether
  the effect size is large enough to warrant a content strategy change.

## Output

```json
{
  "test_type": "t_test_independent | t_test_paired | chi_square | anova_one_way | mann_whitney_u | proportion_test",
  "test_statistic": 2.41,
  "p_value": 0.0231,
  "confidence_interval": [0.8, 4.2],
  "effect_size": 0.54,
  "effect_size_label": "medium (Cohen's d)",
  "alpha": 0.05,
  "conclusion": "reject_null | fail_to_reject | insufficient_data",
  "interpretation": "plain-language interpretation anchored to the creator's hypothesis",
  "assumption_warnings": [],
  "sample_size_warning": null,
  "computation_source": "wolfram_alpha | e2b | stats_compass | r_statistics | guidance_only",
  "runnable_code": "null unless guidance_only — then contains self-contained Python code",
  "retrieval_gaps": []
}
```

- `conclusion`: `reject_null` when `p_value < alpha`; `fail_to_reject` when `p_value >= alpha`;
  `insufficient_data` when data is too sparse or no computation tool is connected.
- `interpretation`: always present, always in creator language, never in jargon-only form.
- `assumption_warnings`: array of strings. Empty if all assumptions are met or untestable.
- `runnable_code`: null when a computation tool produced the result. Contains full Python code
  when `computation_source` is `guidance_only`.
- `retrieval_gaps`: notes on anything that could not be computed or verified.

## Fabrication rules

Inherited from `protocols/no-fabrication.md` and `shared/compute-engine.md` Section 4:
- Never invent p-values, confidence intervals, effect sizes, or test statistics.
- Never round intermediate results.
- State all assumptions. Flag violations.
- Emit sample size warnings when n < 30 for parametric tests.
- If no computation tool is connected, produce guidance-only output — never estimate a p-value.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
