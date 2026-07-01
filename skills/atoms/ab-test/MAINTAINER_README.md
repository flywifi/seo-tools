---
file: skills/atoms/ab-test/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for ab-test so it stays stable under iteration.
---

# ab-test: Maintainer README

## Purpose

The ab-test atom designs and analyzes A/B tests for creator content experiments —
thumbnail variants, title variants, posting time, format comparisons — in the
moody-vintage home decor and DIY niche. In design mode it computes required sample
size, test duration estimate, and statistical power. In analyze mode it computes
significance, effect size, and declares a winner or no-call. Its job ends at
experiment design or result interpretation — it does not run standalone hypothesis
tests (use hypothesis-test) or model relationships between variables (use
regression-analysis).

## Non-negotiable invariants

1. References the pipeline (`shared/method.md`); self-checks against
   `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
   `protocols/formatting-metadata.md`.
2. Sample size must be computed from effect size, alpha, and power — never guessed,
   hardcoded, or pulled from a rule of thumb.
3. Minimum detectable effect must be stated in every design-mode output.
4. Underpowered tests must be flagged with an explicit warning when power < 0.8;
   the atom must refuse to declare a winner on underpowered data.
5. Analyze mode must verify that the experiment ran long enough (minimum duration
   met) before declaring a winner.
6. Never fabricate conversion rates, lift percentages, p-values, or sample sizes.
   Null and flag instead.
7. When no computation tool is connected, output must be clearly labeled
   "guidance-only" and include runnable code the creator can execute elsewhere.

## Known failure modes

1. Declaring a winner on an underpowered test — violates invariant 4 and
   produces unreliable recommendations.
2. Sample size pulled from a rule of thumb or industry default instead of
   computed from the caller's specific parameters.
3. Ignoring early stopping bias (peeking) — reporting significance from
   interim checks without adjusting for multiple looks.
4. Confusing per-variant sample size with total sample size, leading to an
   experiment that runs at half the required power.

## Regression cases to preserve

1. Design mode with a CTR baseline of 3.5% and a 20% target lift produces a
   computed sample size per variant, estimated duration, minimum detectable
   effect, and power confirmation.
2. Analyze mode with two thumbnail variants and adequate data produces a winner
   declaration with p-value, effect size, and a plain-language conclusion.
3. Analyze mode with insufficient sample size flags underpowered status (power
   < 0.8) and refuses to declare a winner, returning an insufficient-data
   conclusion instead.
4. No computation tool connected returns guidance-only output with runnable code
   and a clear "guidance-only" label.

## Update checklist

1. Edit the canonical file (`skills/atoms/ab-test/SKILL.md` or engine references).
2. Run evals: verify all cases in `evals/evals.json` still pass.
3. Confirm sample-size computation path never falls back to a hardcoded value.
4. Check that the underpowered-warning path still triggers and blocks winner
   declaration.
5. Update `STATE.md` if a phase boundary was crossed.
6. Run `python3 tools/sync_check.py` — must exit 0.
