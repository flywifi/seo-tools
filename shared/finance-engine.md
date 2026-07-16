# Finance Engine

Canonical knowledge layer for the Creator OS accounting bucket (P30): accounts receivable,
invoicing, projected and actual costs, pricing standardization, and the money half of
creator-economy terms (revenue share, commission, IP licensing fees). Loaded by the finance
atoms (`invoice-generate`, `ar-review`, `cost-estimate`, `proposal-price`) and the
`finance-desk` spoke, and realized offline by `tools/finance.py`. Internal engine doc; may use
em dashes freely. Ranges are written with "to".

## The design in one paragraph

Money facts live in records, never in prose. The `pipeline/finance/` store holds standalone
invoice records, cost estimates, and cost actuals (committed blank templates; real data in
gitignored `.local.json`, invariant 19). All arithmetic — due dates, aging, penalty accrual,
revenue-share math, cost rollups, price floors — runs offline in `tools/finance.py` (exact
decimal, zero tokens, `computed_by` on every result), which imports the date machinery from
`tools/obligations.py` rather than duplicating it. The model reads results and drafts documents;
it never computes money by hand and never invents a figure (null and flag,
`protocols/no-fabrication.md`). Read-only scans are always available; anything that writes a
record is gated behind the `finance_management` flag family; and nothing money-facing leaves the
system (an invoice sent, a price quoted) without an explicit human confirmation.

## The boundary (verbatim, non-negotiable)

Every output that touches expense categorization, capital classification, or anything a tax
return could rely on carries this first line, exactly:

ARITHMETIC AND RESEARCH NOTES. NOT TAX, ACCOUNTING, OR INVESTMENT ADVICE. REVIEW WITH A CPA OR
TAX PROFESSIONAL BEFORE FILING OR RELYING ON CATEGORIZATIONS.

This is the financial sibling of the contract stack's legal boundary
(`shared/contract-engine.md`). The system does arithmetic and organizes records; it never
advises on deductibility, tax treatment, depreciation schedules, or accounting method choices.
Every finance artifact sets `human_review_required: true`.

## Consequential-action gate

Before any step that commits money externally — sending an invoice, quoting a price to a brand,
agreeing a rate in an outreach draft — the system stops and asks for an explicit yes, restating
the amount, the counterparty, and the terms. Mirrors the contract stack's
consequential-action gate. Invoice documents are drafted, never sent; the human sends.

## Record store (`pipeline/finance/`)

- `invoice.template.json` — invoices are STANDALONE records, many per deal (deposits, partials,
  kill fees, final balances are separate invoices). This resolves the prior drift: the pipeline
  engine always described standalone invoice records while the deal schema embedded a single
  `invoice` object. The deal's embedded `invoice` object is now a denormalized summary of the
  most recent invoice record, and the deal carries `invoice_refs[]`. Invoice status uses the full
  six-state lifecycle: `draft`, `sent`, `viewed`, `paid`, `overdue`, `disputed`.
- `cost-estimate.template.json` — projected costs for a future project: line items with
  category, capex flag, source (`quote | cost_library | cost_research | assumption`), citation,
  and confidence label, plus time phases and totals.
- `cost-actuals.template.json` — what was actually spent, entry by entry, with vendor, category,
  capex flag, and receipt reference. Carries the boundary line.

Real records are `pipeline/finance/*.local.json` (gitignored). Invoice numbering is
deterministic: `INV-<deal_id>-<seq:03d>`, assigned by `tools/finance.py`, never by the model.

## Money arithmetic rules

- All amounts are exact decimals (`decimal.Decimal`), never floats. Rounding is ROUND_HALF_UP,
  quantized to cents, applied once at the end of each computation, not per intermediate step.
- Every computed value carries `computed_by` (for example `tools/finance.py accrue_late_penalty`)
  so a number's origin is always auditable.
- No fabrication, ever: amounts, rates, percentages, and dates come from records or explicit
  inputs. A missing figure is null plus a `gaps[]` entry naming what to provide
  (`shared/method.md` honest-gap rule). Benchmarks are labeled benchmarks; assumptions are
  labeled assumptions; nothing unlabeled is presented as fact.
- Currency is USD throughout. The `currency` field exists on every money-bearing record for the
  future, but no conversion math is performed.

## Structured payment terms

Free-text terms ("net 30 from delivery, 1.5% monthly late fee") stay on the record as received,
and a structured sibling makes them computable:

```json
"payment_terms_structured": {
  "net_days": 30,
  "anchor": "delivery | invoice_date | contract_signing | publish_date",
  "deposit_percent": null,
  "late_penalty": {"type": "none | flat | percent_per_month", "rate": null, "grace_days": 0},
  "kill_fee": null
}
```

Normalization procedure (runs wherever the record is written — deal-pipeline on deal updates,
obligation-extract on signed contracts): read the free text, fill only the fields the text
actually states, quote the supporting phrase as evidence, and leave everything else null with a
flag. Never infer a net period, a penalty rate, or an anchor that is not written down. The
structured block is input to `tools/finance.py`; the free text remains the source of truth for
what was agreed.

## Accounts receivable

- Aging buckets, computed from `payment_due_date` against today: `current` (not yet due),
  `1_to_30`, `31_to_60`, `61_to_90`, `over_90` days past due. Bucket edges are inclusive on the
  left (day 31 is in `31_to_60`).
- Chase timing reuses the obligation machinery: the send-by/action date for a follow-up gets an
  urgency band (`overdue`, `red`, `orange`, `yellow`) from `tools/obligations.py:urgency_band`,
  and weekend/holiday roll-back applies to derived action dates, never to the contractual due
  date itself.
