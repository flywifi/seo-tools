---
file: skills/account-manager/references/artifact-types.md
role: the artifact types account-manager produces and the required elements of each.
---

# account-manager artifact types

## Account report
A health snapshot and renewal signals for one brand account. Required elements: account_id, brand_name, health_score (green/yellow/red), last_contact_days_ago, open_deals count, overdue_invoices count, exclusivity_conflicts list, renewal_candidates list (from renewal-signal, may be empty), recommended_actions list, and a govern-artifact gate result.

## Health snapshot
A single-account health score from account-health. Required elements: health_score, last_contact_days_ago, open_deals, open_deals_total_value_usd, overdue_invoices, exclusivity_conflicts, recommended_action, and notes (which signal drove the score).

## Renewal candidates list
A ranked list of closed deals flagged for re-outreach. Required elements: list of candidates (each: deal_id, brand_name, closed_date, exclusivity_expires, renewal_reason, priority), recommended_next_step, and a note if the list is empty.
