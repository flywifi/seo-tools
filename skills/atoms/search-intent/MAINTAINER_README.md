---
file: skills/atoms/search-intent/MAINTAINER_README.md
purpose: keep search-intent to pure classification; it never writes titles, hooks, or keyword clusters.
---

# search-intent: Maintainer README

## Purpose
Classify the search intent and best-fit content format for a keyword. Feeds downstream atoms; stops at classification.

## Non-negotiable invariants
- Does not call web-intel or retrieve live data; classifies from keyword signals only.
- Returns exactly one intent and one content_format_fit; ambiguity goes into notes.
- confidence reflects signal strength, not certainty; low is a valid and honest output.

## Known failure modes
- Inferring intent from assumed topic knowledge rather than keyword signals.
- Returning two intents instead of one primary.
- Setting confidence to high when the keyword phrase is genuinely ambiguous.

## Regression cases to preserve
1. "how to refinish a thrifted dresser": intent is informational; format is tutorial; confidence high.
2. "best chalk paint brand": intent is commercial; format is review; confidence medium.

## Update checklist
- Run python3 tools/sync_check.py.
