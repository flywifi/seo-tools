---
file: shared/tasks-engine.md
role: Source of truth for the project task and obligation tracker — the task record schema, the status
  lifecycle, the provenance (anti-phantom) rules, backwards/forward scheduling, recurrence, waiting-on
  accountability, payment milestones, shipment anchors, email-to-task, requirement coverage verification,
  and the cross-surface data-continuity model. Read by task-desk and its atoms; interoperates with
  pipeline-engine (deals/parties), contract-engine (obligations/payment terms), finance-engine (invoicing),
  and integrations-engine (connectors/store backends).
load: for every task-tracking, backwards-planning, waiting-on, milestone-billing, shipment, or deliverable
  coverage-verification request.
---

# Tasks Engine

The tracker for the outstanding work a brand deal generates: who owes what, by when, from what source, and
whether a deliverable met its requirements. It answers "what am I waiting on, what do I owe, what is due,
and can I bill yet" — always tracing every task to a real, human-created item, and always leaving the send
to the human.

## Boundary (on every output)
> ORGANIZATIONAL TRACKING, NOT LEGAL, FINANCIAL, OR COMPLIANCE ADVICE. Dates, tasks, and billable flags are
> computed from the sources you provide; verify them against the contract and the counterparty. Nothing is
> sent, filed, invoiced, or posted automatically; every external action is drafted for your confirmation.

No task, date, or billable flag is ever invented. A value with no resolvable source stays null and is
flagged in `gaps[]` (`protocols/no-fabrication.md`). Legal questions route to contract-desk / a licensed
attorney; money math routes to finance-desk / a CPA (`protocols/safety.md`).

## The non-negotiable: every task cites a source (anti-phantom rule)
No task may exist that cannot be cited to a real human-created or human-accepted item. Every task carries a
`source` of exactly one kind:
- **`document`** — a contract clause, an email/message, or a brief. Records the artifact type, a locatable
  reference (contract id + section, or RFC 5322 `message_id` + permalink), a verbatim `quote`, and an
  optional `content_hash` (sha256 of the cited text, cheap tamper-evidence).
- **`event_derived`** — a backwards-planning result. Cites a named `rule` plus the `anchor_event` it fired
  from; the rule's `defined_in` itself points to a human artifact, so a derived task is transitively
  grounded (rule to clause, anchor to a real dated event).
- **`user_stated`** — the creator asserted it (a call, an in-app note). Records the statement, channel, and
  who/when.

`tools/tasks.py` `validate(task)` rejects any task with a missing or malformed `source` for its kind; drift
invariant enforces it in the repo. Generated occurrences inherit `source` from their recurrence template.

## Store and cross-surface continuity
The task register lives in `pipeline/user-context/task-register.local.json` (real data, gitignored; the
committed `task-register.template.json` is the null schema), keyed by `deal_id` + `contract_ref`, mirroring
the obligation register. `tools/tasks.py` reads and writes it through a **store adapter** with selectable
backends over one canonical JSON schema:
- **`local_fs`** — the `.local.json` on the machine (Claude Desktop + MCP). Full offline fidelity; default.
- **`google_drive`** — the canonical JSON in the creator's Google Drive plus a human-readable Google Sheets
  mirror; both Claude Desktop and claude.ai web/mobile read and write the same file (the native Drive/Sheets
  connector), so tasks are continuous across surfaces with no server to host. See
  `shared/integrations-engine.md`.
- **`remote_mcp`** — the same tools behind a remote streamable-HTTP MCP endpoint, so one custom connector
  serves Claude, ChatGPT, and Gemini. Optional; requires a host to deploy it.

**Concurrency is safe because history is append-only.** Every change is an event carrying `(uid, seq,
timestamp, actor)`; two surfaces editing the same store are reconciled by **union of events then re-fold**
(a deterministic projection), never last-writer-wins clobber. A sha256 bucket manifest verifies an offline
copy. The Sheets mirror is a regenerated projection, never the source of truth. See §Cross-surface below.

## Task record schema
`pipeline/user-context/task-register.local.json` `tasks[]`, one object per task:
- `id`, `schema_version`, `title`
- `project_id` (the deal), `contract_id`, `obligation_id` (link to the source-cited obligation row when
  contract-derived), `parent_id` (hierarchy only, no scheduling), `deliverable_ref` (a deal
  `agreed_deliverables[].deliverable_id`)
- `task_kind`: `next_action | waiting_on | agenda | milestone`
- `responsible_party`: `creator | brand | agency | platform | other` (whose court the ball is in; flips on
  handoff), `party_ref` (free text/id when not the creator), `accountable_party` (RACI: exactly one owner of
  the outcome), `waiting_on_party` (set when `status = waiting_external`)
- `status`: the 7-state enum below; `status_reason` (required for waiting_external/blocked/cancelled/deferred)
- `blocked_by[]`: task ids (finish-to-start, internal only; BLOCKED is derived)
- dates (Taskwarrior four-date vocabulary): `defer_until` (hidden/not actionable before this),
  `scheduled_date` (earliest sensible start), `due_date` (the hard date), `expires_at` (auto-cancel if unmet)
