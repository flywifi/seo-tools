---
files_combined:
  - skills/account-manager/SKILL.md
  - skills/deal-pipeline/SKILL.md
  - skills/deal-resourcing/SKILL.md
  - skills/partnership-mediakit/SKILL.md
lane: pipeline-crm
note: These are the four Pipeline/CRM lane spokes. Load the one matching the request type.
---

---
file: skills/account-manager/SKILL.md
name: account-manager
description: "manages brand account records in pipeline/accounts/: health-check, renewal signals, and follow-up recommendations; does NOT create or delete records directly and does NOT advance deal stages."
load: always
---

# account-manager

CRM first stop for any brand relationship question. Reads `pipeline/accounts/` records, surfaces
health signals, and identifies renewal candidates. Never writes to records, advances deal stages, or
synthesizes creative content. Null values are flagged, not estimated.

## Inputs

| Field | Required | Description |
|---|---|---|
| `account_id` or `brand_name` | one required | Identifies the brand account record |
| `action` | required | `health_check`, `renewal_scan`, or `overview` |
| `lookback_days` | optional | Days of history for renewal_scan (default: 180) |

## Primary outputs

`account_report` object with: `account_id`, `brand_name`, `health_score`, `open_deals`,
`renewal_candidates`, `recommended_actions`, `quality_gate_result`

## Atoms composed
account-health, renewal-signal, gap-record, govern-artifact

## Engines required
`shared/pipeline-engine.md`

## Do NOT use for
- Advancing deal stages (use deal-pipeline).
- Producing media kits or pitches (use partnership-mediakit).
- Generating creative content.
- Creating or deleting account records directly.

---

---
file: skills/deal-pipeline/SKILL.md
name: deal-pipeline
description: "manages the full deal lifecycle from identified to closed/fulfilled: stage transitions, contract review triggers, usage rights checks, and exclusivity conflict detection; does NOT write pipeline records without going through stage-transition rules."
load: always
---

# deal-pipeline

Manages brand deal records through a 9-stage lifecycle with evidence-gated stage transitions.

## The 9-stage lifecycle

1. **identified** -- potential deal spotted
2. **outreach-sent** -- initial contact made
3. **in-discussion** -- two-way communication active
4. **contract-negotiating** -- formal terms being drafted (contract review triggered here)
5. **signed** -- contract executed by both parties
6. **in-production** -- content being created
7. **delivered** -- content published per contract terms
8. **invoiced** -- payment requested
9. **closed/fulfilled** -- payment received, all obligations met

**archived**: terminal side-state for cancelled or lapsed deals.

## Evidence-gated transitions
No stage advance is written without the required evidence fields for that transition.
`deal-stage-advance` validates evidence and writes the record. Skipping stages is rejected.

## FTC disclosure requirement
`ftc_disclosure_required` is set to `true` on every deal where `deal_type` is sponsored, gifted,
affiliate, or barter. Enforced by `protocols/safety.md`.

## Inputs
- `deal_id` (required for advance or status check)
- `brand_name` (required for new deal creation)
- `action`: `advance_stage`, `create_deal`, `check_status`, `check_exclusivity`
- `target_stage`, `evidence` (per-transition schema in `shared/pipeline-engine.md`)

## Primary outputs
`deal_report` with: `deal_id`, `brand_name`, `current_stage`, `stage_change_record`,
`usage_rights_summary`, `exclusivity_conflicts`, `ftc_disclosure_required`,
`recommended_next_step`, `quality_gate_result`

## Atoms composed
deal-stage-advance, usage-rights-check, account-health, gap-record, govern-artifact

## Engines required
`shared/pipeline-engine.md`

## Do NOT use for
- Generating creative content.
- Writing media kits or pitch decks (use partnership-mediakit).
- Advancing a deal to a non-adjacent stage in a single action.
- Bypassing stage-transition evidence requirements.

---

---
file: skills/deal-resourcing/SKILL.md
name: deal-resourcing
description: takes a signed deal and produces a production resource plan: task list with due dates, production timeline, invoice schedule, and go/no-go checklist. Pipeline/CRM lane spoke.
load: always
---

# deal-resourcing

Converts a signed brand deal into a complete, actionable production resource plan. Reads
`pipeline/deals/`, validates the stage, and emits a task list, timeline, invoice schedule,
and go/no-go checklist.

**Stage gate:** only processes deals in `signed`, `in-production`, or `delivered` stage.

