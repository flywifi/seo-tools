---
name: coverage-verify
atom: true
standalone: true
description: "verifies that a deliverable met its required points by reconciling all provided media transcripts to a canonical truth and checking each required point against it, citing the exact supporting sentence per point and abstaining when unsure. Triggers: 'did the video cover points a, b, c, d', 'does the final cut hit the approved talking points', 'reconcile these two transcripts'. Do NOT assert coverage it cannot ground in a quoted sentence, and never infer. Runs tools/coverage_verify.py; conflicts between inputs are surfaced in a minority report and routed to human review."
engines_required:
  - shared/tasks-engine.md
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/research-citation.md
  - protocols/formatting-metadata.md
---

# coverage-verify

Proves (or honestly cannot prove) that a deliverable covered its required points. It first reconciles the
media transcripts into one canonical truth, then verifies each point with a cited, verbatim supporting
sentence, abstaining rather than guessing.

## First line of every output (verbatim)

```
COVERAGE ANALYSIS FROM THE SOURCES YOU PROVIDED. Each verdict cites a specific sentence; when no sentence supports a point the tool abstains and routes to your review. Not compliance advice.
```

## When to use this skill
- "did the video cover points a, b, c, d", "does the final cut hit the approved script's talking points",
  "reconcile these two transcripts and tell me where they disagree", routed as `coverage_check`.

Do NOT use for:
- Asserting coverage without a supporting quote (it abstains instead).
- Legal or compliance sign-off (it is analysis, not advice).
- Editing the video or transcript.

## Inputs
One or more transcripts/captions/scripts of the deliverable (SRT/VTT/JSON/text) and the list of required
points (from the approved script or contract). More inputs improve the reconciliation.

## Core procedure
Follow `shared/method.md`. Call `tools/coverage_verify.py` / the `coverage_verify` MCP tool.

### Step 1: reconcile to a canonical truth
Align the transcripts and vote to a canonical transcript, surfacing every tie or credible dissent as a
conflict (never silently picking). Credible conflicts force human review.

### Step 2: verify each required point, cite or abstain
For each point, find the supporting sentence; assert `satisfied` only with a verbatim, present quote and a
timestamp; decompose compound points into sub-claims; `partial` when some sub-claims are met; abstain to
`missing` when no sentence supports it. Never infer coverage.

## Output contract
Per-point verdicts with extractive quotes and timestamps, a summary, a minority report of input conflicts,
and `human_review_required` always. Honor `protocols/research-citation.md` and
`protocols/no-fabrication.md`.

## Engines and protocols loaded
`shared/tasks-engine.md`; `protocols/safety.md`, `protocols/no-fabrication.md`,
`protocols/research-citation.md`, `protocols/formatting-metadata.md`.

## Atoms used
None. Directly callable and used by `task-desk`. Feeds a deliverable's `approval_state` and any coverage
obligation.

## Standalone usability
Reconciles transcripts and returns cited per-point coverage verdicts offline, abstaining when unsure.

## Failure modes
- No sentence supports a point: abstains (missing) and routes to the human, never fabricates coverage.
- Inputs disagree: the conflict is retained in the minority report and, if credible, forces review.
- A single low-quality transcript: coverage is reported with lower confidence; the gap is stated.
