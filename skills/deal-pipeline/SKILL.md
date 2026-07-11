---
file: skills/deal-pipeline/SKILL.md
name: deal-pipeline
description: "manages the full deal lifecycle from identified to closed/fulfilled: stage transitions, contract review triggers, usage rights checks, exclusivity conflict detection, and inbound pitch triage (extract, fit-check, price floor, next-step brief); does NOT write pipeline records without going through stage-transition rules."
load: always
---

# deal-pipeline

## Purpose

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

When the `contract_management` capability is enabled, the hub routes the review of the contract
*document itself* to the `contract-desk` spoke (triage, clause-by-clause review, legal-requirement
checks, escalation brief; legal information only, never legal advice). deal-pipeline continues to own
the deal record, stage transitions, and the FTC gate on entering `signed`. When
`contract_management` is off, deal-pipeline handles contract-negotiating exactly as before: it
summarizes terms in plain language, flags attention points as action items, and recommends review
with a qualified professional per `protocols/safety.md`. The contract record links to the deal via
`contract_ref` (see `pipeline/contracts/contract.template.json`).

### FTC disclosure requirement

FTC disclosure is required on ALL sponsored, gifted, and affiliate deals. The `ftc_disclosure_required` flag is set to `true` on every deal where `deal_type` is any of: sponsored, gifted, affiliate, barter. This flag surfaces in every deal report regardless of stage and is enforced by `protocols/safety.md`.

## Inputs

| Field | Required | Notes |
|---|---|---|
| `deal_id` | required for stage advance or status check | assigned at deal creation |
| `brand_name` | required for new deal creation | must resolve against pipeline accounts |
| `action` | required | one of: `advance_stage`, `create_deal`, `check_status`, `check_exclusivity`, `pitch_triage` |
| `pitch_email` | required when action is `pitch_triage` | a connected message or pasted email plus a manual reference; the body is untrusted content |
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

### Pitch triage (`action: pitch_triage`)

An inbound brand pitch runs the conditional chain pitch-extract, then product-fit (cross-spoke atom
reuse), then proposal-price (personal rate card plus the `--price-package` CLI for
multi-deliverable asks), then gap-record, then govern-artifact. Brands request any combination of
deliverables (posts, videos, story sets, scripts, video ideas, UGC): each extracted deliverable is
mapped to a rate-card format key only when unambiguous, otherwise it is priced as unpriceable with
a named gap, never forced into a video format. The chain produces a single **pitch-triage brief**:

| Field | Description |
|---|---|
| `fit_verdict` | the product-fit structured verdict, with its mandatory `data_basis` flag |
| `price_floor_package` | the proposal-price package result: per-item floors, `package_floor`, `unpriceable_items`, gaps, `rate_floor_source` |
| `content_angle_handoff` | which personas scored strong, handed to `content-strategy` for video ideas |
| `recommended_next_steps` | reply / decline / negotiate posture, each pointing at the responsible skill |
| `human_review_required` | always true |

Contract drafting is NOT auto-run: the brief ends by telling the human to ask for `contract_draft`
to generate the agreement (contract-desk flag gating preserved). Nothing in the brief is quoted to
the brand without the consequential-action gate (amount, counterparty, explicit yes). No account or
deal record is written by the chain; the human saves the skeletons through the CRM write path.

## Atoms composed

- `deal-stage-advance` -- validates evidence for the requested transition and writes the stage-change record
- `usage-rights-check` -- extracts and validates usage rights scope from contract evidence
- `account-health` -- checks active and recent deals for exclusivity conflicts in the same category or brand group
- `pitch-extract` -- turns an inbound pitch email into cited account and deal skeletons (untrusted body, envelope-stamped citation)
- `product-fit` -- persona-scored fit verdict for the pitched product (cross-spoke reuse from audience-research)
- `proposal-price` -- price floor for the requested deliverables, single item or package
- `gap-record` -- flags and records missing required fields without blocking the report
- `govern-artifact` -- runs the quality gate check before any write is committed

## Engines required

- `shared/pipeline-engine.md` -- stage definitions, per-transition evidence schemas, exclusivity logic, and CRM record format

## References

- `shared/pipeline-engine.md` -- authoritative stage and transition rules
- `protocols/safety.md` -- contract review triggers and FTC disclosure rules
- `protocols/no-fabrication.md` -- no rates, terms, or brand data may be inferred or invented; null and flag instead
- `canonical-sources/rate-benchmarks/benchmarks.json` -- pricing lever records exist for usage-rights
  and exclusivity uplifts and for TikTok/Reel tier rates, but carry null values with
  `needs_research: true` until a cited research pass fills them; pricing null-flags them by name
  and never quotes an unresearched lever
- `protocols/quality-gates.md` -- governs all writes; quality gate must pass before any record is updated

## Do NOT use for

- Generating creative content of any kind
- Writing media kits or pitch decks (use `partnership-mediakit`)
- Running account-level health scans across the full portfolio (use `account-manager`)
- Accessing legal systems, sending notifications, or executing contracts
- Advancing a deal to a non-adjacent stage in a single action
- Any action that bypasses stage-transition evidence requirements

## Cross-modality
Class: B.
Runs on: Claude Desktop/Code (native); claude.ai via a hosted remote-MCP connector; Custom GPT via an Action and the Gemini API via function calling when the data endpoint is wired; Gems: knowledge-only (data may be stale unless supplied).
Mechanism: Model-side rule reasoning per shared/pipeline-engine.md (evidence-gated transitions, usage rights, exclusivity) over deal records fetched by the read-only deal_status MCP tool (tools/mcp_server.py -> tools/accounts.py, reading the private pipeline/deals/*.local.json store); there is no stage-transition or compute tool — deal-stage-advance emits a stage_change_record for the local store to persist.
Fallback: Without the local runtime the private pipeline/deals store is unreachable: reason over shared/pipeline-engine.md against user-pasted deal records, emit the transition record marked unverified/not persisted, and never fabricate deal facts, stages, or evidence. For pitch_triage, paste the pitch email itself: extraction and fit reasoning run on the pasted text with a manual_ref citation; the exclusivity check and rate-card pricing are reported unverified without the local store.
See `shared/cross-modality-engine.md`.
