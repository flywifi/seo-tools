---
file: skills/atoms/seasonal-map/MAINTAINER_README.md
purpose: keep seasonal-map to static seasonal knowledge only; never make live trend calls or fabricate peak windows.
---

# seasonal-map: Maintainer README

## Purpose
Map a topic to its seasonal window using static knowledge from canonical-sources/seasonal-aesthetic/seasonal.json and the four known peaks for moody/vintage home decor. Never make live retrieval calls.

## Non-negotiable invariants
- Does not call web-intel or trend-check; those are separate atoms.
- Peak windows come from canonical-sources or the four documented peaks; not invented.
- Urgency thresholds are deterministic: 0 to 14 days = immediate, 15 to 42 days = upcoming, 43 to 90 days = plan_ahead, else off_season.

## Known failure modes
- Claiming a live trend signal when only static knowledge is used.
- Inventing a peak window not in canonical-sources or the four documented peaks.
- Returning immediate urgency for a topic 8 weeks away.

## Regression cases to preserve
1. Fall mantel topic in July: urgency is upcoming (publish_by mid-August); peak_window is September to October.
2. Evergreen topic (bathroom organization): seasonal_type is evergreen; urgency is plan_ahead year-round.

## Update checklist
- Run python3 tools/sync_check.py.
