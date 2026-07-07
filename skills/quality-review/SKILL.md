---
name: quality-review
description: scores any drafted artifact (content, document, or CRM record write) against the nine Quality Gates dimensions and returns a release verdict with specific fixes. use whenever a spoke has produced a draft and needs the gate before release, or when the user asks to quality check, review, or score a piece. do NOT use to generate the artifact; it only evaluates.
---

# Quality Review

The governance skill. It does not create; it evaluates. It applies `protocols/quality-gates.md` with
evidence, then runs the deterministic scorer so the verdict is reproducible.

## Inputs
- The drafted artifact and the request it answers.
- The routing object from `creator-core` (lane, persona_targets, adaptation_axes, platform_targets).
- The engines the artifact was built against (`shared/brand-engine.md`, `shared/audience-engine.md`,
  `shared/platform-engine.md`, `shared/adaptation-engine.md`, and for CRM `shared/pipeline-engine.md`).

## Score the nine dimensions, in gate order
Score each 0 to 5 with a one-line evidence note (see `references/rubric.md` for anchors). Stop early
and mark a hard fail if Integrity or Safety scores 0 to 1.

1. Integrity (critical)
2. Safety (critical)
3. Governance
4. Accuracy
5. Brand and Aesthetic Alignment
6. Audience Fit
7. User Intent
8. Accessibility
9. Professional Quality

## Compute the verdict deterministically
Pass the nine scores to the scorer and use its result verbatim:

```bash
echo '{"integrity":5,"accuracy":4,"brand_alignment":5,"audience_fit":4,"governance":5,"user_intent":4,"accessibility":4,"professional_quality":4,"safety":5}' | python3 scripts/score.py
```

Release requires: no dimension below 3, Integrity and Safety each 4 or higher, and a composite
average of 4.0 or higher. Integrity or Safety at 0 to 1 is a hard fail regardless of composite
(`protocols/quality-gates.md`).

## Emit the decision record
Return the per-dimension scores with evidence, the composite, the verdict, and for anything below
threshold the specific fix. For a CRM artifact, the verdict is recorded alongside the record in the
`pipeline/` store.

## On not released
List the failing dimensions and the concrete fix for each. The generating skill fixes and re-scores
until it passes. Never soften, partially ship, or release a hard-failed artifact.

## Engines and protocols loaded
`protocols/quality-gates.md` (authoritative), and the engines the artifact claims to satisfy. The
other protocols (`safety`, `no-fabrication`, `research-citation`, `formatting-metadata`) feed the
Safety, Integrity, Accuracy, and Professional Quality dimensions.

## Standalone usability
Produces a complete, evidence-backed verdict and fix list for any single artifact handed to it, with
no downstream skill required.

## Failure modes
- Scoring from impression rather than evidence. Every score carries a one-line reason.
- Treating a missing Integrity or Safety check as a pass. Absence of evidence is not a 5.
- Doing the arithmetic by hand instead of using `scripts/score.py`.

## Cross-modality
Class: C.
Runs on: Claude Desktop/Code (native, MCP + the tool module); claude.ai via a hosted remote-MCP connector; Custom GPT / Gemini only when the tool is hosted behind a remote MCP or an Action; Gems: no.
Mechanism: skills/quality-review/scripts/score.py deterministic Quality-Gates scoring, invoked by every spoke's govern-artifact; MCP gate. A governance/meta capability.
Fallback: No runtime or hosted seam -> the model scores under the quality-gates.md rubric explicitly labelled an estimate (not the deterministic score); never release on a hard-fail dimension.
See `shared/cross-modality-engine.md`.