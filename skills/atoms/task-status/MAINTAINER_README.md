---
file: skills/task-status/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for task-status so it stays stable under iteration.
---

# task-status: Maintainer README

## Purpose
One paragraph on what this skill is responsible for and where its job ends.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Skill-specific: the rules unique to this skill.

## Known failure modes
The highest-impact ways this skill goes wrong.

## Fragile fallbacks that must not become defaults
Degraded behaviors that are acceptable only when labeled, never silent.

## Regression cases to preserve
Numbered, at least five, mapped to evals/evals.json.

## Approval-gated changes
Behavior-changing edits that need review (output schema, engine loading, atom wiring).

## Minority-report policy
When sources or routings disagree, record the chosen interpretation, the conflicts, why it was
chosen, and what would overturn it.

## Update checklist
Ordered steps to run on any change, always ending with python3 tools/sync_check.py.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
