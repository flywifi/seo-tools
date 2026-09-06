---
name: ab-test
atom: true
description: "Designs A/B test experiments and analyzes results for content optimization: thumbnail variants, title variants, posting time experiments. Do NOT use for general hypothesis testing without A/B context (use hypothesis-test)."
load:
  - shared/compute-engine.md
  - shared/platform-engine.md
  - protocols/no-fabrication.md
---

# ab-test

Design or analyze an A/B test experiment for content optimization. In design mode, compute the
required sample size, estimated duration, and statistical power. In analyze mode, determine the
winner, p-value, effect size, and a plain-language recommendation.

## Purpose

The creator runs informal experiments constantly — trying different thumbnails, title structures,
posting times, and content formats. This atom brings statistical rigor to those experiments: it
calculates how much data is needed to detect a meaningful difference (design mode) and whether the
observed difference is real or noise (analyze mode). It uses `shared/platform-engine.md` for
platform-specific metric definitions and baselines.

## When to invoke

- "How many views do I need to test two thumbnails?"
- "Design an A/B test for my title format."
- "Which thumbnail won — here are the results."
- "Is this CTR difference significant between my two posting times?"
- "How long should I run a thumbnail test on YouTube?"
- Invoke directly or from a spoke that needs experiment design or analysis.

## Do NOT use for

- General hypothesis testing without A/B experiment structure — comparing historical groups or
  testing independence. Use `hypothesis-test`.
- Regression modeling — understanding predictor relationships. Use `regression-analysis`.
- Forecasting future metrics. Use `forecast`.
- YouTube's built-in A/B test feature analysis — this atom handles custom experiments; for
  YouTube's native "Test and Compare" feature, interpret the platform's own results directly.

## Inputs

```json
{
  "mode": "design | analyze",
  "metric": "ctr | avd | engagement_rate | conversion_rate",
  "variants": [
    {
      "name": "variant_a",
      "description": "original thumbnail — close-up face with text overlay"
    },
    {
      "name": "variant_b",
      "description": "new thumbnail — wide shot of finished room, no text"
    }
  ],
  "baseline_rate": 0.06,
  "minimum_detectable_effect": 0.05,
  "confidence_level": 0.95,
  "power": 0.8,
  "results": null
}
```

### Design mode fields
- `mode`: `"design"`.
- `metric`: required. The metric being optimized.
- `variants`: required. At least 2 variants with names and descriptions.
- `baseline_rate`: required for design. The current baseline metric value (e.g., CTR = 0.06).
- `minimum_detectable_effect`: optional, defaults to 0.05. The smallest relative improvement
  worth detecting (5% = a lift from 6.0% CTR to 6.3% CTR).
- `confidence_level`: optional, defaults to 0.95.
- `power`: optional, defaults to 0.8.
- `results`: null in design mode.

### Analyze mode fields
- `mode`: `"analyze"`.
- `metric`: required.
- `variants`: required, with the same structure as design mode.
- `results`: required. Observed data per variant:
  ```json
  {
    "variant_a": { "impressions": 5000, "successes": 300 },
    "variant_b": { "impressions": 5000, "successes": 345 }
  }
  ```
- `confidence_level`: optional, defaults to 0.95.

## Procedure

### Step 1: validate inputs

**Design mode:**
- Check that `baseline_rate` is between 0 and 1 (exclusive).
- Check that `minimum_detectable_effect` is positive and reasonable (warn if > 0.50, as detecting
  a 50%+ lift rarely requires a formal test).
- Check that at least 2 variants are provided.

**Analyze mode:**
- Check that `results` contains data for every variant listed in `variants`.
- Check that impressions and successes are non-negative integers.
- Check that successes <= impressions for each variant.

### Step 2: check compute-engine tool selection

Read `shared/compute-engine.md` Section 1. For sample size calculation and proportion tests:
stats-compass (preferred), E2B Python with statsmodels (alternative), Wolfram Alpha (for simple
power calculations).

Check connector availability. Set `computation_source` accordingly.

### Step 3: compute (design mode)

Calculate the required sample size per variant using the formula for a two-proportion z-test:
- Inputs: baseline_rate, minimum_detectable_effect, alpha = 1 - confidence_level, power.
- Output: n per variant.

Estimate duration:
- Use the creator's typical daily impressions (from `shared/platform-engine.md` metric benchmarks
  or user-supplied data) to estimate how many days are needed to reach n per variant.
- If daily impressions are unknown, output sample_size_per_variant and note that duration cannot
  be estimated without impression volume.

### Step 4: compute (analyze mode)

Run a two-proportion z-test (or chi-square test of independence for > 2 variants):
- Compute the test statistic, p-value, and confidence interval for the difference in proportions.
- Compute effect size (Cohen's h for two proportions).
- Determine winner: the variant with the higher success rate, if p < alpha.

For continuous metrics (avd, engagement_rate with raw values rather than counts):
- Use a t-test or Mann-Whitney U instead. Delegate to `hypothesis-test` internally if needed.

### Step 5: fallback to guidance-only if no tool

If no computation tool is connected:
- Produce the sample size formula and a runnable Python code block.
- For analyze mode: emit the test code with the user's data embedded.
- Set `computation_source` to `"guidance_only"`.

### Step 6: interpret and recommend

**Design mode:**
- State the sample size clearly: "You need approximately {n} impressions per variant."
- State the estimated duration if computable.
- Recommend how to split traffic (if applicable to the platform).

**Analyze mode:**
- State the winner or that no significant difference was found.
- Interpret effect size: is the lift practically meaningful for the creator's scale?
- Recommend next steps: "Roll out variant B as your default thumbnail" or "The difference is
  too small to act on — consider testing a more distinct variant."
- Reference `shared/platform-engine.md` for context on what constitutes a meaningful CTR lift
  on the relevant platform.

## Output (design mode)

```json
{
  "mode": "design",
  "metric": "ctr",
  "sample_size_per_variant": 3842,
  "total_sample_size": 7684,
  "estimated_duration_days": 15,
  "power": 0.8,
  "minimum_detectable_effect": 0.05,
  "test_plan": "plain-language description of how to run the test",
  "computation_source": "stats_compass | e2b | wolfram_alpha | guidance_only",
  "retrieval_gaps": []
}
```

## Output (analyze mode)

```json
{
  "mode": "analyze",
  "metric": "ctr",
  "winner": "variant_a | variant_b | no_significant_difference",
  "variant_results": {
    "variant_a": { "rate": 0.060, "impressions": 5000, "successes": 300 },
    "variant_b": { "rate": 0.069, "impressions": 5000, "successes": 345 }
  },
  "p_value": 0.0412,
  "confidence_interval_difference": [0.001, 0.017],
  "effect_size": 0.037,
  "effect_size_label": "small (Cohen's h)",
  "recommendation": "plain-language recommendation for the creator",
  "computation_source": "stats_compass | e2b | wolfram_alpha | guidance_only",
  "retrieval_gaps": []
}
```

## Fabrication rules

Inherited from `protocols/no-fabrication.md` and `shared/compute-engine.md` Section 4:
- Never invent p-values, sample sizes, or effect sizes.
- Never claim a winner without a computation to support it.
- If the test is underpowered (observed n < required n), flag it: "This test may be underpowered.
  The result is directional but not conclusive."
- Never round intermediate results.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
