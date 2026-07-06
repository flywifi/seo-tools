---
file: skills/account-manager/SKILL.md
name: account-manager
description: "manages brand account records in pipeline/accounts/: health-check, renewal signals, and follow-up recommendations; does NOT create or delete records directly and does NOT advance deal stages."
load: always
---

_Data freshness: as of 2026-07-06 (Creator OS baseline 7ffff31a). Live updates come from your own store; see docs/FRESHNESS.md._

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

---

---
file: skills/deal-pipeline/SKILL.md
name: deal-pipeline
description: "manages the full deal lifecycle from identified to closed/fulfilled: stage transitions, contract review triggers, usage rights checks, and exclusivity conflict detection; does NOT write pipeline records without going through stage-transition rules."
load: always
---

# deal-pipeline

deal-pipeline is the Pipeline/CRM spoke responsible for managing brand deal records through a 9-stage lifecycle. It enforces evidence-gated stage transitions, triggers contract review at the appropriate stage, checks usage rights, and detects exclusivity conflicts across active deals.

### The 9-stage lifecycle

1. **identified** -- a potential deal has been spotted or flagged (brand name, category, source noted)
2. **outreach-sent** -- initial contact has been made to the brand or its representative
3. **in-discussion** -- two-way communication is active; rates, deliverables, or fit are being explored
4. **contract-negotiating** -- formal terms are being drafted or reviewed; contract review is triggered at this stage
5. **signed** -- contract is executed by both parties
6. **in-production** -- content is being created or scheduled
7. **delivered** -- content has been published or submitted per contract terms
8. **invoiced** -- payment has been requested
9. **closed/fulfilled** -- payment received and all obligations met

**archived** is a terminal side-state applied to deals that are cancelled, declined, or lapsed at any stage. Archived deals are retained for exclusivity and history lookups but do not advance through stages.

### Evidence-gated transitions

No stage advance is written without the required evidence fields for that transition. The atom `deal-stage-advance` validates evidence and writes the stage-change record. Attempts to skip stages or advance without evidence are rejected and returned as quality gate failures.

### Contract review rule triggers

When a deal moves to **contract-negotiating**, deal-pipeline automatically flags:
- contract review required (route to legal or designated reviewer)
- usage rights scope (exclusivity window, platforms, content types) must be captured before advancing to signed

### FTC disclosure requirement

FTC disclosure is required on ALL sponsored, gifted, and affiliate deals. The `ftc_disclosure_required` flag is set to `true` on every deal where `deal_type` is any of: sponsored, gifted, affiliate, barter. This flag surfaces in every deal report regardless of stage and is enforced by `protocols/safety.md`.

## Inputs

| Field | Required | Notes |
|---|---|---|
| `deal_id` | required for stage advance or status check | assigned at deal creation |
| `brand_name` | required for new deal creation | must resolve against pipeline accounts |
| `action` | required | one of: `advance_stage`, `create_deal`, `check_status`, `check_exclusivity` |
| `target_stage` | required when action is `advance_stage` | must be the immediately next stage or `archived` |
| `evidence` | conditionally required | required fields vary by transition; see `shared/pipeline-engine.md` for per-transition evidence schema |

## Primary outputs

A single `deal_report` object with the following fields:

| Field | Type | Description |
|---|---|---|
| `deal_id` | string | the canonical deal identifier |
| `brand_name` | string | resolved brand name from pipeline accounts |
| `current_stage` | string | stage after the action completes |
| `stage_change_record` | object or null | populated by `deal-stage-advance` when action is `advance_stage`; null otherwise |
| `usage_rights_summary` | object or null | populated by `usage-rights-check`; null if not yet captured |
| `exclusivity_conflicts` | array | populated by `account-health`; empty array if no conflicts detected |
| `ftc_disclosure_required` | boolean | true for sponsored, gifted, affiliate, and barter deal types |
| `recommended_next_step` | string | the single most actionable next step given current stage and evidence state |
| `quality_gate_result` | object | pass or fail with reason; fail blocks all writes |

