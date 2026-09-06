---
file: skills/construction-desk/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for construction-desk so it stays stable under iteration.
---

# construction-desk: Maintainer README

## Purpose
The residential construction and DIY reference spoke. Composes `construction-lookup`, `code-lookup`,
and `build-calc`, then `govern-artifact`. Its job ends at cited reference answers and calculations; it
does not plan whole projects (`project-builder`), estimate cost (`finance-desk`), or give engineering,
code-compliance, or legal advice.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`; every named atom exists and is installed.
- Skill-specific: every output carries the construction boundary (`protocols/safety.md`,
  `shared/construction-engine.md`); electrical, plumbing, structural, roofing, and HVAC-design answers
  lead with the licensed-professional requirement; copyrighted code text and tables are never
  reproduced, only cited by section with a free-viewer link; Florida (2023 FBC 8th Edition) and North
  Carolina (2018 NC RC on 2015 IRC, 2024 pending) are stated distinctly; all lookups and math run
  offline from the cache and `tools/build_calc.py`.

## Known failure modes
Answering from memory when the cache is not built; presenting the NC pending 2024 code as enforced;
returning an authoritative structural member size; reproducing a copyrighted table.

## Fragile fallbacks that must not become defaults
The deck-span advisory ceiling and "cite the section, read the viewer" for copyrighted tables are
acceptable labeled fallbacks; inventing a value or pasting code text is never acceptable.

## Regression cases to preserve
1. A construction_question ("attach a deck ledger") routes to construction-lookup and returns cited steps.
2. A code_lookup ("Florida egress") returns IRC R310 with the FL 8th Edition status and a viewer link.
3. A build_calc ("risers for 108 in rise") returns 14 risers from build-calc with the boundary.
4. An NC code question states the enforced 2018 code and flags the pending 2024 transition.
5. An electrical question leads with the licensed-electrician requirement.
6. Every output ends through govern-artifact with the boundary and citations intact.

## Approval-gated changes
workflow.json step wiring, which atoms are composed, engine loading, or the boundary text.

## Minority-report policy
When FL and NC differ or NC edition status is ambiguous, record both, name the chosen basis, and what
would overturn it (a newly effective edition).

## Update checklist
1. Confirm the three atoms and govern-artifact are installed.
2. Confirm the cache builds and the regression queries resolve.
3. Run `python3 tools/sync_check.py`. Verify all backticked paths resolve.
