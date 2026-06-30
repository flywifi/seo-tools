---
file: skills/shortform-repurposing/MAINTAINER_README.md
purpose: keep shortform-repurposing converting existing long-form content only; it never generates the original long-form video.
---

# shortform-repurposing: Maintainer README

## Purpose
Convert a long-form YouTube project into a short-form content package (3 to 5 Shorts/Reels, captions, hashtags, Pins, and a drop schedule). Never generates the underlying long-form content.

## Non-negotiable invariants
- 3 to 5 clips from short-extract; never fewer than 3.
- FTC disclosure is flagged whenever content is sponsored, gifted, or affiliate; never omitted.
- The ecosystem ratio is 1 long-form + 3 to 5 Shorts/Reels + 1 to 3 Pins per project.

## Known failure modes
- Generating long-form video scripts or hooks (use video-development for that).
- Producing fewer than 3 short-form clips.
- Omitting FTC disclosure flag when sponsored: true.

## Regression cases to preserve
1. Sponsored content: caption-write output includes ftc_disclosure_line for every clip.
2. No source transcript provided: short-extract still returns 3 to 5 conceptual clip proposals with hook angles.

## Approval-gated changes
- The atom wiring in workflow.json and the minimum clip count.

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
