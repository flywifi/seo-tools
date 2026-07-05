# Task & Obligation Tracker (P35)

The tracker turns a brand deal's event-triggered, multi-party obligations into dated,
source-cited tasks: every open task, who owes the next move (you, the brand, an agency), when it
is due, and — the non-negotiable — the specific human artifact each task comes from. It plans
backwards from deadlines, remembers what you are waiting on, verifies a deliverable covered its
approved talking points, and tells you when a payment milestone is billable. Nothing is ever sent,
invoiced, or posted automatically.

**Source of truth for the model:** `shared/tasks-engine.md`. This doc is the operator and
deployment guide. The engine file governs the record shapes and rules; the tools implement them.

**Boundary.** Local, offline, human-gated. The tools compute dates, statuses, schedules, coverage,
and billable-readiness deterministically. They propose; a human confirms every status change,
nudge, invoice, and post. No auto-send anywhere. API keys (carrier aggregators) are read from the
environment only, never persisted or logged.

---

## 1. The anti-phantom rule (the one you asked for)

> There is never a task the tool identifies that it cannot cite.

Every task carries a `source` of one of three kinds, and `tools/tasks.validate_task` rejects any
task whose source is missing or malformed. Drift invariant 24 backstops the data at rest.

| Source kind | Means | Carries |
|---|---|---|
| `document` | a contract clause or an email | contract id + clause, or an RFC 5322 `message_id` (+ optional content hash) |
| `event_derived` | a backwards-planned task off a named rule and an anchor event | `rule.defined_in` (which itself points to a human artifact) + the `anchor_event` |
| `user_stated` | you said so | the channel + timestamp of your statement |

