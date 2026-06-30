---
file: skills/atoms/pin-write/MAINTAINER_README.md
purpose: keep pin-write keyword-front-loaded, within Pinterest character limits, and SEO-optimized for the home decor niche.
---

# pin-write: Maintainer README

## Purpose
Write a Pinterest Pin title, description, and alt text. Pinterest is a search engine; titles must be keyword-first.

## Non-negotiable invariants
- pin_title: max 100 chars, primary keyword must appear in the first 40 chars.
- pin_description: max 500 chars, keyword-rich, ends with a CTA.
- alt_text: descriptive for accessibility; does not duplicate the title verbatim.

## Known failure modes
- Burying the keyword in the middle of the title.
- Exceeding 500 chars in the description.
- Writing alt_text as "decorative image" with no descriptive content.

## Regression cases to preserve
1. keyword_cluster provided from keyword-cluster atom: primary keyword appears first in title.
2. Pinterest-specific niche vocabulary used (e.g., "vintage home decor ideas" not "nice house stuff").

## Update checklist
- Run python3 tools/sync_check.py.
