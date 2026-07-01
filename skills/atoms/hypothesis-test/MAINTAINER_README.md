---
file: skills/atoms/hypothesis-test/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for hypothesis-test so it stays stable under iteration.
---

# hypothesis-test: Maintainer README

## Purpose

hypothesis-test performs statistical hypothesis tests (t-test, chi-square, ANOVA, Mann-Whitney U,
proportion test) on creator-supplied data via connected computation tools. It returns a structured
result containing the test statistic, p-value, effect size, confidence interval, and a plain-language
interpretation written for a creator audience — not a statistics textbook. Its job ends at result
delivery. It does not do regression modeling (use regression-analysis) or project future values
(use forecast). It loads `shared/compute-engine.md`, `protocols/no-fabrication.md`, and
`protocols/research-citation.md`.

## Non-negotiable invariants

1. Shared: references `shared/method.md` in procedure; self-checks against
   `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` (no invented statistics,
   no fabricated p-values, no fake effect sizes) and `protocols/formatting-metadata.md`
   (ranges use "to").
2. Never fabricate p-values, test statistics, effect sizes, or confidence intervals. If no
   computation tool is connected, return guidance-only output with runnable Python code — never
   produce numeric results from the model's own generation.
3. Must emit a `sample_size_warning` when n < 30 for any group in a parametric test (t-test,
   ANOVA). Small samples invalidate normal-approximation assumptions.
4. Guidance-only mode (no computation tool connected) must be clearly labeled with
   `computation_source: "guidance_only"` in the output. The output must include runnable
   Python code the creator can execute independently.
5. `test_type` must match the data structure (two independent groups for independent t-test,
   categorical counts for chi-square, 3+ groups for ANOVA). If the requested test does not
   match the data shape, downgrade to the appropriate test with an explicit note explaining
   the change.
6. `alpha` defaults to 0.05 when not supplied by the caller. The chosen alpha must appear in
   the output alongside the p-value for correct interpretation.

## Known failure modes

1. Hallucinated p-values when no computation tool is connected: the model generates
   plausible-looking numeric results instead of switching to guidance-only mode. Mitigation:
   hard gate on `computation_source` — if not `"connected"`, numeric fields must be null.
2. Wrong test type selected for data shape: e.g., running a t-test on 4 groups or chi-square
   on continuous data. Mitigation: validate data shape before test execution; downgrade with
   explicit note.
3. Missing sample size warning on small groups: parametric tests run on n < 30 without
   flagging reduced statistical power. Mitigation: mandatory pre-check populates
   `sample_size_warning` before any parametric computation.
4. Silent rounding of intermediate values: effect sizes or p-values rounded mid-calculation,
   producing inaccurate final results. Mitigation: request full-precision output from the
   computation tool; round only at the display layer (4 decimal places for p-values, 3 for
   effect sizes).

## Regression cases to preserve

1. **t-test with adequate sample** (eval hypothesis-test-ttest-basic): two groups of watch-time
   data, each n >= 30. Expected: `test_statistic`, `p_value`, `effect_size`, `conclusion`, and
   `interpretation` all populated with computation-derived values. No sample size warning.

2. **No computation tool connected** (eval hypothesis-test-no-tool): same input but
   `computation_source` set to `"guidance_only"`. Expected: `runnable_code` populated with
   executable Python, `conclusion` set to `"insufficient_data"`, numeric fields null.

3. **Sample size under 5** (eval hypothesis-test-small-sample): two groups each with n < 5.
   Expected: `sample_size_warning` populated, `conclusion` of `"insufficient_data"`, parametric
   test refused, output recommends descriptive statistics instead.

4. **Mismatched test type and data shape** (eval hypothesis-test-chi-square): chi-square test
   requested with proper categorical observed counts. Expected: `test_statistic`, `p_value`,
   and `effect_size_label` all populated; test type preserved because data shape matches.

## Update checklist

1. Edit the relevant section in SKILL.md or this file.
2. If the output contract changes (new fields, renamed fields, type changes), update
   `evals/evals.json` to reflect the new expected fields.
3. If an engine is added or removed, update `engines_required` in SKILL.md frontmatter and
   verify the engine file exists in `shared/`.
4. Run `python3 tools/sync_check.py` — must exit 0 before committing.
