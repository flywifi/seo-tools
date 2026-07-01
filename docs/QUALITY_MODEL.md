---
file: docs/QUALITY_MODEL.md
role: Reference for the Creator OS quality model. Covers the nine dimensions, release thresholds,
  hard fail rule, score.py design, the govern-artifact atom, and when to invoke quality-review.
  The authoritative source for thresholds is protocols/quality-gates.md.
---

# Creator OS Quality Model

The quality model is defined in `protocols/quality-gates.md`. The rubric anchors are in
`skills/quality-review/references/rubric.md`. This document is a reference companion; the
protocols file is authoritative for thresholds and the gate process.

---

## The nine dimensions

Every artifact is scored across nine dimensions. Each dimension uses the same scale:
0 absent or harmful, 1 poor, 2 weak, 3 acceptable, 4 strong, 5 excellent.

The artifact is evaluated against the shared engines (brand, audience, platform, adaptation) and
the other protocols. Dimensions marked "critical" have hard-fail rules (see below).

### 1. Integrity (critical)

**What it measures:** no fabricated data, sources, brands, deals, figures, or metrics. Every
claim is real and supportable. Governed by `protocols/no-fabrication.md`.

- 5: every claim, figure, brand, and source is real and supportable; nothing invented.
- 4: strong; all material claims verified; one minor unverified peripheral detail.
- 3: minor unverified claim that does not affect the core.
- 2: one unverified figure or source that could mislead.
- 1: a fabricated metric, rate, brand, or source present.
- 0: fabrication is central to the artifact; the artifact cannot be repaired without replacement.

Score of 0 to 1 triggers a hard fail regardless of composite. See hard fail rule below.

### 2. Accuracy

**What it measures:** facts, specs, techniques, prices as ranges, and platform details are correct
and current. Time-sensitive claims are cited per `protocols/research-citation.md`.

- 5: all facts, specs, techniques, and prices correct and current; time-sensitive claims cited.
- 4: mostly correct; one stale detail that is noted.
- 3: mostly correct; one stale or unsourced figure.
- 2: one factual error that could affect the outcome.
- 1: multiple factual errors; content cannot be used without correction.
- 0: accuracy is absent; the artifact contains materially wrong information throughout.

### 3. Brand and Aesthetic Alignment

**What it measures:** the artifact matches the identity, pillars, and aesthetic defined in
`shared/brand-engine.md`, delivered in the correct voice mode (planning voice vs. audience voice).

- 5: matches identity, pillars, and aesthetic in the correct voice mode; home decor anchor
  maintained; examples are specific to the channel.
- 4: strong alignment; one generic example that could be more specific.
- 3: on brand but flat voice or a generic example.
- 2: partially aligned; drifts toward a different aesthetic (e.g. bright farmhouse).
- 1: off brand in voice or aesthetic; requires significant revision.
- 0: brand alignment absent; the artifact could belong to any creator.

### 4. Audience Fit

**What it measures:** the artifact serves a named persona at the right skill level, tenure, and
budget tier as defined in `shared/audience-engine.md` and adapted per `shared/adaptation-engine.md`.

- 5: serves a named persona at the right skill, tenure, and budget tier; adaptation axes stated.
- 4: serves the named persona; adaptation axes stated but one is thin.
- 3: serves the audience broadly without naming a specific persona.
- 2: persona unclear; adaptation axes not addressed.
- 1: mismatches the evident persona (e.g. advanced techniques for a beginner request).
- 0: audience fit absent; the artifact ignores who it is for.

### 5. Governance

**What it measures:** the artifact obeys the applicable protocols (safety, no-fabrication,
research-citation, formatting-metadata); assumptions are logged; for CRM artifacts the verdict
is recorded alongside the record.

- 5: every applicable protocol obeyed; assumptions logged; CRM verdict recorded if applicable.
- 4: all protocols obeyed; one assumption not logged.
- 3: one protocol partially applied.
- 2: one protocol missed; a material formatting or citation rule violated.
- 1: multiple protocol violations.
- 0: governance absent; protocols not applied.

### 6. User Intent

