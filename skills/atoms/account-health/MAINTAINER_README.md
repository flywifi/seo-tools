---
file: skills/atoms/account-health/MAINTAINER_README.md
purpose: keep account-health as a pure read-and-score operation with no record writes.
---

# account-health: Maintainer README

## Purpose
Read one pipeline/accounts/ record and return a deterministic health snapshot. Green/yellow/red scoring is driven by stored timestamps and counts only; nothing is estimated.

## Non-negotiable invariants
- All data comes from pipeline/accounts/ and pipeline/deals/; never estimated or inferred beyond the scoring thresholds.
- null field in the record means null in the output; never substitute a default or guess.
- Output passes through govern-artifact before reaching the user.

## Known failure modes
- Computing last_contact_days_ago from memory instead of the stored last_contact_date.
- Inferring exclusivity conflicts from brand names alone instead of the stored exclusivity fields.
- Returning a health score when neither account_id nor brand_name resolves to a record.

## Regression cases to preserve
1. Missing last_contact_date: output null for that field and note the gap; do not score it as 0 days ago.
2. Two or more overdue invoices: health_score is red regardless of all other signals.
3. Unknown account: emit a gap-record object; do not fabricate a score.

## Update checklist
- Run python3 tools/sync_check.py.
