---
file: skills/seasonal-trends/MAINTAINER_README.md
purpose: keep seasonal-trends using static seasonal knowledge for window mapping and live retrieval (trend-check) only for momentum validation.
---

# seasonal-trends: Maintainer README

## Purpose
Build a seasonal content plan for a defined window. seasonal-map provides static window knowledge; trend-check provides live momentum validation. Never invents seasonal windows.

## Non-negotiable invariants
- seasonal-map runs first to anchor the window; trend-check is conditional (only fires when trend claims are in scope).
- Stale trend data from trend-check is marked, not dropped.
- The four documented moody/vintage peaks are the canonical windows: fall mantel (Sep to Oct), holiday tablescapes (Nov to Dec), spring refresh (Mar to Apr), summer outdoor (May to Jun).

## Known failure modes
- Inventing a seasonal peak not in canonical-sources or the four documented windows.
- Dropping stale trend data instead of marking it.
- Running trend-check before seasonal-map (wrong order; seasonal-map must anchor first).

## Regression cases to preserve
1. Fall window request in June: urgency is plan_ahead; publish_by is mid-August; peak is Sep to Oct.
2. Trend-check fails for a topic: result is momentum_unknown; not fabricated; gap noted.

## Approval-gated changes
- The four seasonal windows (changes require seasonal-aesthetic data update as well).

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
