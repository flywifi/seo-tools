# ab-test — Maintainer Reference

## What this atom does

Designs A/B test experiments (computing sample size, duration, power) and analyzes results
(determining winner, p-value, effect size) for content optimization experiments. Delegates
computation via `shared/compute-engine.md` and references `shared/platform-engine.md` for
platform-specific metric context.

## Invariants

1. Design mode always outputs `sample_size_per_variant` and `total_sample_size`. If duration
   cannot be estimated (no impression volume data), `estimated_duration_days` is null with
   an explanation — never fabricated.
2. Analyze mode never declares a winner without a computed p-value below alpha. If
   `computation_source` is `guidance_only`, `winner` is `no_significant_difference` with a note
   that results need computation to confirm.
3. `minimum_detectable_effect` values above 0.50 trigger a warning. Values above 1.0 are rejected.

## Failure modes

1. **Underpowered test.** In analyze mode, if observed n < required n for the given MDE, the atom
   flags the test as underpowered and marks the result as directional only.
2. **No computation tool connected.** Both modes produce guidance-only output with runnable code.
   Design mode can still emit the sample size formula. Analyze mode cannot declare a winner.
3. **Continuous metric submitted as counts.** If the user provides raw values instead of
   successes/impressions for a rate metric, the atom routes to hypothesis-test internally.

## Regression cases (map to evals/evals.json)

| # | Case | Eval ID |
|---|---|---|
| 1 | Design mode — sample size for thumbnail CTR test | ab-001 |
| 2 | Analyze mode — clear winner with sufficient data | ab-002 |
| 3 | Analyze mode — underpowered test flagged | ab-003 |
| 4 | No computation tool — guidance-only output | ab-004 |

## Update checklist

1. If `shared/platform-engine.md` CTR benchmarks change, update Step 6 interpretation thresholds.
2. If `shared/compute-engine.md` tool matrix changes, update Step 2.
3. Re-run all evals after any change.
4. Run `python3 tools/sync_check.py`.