## Atoms composed

- `deal-stage-advance` -- validates evidence for the requested transition and writes the stage-change record
- `usage-rights-check` -- extracts and validates usage rights scope from contract evidence
- `account-health` -- checks active and recent deals for exclusivity conflicts in the same category or brand group
- `gap-record` -- flags and records missing required fields without blocking the report
- `govern-artifact` -- runs the quality gate check before any write is committed

## Engines required

- `shared/pipeline-engine.md` -- stage definitions, per-transition evidence schemas, exclusivity logic, and CRM record format

## References

- `shared/pipeline-engine.md` -- authoritative stage and transition rules
- `protocols/safety.md` -- contract review triggers and FTC disclosure rules
- `protocols/no-fabrication.md` -- no rates, terms, or brand data may be inferred or invented; null and flag instead
- `protocols/quality-gates.md` -- governs all writes; quality gate must pass before any record is updated

## Do NOT use for

- Generating creative content of any kind
- Writing media kits or pitch decks (use `partnership-mediakit`)
- Running account-level health scans across the full portfolio (use `account-manager`)
- Accessing legal systems, sending notifications, or executing contracts
- Advancing a deal to a non-adjacent stage in a single action
- Any action that bypasses stage-transition evidence requirements

---

---
file: skills/deal-resourcing/SKILL.md
name: deal-resourcing
description: takes a signed deal and produces a production resource plan: task list with due dates, production timeline, invoice schedule, and go/no-go checklist. Pipeline/CRM lane spoke.
load: always
---

# deal-resourcing

Pipeline/CRM lane spoke that converts a signed brand deal into a complete, actionable production
resource plan. It reads the deal record from `pipeline/deals/`, validates the stage, and emits a
task list, production timeline, invoice schedule, and go/no-go checklist that the creator can
act on immediately.

## Purpose

deal-resourcing answers the question: "Now that this deal is signed, what exactly needs to happen,
when does each step need to be done, and when do I get paid?" It does not negotiate terms, draft
contracts, or create new deal records. It does not fabricate due dates, invoice amounts, or
deliverable specs that are not present in the deal record. Any field that is missing or ambiguous is
recorded as a gap via gap-record and flagged for human resolution before the plan is considered
complete.

The spoke enforces the stage gate: it will only process deals in the `signed`, `in-production`, or
`delivered` stage. Deals in `prospecting`, `outreach`, `proposal`, or `closed-lost` are rejected
with a clear status message directing the user to deal-pipeline instead.

All financial figures (rates, invoice amounts, payment dates) come directly from the deal record or
a confirmed amendment. No rate is estimated or inferred from benchmarks unless the deal record
explicitly says to apply a benchmark and names the benchmark source. Per `protocols/no-fabrication.md`,
fabricated rates are a hard-fail violation.

## Inputs

```json
{
  "deal_id": "string -- the deal slug matching a file under pipeline/deals/",
  "as_of_date": "ISO-8601 date -- defaults to today if omitted; used to compute relative due dates",
  "options": {
    "include_roi_metric": true,
    "invoice_currency": "USD",
    "task_granularity": "summary | detailed"
  }
}
```

- `deal_id`: required. If the referenced file does not exist or the deal stage is not `signed`,
  `in-production`, or `delivered`, the spoke returns a stage-gate rejection and records a gap.
- `as_of_date`: optional. Defaults to today. All relative due-date calculations anchor to this
  value.
- `include_roi_metric`: optional boolean, default true. When true, roi-metric is composed to append
  a projected and (if available) actual ROI summary to the plan.
- `invoice_currency`: optional string, default `USD`. Applied to all invoice schedule line items.
- `task_granularity`: optional, default `detailed`. `summary` returns one task per deliverable;
  `detailed` breaks each deliverable into its constituent production steps.

## Primary outputs

