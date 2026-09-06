---
file: shared/pipeline-engine.md
role: Source of truth for the CRM data model, the deal lifecycle, stage-transition rules, and the
  radar views. Read by account-manager, deal-pipeline, deal-resourcing, and partnership-mediakit.
  Identity and voice live in shared/brand-engine.md; disclosure and legal boundaries live in
  protocols/safety.md.
load: for every Pipeline/CRM request
status: authored from the Creator OS handoff CRM spec; supersede with the canonical file if one surfaces.
---

# Pipeline Engine

The `pipeline/` store (`pipeline/accounts/` and `pipeline/deals/`) is the canonical record of real
brand relationships and real money. It is the source of truth for all CRM facts. Connected ingest
sources (email, calendar, Drive, a general CRM) may inform a record but never overwrite it. Every
value written to an account or deal comes from the user or a real, named source (see
protocols/no-fabrication.md). If a value is unknown, it stays null and is flagged as missing.

## Account schema (pipeline/accounts/<brand-slug>.json)
- `brand_name`: string.
- `aliases`: list of alternate names or nicknames the creator uses for this brand (for the
  account resolver in `tools/accounts.py`; empty list when none).
- `brand_category`: one of furniture, home decor, paint and finishes, tools and hardware, textiles,
  lighting, organization, garden and outdoor, marketplace and thrift, other.
- `primary_contact`: { name, role, email } (null fields allowed and flagged).
- `secondary_contacts`: list of { name, role, email }.
- `relationship_health`: one of warm, neutral, cold, at-risk.
- `last_contact_date`: ISO-8601 date or null.
- `channel_preferences`: list (email, Instagram DM, agency portal, phone).
- `deal_history_summary`: short text plus references to deal IDs.
- `notes`: free text.
- `renewal_candidate`: boolean, set by the renewal-signal rule below.

### Relationship health rules
- Health degrades to `cold` automatically when `last_contact_date` exceeds 90 days with no active
  deal in progress. State the degradation; do not hide it.
- Distinguish `warm` (active relationship, regular communication, deal likely) from `neutral`
  (completed deal, no active follow-up, deal possible). Never merge these into one "positive" label;
  the distinction sets outreach priority.
- `renewal_candidate` is set to true at the 60-day mark after a deal closes successfully when the
  brand has expressed interest in future work.

## Deal schema (pipeline/deals/<deal-id>.json)
- `deal_id`: stable identifier.
- `brand_name` and `account_ref`: link to the account record.
- `deal_type`: one of dedicated_video, integrated_segment, product_mention, shorts, bundle.
- `platforms`: list (youtube, youtube_shorts, instagram_reels, instagram_feed, tiktok, pinterest).
- `agreed_deliverables`: list of { deliverable_id, format, count, platform, due_date, ftc,
  approval_state } where `ftc` records the required disclosure for that deliverable (see
  protocols/safety.md FTC disclosure). `ftc` is a required field on every sponsored deliverable and is
  never left blank on a signed deal. `deliverable_id` is a stable id so tasks and milestones (the task
  tracker, shared/tasks-engine.md) can reference a specific deliverable; `approval_state` is one of
  not_submitted, submitted, in_revision, approved, rejected, tracking the brand-approval round-trip per
  deliverable (for example the long-form approved while the short is still in revision).
- `compensation`: { amount, type } where type is one of cash, product, affiliate, mixed. Amount is
  null until a real figure is provided; never invent a rate.
- `usage_rights`: { scope, window_start, window_end } where scope is one of social_only,
  paid_amplification, in_perpetuity, white_label.
- `exclusivity`: { active, scope, window_start, window_end, blocks } where `blocks` names the deal
  types or brand categories the exclusivity prevents during the window.
- `payment_terms`: text (for example, net 30 from delivery).
- `payment_due_date`: ISO-8601 or null.
- `stage`: one of the nine lifecycle stages below, plus `archived`.
- `quality_verdict`: the quality-review decision recorded alongside the record (see
  protocols/quality-gates.md).

## Nine lifecycle stages
1. `identified`: a fit brand has been found; no contact yet.
2. `outreach-sent`: a pitch or inquiry has gone out.
3. `in-discussion`: a real two-way conversation is underway.
4. `contract-negotiating`: terms are being worked; the Contract Review rule applies here.
5. `signed`: an executed agreement exists.
6. `in-production`: deliverables are being created against the signed deal.
7. `delivered`: deliverables have been handed off and confirmed.
8. `invoiced`: an invoice has been issued for delivered work.
9. `closed/fulfilled`: payment received and obligations met.
Plus `archived` for inactive or dead deals (kept for history, excluded from the active radar).

## Stage-transition rules (evidence-gated)
A deal stage is never advanced on the stage field alone. Review the actual evidence artifacts before
accepting a transition. Key gates:
- `signed` to `in-production` requires the signed contract artifact.
- `delivered` to `invoiced` requires delivery confirmation.
- `invoiced` to `closed/fulfilled` requires payment-received confirmation.
- Any transition into `signed` requires that every sponsored deliverable has its `ftc` disclosure
  field populated.