`event_derived` is what makes backwards-planned tasks legitimate: the rule ("draft due 7 business
days after the product is received") is grounded in the clause that defines it, so a computed due
date is transitively traceable to a human artifact. A task the model cannot ground is not created;
it is surfaced as a gap for you to confirm.

## 2. Task record and lifecycle

Tasks live in `pipeline/user-context/task-register.local.json` (gitignored; a blank
`.template.json` is committed), keyed by `deal_id` + `contract_ref`, modeled on the obligation
register so deal writes stay governed.

The tool stores coarse bands and derives everything else at read time (`is_overdue`, `is_due_soon`,
`is_actionable`, `is_aging_wait`, urgency) — no stale computed fields on disk.

**Seven states in two buckets**, one `transition()` choke point that validates the allowed-transition
table, stamps `updated_at`, and appends to the append-only `history[]`:

- **Open:** `not_started`, `in_progress`, `waiting_external`, `blocked`, `deferred`
- **Closed:** `done`, `cancelled`

`waiting_external` is a first-class state, not a label: the ball is in **their** court, and it starts
an aging clock. `blocked` is the ball in **our** court, gated by another of our tasks; `done` is
refused while any `blocked_by` task is still open. `history[]` is the source of truth — status,
responsible party, and billable-readiness are folds over it (event sourcing), which is also what
makes the shared store safe to edit from two surfaces (Section 8).

## 3. Scheduling (offline, stdlib)

`tools/tasks.py`, reusing the obligations date math (US federal holidays, business-day roll):

- **Forward pass** — earliest start/finish from trigger events.
- **Backward pass / reverse-plan** — from a hard deadline, when must each upstream step start.
- **Feasibility** — a negative-slack check surfaces "the trigger is too late for this deadline" as
  a conflict rather than silently producing an impossible plan.

`after_event` triggers name a business event ("draft due 7 business days after `product_received`");
until that event's date is known the task is `deferred` with no firm due date, and the trigger
still cites the clause that defines it.

## 4. Recurrence, waiting-on, ping-pong

- **Recurrence** (`pipeline/user-context/recurrence-rules.local.json`): an RFC 5545 RRULE subset
  (FREQ/INTERVAL/COUNT-xor-UNTIL/BYDAY). Occurrences are **materialized on demand by date**, not
  spawned on completion, idempotent on `(recurrence_id, occurrence_index)`; every occurrence
  inherits the template's `source`.
- **Waiting-on** carries a `handoff{response_due_at, nudge_at (80% of the window), escalate_at
  (50% past due)}`. A wait becomes an aging follow-up, not a silent to-do.
- **Ping-pong** (`advance_ping_pong`) models the approval/revision loop: on `submit` the ball flips
  to the brand; on `request_changes` it flips back and the iteration count increments; beyond
  `max_iterations` it escalates; `approve` closes it. The party who owes the next move is always the
  `responsible_party`.

## 5. Shipments (what started the clock)

`tools/shipments.py` normalizes a tracking event to a canonical status enum and, once delivered,
sets `delivered_at` from the delivered checkpoint — the **immutable backwards-planning anchor**.
Before delivery, an optional provisional estimate off `est_delivery` is clearly labeled and never
confused with the real event.

Three ways in, one schema:
- **EasyPost** (default) or **Ship24** (free-tier alternative): flag-gated behind `shipment_tracking`,
  polled over stdlib `urllib` honoring the env proxy + CA bundle. The key comes from `EASYPOST_API_KEY`
  / `SHIP24_API_KEY` **only**; with no key and no injected getter, the tool returns a config gap and
  points to manual entry — never a surprise network call.
- **Manual entry** is a first-class equal: `shipments.manual_shipment(...)` produces the identical
  record and the same `delivered_at` anchor.

## 6. Coverage verification (did the video cover a, b, c, d)

`tools/coverage_verify.py`, reusing `shared/docintel/transcripts.py` + `wer.py`:

1. **Reconcile** N media transcripts to one canonical truth via progressive `difflib` alignment +
   confidence-weighted voting. **Every tie or credible dissent is surfaced as a conflict** (with the
   options, weights, and source ids) — it never silently picks; a pairwise-WER divergence matrix
   seeds source-reliability weights.
2. **Verify each required point** in ascending cost: lexical/fuzzy (stdlib, always on) → optional
   semantic → optional NLI. When the semantic tiers are unavailable it **abstains and routes to the
   human gate** rather than inferring. Per point: `{verdict: satisfied|partial|missing,
   supporting_quote (extractive, verified present in the canonical text), timestamp, abstained}`.
   Compound points decompose into atomic sub-claims.
3. Conflicts flow into a `minority_report` that retains every credible dissent and forces the human
   gate on any compliance-relevant disagreement.

## 7. Payment milestones → billable-readiness → finance

A payment schedule (`pipeline/user-context/payment-schedule.local.json`) attaches milestones to a
contract, each with a trigger (`on_signature` or `on_deliverable_event{deliverable_id, event}`), an
amount or percentage, `acceptance_required`, and a `source`. When the triggering event lands in the
append-only log — the same `approve` hand-off that closes a ping-pong cycle — `billable_ready` flips
and a citation-carrying (`event_derived`) billable task drops into the existing finance lane
(`tools/finance.py`). You confirm before any invoice is drafted or sent.

## 8. Calendar and reminders

- **.ics export** (`register_to_ics`): a stdlib RFC 5545 VCALENDAR of all-day VEVENTs with a VALARM
  each, for due dates and payment milestones. Stable per-task UIDs mean re-export updates rather than
  duplicates. Imports into Apple Calendar, Google Calendar, or Outlook.
- **Reminders digest** (`reminders_digest`): a due-soon / overdue / aging-wait summary for your
  review. Nothing is sent.

## 9. Cross-surface continuity (the Mac / web / mobile question)

The register is read and written through a **store adapter** with three backends, all over the same
canonical JSON schema, selected by the `task_store_backend` flag:

| Backend | Where the data lives | Reaches |
|---|---|---|
| `local_fs` (default) | gitignored `.local.json` on the Mac | Claude Desktop + MCP — full offline fidelity |
| `google_drive` | a canonical JSON + a human-readable Sheets mirror in your Google Drive | **claude.ai web + mobile AND Desktop** via the native Google Drive/Sheets connector — no hosting |
| `remote_mcp` | a hosted streamable-HTTP MCP endpoint (user/host provided) | Claude web/desktop/mobile **AND ChatGPT AND Gemini** — one custom connector |

**Why two surfaces can share the Drive store safely.** Because `history[]` is append-only and every
event carries `(uid, seq, timestamp, actor)`, two surfaces editing the same file are reconciled by
**union of events + re-fold** (`merge_tasks` / `reconcile`), not last-writer-wins clobber. The Sheets
mirror is a regenerated projection, never the source of truth. A `sha256` bucket manifest verifies an
offline copy.

**Per-surface behavior (degradation ladder):**
- **Claude Desktop + MCP** — full deterministic compute in `tools/tasks.py` over the store (local or
  Drive); carrier tracking and .ics export run here.
- **claude.ai web / mobile** — the tracker runs as an Agent Skill (its stdlib scripts run in the
  code-exec sandbox when settings allow; otherwise the model computes under `tasks-engine.md` with a
  `verify` flag), over the Drive/Sheets store, with native Calendar for due dates and native Gmail
  for email→task and nudge drafts (never auto-send). Continuous with Desktop because both share the
  Drive store.
- **Other AIs (ChatGPT / Gemini)** — via the optional remote MCP, or the provider-neutral exports the
  tool already emits (the `.ics` calendar, portable JSON/CSV, the Google Sheet). Gemini reads Drive
  natively; ChatGPT via an app/Drive.

See `docs/DEPLOYMENT.md` (capability matrix) and `docs/LOCAL_CONTEXT.md`.

## 10. Legal, privacy, and injection safety

- **Privacy / data at rest.** The register, recurrence rules, shipments, and payment schedule hold
  the same gitignored-class data as the rest of the CRM: real records live in `.local.json`
  (invariant 19: no tracked `.local.` files; invariant 20: only blank templates tracked under
  `pipeline/`). What is written to the Google Drive store is the same data class — the redaction and
  no-PII-in-commits rules apply equally to it. Secrets stay in the host keychain / connector OAuth /
  env, never in the store or the repo.
- **No legal advice.** The tracker reports what a cited clause says and when a computed date falls;
  it does not interpret contract enforceability or give legal advice. Coverage verification reports
  whether a point is textually supported, not whether a disclosure is legally sufficient — that stays
  a human judgment, which is why it abstains rather than infers.
- **Injection safety (email → task).** Inbound email rides `ingest-route` (classify → parse →
  injection-scan per `shared/injection-guard-engine.md`). The citation is **code-stamped from the
  trusted envelope**, never model-generated; the model does schema-locked extraction over the
  untrusted, delimited body with no side effects; every extracted task is human-confirmed before its
  clock starts (OWASP LLM01 defense-in-depth).
- **No auto-action.** No email, invoice, nudge, or post is sent by the tool. Carrier retrieval is
  poll-only (no webhooks). Free-tier carrier limits apply (EasyPost per-tracker; Ship24 monthly cap).

## 11. Portability runbook for a non-technical Mac user

Goal: the same tasks visible in Claude web, the Claude desktop app, and Claude mobile, with due dates
on the calendar — no terminal, no hosting.

1. **In Claude (web or desktop), enable the Google Drive connector.** Settings → Connectors → Google
   Drive → connect the Google account.
2. **Run the setup wizard's store step** (Desktop) — `python3 tools/wizard.py`, choose the
   `google_drive` task store. It creates a "Creator OS Tasks" Drive JSON and a Sheets mirror. (If you
   only ever use the web app, the Skill creates these on first use instead.)
3. **Add the task-tracker Skill on claude.ai** (Settings → Skills → upload). It is already present on
   Desktop.
4. **Enable native Calendar** in Claude so due dates and reminders land on Google Calendar.
5. Now ask, on any surface: *"what am I waiting on from <brand>?"*, *"plan backwards from my publish
   date"*, *"did my final cut cover the approved talking points?"*, *"which milestones are billable?"*
   The same store answers on web, desktop, and mobile.

**Graduating to ChatGPT / Gemini (optional, later):** deploy the remote MCP (`tools/mcp_server.py
--serve-remote`) once and add it as one custom connector. Nothing in the data model changes — same
canonical store, same exports. We ship the transport option and a runbook; we do not host a server.

**A note on Skill sync:** per Anthropic, a Skill uploaded to claude.ai is a separate copy from the
Desktop/Code one; there is no automatic sync. Re-upload after an update. The *data* stays continuous
because it lives in the shared Drive store, not in the Skill.

## 12. Enabling and verifying

Flags in `creator-os-config.json` (override per-deployment in `creator-os-config.local.json`):
`task_tracking`, `shipment_tracking`, `coverage_verification`, `task_store_backend`
(`local_fs` | `google_drive` | `remote_mcp`).

```bash
# offline core (no keys, no network)
python3 tools/tasks.py --selftest            # state machine, scheduling, recurrence, waiting-on, anti-phantom
python3 tools/shipments.py --selftest        # status normalization + connector host/refusal (no live network)
python3 tools/coverage_verify.py --selftest  # reconciliation voting/conflicts + coverage abstention + citations

# read-only views and exports over a register
python3 tools/tasks.py scan      --register <path> [--today YYYY-MM-DD]
python3 tools/tasks.py plan       --register <path> --deadline-task <id> --deadline YYYY-MM-DD
python3 tools/tasks.py reminders  --register <path>
python3 tools/tasks.py ics        --register <path> --out tasks.ics
python3 tools/tasks.py manifest   --register <path>

# shipments (manual always available; fetch needs an env key)
python3 tools/shipments.py manual --tracking <n> --carrier usps --status delivered --delivered-at YYYY-MM-DD
python3 tools/shipments.py fetch  --tracking <n> --provider easypost   # returns a config gap without a key

# coverage
python3 tools/coverage_verify.py reconcile --files a.srt b.srt
python3 tools/coverage_verify.py coverage  --files a.srt b.srt --points points.json

# governance
python3 tools/sync_check.py       # drift, incl. invariant 24 (task-tracker integrity)
python3 tools/scenario_check.py   # incl. S6: two-party ping-pong + milestone + shipment + coverage
```

## 13. What did not ship this phase

No auto-send of any email, invoice, or nudge. No webhook endpoints (poll only). No hosted remote MCP
server (the transport + runbook ship; standing one up is user/host work). Semantic/NLI coverage tiers
are optional and flag-gated; the offline core (reconciliation + lexical + citation verification +
abstention) works with no ML dependency and abstains rather than guesses. No blockchain chain of
custody; a `sha256` content hash of a cited artifact is the tamper-evidence.
