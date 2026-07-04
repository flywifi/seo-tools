---
file: skills/atoms/construction-lookup/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for construction-lookup so it stays stable under iteration.
---

# construction-lookup: Maintainer README

## Purpose
Answers residential construction and trade questions from the offline dictionary
(`canonical-sources/construction/*.json`) via the scoop cache: dimensions, steps, common mistakes, and
code citations. Its job ends at returning cited reference content; it does not compute numbers
(`build-calc`), resolve editions (`code-lookup`), or plan whole projects (`project-builder`).

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Skill-specific: answers only from cached dictionary records, never from memory; every number and rule
  is traceable to a record and its cited section (`protocols/research-citation.md`); copyrighted code
  text and tables are never reproduced, only cited and linked (`shared/construction-engine.md`); every
  output carries the construction boundary (`protocols/safety.md`), led by the licensed-professional
  requirement for electrical, plumbing, and HVAC.

## Known failure modes
Answering from memory when the cache is not built; guessing a value the dictionary does not carry;
reproducing a copyrighted table instead of citing the section.

## Fragile fallbacks that must not become defaults
If the dictionary lacks an entry, saying so and citing the source to check is acceptable; inventing a
dimension is never acceptable.

## Regression cases to preserve
1. "max stair riser" returns the stairs-riser-tread entry with 7 3/4 in and IRC R311.7.5.1.
2. "deck ledger" returns decks-ledger-attachment with the flashing and lag/bolt requirement.
3. "egress window" returns the egress entry with the 5.7 and 5.0 sq ft net-clear areas.
4. "north carolina insulation" returns the insulation and fl-nc entries with the climate-zone ranges.
5. "what is a soffit" returns the glossary entry.
6. An electrical query leads with the licensed-electrician requirement.

## Approval-gated changes
Output schema, which source prefix is queried, engine loading, or atom wiring.

## Minority-report policy
When FL and NC differ, record both, name the chosen jurisdiction basis, and what would overturn it (a
newer adopted edition).

## Update checklist
1. Confirm the cache builds (`python3 shared/cache/cache.py --build`).
2. Spot-check the regression queries return the expected records.
3. Run `python3 tools/sync_check.py`. Verify all backticked paths resolve.