```json
{
  "skill": "deal-resourcing",
  "deal_id": "string",
  "deal_stage": "signed | in-production | delivered",
  "as_of_date": "ISO-8601 date",
  "go_no_go": {
    "status": "GO | NO-GO | CONDITIONAL",
    "blocking_gaps": ["list of gap IDs that must be resolved before production begins; empty if GO"],
    "conditions": ["list of conditions that must be met for a CONDITIONAL to upgrade to GO"]
  },
  "task_list": [
    {
      "task_id": "string",
      "deliverable": "string -- the contractual deliverable this task belongs to",
      "step": "string -- the specific production action",
      "owner": "the creator | brand | agency | TBD",
      "due_date": "ISO-8601 date or null",
      "due_date_note": "string or null -- explains null or a date flagged as estimated",
      "status": "not-started | in-progress | complete | blocked"
    }
  ],
  "production_timeline": {
    "start_date": "ISO-8601 date or null",
    "publish_date": "ISO-8601 date or null",
    "milestones": [
      {
        "milestone": "string",
        "date": "ISO-8601 date or null",
        "note": "string or null"
      }
    ]
  },
  "invoice_schedule": [
    {
      "invoice_id": "string",
      "amount": "number or null",
      "currency": "USD",
      "trigger": "string -- e.g. contract-signing, content-approval, 30-days-post-publish",
      "due_date": "ISO-8601 date or null",
      "status": "pending | sent | paid | overdue | null",
      "note": "string or null"
    }
  ],
  "roi_metric": {
    "projected_rate": "number or null",
    "actual_rate": "number or null",
    "projected_cpm": "number or null",
    "actual_cpm": "number or null",
    "note": "string or null -- explains null fields or flags unverified values"
  },
  "retrieval_gaps": [
    {
      "tool": "gap-record",
      "gap_type": "string",
      "description": "string",
      "impact": "string",
      "recommended_next_step": "string"
    }
  ],
  "fabrication_flags": ["any field that could not be confirmed and is marked [unverified]"],
  "human_review_required": true
}
```

Key output guarantees:

- `go_no_go.status` is `NO-GO` whenever any blocking gap exists (missing publish date, missing
  invoice trigger, unconfirmed rate). It upgrades to `CONDITIONAL` only when gaps are non-blocking
  (for example, a secondary deliverable date that has not been set yet).
- All `due_date` fields are null and a `due_date_note` is written when the date cannot be derived
  from the deal record. The date is never estimated.
- `invoice_schedule` amounts come directly from the deal record. If the record omits an amount, the
  field is null and a gap is recorded.
- `human_review_required` is always `true`. govern-artifact must pass before the resource plan is
  shared with a brand contact or used to trigger any financial action.

## Atoms composed

1. production-task: reads the deliverables list from the deal record and expands each deliverable
   into a sequenced set of production tasks with owner assignments and computed due dates.
2. invoice-status: reads the payment schedule from the deal record; maps each payment trigger to a
   calendar date; returns the invoice schedule with current status.
3. roi-metric: computes projected and actual ROI and CPM figures from the deal rate and the deal
   record's performance data. Called only when `include_roi_metric` is true.
4. gap-record: called for every field or computation that cannot be resolved from the deal record.
   Produces an explicit gap object rather than a silent blank or estimate.
5. govern-artifact: gates the completed resource plan through quality-review before it is returned
   to the user or a downstream spoke.

## Engines required

- `shared/pipeline-engine.md`: authoritative deal schema, stage definitions, stage-transition rules,
  and payment trigger taxonomy. This spoke reads deal stage and all financial fields from there.

## References

- `shared/pipeline-engine.md`
- `protocols/no-fabrication.md`
- `protocols/quality-gates.md`
- `protocols/formatting-metadata.md`

## Do NOT use for

- Deals in the `prospecting`, `outreach`, `proposal`, or `closed-lost` stage. Use deal-pipeline to
  advance or close a deal before invoking deal-resourcing.
- Drafting or amending contract terms, deliverable specs, or rates. Those changes must be made in
  the deal record by the user; deal-resourcing reads from the record, it never writes to it.