- `trigger`: `{ type: after_event | after_task | fixed, event_key, offset_days, offset_basis: business |
  calendar, resolved, source }` — the event that starts a relative clock
- `priority`: `H | M | L` (a coarse band; urgency is derived, never stored), `tags[]`
- `recurrence_id`, `occurrence_index` (for generated occurrences)
- `source` (MANDATORY; one of the three kinds above)
- `created_at`, `updated_at`, `started_at`, `completed_at`
- `history[]`: append-only event log (the source of truth; see §Provenance)

**Store coarse bands; derive the rest.** `is_overdue`, `is_due_soon`, `is_actionable`, `is_aging_wait`,
`is_closed`, and `urgency` are computed at read time, never persisted (Taskwarrior virtual-tag discipline) —
a stored derived value is the classic source of stale, contradictory records.

## Status lifecycle (7 states, 2 buckets)
Open: `not_started`, `in_progress`, `waiting_external`, `blocked`, `deferred`. Closed: `done`, `cancelled`.
The pivotal distinction, drawn from GTD's Waiting-For list, is that **waiting on the counterparty is a
first-class state, not a label**:
- `waiting_external` — the ball is in THEIR court; the creator has no action but to wait and nudge.
  `waiting_on_party` records who; the entry timestamp gives an aging clock.
- `blocked` — the ball is in OUR court but gated by another of our tasks (an open `blocked_by`).
- `not_started` / `in_progress` — act now.

One `transition(task, to, by, note)` choke point validates the allowed-transition table, stamps <!-- verify: tools/tasks.py::transition -->
`updated_at`, and appends a `history[]` event. Transitions are human-gated. Guards: `done` is refused while
any `blocked_by` is open; `deferred` requires a `defer_until`; reopening a closed task is an explicit,
logged action. Allowed transitions:
```
not_started      -> in_progress | waiting_external | blocked | deferred | cancelled
in_progress      -> waiting_external | blocked | done | deferred | cancelled
waiting_external -> in_progress | blocked | done | cancelled
blocked          -> not_started | in_progress | cancelled
deferred         -> not_started | cancelled
done | cancelled -> (terminal; reopen only via a logged human action)
```

## Dependencies and event triggers
Two relations only: `parent_id` (composition, no scheduling semantics) and `blocked_by[]` (finish-to-start,
internal, acyclic; BLOCKED derived by scanning). External waits are the `waiting_external` status, never a
graph edge (the counterparty is not a task). The `trigger` block generalizes a working-day dependency lag to
a named business event: "draft due 7 business days after `product_received`." Until the event date is known,
the task is `deferred` with no firm `due_date`; when the event resolves, `tools/tasks.py` computes the
`due_date` and sets `trigger.resolved = true`. The trigger still cites the clause that defines it.

## Provenance and the append-only event log
`history[]` is the authoritative append-only event log; `status`, `responsible_party`, `iteration`, and
`billable_ready` are folds (projections) over it, recomputed and never hand-edited (event sourcing). Each
event carries `seq`, `at`, `actor`, `event`, the fields it changed, and — for state-changing events — its
own `source_ref` (5W1H: who, what, when, why, from what source). Only `actor: user:*` or an explicitly
approved `system:*` job may append (human-gated writes).

## Backwards and forward scheduling
`tools/tasks.py` treats the tasks of a project as a dependency DAG and runs the Critical Path Method:
- **Forward pass** (schedule from the trigger event): early start/finish left to right.
- **Backward pass** (schedule from a hard deadline): late start/finish right to left; slack = late minus
  early. `reverse_plan(deadline)` runs the backward pass alone to answer "when must each upstream step <!-- verify: tools/tasks.py::reverse_plan -->
  start" (for example, when must the product ship to hit a fixed publish date).
- **Feasibility**: any task with negative slack means the trigger happened too late for the deadline; this
  surfaces as a conflict, never silently.
Business-day add/subtract mirrors numpy `busday_offset` roll semantics (roll to a valid day first, then
step), reusing `tools/obligations.py`'s federal-holiday set. Chained iterations unroll into distinct DAG
nodes. All pure stdlib, offline.

## Recurrence and iterations
Recurring duties ("monthly report", "each review cycle") live in
`pipeline/user-context/recurrence-rules.local.json`: a `template` (the task blueprint, including its
`source`) + a `rule` (RFC 5545 RRULE subset: FREQ, INTERVAL, COUNT xor UNTIL, BYDAY) + a `generation`
ledger. Occurrences are **materialized on demand by date, never spawned on completion** (so a skipped or
late cycle does not lose the series); idempotent on `(recurrence_id, occurrence_index)`; a skip is an
explicit `cancelled` occurrence; every occurrence inherits `source` from the template. The easy subset runs
in stdlib; `python-dateutil` is an optional aid for BYDAY/BYSETPOS edge cases and degrades gracefully.

