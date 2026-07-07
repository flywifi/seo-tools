---
file: skills/atoms/account-health/SKILL.md
name: account-health
description: evaluate the health of a brand partnership account by reading its record from pipeline/accounts/ and returning a structured health snapshot. Use when a spoke needs to know whether an account is in good standing before scheduling outreach, proposing a deal, or renewing a contract. Do NOT use to edit, create, or delete account records; this atom reads and scores only.
load:
  - shared/pipeline-engine.md
  - protocols/no-fabrication.md
---

# account-health

Read one account record from `pipeline/accounts/` and produce a deterministic health snapshot. Every
field in the output comes directly from the stored record; nothing is estimated or inferred beyond the
scoring thresholds defined below.

## Purpose

Brand partnerships require ongoing attention: missed follow-ups stall deals, overdue invoices damage
trust, and exclusivity conflicts can violate signed contracts. This atom centralizes the health check
so any spoke can request it without duplicating logic. The output surfaces the five signal categories
(recency, open deals, invoice status, exclusivity, and deal value) as a single green/yellow/red score
plus a recommended action.

Scoring thresholds (read from record timestamps and counts; never from memory or guesses):

| Signal | Green | Yellow | Red |
|---|---|---|---|
| last_contact_days_ago | 0 to 30 | 31 to 60 | 61 or more |
| open_deals | 0 to 2 | 3 to 4 | 5 or more |
| overdue_invoices | 0 | 1 | 2 or more |
| exclusivity_conflicts | 0 | 1 | 2 or more |

Overall health_score is the worst individual signal. If any signal is red, the account is red.

## Inputs

```json
{
  "account_id": "string or null -- preferred; the unique ID in pipeline/accounts/",
  "brand_name": "string or null -- fallback if account_id is unknown; must match exactly one record"
}
```

Exactly one of `account_id` or `brand_name` must be provided, and `brand_name` must match one
record exactly. This atom does NOT do fuzzy or nickname matching itself: when the caller has only
a loose phrase ("that lightbulb company"), run `account-resolve` first (it handles the fuzzy,
alias, and brand-category resolution and returns one `account_id`), then pass that exact id here.
If neither input resolves to a record, emit a gap-record object (see `shared/pipeline-engine.md`)
and halt; do not fabricate a score.

## Output

```json
{
  "tool": "account-health",
  "account_id": "string",
  "brand_name": "string",
  "health_score": "green | yellow | red",
  "last_contact_days_ago": 0,
  "open_deals": 0,
  "open_deals_total_value_usd": 0,
  "overdue_invoices": 0,
  "exclusivity_conflicts": ["list of conflicting brand names, empty if none"],
  "recommended_action": "follow_up | review_contract | no_action",
  "notes": "one sentence stating which signal drove the score, or 'all signals green' if health_score is green"
}
```

Field rules:
- `last_contact_days_ago` is computed from the record's `last_contact_date` relative to today's date. If `last_contact_date` is absent, treat as null and flag in `notes`; do not estimate.
- `open_deals_total_value_usd` is the sum of `value_usd` across all open deal records linked to this account. If any deal lacks a value, sum only the present values and note the gap.
- `exclusivity_conflicts` lists every brand in the account's exclusivity clause whose category overlaps with another active account in `pipeline/accounts/`. Pull from the stored exclusivity fields; do not infer conflicts from brand names alone.
- `recommended_action` maps from `health_score`: red yields `follow_up` or `review_contract` (use `review_contract` when overdue_invoices or exclusivity_conflicts drove the red); yellow yields `follow_up`; green yields `no_action`.

## Do NOT use for

- Creating, updating, or deleting any record in `pipeline/accounts/` or `pipeline/deals/` (use the appropriate CRM write atom).
- Generating outreach copy or proposal drafts (use a content or document spoke).
- Scoring across all accounts in bulk; this atom handles one account per call.
- Estimating or guessing any field that is absent from the stored record (`protocols/no-fabrication.md`). Null and flag instead.
- Making final release decisions; output must pass through govern-artifact before surfacing to the user.

## Pipeline note

Follows `shared/pipeline-engine.md` for record resolution and gap handling. All data originates in
`pipeline/accounts/` and `pipeline/deals/`; real records are gitignored and never committed.
Obeys `protocols/no-fabrication.md`: if a required field is missing, emit a gap-record object
rather than an estimate. Pass the output to govern-artifact before the spoke returns it to the user.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
