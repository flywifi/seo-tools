---
name: conflict-check
atom: true
standalone: true
description: "resolves a conflict between two ADVISORY jurisdictional overlays and returns which governs, or escalates a genuine legal conflict to human review. Runs the cited resolution cascade: field/ceiling preemption means the higher jurisdiction governs; floor preemption plus local (home-rule) authority means the more-stringent rule governs; otherwise the more-specific scope governs (lex specialis); a genuine conflict (for example a historic-district frame requirement vs an HVHZ impact-window requirement) returns human_review_required rather than an auto-decision, with a W3C PROV audit of the decision. Triggers: 'which rule wins, historic or hurricane code', 'does the steep-slope ordinance override X', 'these two overlays conflict, what governs'. Advisory only, never a legal or permitting determination. Do NOT use to find which overlays apply in the first place (overlay-resolve), to answer code text (code-lookup), or to give legal advice."
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/research-citation.md
  - protocols/formatting-metadata.md
---

# conflict-check

Given two applicable jurisdictional overlays, determines which governs by the cited legal-precedence
cascade, or flags a genuine conflict for human review. It never auto-resolves a genuine legal conflict.

## First line of every output (verbatim)

```
ADVISORY PLANNING INFORMATION ONLY, NOT A LEGAL OR PERMITTING DETERMINATION. A GENUINE LEGAL CONFLICT IS FLAGGED FOR HUMAN REVIEW, NOT AUTO-RESOLVED. CONSULT THE AUTHORITY HAVING JURISDICTION.
```

## When to use this skill
- "Which rule wins here, the historic-district requirement or the hurricane code?"
- "Does the steep-slope ordinance override the base zoning?"
- "These two overlays conflict; what governs?"

Do NOT use for:
- Finding which overlays apply in the first place: that is `overlay-resolve`.
- What the code text says: that is `code-lookup` / `construction-desk`.
- Legal advice: out of scope; refer to the authority having jurisdiction or an attorney.

## Inputs
Two overlay records (or their ids in `canonical-sources/jurisdiction/`), each carrying its
`jurisdiction_level`, `preemption_type` (floor/ceiling/field/none), `local_authority`, and
`specificity_scope`.

## Core procedure
Follow `shared/method.md`. Uses `tools/geo_overlay.py` `resolve_conflict`. <!-- verify: tools/geo_overlay.py::resolve_conflict -->

### Step 1: run the cascade
Field/ceiling preemption -> higher jurisdiction governs. Floor + local authority -> most-stringent
governs. Else lex specialis -> more-specific scope governs. Else -> `human_review_required`.

### Step 2: return the decision with its audit
Return the governing overlay (or the human-review flag), the basis, and the W3C PROV audit record.
Hand to `govern-artifact`.

## Output contract
The governing overlay id (or `human_review_required: true`), the cited basis, and the PROV audit. No
fabricated resolution of a genuine conflict (`protocols/no-fabrication.md`); honor
`protocols/formatting-metadata.md`.

## Standalone usability
Resolves or escalates a two-overlay conflict offline, cited and audited, with no downstream skill.

## Failure modes
- An overlay id not found: names the missing id rather than guessing.
- A genuine legal conflict: returns `human_review_required`, never a fabricated winner.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