**What it measures:** the artifact answers what was actually asked, at the right scope, in the
requested file type. Neither over-scoped nor under-scoped.

- 5: answers exactly what was asked, at the right scope, in the requested file type.
- 4: answers the request; scope is slightly wider or narrower than optimal.
- 3: answers the request but over- or under-scopes.
- 2: partially answers the request; key elements are missing.
- 1: answers a different question than was asked.
- 0: does not address the request at all.

### 7. Accessibility

**What it measures:** plain language; any jargon or acronym is briefly explained on first use.
The artifact is understandable without specialized prior knowledge.

- 5: plain language throughout; every jargon term explained on first use.
- 4: mostly plain; one term assumed without explanation.
- 3: mostly plain with one unexplained term.
- 2: multiple unexplained terms; a reader without niche knowledge would be confused.
- 1: heavy jargon throughout; accessibility is poor.
- 0: the artifact is inaccessible; meaning cannot be extracted without specialized knowledge.

### 8. Professional Quality

**What it measures:** clean structure, correct formatting and specs, no errors, ready to use. Obeys
`protocols/formatting-metadata.md` (no em dashes, ranges with "to," author metadata set).

- 5: clean structure, correct specs, no errors, no em dashes, ranges with "to," author metadata
  set correctly.
- 4: strong; one minor formatting slip that does not affect usability.
- 3: usable with minor formatting slips.
- 2: structural or formatting issues that require cleanup before use.
- 1: significant structural or formatting problems; the artifact needs substantial revision.
- 0: the artifact is not usable in its current form.

### 9. Safety (critical)

**What it measures:** the artifact obeys `protocols/safety.md` (trade boundaries, legal limits,
FTC disclosure, wellbeing). Structural, electrical, and plumbing DIY is referred to a licensed
professional. Sponsored content carries disclosure.

- 5: trade boundaries, legal limits, and FTC disclosure all handled; renter-safe option offered
  where applicable.
- 4: safety handled; one element thin (e.g. PPE noted but licensed-pro referral is vague).
- 3: present but minimal; safety language is thin.
- 2: a safety boundary is unclear or partially missing.
- 1: unsafe DIY presented as safe, legal advice given as vetted, or sponsored content without
  disclosure.
- 0: a hard safety failure; the artifact could cause harm or legal exposure.

Score of 0 to 1 triggers a hard fail regardless of composite. See hard fail rule below.

---

## Release thresholds

All three conditions must hold simultaneously for an artifact to be released:

1. No dimension scores below 3.
2. Integrity scores 4 or higher.
3. Safety scores 4 or higher.
4. Composite average (sum of all nine scores divided by 9) is 4.0 or higher.

If any condition fails, the artifact is not released. quality-review returns the specific fixes
for each failing dimension, and the generating spoke fixes and re-scores until all conditions hold.

---

## Hard fail rule

If Integrity or Safety scores 0 to 1, the artifact fails immediately. The composite is not
computed. The artifact is not released, not softened, and not partially shipped. Fix the cause
and re-score from the beginning.

The hard fail is evaluated before the composite threshold check. Absence of evidence for
Integrity or Safety is not a score of 5; it is a score that reflects the actual state of the
artifact.

---

## score.py design

`scripts/score.py` is the deterministic scorer. Every verdict that quality-review emits comes
from this script, never from hand arithmetic.

**Inputs:** nine integer scores passed as a JSON object via stdin or as a command-line argument.

```bash
echo '{"integrity":5,"accuracy":4,"brand_alignment":5,"audience_fit":4,
       "governance":5,"user_intent":4,"accessibility":4,
       "professional_quality":4,"safety":5}' | python3 scripts/score.py
```

**Outputs:** a verdict object.

```json
{
  "scores": {
    "integrity": 5, "accuracy": 4, "brand_alignment": 5, "audience_fit": 4,
    "governance": 5, "user_intent": 4, "accessibility": 4,
    "professional_quality": 4, "safety": 5
  },
  "composite": 4.44,
  "hard_fail": false,
  "verdict": "Released",
  "failing_dimensions": [],
  "threshold_checks": {
    "no_dimension_below_3": true,
    "integrity_at_least_4": true,
    "safety_at_least_4": true,
    "composite_at_least_4": true
  }
}
```

