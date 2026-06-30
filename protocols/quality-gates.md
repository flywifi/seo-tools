---
file: protocols/quality-gates.md
role: Authoritative definition of the quality rubric, scoring, thresholds, and the release gate.
  The quality-review skill applies this file. Every other skill self-checks against it before
  handing off. This is the source of truth for "is it good enough to release."
load: by quality-review always; by every generating skill before it finalizes an artifact
---

# Quality Gates

No artifact (content, document, or CRM record write) is released until it passes these gates.

## The nine dimensions
Each is scored 0 to 5. The artifact is evaluated against the shared engines (brand, audience,
platform, adaptation) and the other protocols.

1. Integrity (critical): no fabricated data, sources, brands, deals, figures, or metrics
   (see protocols/no-fabrication.md). Claims are real and supportable.
2. Accuracy: facts, specs, techniques, prices-as-ranges, and platform details are correct and
   current (see protocols/research-citation.md).
3. Brand and Aesthetic Alignment: matches the identity, pillars, and aesthetic in
   shared/brand-engine.md, in the correct voice mode.
4. Audience Fit: serves a named persona and the right skill, tenure, and budget tier
   (see shared/audience-engine.md and shared/adaptation-engine.md).
5. Governance: obeys the protocols (safety, no-fabrication, research-citation, formatting-metadata).
6. User Intent: answers what was actually asked, at the right scope, in the requested file type.
7. Accessibility: plain language; any jargon or acronym is briefly explained on first use.
8. Professional Quality: clean structure, correct formatting and specs, no errors, ready to use.
9. Safety (critical): obeys protocols/safety.md (trade, legal, FTC disclosure, wellbeing).

## Scoring scale
- 5 excellent, 4 strong, 3 acceptable, 2 weak, 1 poor, 0 absent or harmful.

## Release thresholds
- No dimension below 3.
- Integrity and Safety must each be 4 or higher.
- Composite average 4.0 or higher.

## Critical-failure overrides
If Integrity or Safety scores 0 to 1, the artifact fails regardless of the composite. It is not
released, not softened, and not partially shipped. Fix the cause and re-score.

## Gate process
1. The generating skill produces a draft using the shared engines.
2. It self-checks against these nine dimensions.
3. It hands off to quality-review, which scores each dimension and returns a verdict with the
   specific fixes for anything below threshold.
4. The skill fixes and re-scores until it passes.
5. Only then is the artifact released. For CRM artifacts, record the verdict alongside the record.
