---
file: skills/atoms/renter-alt/MAINTAINER_README.md
purpose: keep renter-alt reversible and honest when no alternative exists.
---

# renter-alt: Maintainer README

## Purpose
Rewrite one step or material to be renter-friendly. Always reversible: true in the output. If no renter-friendly alternative exists, return null and explain why.

## Non-negotiable invariants
- reversible is always true in the output (renter alternatives are non-permanent by definition).
- When no alternative exists: renter_alternative is null with a clear reason; never fabricate a workaround that is actually permanent.
- Tradeoffs are always stated honestly (e.g., "removable peel-and-stick is less durable than paint").

## Known failure modes
- Returning an alternative that still requires wall drilling (not reversible).
- Setting reversible: true for a modification that is actually permanent.
- Omitting the reason when renter_alternative is null.

## Regression cases to preserve
1. Painted accent wall: alternative is peel-and-stick wallpaper or removable fabric panels; reversible: true.
2. Structural shelf: no reversible alternative; null returned with reason explaining load-bearing requirement.

## Update checklist
- Run python3 tools/sync_check.py.
