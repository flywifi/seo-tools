---
file: skills/atoms/build-calc/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for build-calc so it stays stable under iteration.
---

# build-calc: Maintainer README

## Purpose
Offline residential construction calculators. A thin wrapper over `tools/build_calc.py`; the model
never re-does the arithmetic. Its job ends at returning a computed value with its code citation and
boundary; it does not look up prose requirements (`code-lookup`) or explain techniques
(`construction-lookup`).

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Skill-specific: all math runs in `tools/build_calc.py` (stdlib, offline, `--selftest`). No
  copyrighted span, ampacity, or fixture-unit table is reproduced; values are first-principles or
  restated from public-domain sources (`shared/construction-engine.md`). Every result carries the
  construction boundary from `protocols/safety.md`. The `deck-span` result is advisory only and must
  never be presented as a code-compliant span.

## Known failure modes
Out-of-range inputs return a structured error, not a guessed number; deck-span mistaken for an
authoritative span; climate-zone or edition ambiguity resolved silently instead of surfaced.

## Fragile fallbacks that must not become defaults
The deck-span rough ceiling is acceptable only when labeled non-authoritative with the DCA6 pointer;
it is never a substitute for the span table.

## Regression cases to preserve
1. stair(total_rise=108) yields 14 risers at ~7.714 in, riser_ok true. <!-- verify: tools/build_calc.py::stair -->
2. egress(20x24) fails; egress(30x30) passes at 6.25 sq ft; at_grade uses the 5.0 sq ft minimum. <!-- verify: tools/build_calc.py::egress -->
3. rvalue(ceiling, zone 2) returns "R30 to R49"; a county letter suffix like 4A normalizes to 4.
4. box_fill([14,14,14], device, clamp, ground) returns 14.0 cubic inches.
5. drain_slope(2 in, 20 ft) returns 5.0 in fall at 1/4 in per foot; 4 in uses 1/8 in per foot.
6. roof_pitch(6,12) returns 26.57 degrees and slope factor 1.1180; 1:12 fails the asphalt check.

## Approval-gated changes
Output schema, the R-value table values, the NEC box-fill constants, engine loading, or atom wiring.

## Minority-report policy
When a value could come from more than one edition or source, record the chosen basis (public-domain
restatement, first principles), the alternative, and what would overturn it (a newer adopted edition).

## Update checklist
1. Edit `tools/build_calc.py` and add a matching check in its `selftest`.
2. Run `python3 tools/build_calc.py --selftest`.
3. Update this file and SKILL.md; verify all backticked paths resolve.
4. Run `python3 tools/sync_check.py`.
