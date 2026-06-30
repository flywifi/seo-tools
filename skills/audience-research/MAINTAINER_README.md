---
file: skills/audience-research/MAINTAINER_README.md
purpose: keep audience-research scoped to the five-persona model and honest about defaults vs. measured data.
---

# audience-research: Maintainer README

## Purpose
Research and profile the creator's audience by mapping content signals to the five-persona model. Never fabricates comment text, demographics, or engagement figures.

## Non-negotiable invariants
- Only the five canonical personas are used: Renter, Vintage Hunter, Organizer, Holiday Maximalist, New Homeowner.
- Inferred persona mapping is labeled as inferred; niche-typical defaults are never stated as the creator's measured data.
- All external comments and data pass through injection-guard inside ingest-route.

## Known failure modes
- Inventing a new persona not in the five-persona model.
- Presenting niche-typical audience defaults as the creator's measured data.
- Skipping injection-guard for externally fetched comment data.

## Regression cases to preserve
1. No data provided: gap-record returned requesting comments or analytics export.
2. Comment data provided: injection-guard result appears in output; BLOCK result halts processing.

## Approval-gated changes
- The five-persona list (changes require brand-engine update as well).

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