- Estimating rates, CPMs, or invoice amounts when none are present in the deal record. Record a gap
  and surface it for human resolution.
- Account-level relationship management or outreach drafting. Use account-manager for those tasks.
- Any deal not associated with the creator's Creator OS pipeline. This spoke is calibrated to
  the pipeline schema in `shared/pipeline-engine.md` and will misread records from other schemas.

---

---
file: skills/partnership-mediakit/SKILL.md
name: partnership-mediakit
description: Pipeline/CRM spoke that builds brand partnership outreach materials for the creator: pitch paragraph, media kit sections, and rate card. Uses real data when supplied; uses labeled benchmarks when not.
load: always
---

# partnership-mediakit

Pipeline/CRM lane spoke that assembles a complete brand partnership outreach package for the creator's home decor and DIY channel. On a single request it produces the pitch
paragraph, the full set of media kit sections, and a rate card. It never guesses at figures or
invents data: real channel data is used when the caller supplies it; labeled industry benchmark
ranges from `canonical-sources/rate-benchmarks/benchmarks.json` are used when real data is absent;
fields that cannot be filled by either source are returned as explicit placeholders.

## Purpose

Brand partnerships are the primary direct-revenue lane for this channel. partnership-mediakit
exists so that every outreach package the creator sends is accurate, on-brand, legally compliant, and
ready for human review before it leaves the system. It orchestrates four atoms in sequence and
gates the completed package through govern-artifact before surfacing it to the user.

The spoke answers the question: "Given a target brand and whatever channel data I have right now,
what is the strongest, most honest outreach package I can produce?"

It does not make strategic decisions about which brands to pursue, set editorial direction, or
write any copy that could not be defended line-by-line against `protocols/no-fabrication.md`.

Key invariants:

- Benchmark rates are always labeled as industry reference ranges, never as the creator's personal rates.
  This rule is enforced at the atom level (rate-card-fill) and re-checked by govern-artifact.
- Any sponsored content arrangement described in this package must carry an FTC disclosure note per
  `protocols/safety.md`. The spoke flags this in the pitch paragraph's `personalization_notes` and
  in the final package's `compliance_notes` field. The human sender is responsible for including the
  disclosure statement in the final published content.
- No metric, brand name, campaign result, audience demographic, or rate figure is invented. Fields
  that cannot be sourced are returned as null with a `placeholders_to_fill` entry.
- The package is not final until govern-artifact passes and a human reviewer has resolved all
  `placeholders_to_fill` entries.

All voice and identity language comes from `shared/brand-engine.md` (professional outreach mode).
All CRM facts (existing deal stage, brand account history) are read from `shared/pipeline-engine.md`
and the relevant `pipeline/accounts/` and `pipeline/deals/` records when available; they are never
assumed or invented.

## Inputs

```json
{
  "brand_name": "string -- exact brand name as it should appear in the pitch and media kit",
  "brand_product_category": "string -- the product category or specific product line being pitched",
  "proposed_format": "integration | dedicated | short-form -- primary content format to propose",
  "brand_fit_notes": "string or null -- optional: specific aesthetic or audience overlap the caller knows; strengthens the pitch paragraph if provided",
  "alex_pillar": "string or null -- optional: which of the creator's five content pillars this partnership fits",
  "channel_data": {
    "subscribers": "integer or null",
    "avg_views_per_video": "integer or null",
    "engagement_rate_pct": "number or null",
    "avg_monthly_views": "integer or null",
    "top_demographics": "object or null",
    "recent_case_study": "object or null"
  },
  "alex_actual_rates": {
    "long-form-integration": "number or string or null",
    "dedicated-video": "number or string or null",
    "short-form": "number or string or null",
    "instagram-reel": "number or string or null",
    "tiktok": "number or string or null",
    "pinterest-pin": "number or string or null",
    "usage-rights-addon": "number or string or null",
    "exclusivity-addon": "number or string or null"
  },
  "sections_requested": [
    "channel_overview",
    "audience_demo",
    "content_pillars",
    "partnership_formats",
    "case_study",
    "rates_summary"
  ],
  "crm_account_id": "string or null -- pipeline/accounts/ record ID for this brand, if one exists"
}
```

