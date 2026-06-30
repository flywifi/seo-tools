---
file: skills/atoms/pitch-paragraph/MAINTAINER_README.md
purpose: keep pitch-paragraph specific to the named brand, connected to the creator's aesthetic, and within 150 to 250 words.
---

# pitch-paragraph: Maintainer README

## Purpose
Write the personalized pitch paragraph for brand outreach. Never write a generic template; always anchor to the specific brand and the creator's aesthetic.

## Non-negotiable invariants
- pitch_paragraph is 150 to 250 words.
- Three subject_line_options are always provided (not one or two).
- personalization_notes flags at least one thing the writer must verify or customize before sending.

## Known failure modes
- Writing a generic paragraph that could apply to any creator.
- Fewer than 3 subject_line_options.
- Omitting personalization_notes entirely.

## Regression cases to preserve
1. Vintage furniture brand: paragraph connects the creator's thrifting pillar and 1920s bungalow aesthetic.
2. Brand fit notes provided: those notes anchor the paragraph; they are not ignored.

## Update checklist
- Run python3 tools/sync_check.py.
