---
file: skills/atoms/materials-list/MAINTAINER_README.md
purpose: keep materials-list cost estimates labeled as estimates and safety-required items flagged.
---

# materials-list: Maintainer README

## Purpose
Write a complete materials and tools list for a DIY project. Cost ranges are always labeled as estimates; safety-required tools are always flagged.

## Non-negotiable invariants
- estimated_cost_range is labeled "estimated range" in the output; never presented as guaranteed prices.
- Any tool with safety_required: true must have a note (e.g., "eye protection required").
- Renter notes appear whenever renter_friendly: true is provided in the input.

## Known failure modes
- Presenting a cost range as an exact price.
- Omitting safety_required: true for tools like heat guns, circular saws, or chemical strippers.
- Missing renter_notes when the project can be adapted.

## Regression cases to preserve
1. High-budget project: estimated_total_range reflects higher-quality material options.
2. Renter-friendly flag: every item includes buy_vs_borrow consideration and renter_notes.

## Update checklist
- Run python3 tools/sync_check.py.
