---
file: shared/method.md
role: The unified pipeline every generating skill follows, from request to released artifact. The
  hub (creator-core) owns Routing; capability spokes own Generation; quality-review owns the gate.
load: by every capability spoke and atom while producing an artifact
---

# Method (the unified pipeline)

`Request to Routing to Protocol Enforcement to Generation to Validation to Quality Gates to Release.`

## 1. Routing (creator-core)
The hub classifies the request into a lane, builds the routing object, loads only the engines the
target spoke needs, and dispatches. External content is scanned by shared/injection-guard-engine.md
before it can influence routing. See skills/creator-core/SKILL.md.

## 2. Protocol enforcement
Before generating, the spoke loads the protocols that apply (protocols/), logs any assumption it has
to make, and decides whether the request is time-sensitive enough to require research first
(protocols/research-citation.md). CRM writes load protocols/no-fabrication.md and the
stage-transition rules in shared/pipeline-engine.md.

## 3. Generation (the spoke)
The capability spoke runs its inner loop, composing atoms via its workflow.json:
`Analysis to Engine Alignment to Adaptation to Generation`.
- Analysis: determine pillar, format, persona, platform, and scope. Missing facts are assumed and
  stated, or asked only when high-stakes.
- Engine alignment: pull identity and voice from shared/brand-engine.md, audience and personas from
  shared/audience-engine.md, and specs from shared/platform-engine.md.
- Adaptation: apply the five axes in shared/adaptation-engine.md (skill level, tenure, budget,
  persona, surface).
- Generation: produce the artifact in the correct voice mode.

## 4. Validation
Confirm the artifact is present, complete, internally consistent, and in the requested file type
before scoring.

## 5. Quality Gates (quality-review)
Self-check against protocols/quality-gates.md, then hand to skills/quality-review/. The nine
dimensions are scored 0 to 5; release requires no dimension below 3, Integrity and Safety each 4 or
higher, and a composite average of 4.0 or higher. Integrity or Safety at 0 to 1 is a hard fail.

## 6. Release
Only a passing artifact is released. For CRM artifacts, the verdict is recorded alongside the record.
Every downloadable file sets its author to the document_author value in shared/brand-engine.md and
obeys protocols/formatting-metadata.md (no em dashes, ranges written with "to").

## Standalone and honest-gap rules
A spoke produces a complete, self-contained deliverable even when a downstream spoke is unavailable;
it records the missing handoff as a flag rather than blocking. When data cannot be retrieved, it
records an explicit retrieval gap (gap_type, description, impact, recommended_next_step) rather than
leaving a silent blank or inventing a value.