**Financial fields:** all rates and invoice amounts come directly from the deal record. No rate
is estimated or inferred from benchmarks unless the deal record explicitly says to apply one.
Per `protocols/no-fabrication.md`, fabricated rates are a hard-fail violation.

## Inputs
```json
{
  "deal_id": "string",
  "as_of_date": "ISO-8601 date (defaults to today)",
  "options": {
    "include_roi_metric": true,
    "invoice_currency": "USD",
    "task_granularity": "summary | detailed"
  }
}
```

## Primary outputs
```json
{
  "go_no_go": { "status": "GO | NO-GO | CONDITIONAL", "blocking_gaps": [], "conditions": [] },
  "task_list": [{ "task_id", "deliverable", "step", "owner", "due_date", "status" }],
  "production_timeline": { "start_date", "publish_date", "milestones": [] },
  "invoice_schedule": [{ "invoice_id", "amount", "trigger", "due_date", "status" }],
  "roi_metric": { "projected_rate", "actual_rate", "projected_cpm", "actual_cpm" },
  "retrieval_gaps", "fabrication_flags", "human_review_required": true
}
```

Key guarantees:
- `go_no_go.status` is `NO-GO` whenever any blocking gap exists.
- All `due_date` fields are null (never estimated) when not derivable from the deal record.
- `human_review_required` is always `true`.

## Atoms composed
production-task, invoice-status, roi-metric (conditional), gap-record, govern-artifact

## Engines required
`shared/pipeline-engine.md`

## Do NOT use for
- Deals in prospecting, outreach, proposal, or closed-lost stage (advance via deal-pipeline first).
- Estimating rates or invoice amounts not in the deal record.
- Account-level relationship management (use account-manager).

---

---
file: skills/partnership-mediakit/SKILL.md
name: partnership-mediakit
description: Pipeline/CRM spoke that builds brand partnership outreach materials for the creator: pitch paragraph, media kit sections, and rate card. Uses real data when supplied; uses labeled benchmarks when not.
load: always
---

# partnership-mediakit

Assembles a complete brand partnership outreach package: pitch paragraph, media kit sections, and
rate card. Uses real channel data when supplied; uses labeled industry benchmark ranges when absent;
returns explicit placeholders for anything that cannot be filled.

`human_review_required` is always `true`. FTC disclosure reminder is always included in
`compliance_notes`. No metric, brand name, or rate is invented.

## Inputs
```json
{
  "brand_name": "string (required)",
  "brand_product_category": "string (required)",
  "proposed_format": "integration | dedicated | short-form (required)",
  "brand_fit_notes": "string or null",
  "alex_pillar": "string or null",
  "channel_data": { "subscribers", "avg_views_per_video", "engagement_rate_pct", ... },
  "alex_actual_rates": { "long-form-integration", "dedicated-video", "short-form", ... },
  "sections_requested": ["channel_overview", "audience_demo", "content_pillars", "partnership_formats", "case_study", "rates_summary"],
  "crm_account_id": "string or null"
}
```

## Primary outputs
```json
{
  "pitch_paragraph": { "body", "subject_line_options", "personalization_notes", "fabrication_check" },
  "media_kit_sections": [{ "section_name", "section_body", "data_source", "placeholders_to_fill" }],
  "rate_card": { "line_items": [{ "format", "rate_or_range", "source" }], "disclaimer" },
  "compliance_notes": ["FTC disclosure reminder always present"],
  "placeholders_to_fill": ["aggregate list of unresolved placeholders"],
  "govern_artifact_result": "PASS | HOLD:<reason>",
  "human_review_required": true
}
```

Key guarantees:
- `disclaimer` is present whenever any rate carries `source: benchmark_range`.
- `compliance_notes` always includes the FTC disclosure reminder.
- Benchmark rates are labeled as industry reference ranges, never the creator's personal rates.

## Atoms composed
pitch-paragraph, mediakit-section (per section), rate-card-fill, govern-artifact

## Engines required
`shared/brand-engine.md`, `shared/pipeline-engine.md`

## Do NOT use for
- Deciding which brands to pitch (use content-strategy or deal-pipeline for prospecting).
- Sending outreach emails or posting to any external platform.
- Fabricating subscriber counts, engagement rates, or audience demographics.
- Presenting benchmark rates as the creator's personal rates.
- Outreach for product categories outside moody-vintage home decor, DIY, thrifting, seasonal decor, or outdoor living.
