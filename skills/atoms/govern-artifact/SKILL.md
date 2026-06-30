---
name: govern-artifact
description: run the Quality Gates on a drafted artifact by handing it to quality-review and returning the verdict. Use as the final step of any spoke workflow before release. Do NOT use to generate or fix the artifact; it only gates.
---

# govern-artifact

The gate step. Hands a drafted artifact to `quality-review` and returns the deterministic verdict.

## Input
```json
{
  "artifact": "the drafted content, document, or CRM record write",
  "request": "the original request it answers",
  "lane": "content | document | pipeline_crm"
}
```

## Output
```json
{
  "tool": "govern-artifact",
  "scores": {
    "integrity": 0, "accuracy": 0, "brand_alignment": 0, "audience_fit": 0,
    "governance": 0, "user_intent": 0, "accessibility": 0, "professional_quality": 0, "safety": 0
  },
  "composite": 0,
  "verdict": "Released | Not released",
  "hard_fail": false,
  "fixes": ["specific fix for each dimension below threshold"],
  "note": "verdict and arithmetic come from quality-review scripts/score.py"
}
```

## Do NOT use this atom for
- Generating or fixing the artifact (the spoke does that, then re-gates).
- Releasing a hard-failed artifact or one with a dimension below threshold.

## Pipeline note
Wraps `skills/quality-review/`. Scores the nine dimensions with evidence, then runs the deterministic
scorer. For a CRM artifact, the verdict is recorded alongside the record (`shared/pipeline-engine.md`).
