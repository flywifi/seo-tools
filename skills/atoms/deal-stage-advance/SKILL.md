---
file: skills/atoms/deal-stage-advance/SKILL.md
name: deal-stage-advance
description: "validates a deal stage transition against the pipeline-engine.md rules and emits a transition record; does NOT write pipeline records directly or advance stages without evidence."
load:
  - shared/pipeline-engine.md
  - protocols/safety.md
  - protocols/no-fabrication.md
---

# deal-stage-advance

Validate that a requested deal stage transition is permitted under the pipeline stage rules and, when
all required evidence is present, emit a structured transition record for the calling spoke to
persist. This atom never writes to `pipeline/deals/` directly and never advances a stage without
confirming the required evidence fields.

## Purpose

Brand partnership deals move through a fixed nine-stage lifecycle. Skipping stages, advancing without
evidence, or misrecording transition dates corrupts the CRM history and undermines revenue tracking.
This atom centralizes the transition logic so every spoke that needs to move a deal uses one shared,
auditable check rather than duplicating rules. It returns either a ready-to-persist transition record
or a precise list of what evidence is still missing, so the spoke can prompt the creator for only what
is needed.

## Inputs

```json
{
  "deal_id": "string -- required; unique ID of the deal record in pipeline/deals/",
  "current_stage": "string -- required; the stage currently stored on the deal record",
  "target_stage": "string -- required; the stage the caller wants to advance to",
  "evidence": {
    "outreach_date": "ISO 8601 date string or null",
    "contact_name": "string or null",
    "signed_contract_date": "ISO 8601 date string or null",
    "agreed_deliverables": "boolean or null -- true when deliverables list is confirmed in writing",
    "invoice_number": "string or null",
    "payment_confirmed_date": "ISO 8601 date string or null",
    "notes": "string or null -- free-text context for the transition; optional for all stages"
  }
}
```

`evidence` is an object; include only the fields relevant to the transition. Fields not listed for a
given transition are ignored. `notes` is always optional but recommended.

## Output

```json
{
  "tool": "deal-stage-advance",
  "deal_id": "string",
  "transition_allowed": true,
  "missing_evidence": [],
  "stage_change_record": {
    "deal_id": "string",
    "from_stage": "string",
    "to_stage": "string",
    "timestamp_utc": "ISO 8601 datetime string",
    "evidence_provided": {}
  },
  "warnings": []
}
```

When `transition_allowed` is `false`:

- `stage_change_record` is omitted entirely (do not emit a null or empty object).
- `missing_evidence` lists every required field that is absent or null for this transition.
- `warnings` may list non-blocking concerns (for example, an unusually long gap since the last stage
  change).

When `transition_allowed` is `true`:

- `missing_evidence` is an empty list.
- `stage_change_record` contains the full record ready for the spoke to write.
- `timestamp_utc` is the current UTC datetime at the moment of validation; do not use a field from
  the evidence object as the timestamp.

## Stage transition rules

Valid forward transitions and their required evidence fields. Transitions not listed in the table are
not permitted. Backward transitions (rewinding a stage) are also not permitted; if the caller
requests one, set `transition_allowed` to `false` and add a warning explaining that rollback requires
manual correction in the CRM.

| from_stage | to_stage | required_evidence |
|---|---|---|
| identified | outreach-sent | `outreach_date`, `contact_name` |
| outreach-sent | in-discussion | `contact_name` (confirm same contact responded) |
| in-discussion | contract-negotiating | `notes` (summary of verbal or written terms under discussion) |
| contract-negotiating | signed | `signed_contract_date` |
| signed | in-production | `agreed_deliverables` must be `true` |
| in-production | delivered | `notes` (delivery confirmation or link) |
| delivered | invoiced | `invoice_number` |
| invoiced | closed/fulfilled | `payment_confirmed_date` |
| any | archived | `notes` (reason for archiving) |

Stage names are case-sensitive and must match exactly. The valid stage set is: `identified`,
`outreach-sent`, `in-discussion`, `contract-negotiating`, `signed`, `in-production`, `delivered`,
`invoiced`, `closed/fulfilled`, `archived`.

Skipping stages (for example, advancing from `identified` directly to `signed`) is not permitted. If
the caller requests a multi-stage jump, set `transition_allowed` to `false` and list each skipped
stage in `warnings`.

## Do NOT use for

- Writing or mutating any record in `pipeline/deals/` or `pipeline/accounts/`. This atom emits a
  record for the calling spoke to persist; it does not persist anything itself.
- Validating account health or scheduling follow-up outreach (use account-health or the outreach
  spoke).
- Advancing stages when `agreed_deliverables` is `false` or the field is absent for the
  `signed` to `in-production` transition; the transition must be blocked.
- Fabricating or inferring any evidence field that the caller did not supply
  (`protocols/no-fabrication.md`). If evidence is missing, block and list it; never assume.
- Making final release or payment decisions; the transition record must pass through govern-artifact
  before surfacing to the creator.
- Archiving a deal that still has an unpaid invoice without adding a warning in `warnings` flagging
  the open invoice.

## Pipeline note

Follows `shared/pipeline-engine.md` for stage definitions, evidence field names, and record format.
All real deal records live in `pipeline/deals/` and are gitignored; never committed. Obeys
`protocols/no-fabrication.md`: if a required evidence field is null or absent, `transition_allowed`
is `false` and the field is listed in `missing_evidence`; the atom never estimates or infers evidence
values. Obeys `protocols/safety.md`: the atom emits warnings for unusual patterns (multi-stage jump,
archiving with open invoice, stage gap exceeding 90 days) without blocking on them unless the
transition rules above explicitly require it. The calling spoke is responsible for persisting the
`stage_change_record` and updating the deal record in `pipeline/deals/`.

## Cross-modality
Inherits its calling spoke's class (Class B); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