Field rules:

- `brand_name` and `brand_product_category` are required. The spoke cannot produce a grounded pitch
  without them.
- `proposed_format` is required. Choose one of `integration`, `dedicated`, or `short-form`. The
  pitch paragraph and partnership_formats section are built around this choice.
- `channel_data` and `alex_actual_rates` are both optional. Any field within them may be null.
  Missing fields fall through to benchmark ranges or placeholders per the atom-level rules.
- `sections_requested` defaults to all six sections if omitted.
- `crm_account_id` is optional. When provided, the spoke reads the account record via
  `shared/pipeline-engine.md` to incorporate known deal history or contact details into
  `personalization_notes`. When absent, the spoke proceeds without CRM context.

## Primary outputs

```json
{
  "skill": "partnership-mediakit",
  "brand_name": "echo of input",
  "proposed_format": "echo of input",
  "pitch_paragraph": {
    "body": "string -- 150 to 250 words; professional, warm, specific; ready to paste into an outreach email draft",
    "subject_line_options": [
      "string -- direct value proposition angle",
      "string -- aesthetic or niche angle",
      "string -- question or curiosity angle"
    ],
    "personalization_notes": [
      "string -- items the sender must verify or customize before use, including mandatory FTC disclosure reminder"
    ],
    "fabrication_check": "PASS | FLAG:<reason>"
  },
  "media_kit_sections": [
    {
      "section_name": "string -- one of the six section names",
      "section_title": "string -- display heading",
      "section_body": "string -- markdown-formatted section body",
      "data_source": "real | benchmark | placeholder | mixed",
      "benchmark_label": "string or null -- present when data_source is benchmark or mixed",
      "placeholders_to_fill": ["list of fields requiring real data before publishing"],
      "fabrication_check": "PASS | FLAG:<reason>"
    }
  ],
  "rate_card": {
    "line_items": [
      {
        "format": "string",
        "rate_or_range": "string or null",
        "source": "personal_rate | benchmark_range | no_data",
        "notes": "string or null"
      }
    ],
    "disclaimer": "string or null -- present whenever any line item carries source: benchmark_range",
    "recommended_negotiation_floor": "string or null"
  },
  "compliance_notes": [
    "FTC disclosure: any sponsored content produced under this partnership must include a clear and conspicuous disclosure statement per protocols/safety.md. The sender is responsible for including the disclosure in the final published content.",
    "All benchmark rates are industry reference ranges only; verify against current market data before quoting to a brand."
  ],
  "placeholders_to_fill": ["aggregate list of all unresolved placeholders across pitch, sections, and rate card"],
  "govern_artifact_result": "PASS | HOLD:<reason>",
  "human_review_required": true
}
```

Output guarantees:

- `human_review_required` is always `true`. No package is final until a human reviewer has
  resolved every entry in `placeholders_to_fill` and the sender has confirmed `compliance_notes`.
- `govern_artifact_result` is `PASS` only when govern-artifact clears the full package through
  `protocols/quality-gates.md`. A `HOLD` result surfaces the blocking reason; the spoke does not
  suppress or soften it.
- `disclaimer` in the rate card is null only when every line item carries `source: personal_rate`.
  Whenever any benchmark range appears, the full disclaimer text from rate-card-fill is present.
- `compliance_notes` always includes the FTC disclosure reminder regardless of whether
  `proposed_format` is a dedicated video, integration, or short-form piece.

## Atoms composed

1. pitch-paragraph: writes the personalized pitch paragraph, three subject line options, and
   personalization notes for the brand. Called first. Receives `brand_name`,
   `brand_product_category`, `proposed_format`, `brand_fit_notes`, and `alex_pillar`.
2. mediakit-section (called once per requested section): writes one self-contained media kit
   section per invocation, using `channel_data` and `brand_name` as inputs. The spoke sequences
   these calls across all entries in `sections_requested`.
