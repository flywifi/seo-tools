---
file: skills/atoms/title-generate/MAINTAINER_README.md
purpose: keep title-generate to human-first, keyword-front-loaded options that never overpromise.
---

# title-generate: Maintainer README

## Purpose
Generate a few title options, human readable first and SEO aware second.

## Non-negotiable invariants
- Front-load the primary keyword; balance curiosity with clarity.
- Title and the eventual thumbnail must align; never overpromise.
- Length guidance from `shared/platform-engine.md`.

## Known failure modes
- Keyword-stuffed titles that read like a robot.
- Clickbait that the video does not deliver.

## Regression cases to preserve
1. Search and how-to concept: primary keyword is front-loaded, length near 80 to 100 characters.
2. Each option reports its character count.

## Update checklist
- Run python3 tools/sync_check.py.
