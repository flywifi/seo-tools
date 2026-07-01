---
file: skills/atoms/regression-analysis/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for regression-analysis so it stays stable under iteration.
---

# regression-analysis: Maintainer README

## Purpose

regression-analysis fits regression models (linear, multiple linear, logistic) to creator-supplied
data via connected computation tools. It returns coefficients, R-squared (or pseudo R-squared for
logistic models, labeled as such), a residual summary, and a plain-language interpretation written
for a creator audience. Its job ends at model results — it does not test hypotheses about group
differences (use hypothesis-test) or project future values beyond the observed range (use forecast).
It loads `shared/compute-engine.md`, `protocols/no-fabrication.md`, and
`protocols/research-citation.md`.

## Non-negotiable invariants

1. Shared: references `shared/method.md` in procedure; self-checks against
   `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` (no invented coefficients,
   no fabricated R-squared values, no fake residual statistics) and
   `protocols/formatting-metadata.md` (ranges use "to").
2. Coefficients come from the computation engine only — never fabricated by the model. If no
   computation tool is connected, return guidance-only output with runnable Python code. Numeric
   coefficient fields must be null in guidance-only mode.
3. R-squared must be between 0 and 1 (inclusive). Any computed value outside this range
   indicates a computation error and must be flagged, not silently clamped.
4. Logistic regression must use pseudo R-squared (McFadden or equivalent) and label it
   explicitly as `"pseudo_r_squared"` in the output — never present it as standard R-squared.
5. Multicollinearity warnings must be emitted when any predictor's VIF exceeds 5 in multiple
   regression. The warning must name the affected predictors and their VIF values.
6. Guidance-only mode (no computation tool connected) must be clearly labeled with
   `computation_source: "guidance_only"` in the output. The output must include runnable
   Python code the creator can execute independently.
7. Interpretation must not confuse correlation with causation. Plain-language summaries use
   "associated with" or "predicts," never "causes" or "drives."

## Known failure modes

1. Fabricated coefficients when no computation tool is connected: the model generates
   plausible-looking regression coefficients instead of switching to guidance-only mode.
   Mitigation: hard gate on `computation_source` — if not `"connected"`, all numeric model
   fields must be null.
2. Presenting R-squared without context of sample size: a high R-squared on n = 8 is
   misleading. Mitigation: always report sample size alongside R-squared; emit a warning
   when n < 20 for linear models.
3. Ignoring multicollinearity in multiple regression: correlated predictors inflate
   coefficient standard errors and make individual coefficients uninterpretable. Mitigation:
   compute VIF for all predictors when model type is multiple linear; warn when VIF > 5.
4. Confusing correlation with causation in interpretation: the plain-language summary implies
   that changing a predictor will cause the outcome to change. Mitigation: hard rule in
   interpretation template — use "associated with" language only.

## Regression cases to preserve

1. **Simple linear regression with adequate data** (eval regression-linear-basic): views
   regressed on upload hour, n >= 20. Expected: `coefficients` (intercept + slope), `r_squared`
   between 0 and 1, `residual_summary` populated, `interpretation` in plain language. No
   multicollinearity warning (single predictor).
2. **Multiple regression with correlated predictors** (eval regression-multiple-vif): views
   regressed on title length, description length, and tag count where title length and
   description length are correlated. Expected: `multicollinearity_warning` populated naming
   the correlated predictors, VIF values reported, coefficients flagged as potentially unstable.
3. **Logistic regression for viral threshold** (eval regression-logistic): binary outcome
   (viral vs. not viral) regressed on watch time and like ratio. Expected: `pseudo_r_squared`
   labeled as such, logistic `coefficients` (log-odds), `interpretation` explains probability
   direction without causal language.
4. **No computation tool connected** (eval regression-no-tool): same linear regression input
   but `computation_source` set to `"guidance_only"`. Expected: `guidance_only` flag set,
   `runnable_code` populated with executable Python, all numeric model fields null.

## Update checklist

1. Edit the relevant section in SKILL.md or this file.
2. If the output contract changes (new fields, renamed fields, type changes), update
   `evals/evals.json` to reflect the new expected fields.
3. If an engine is added or removed, update `engines_required` in SKILL.md frontmatter and
   verify the engine file exists in `shared/`.
4. Run `python3 tools/sync_check.py` — must exit 0 before committing.
