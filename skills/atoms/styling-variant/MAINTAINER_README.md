---
file: skills/atoms/styling-variant/MAINTAINER_README.md
purpose: keep styling-variant to 2 to 3 aesthetic remixes with descriptive swap language; never fabricate specific product SKUs or prices.
---

# styling-variant: Maintainer README

## Purpose
Generate 2 to 3 aesthetic remixes of a completed project. Swap suggestions use descriptive language, not specific products.

## Non-negotiable invariants
- Always returns 2 to 3 variants; never 1 or 4.
- No specific product SKUs, brand names as required items, or guaranteed prices in swap descriptions.
- difficulty_delta and budget_delta are relative to the base project, never absolute claims.

## Known failure modes
- Returning only 1 variant when the base project has obvious remix potential.
- Naming a specific product ("Rust-Oleum Chalked") as the required item rather than a descriptive category ("chalk-finish paint").
- Stating a budget_delta as an exact dollar amount instead of a relative direction.

## Regression cases to preserve
1. Moody base + cottagecore remix: color palette shifts from dark to muted sage/cream; materials swap from velvet to linen.
2. Renter-friendly flag: all variants preserve reversibility; no permanent modifications.

## Update checklist
- Run python3 tools/sync_check.py.
