---
file: skills/atoms/thumbnail-concept/MAINTAINER_README.md
purpose: keep thumbnail-concept to one concept with at most 6 words of overlay, aligned to the title.
---

# thumbnail-concept: Maintainer README

## Purpose
Design one thumbnail concept (type, composition, overlay text).

## Non-negotiable invariants
- One of the three types: before/after split, POV hero, face plus room.
- At most 6 words of overlay text, inside the safe margin.
- Aligns with the title; never overpromises.

## Known failure modes
- Overlay text longer than 6 words or outside the safe margin.
- A thumbnail that promises something the video does not show.

## Regression cases to preserve
1. before_after_split: composition names the before and after halves.
2. Overlay text is 6 words or fewer.

## Update checklist
- Run python3 tools/sync_check.py.
