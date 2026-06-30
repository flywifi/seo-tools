---
file: skills/atoms/persona-map/MAINTAINER_README.md
purpose: keep persona-map scoped to the five canonical personas and honest about inference vs. measured data.
---

# persona-map: Maintainer README

## Purpose
Map a topic to one or more of the creator's five canonical personas. Never invent personas or present inferred demographics as measured data.

## Non-negotiable invariants
- Only the five canonical personas are valid outputs: Renter, Vintage Hunter, Organizer, Holiday Maximalist, New Homeowner.
- Inferred persona mapping is labeled "inferred from topic signals" and does not state demographic facts as measured.
- adaptation_notes reflect the adaptation axes from shared/adaptation-engine.md (skill level, tenure, budget, persona, surface).

## Known failure modes
- Inventing a sixth persona not in the five-persona model.
- Stating "most of the creator's audience is renters" as a fact without real analytics data.
- Mapping all topics to "Renter" because it is the most common niche persona.

## Regression cases to preserve
1. Holiday decor topic: Holiday Maximalist is primary; Organizer may be secondary.
2. Budget constraint mentioned in input: reflected in adaptation_notes, not ignored.

## Update checklist
- Run python3 tools/sync_check.py.