## Waiting-on, nudge, and approval ping-pong
A `waiting_on` task carries `handoff{ handed_off_at, expected_response_business_days, response_due_at,
nudge_at (80% of the window), escalate_at (50% past due), nudge_count }` and `ping_pong{ cycle_id,
iteration, max_iterations, stage }`. On each hand-off `responsible_party` flips; on a rejection `iteration`
increments; beyond `max_iterations` the cycle escalates. Nudge and escalate dates are business-day computed.
This is what turns "waiting on the brand" into an aging follow-up rather than a silent creator to-do.
Nudges are drafted for the human, never auto-sent.

## Payment milestones and billable readiness
A payment schedule (`pipeline/user-context/payment-schedule.local.json`, keyed by contract) holds
`payment_model (deposit_plus_milestone | milestone | retainer)`, `net_terms_days`, and `milestones[]` each
with a `trigger (on_signature | on_deliverable_event{ deliverable_id, event: delivery | approval |
publish })`, an amount or percent, `acceptance_required`, `billable_ready`, and a `source`. When the
triggering event lands in the event log (the same `approved` hand-off that closes a ping-pong cycle),
`billable_ready` flips and a citation-carrying billable task (`event_derived` source) drops into the finance
lane (`shared/finance-engine.md`), which drafts the invoice and runs the dunning cadence. The human confirms
before anything is sent (`finance_management` + `invoice_generation` gates).

## Shipments as anchor events
Product shipments start many clocks. `pipeline/user-context/shipments.local.json` + `tools/shipments.py`
hold a normalized record (`tracking_number, carrier, status, checkpoints[], est_delivery, delivered_at,
source`) with a canonical status enum (`pre_transit, in_transit, out_for_delivery, delivered,
available_for_pickup, returned, exception, cancelled, unknown`). Live tracking is an optional, flag-gated
aggregator connector (EasyPost default, Ship24 free-tier alternative; API key from env only, poll not
webhook); manual entry uses the identical schema. `delivered_at` (from the delivered checkpoint only) is the
**immutable anchor** that starts backwards-planning; before it, a provisional due date off `est_delivery` is
clearly labeled.

## Email to task (cited, injection-safe)
Inbound brand messages become tasks through `ingest-route` (classify, parse, injection-scan). The citation
is **code-stamped from the trusted message envelope, never model-generated**: it stores both the durable RFC
5322 `message_id` and the provider id/permalink (so a human can re-open the exact message) plus an account
hint. The model does schema-locked extraction over the untrusted, delimited body with no side effects; every
extracted task is human-confirmed before its clock starts (`shared/injection-guard-engine.md`). Manual paste
with a user reference is a first-class equivalent.

## Requirement / deliverable coverage verification
To confirm a deliverable met its requirements (for example, the approved script covered points a, b, c, d),
`tools/coverage_verify.py` first **reconciles all provided media transcripts to a canonical truth** (a
progressive alignment plus confidence-weighted vote that surfaces every disagreement as a conflict, never
silently picking), then **verifies each required point** against the canonical transcript, emitting per
point `{ verdict: satisfied | partial | missing, supporting_quote (a verbatim span, verified present),
source_citations, timestamp, confidence, abstained }`. Coverage is asserted only when a specific sentence
supports the point; when unsure it abstains and routes to the human, never inferring. Conflicts between
inputs are reconciled by source reliability and retained in a `minority_report`; any compliance-relevant
conflict forces the human gate.

## Cross-surface behavior (degradation ladder)
- **Claude Desktop + MCP** — full deterministic compute in the tools over the store; carrier connector and
  .ics export run here.
- **claude.ai web / mobile** — the tracker as a bundled Agent Skill (its stdlib scripts run in the
  code-exec sandbox when allowed; otherwise the model computes under this engine with a `verify` flag), the
  Drive/Sheets store, native Calendar for due dates, native Gmail for email-to-task and nudge drafts
  (never auto-send). Continuous with Desktop through the shared Drive store.
- **Other AIs (ChatGPT / Gemini)** — the optional remote MCP, or the provider-neutral exports (.ics, JSON,
  CSV, the Google Sheet).

## Governance
Every output sets `human_review_required`. Nothing is sent, invoiced, or posted automatically. No
fabrication (null + `gaps[]`). Durable writes are append-only and human-gated. Secrets stay in the host
keychain / connector OAuth / env, never in the store or the repo. Real data is gitignored; only null
templates are committed.

## Tool / atom / MCP map
- Tools: `tools/tasks.py` (records, state machine, scheduling, recurrence, waiting-on, billable, .ics,
  store adapter), `tools/shipments.py` (shipment records + carrier connector), `tools/coverage_verify.py`
  (reconciliation + coverage).
- Atoms: `task-extract`, `task-plan`, `task-status`, `task-radar`, `coverage-verify`, `shipment-track`,
  `milestone-bill`; composed by the `task-desk` spoke with `govern-artifact`.
- MCP: `task_scan`, `task_plan`, `task_transition`, `task_ics_export`, `coverage_verify`, `shipment_track`,
  `milestone_status`; `import_obligations` extended to carry who-owes-whom, the waiting-on queue, skip
  completed, and feed billable readiness to finance.
- Flags: `task_tracking` (register writes; read-only scans always available), `shipment_tracking` (carrier
  connector), `coverage_verification` (semantic/NLI tiers), `task_store_backend` (`local_fs | google_drive |
  remote_mcp`).
