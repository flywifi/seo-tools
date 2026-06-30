---
file: skills/account-manager/MAINTAINER_README.md
purpose: keep account-manager read-only; it never creates, updates, or deletes pipeline records.
---

# account-manager: Maintainer README

## Purpose
CRM first stop for any brand relationship question. Health-checks accounts, scans for renewal candidates, and recommends next steps. Reads pipeline/accounts/ only.

## Non-negotiable invariants
- No pipeline record is created, updated, or deleted by this spoke; it reads only.
- gap-record fires when account_id or brand_name does not resolve to a record.
- Renewal candidates from renewal-signal are always labeled as candidates, not confirmed opportunities.

## Known failure modes
- Attempting to advance a deal stage inside this spoke (that belongs to deal-pipeline).
- Presenting renewal candidates as confirmed without noting they are flagged for Alex's review.
- Fabricating account data when the account is not found.

## Regression cases to preserve
1. Unknown account: gap-record emitted; no fabricated health score.
2. Renewal scan returns 0 candidates: empty list with note; no fabrication.

## Approval-gated changes
- The health_score thresholds in account-health atom.

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
