---
file: skills/deal-resourcing/SKILL.md
name: deal-resourcing
description: "takes a signed deal and produces a production resource plan: task list with due dates, production timeline, invoice schedule, and go/no-go checklist. Pipeline/CRM lane spoke."
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

## Cross-modality
Class: C.
Runs on: Claude Desktop/Code (native, MCP + the tool module); claude.ai via a hosted remote-MCP connector; Custom GPT / Gemini only when the tool is hosted behind a remote MCP or an Action; Gems: no.
Mechanism: Deterministic scheduling and money math on the local deal record: reads pipeline/deals/ via the deal_status MCP tool (tools/accounts.py), computes D-minus-N business-day due dates via tools/obligations.py + tools/tasks.py (task_scan/task_plan MCP tools), and invoice schedule/AR figures via tools/finance.py (finance_scan); ROI/CPM decimal math from deal-record figures only.
Fallback: No MCP runtime or hosted seam -> emit the resource plan structure from the deal record with all computed due dates and invoice amounts set to null plus a due_date_note/gap-record per field, go_no_go downgraded to CONDITIONAL or NO-GO; never estimate a date, rate, or invoice amount. On ChatGPT this is reasoning-only and outputs are labeled provisional (no local tools, no flag enforcement); the desktop app can reach the full tool only via a deployed remote MCP connector in developer mode (implementation/gpt/mcp-connector/README.md).
See `shared/cross-modality-engine.md`.
