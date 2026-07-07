---
name: finance-desk
description: "the Pipeline/CRM spoke for the money book: drafts invoices from a deal's agreed figures (never sends), reports portfolio-wide accounts receivable with aging and accrued late penalties, builds projected cost estimates for future projects, and computes standardized proposal price floors from the rate card and cost data. All arithmetic runs offline in tools/finance.py; every figure comes from records or explicit inputs. Does NOT manage the deal lifecycle (deal-pipeline), review contracts (contract-desk), plan production for one signed deal (deal-resourcing), or send anything anywhere."
load: for finance-desk requests (invoicing, AR, cost estimates, proposal pricing)
---

# finance-desk

finance-desk is the accounting bucket's front door: cross-deal money views (who owes what) and
pre-deal money work (what will this cost, what should I charge), plus per-deal invoice drafting.
It complements deal-pipeline (lifecycle), contract-desk (the contract document), and
deal-resourcing (per-deal production planning with its trigger-based invoice schedule). It is
arithmetic and organization only, never tax or accounting advice, and it never sends anything.

## Boundary (verbatim on every tax-adjacent artifact)

```
ARITHMETIC AND RESEARCH NOTES. NOT TAX, ACCOUNTING, OR INVESTMENT ADVICE. REVIEW WITH A CPA OR TAX PROFESSIONAL BEFORE FILING OR RELYING ON CATEGORIZATIONS.
```

A consequential-action gate (amount, counterparty, terms, explicit yes) precedes anything that
commits money externally: sending an invoice, quoting a price, agreeing a rate
(`shared/finance-engine.md`, `protocols/safety.md`).

## Actions

- `invoice` — draft a standalone invoice record for a deal (`invoice-generate`). Routed as
  `invoice_create`.
- `ar` — the accounts-receivable book: aging buckets, per-brand totals, accrued penalties,
  chase queue (`ar-review`). Routed as `finance_review`. Read-only, always available.
- `estimate` — projected costs for a future project: sourced line items, capex split, time cost
  (`cost-estimate`). Routed as `cost_estimate`.
- `price` — a standardized price floor for a proposal: cost floor vs negotiation floor, fed by
  the rate card and the estimate (`proposal-price`). Routed as `proposal_price`. Output feeds
  `pitch-paragraph` and `contract-draft`.
- `cashflow` — the weekly cash-movement view over the horizon: expected inflows from open
  invoices and dated scheduled rows, outflows from dated estimates (`cashflow-view`). Routed as
  `cashflow_projection`. Read-only, always available; redacted output (banded amounts,
  initialed brands) for anything that leaves the machine.
- `reconcile` — match a bank or PayPal export against open invoices with confidence tiers,
  confirm each proposal, then the gated mark-paid write (`payment-reconcile`). Routed as
  `payment_reconcile`. The export must live at a gitignored .local. path or outside the repo;
  the tool structurally refuses anything else.
- `dun` — an escalating payment-reminder DRAFT for one overdue invoice, tone keyed to the aging
  bucket (gentle for current and 1 to 30 days, firm for 31 to 60, final for 61 plus), figures
  verbatim from a fresh ar-review row (`dunning-draft`). Routed as `dunning_draft`. NEVER sends;
  drafts land in gitignored .local files and the human sends from their own client.

## How the money math runs

Every computation is `tools/finance.py` (offline, exact Decimal, `computed_by` on every result;
see `shared/finance-engine.md` for the rules). Read-only scans need no flag. Record writes are
gated by `finance_management`; invoice writes additionally by `invoice_generation`. Real records
live in `pipeline/finance/*.local.json` (gitignored); this spoke never invents a figure: missing
data is null plus a gap naming the fix.

## Engines and protocols loaded
- `shared/finance-engine.md` (money rules, boundary, record store)
- `shared/pipeline-engine.md` (deal facts, invoice lifecycle, stage gates)
- `protocols/no-fabrication.md`, `protocols/safety.md`, `protocols/quality-gates.md`,
  `protocols/formatting-metadata.md`

## Atoms used
Composed: `invoice-generate`, `ar-review`, `cost-estimate`, `proposal-price`, `invoice-status`,
`govern-artifact`. Callable directly as shortcuts (see `workflow.json`).

## Standalone usability
Each action produces a complete artifact on its own: a reviewable invoice draft, an AR aging
report, a sourced cost estimate, or a price floor with its binding constraint named.

## Failure modes
- Flags off: computations still run and are reported; nothing is written. Each refusal points at
  its `degraded_behavior` entry.
- No finance records yet: honest empty states, never fabricated pipelines.
- Unstructured payment terms: due dates and penalties cannot be computed until the terms are
  normalized (quoted evidence or null, per the engine); the gap says exactly that.

## Cross-modality
Class: C.
Runs on: Claude Desktop/Code (native, MCP + the tool module); claude.ai via a hosted remote-MCP connector; Custom GPT / Gemini only when the tool is hosted behind a remote MCP or an Action; Gems: no.
Mechanism: tools/finance.py offline money math (invoices, cost estimates, proposal pricing, cash flow) over the private pipeline/finance store; MCP finance tools; redaction before figures leave.
Fallback: No runtime or hosted seam -> reason over finance-engine.md formulas against pasted figures, show the math, flag unverified; never fabricate a dollar amount.
See `shared/cross-modality-engine.md`.