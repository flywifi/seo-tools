---
file: skills/analytics-compute/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for analytics-compute so it stays stable under iteration.
---

# analytics-compute: Maintainer README

## Purpose
This spoke performs real statistical computation on the creator's data by routing to the appropriate
statistical atom and executing against a connected MCP stats tool. Its job ends at delivering a
structured statistical result with confidence metrics; interpretation for content strategy belongs
to analytics-insights.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Skill-specific: never fabricate statistical output -- if computation fails, emit a gap-record.
  Always require at least one MCP stats tool to be connected before executing any atom. Every
  numeric result must include a confidence interval or p-value. Ranges always use "to" (e.g.,
  "95% CI: 1.2 to 3.4").

## Known failure modes
1. No MCP stats tool connected -- spoke cannot compute anything; must emit gap-record.
2. Dataset too small for the requested test -- must downgrade and warn, never pad data.
3. Stats tool returns a runtime error -- surface the raw error, do not retry silently.
4. Ambiguous analysis type -- must ask a clarifying question, not guess.

## Fragile fallbacks that must not become defaults
- Descriptive-summary fallback when sample size is insufficient: acceptable only when explicitly
  labeled as a fallback, never presented as the primary analysis.
- Manual computation when no MCP tool is connected: never acceptable; the spoke must not
  attempt to compute statistics inline.

## Regression cases to preserve
1. Hypothesis test with sufficient data returns p-value and effect size (maps to evals case 1).
2. Regression with two variables returns coefficients, R-squared, and residual diagnostics (case 2).
3. Forecast request produces time-series projection with confidence bands (case 3).
4. A/B test design returns required sample size and power analysis (case 4).
5. Missing MCP tool emits gap-record instead of fabricated output (implicit in all cases).

## Approval-gated changes
- Any change to the atom wiring in workflow.json.
- Any change to the output schema of a statistical result.
- Adding or removing an engine from the load list.
- Changing the minimum sample size thresholds.

## Minority-report policy
When multiple statistical tests could answer the same question (e.g., t-test vs. Mann-Whitney),
record the chosen test, the alternative, why it was chosen, and what data pattern would make the
alternative preferable.

## Update checklist
1. Edit the canonical file (SKILL.md, workflow.json, or atom).
2. Run `python3 tools/sync_check.py` -- must exit 0.
3. Run evals: verify all cases in `evals/evals.json` still pass.
4. Update STATE.md if the change crosses a phase boundary.
5. Commit with a message referencing analytics-compute and the affected component.