When evidence is missing, do not advance; record a conflict noting the missing artifact and keep the
deal at its current stage.

### Contract Review entry rule
At `contract-negotiating`, summarize terms in plain language and surface the points that deserve
attention as action items on the deal record. Do not advise that a term is or is not enforceable and
do not draft binding legal language as if it were vetted. Recommend review by a qualified
professional and by the owner before signing (see protocols/safety.md).

## Invoice states
`draft`, `sent`, `viewed`, `paid`, `overdue`, `disputed`. An invoice record references its deal,
carries `amount`, `invoice_date`, `payment_due_date`, `payment_received_date`, and `payment_method`,
and never invents a figure.

Invoices are standalone records in `pipeline/finance/` (schema:
`pipeline/finance/invoice.template.json`), many per deal: deposits, partials, kill fees, and
final balances are separate invoices. The deal record carries `invoice_refs[]` plus an embedded
`invoice` object that is a denormalized summary of the most recent invoice record (kept for the
radar and quick reads; the standalone record is authoritative). Due dates, aging, and
late-penalty accrual are computed offline by `tools/finance.py` from the deal's
`payment_terms_structured` block, never by the model; see `shared/finance-engine.md`.

## Radar views (read-only computed flags)
The radar reads the store and surfaces, without writing anything:
- `payment_overdue`: any invoice unpaid past its due date, with a days-overdue count.
- `exclusivity_active`: any deal with `exclusivity.active = true`, naming what it blocks.
- `usage_rights_expiring`: any rights window ending within 14 days.
- `deliverable_past_due`: any agreed deliverable past its due date.
- `relationship_at_risk`: any account at `cold` or `at-risk` health.
- `renewal_candidate`: any account flagged for renewal at the 60-day mark.

Usage rights and exclusivity are tracked separately from invoice status and never collapsed into a
single status field: a brand can have paid its invoice yet still hold active exclusivity that blocks
other deals.

## Evidence bundles and completeness
Evidence that informs a CRM write (a pasted email, an uploaded contract, a meeting recap, a
connector response) is packaged as an evidence bundle before anything reads it. Every bundle
carries:
- `acquisition_mode`: which rung of the connector degradation ladder produced it (see
  `shared/connectors/connectors.md`, Evidence acquisition modes).
- `artifact_completeness`: `minimal` (an excerpt or single fragment), `partial` (some artifacts
  present, known gaps), or `rich` (full artifact set for the source). Downstream consumers gate on
  this grade instead of assuming the bundle is whole.
- Per-item provenance: source name or connector, artifact identifier, and retrieval or paste time.
  A value with no provenance is treated as unsourced and cannot support a write.

## Memory safety model (field-level write classes)
Not everything extracted from evidence may be written to a durable account or deal record. Every
value falls into one of four write classes:

| Write class | What falls here | Rule |
|---|---|---|
| `raw` | Transcript or email text, pasted threads, meeting excerpts, chat fragments | Never written to a durable field. Raw evidence stays in the bundle; records reference it. |
| `conditional` | Verbatim quotes and evidence snippets supporting a field value | Writable only with provenance attached (source + artifact id + time). The quote must be exact; a paraphrase is `derived`, not `conditional`. |
| `derived_reviewed` | Conclusions: stage changes, `relationship_health`, commitments, action items, `deal_history_summary` updates, contact role changes | Writable only through the stage-transition rules with the quality-review verdict recorded, and flagged `human_review_required` when linkage or identity is unresolved. |
| `safe` | The confidence fields themselves: claim confidence, identity confidence, `artifact_completeness`, retrieval gaps | Always writable; these describe the evidence, not the account. |

Two confidences, kept separate:
- **Claim confidence**: is the statement itself well supported by the evidence?
- **Identity confidence**: is the person or brand the statement is attributed to actually who the
  record says? A raw label in a pasted thread ("Alex", "the brand contact") starts unresolved.
A strong claim never raises identity confidence, and a resolved identity never raises claim
confidence. Both are recorded on any write where attribution matters (contact updates,
commitments, relationship health changes).

## Write stop conditions
Before any durable CRM write, stop — do not write, record why — when:
- **Account linkage is weak.** The evidence cannot be tied to a specific account record with named
  support. Record `account_link: unknown` on the bundle rather than guessing a brand. An unknown
  linkage routed for human review is always preferred over a confident wrong one.
- **Identity is unresolved** for a value whose meaning depends on who said it (a commitment, a
  rate, a renewal signal). Keep the value in the bundle with `identity_confidence: unresolved`.
- **The evidence bundle is `minimal`** and the write is `derived_reviewed` class. Minimal bundles
  can update `safe`-class fields and raise flags; they cannot change stages or health.
- **Sources conflict** on the value. Record the conflict (minority report) and route to human
  review; never average or silently pick one.

## Store and integrity rules
- Real CRM data lives in gitignored files (for example, `pipeline/accounts/*.local.json`); only
  schemas, templates, and blank structures are committed.
- No spoke writes a record outside these stage-transition rules. The hub enforces this before
  routing any Pipeline/CRM request.
- Every CRM write records the quality-review verdict alongside the record.