- `disputed` invoices are excluded from penalty accrual and reported in their own line; `paid`
  invoices leave the aging report and keep their history.
- The AR scan is read-only and always available (no flag), like `--scan` in the obligations
  tool and the radar's `payment_overdue` view.

## Late-penalty math

Only when the terms state a penalty (`late_penalty.type` is not `none`), and only after
`grace_days` past the due date:

- `flat` — a single fixed `rate` (an amount) added once when the grace period lapses.
- `percent_per_month` — `rate` percent of the outstanding amount per FULL elapsed month past
  (due date + grace days). Full elapsed periods only, no proration of a partial month; months
  advance on the day-of-month anniversary.

Accrued penalties are reported alongside the principal (`accrued_penalty{amount, as_of,
computed_by}`), never silently folded into it, and never invoiced without human review. If the
free text describes a penalty structure these two types cannot express, the structured block
stays null and the scan flags the term for manual handling; the math never approximates a term.

## Revenue share, commission, and IP licensing fees

The rights and duties side of these clauses belongs to the contract stack (usage-rights-check
extracts scope and duration; obligation-extract turns reporting cadences and renewal dates into
dated obligation rows). This engine owns the money side:

```json
"revenue_share": {"basis": "ad_revenue | affiliate_sales | gross | other", "percent": null,
                  "floor": null, "cap": null, "reporting_cadence": "monthly | quarterly | null",
                  "source_of_truth": "who reports the basis figure"},
"commission":    {"basis": "tracked_sales | leads | other", "rate_percent": null,
                  "cookie_window_days": null, "floor": null, "cap": null},
"ip_license_fee": {"fee": null, "term_months": null, "renewal_fee": null,
                   "renewal_date": null, "exclusivity_premium": null}
```

- Payout math: `payout = clamp(basis_amount x percent / 100, floor, cap)`, computed by
  `tools/finance.py:revenue_share` only from a REPORTED basis figure (a platform statement, a
  brand report, an affiliate dashboard export). The system never estimates the basis.
- Every reporting cadence and license renewal date becomes an obligation row (duties with dates
  belong in the obligation register); the fee arithmetic stays here.
- The basis reporter is recorded (`source_of_truth`) because rev-share disputes are usually
  about whose number counts; flag terms that leave it unstated.

## Pricing standardization

Rate sources, in order of authority (never blended without labels, per `rate-card-fill`):

1. Personal rate actuals — `rate-card.local.json` under pipeline/finance/ (schema `pipeline/finance/rate-card.template.json`), rows written by the
   human (deal-debrief PROPOSES a row from each closed deal; only the human saves it).
2. Industry benchmarks — `canonical-sources/rate-benchmarks/benchmarks.json`, structured
   low/high/unit rows, always labeled as benchmarks with the verify-before-quoting caveat.
3. No data — say so; never extrapolate a rate from an adjacent format.

Proposal price floor: `price_floor = max(cost_floor, negotiation_floor)` where
`cost_floor = (expense_total + time_cost) x (1 + margin_percent / 100)` from the cost estimate,
and `negotiation_floor` comes from the rate card / playbook `pricing_and_rates` standard. The
proposal-price atom reports both inputs and which one bound. A price below documented cost is
flagged, never silently accepted. All of this is decision support for the human's quote; the
consequential-action gate applies before any number goes to a brand.

## Cost taxonomy

- `expense` — consumed by the project: production_materials, software_subscriptions (the
  project-attributable share), contractor_labor, travel, shipping_and_fees.
- `capex` — outlives the project: equipment_capex (camera, lens, lighting, tools that stay in
  the shop). Classification here is organizational, not a tax determination — the boundary line
  applies to every output that shows it.
- Time cost: `hours x hourly_rate`. The hourly rate comes from the personal rate card
  (`effective_hourly`) when present, else it is an explicit labeled assumption; hours come from
  the human or a labeled estimate tied to production-task phases. Never presented as measured
  when assumed.
- Cost line sources: `quote` (a vendor quoted it), `cost_library`
  (`canonical-sources/cost-library/costs.json`, dated), `cost_research` (the cost-researcher
  agent found it, cited), `assumption` (labeled). Every line carries its source.

## Offline compute lane

`tools/finance.py` is the second instance of the offline lane (`docs/LOCAL_CONTEXT.md`), same
shape as `tools/obligations.py`: stdlib only, no network, `CREATOR_OS_ROOT` sandbox override,
read-only scans always on, writes gated (`finance_management` for records, `invoice_generation`
for invoice writes), sha256 bucket manifest over `pipeline/finance/*.local.json`, and a
selftest. MCP tools (`finance_scan`, `invoice_build`, `cost_rollup`, `proposal_price`, <!-- verify: tools/finance.py::proposal_price --> <!-- verify: tools/finance.py::cost_rollup -->
`import_finance`) delegate to it so the model never does the arithmetic. `import_finance` fans
results out to the existing join points: chase dates to the content calendar and production
tasks, deposit due dates to deal-resourcing — never a parallel calendar.

## Reuse map (what this engine does NOT own)

- Date derivation, holidays, roll-back, urgency bands: `tools/obligations.py` (imported).
- Duties with dates (reporting cadences, renewals, deliverable deadlines): the obligation
  register (`shared/contract-engine.md`).
- Clause extraction and negotiation posture: the contract stack and the deal playbook.
- Rights scope and duration: `usage-rights-check`.
- Per-deal production planning and the trigger-to-date invoice schedule: `deal-resourcing`.
- Rate benchmark presentation: `rate-card-fill`; performance benchmarks: `benchmark-compare`.
- Revenue forecasting from historical series: the `forecast` atom (`shared/compute-engine.md`
  labeling rules apply).