3. rate-card-fill: populates the rate card from `alex_actual_rates` when supplied, falling back to
   `canonical-sources/rate-benchmarks/benchmarks.json` benchmark ranges with mandatory labeling.
4. govern-artifact: gates the assembled package through `protocols/quality-gates.md` before the
   spoke returns output to the user. Any quality gate failure is surfaced as `HOLD` in
   `govern_artifact_result`; the spoke never silently passes a failing package.

## Engines required

- `shared/brand-engine.md`: channel identity, aesthetic description, content pillars, voice modes
  (professional outreach mode for pitch and media kit copy).
- `shared/pipeline-engine.md`: CRM record access and deal-stage context; used when
  `crm_account_id` is provided to pull existing account history into `personalization_notes`.

## References

- `shared/brand-engine.md`
- `shared/pipeline-engine.md`
- `protocols/safety.md`
- `protocols/no-fabrication.md`
- `protocols/quality-gates.md`
- `canonical-sources/rate-benchmarks/benchmarks.json`

## Do NOT use for

- Deciding which brands to pitch or evaluating brand fit as a strategy. This spoke builds materials
  for a brand the caller has already selected. Use content-strategy or deal-pipeline for brand
  prospecting and prioritization.
- Sending outreach emails, posting to any external platform, or writing any content to any CRM
  record. This spoke produces text only; all external actions require a human.
- Producing final publishable materials without human review. `human_review_required` is always
  `true`; every `placeholders_to_fill` entry must be resolved and `compliance_notes` confirmed
  before the package goes out.
- Presenting benchmark rate ranges as the creator's personal rates in any context. Benchmark figures are
  always labeled as industry reference ranges. Presenting them otherwise violates
  `protocols/no-fabrication.md`.
- Fabricating subscriber counts, engagement rates, audience demographics, case study outcomes, or
  brand endorsements. If real data is not supplied and no benchmark applies, the field is null and
  flagged, never filled with an invented figure.
- Outreach for product categories outside home decor, DIY, thrifting, seasonal decor,
  or outdoor living. Pitches for out-of-niche products misrepresent the creator's audience and brand.
- Creating or updating `pipeline/` CRM records. Read access to an existing account record is
  permitted when `crm_account_id` is supplied; write operations belong to deal-pipeline or
  account-manager.

---

# task-desk (P35: project task & obligation tracker)

Tracks the outstanding work a brand deal generates: event-triggered, source-cited tasks per deal and
contract; who is responsible (creator vs brand vs agency); backwards-planning from a deadline; recurring
duties; waiting-on-the-brand follow-ups; shipment anchors; payment-milestone billable readiness; and
deliverable requirement-coverage verification.

Routes: `task_status`, `task_plan`, `coverage_check`, `shipment_update`, `milestone_bill`.

Non-negotiables: every task cites a real source (a contract clause, an email Message-ID, a user statement, or
a named rule + anchor event) — no phantom tasks. Nothing is sent, invoiced, or posted automatically; nudges,
replies, and invoices are drafted for the human. Waiting-on items surface as aging follow-ups, not silent
creator to-dos. Coverage cites the supporting sentence or abstains, never inferring.

Capability tiers (see docs/TASK-TRACKER.md for the setup runbook):
- Claude Desktop + MCP: full offline compute (tools/tasks.py, shipments.py, coverage_verify.py), the carrier
  connector, and .ics export.
- claude.ai web / mobile: the tracker runs as an Agent Skill with the native Google Drive/Sheets store (the
  same file Desktop uses, so tasks are continuous across surfaces), native Calendar for due dates, and native
  Gmail for email-to-task and nudge drafts. In knowledge-only mode the offline math is unavailable and the
  model computes under shared/tasks-engine.md with a verify flag.
- Other AIs (ChatGPT / Gemini): the optional remote MCP endpoint, or the portable exports (.ics, JSON, the
  Google Sheet). Gemini reads Drive natively.