**Design properties:**
- Deterministic: the same nine scores always produce the same verdict. There is no probabilistic
  element, no rounding ambiguity beyond standard floating-point division, and no model judgment
  in the scorer itself.
- Reproducible: anyone running score.py with the same inputs gets the same output. Verdicts can
  be audited against the ledger.
- Hard fail first: score.py checks Integrity and Safety for the 0 to 1 hard-fail condition before
  computing the composite. If either triggers, `hard_fail` is `true` and `verdict` is
  "Not released" immediately.
- All threshold checks are explicit: every threshold condition appears as a named boolean in
  `threshold_checks` so the caller can see exactly which condition failed.
- No side effects: score.py reads stdin (or a CLI argument), writes stdout, and exits. It does
  not write to the pipeline store or the ledger; the calling skill does that.

---

## How govern-artifact wraps quality-review and score.py

`skills/atoms/govern-artifact/` is the gate atom. It is the final step in every spoke workflow
before the artifact is released.

**What govern-artifact does:**
1. Receives the drafted artifact, the original request, and the lane from the calling spoke.
2. Hands the artifact to `skills/quality-review/` with the routing context (persona targets,
   adaptation axes, platform targets, engines the spoke used).
3. quality-review scores each of the nine dimensions with a one-line evidence note.
4. quality-review calls `scripts/score.py` with the nine integer scores and receives the verdict
   object.
5. govern-artifact returns the full verdict: per-dimension scores with evidence, the composite,
   the verdict string, the hard-fail flag, and the list of specific fixes for any failing dimension.

**govern-artifact output:**

```json
{
  "tool": "govern-artifact",
  "scores": {
    "integrity": 0, "accuracy": 0, "brand_alignment": 0, "audience_fit": 0,
    "governance": 0, "user_intent": 0, "accessibility": 0,
    "professional_quality": 0, "safety": 0
  },
  "composite": 0,
  "verdict": "Released | Not released",
  "hard_fail": false,
  "fixes": ["specific fix for each dimension below threshold"],
  "note": "verdict and arithmetic come from quality-review scripts/score.py"
}
```

**CRM artifacts:** when the artifact is a CRM record write (`pipeline_crm` lane), govern-artifact
records the verdict alongside the record in the `pipeline/` store per the rules in
`shared/pipeline-engine.md`.

**govern-artifact does not:**
- Generate, draft, or fix the artifact. That is the generating spoke's responsibility.
- Release a hard-failed artifact or one with a dimension below threshold.
- Soften or partially ship a non-passing artifact.

If the verdict is "Not released," the generating spoke reads the fixes list, applies the
corrections, and calls govern-artifact again. This loop continues until the artifact passes.

---

## When to invoke quality-review

quality-review is invoked via govern-artifact at the end of every spoke workflow, before the
artifact is delivered to the user. There are no exceptions.

**Mandatory invocation points:**
- After every content artifact (idea cluster, script section, hook, title set, caption, pin).
- After every document artifact (media kit, calendar, brief, invoice, one-pager).
- After every CRM record write (account create or update, deal create or update or stage move).
- After any repurposing or short-form extraction.
- After any SEO or competitor analysis artifact.

**quality_check classification:** when the user explicitly requests a quality check on an existing
artifact, creator-core classifies the request as `quality_check` and routes directly to
quality-review as a standalone skill (not via govern-artifact). The artifact and its routing
context are provided as inputs. quality-review scores, runs score.py, and returns the verdict
with specific fixes. It does not generate or fix the artifact.

**Self-check before handoff:** before calling govern-artifact, the generating spoke performs a
self-check against `protocols/quality-gates.md`. If any dimension is obviously below 3, the spoke
fixes the artifact before handing it to quality-review. The self-check does not replace the
deterministic score; it is a pre-flight to avoid unnecessary gate cycles.

**Scoring order in quality-review:** quality-review scores Integrity first, then Safety, to catch
hard-fail conditions as early as possible and avoid scoring all nine dimensions when the artifact
cannot pass regardless of the remaining scores.
