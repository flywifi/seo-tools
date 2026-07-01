# hypothesis-test — Maintainer Reference

## What this atom does

Performs statistical hypothesis testing on creator-supplied data by delegating computation to a
connected MCP tool (stats-compass, E2B, R) via `shared/compute-engine.md`. Returns test statistic,
p-value, effect size, confidence interval, and a plain-language interpretation. Falls back to
guidance-only output (runnable Python code) when no computation tool is connected.

## Invariants

1. `computation_source` is always set to one of: `stats_compass`, `e2b`, `r_statistics`,
   `wolfram_alpha`, `guidance_only`. Never null, never omitted.
2. `p_value`, `test_statistic`, `effect_size`, and `confidence_interval` are never fabricated.
   If no computation tool is connected, all four are null and `conclusion` is `insufficient_data`.
3. Sample size warnings are emitted whenever any group has n < 30 for parametric tests. If any
   group has n < 5, the atom refuses parametric tests entirely.

## Failure modes

1. **No computation tool connected.** The atom produces guidance-only output with runnable code.
   This is the expected degraded path, not an error — but the output must be labeled
   `[guidance-only — no computation engine connected]`.
2. **Mismatched test type and data structure.** The atom detects mismatches (e.g., ANOVA with
   two groups) and either downgrades the test or flags the mismatch. It never silently runs a
   wrong test.
3. **Small sample size.** Parametric results on n < 30 carry a warning. On n < 5, the atom
   refuses and recommends descriptive statistics. It never silently proceeds without the warning.

## Regression cases (map to evals/evals.json)

| # | Case | Eval ID |
|---|---|---|
| 1 | Independent t-test with computation tool | ht-001 |
| 2 | No computation tool — guidance-only output | ht-002 |
| 3 | Small sample size triggers warning | ht-003 |
| 4 | Test type mismatch detected and corrected | ht-004 |

## Update checklist

1. If `shared/compute-engine.md` tool selection matrix changes, update Step 2 in SKILL.md.
2. If `protocols/no-fabrication.md` adds new statistical constraints, update the Fabrication
   rules section.
3. If a new computation MCP is added, add it to the `computation_source` enum.
4. Re-run all evals after any change.
5. Run `python3 tools/sync_check.py`.
