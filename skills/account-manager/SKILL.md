---
file: skills/account-manager/SKILL.md
name: account-manager
description: "manages brand account records in pipeline/accounts/: health-check, renewal signals, and follow-up recommendations; does NOT create or delete records directly and does NOT advance deal stages."
load: always
---

# account-manager

## Purpose

account-manager is the CRM first stop for any brand relationship question. It reads records from
`pipeline/accounts/`, surfaces health signals for each account, and identifies renewal candidates
for proactive outreach. It does not write to records, advance deal stages, or synthesize creative
content. Every output is grounded in the data present in the pipeline store; null values are
flagged rather than estimated.

## Inputs

| Field | Type | Required | Description |
|---|---|---|---|
| account_id | string | one of account_id or brand_name required | Unique identifier for the brand account record in pipeline/accounts/ |
| brand_name | string | one of account_id or brand_name required | Human-readable brand name; resolved to account_id internally |
| action | enum | required | One of: health_check, renewal_scan, overview |
| lookback_days | integer | optional | Days of history to consider for renewal_scan (default: 180) |

## Primary outputs

Returns an `account_report` object with the following fields:

| Field | Type | Description |
|---|---|---|
| account_id | string | Resolved unique identifier for the account |
| brand_name | string | Display name for the brand |
| health_score | object | Score and signal breakdown produced by the account-health atom |
| open_deals | array | List of open deal references linked to this account |
| renewal_candidates | array | Renewal opportunities surfaced by the renewal-signal atom |
| recommended_actions | list | Prioritized follow-up actions based on health score and renewal signals |
| quality_gate_result | object | Pass/fail result from govern-artifact; includes any flags |

## Atoms composed

- **account-health** -- scores the account on recency, engagement cadence, and deal history
- **renewal-signal** -- scans the lookback window and flags accounts approaching renewal or lapsed
- **gap-record** -- invoked when account_id or brand_name cannot be resolved; returns a structured null rather than fabricating data
- **govern-artifact** -- runs the output through Quality Gates before returning

## Engines required

- `shared/pipeline-engine.md` -- provides the data-access contract, field definitions, and scoring
  schemas for all pipeline/accounts/ operations

## References

- `shared/pipeline-engine.md`
- `protocols/no-fabrication.md`
- `protocols/quality-gates.md`

## Do NOT use for

- Advancing deal stages -- use the deal-pipeline spoke for stage transitions
- Producing media kits or pitches -- use the partnership-mediakit spoke
- Generating creative content of any kind
- Accessing real account data outside the `pipeline/accounts/` records
- Creating or deleting account records directly
