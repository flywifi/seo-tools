# 14. P30 Accounting Bucket

- Date: 2026-07-04
- Status: Accepted

## Context

The creator needed AR tracking, invoicing matched to deals/contracts/terms (net days, late penalties), projected costs, standardized pricing feeding proposals and contract drafts, and structured revenue-share/commission/IP-licensing money terms. Everything reuses the established disciplines: the obligations date machinery rather than duplicated math, records-or-null over estimation for every figure, read-scans always available with writes flag-gated, committed blank templates with gitignored .local data (invariant 19), human confirmation before anything money-facing leaves the system, and findings-as-contract for the G8 close. Explicitly out of scope: sending invoices or payments, bank reconciliation, multi-currency math, any tax computation, dashboard finance UI, auto-dunning.

## Decision

Built the accounting bucket. Record store: pipeline/finance/ standalone invoice records (many per deal, line items, terms_snapshot frozen at issue), cost estimates, and cost actuals, resolving the invoice drift toward the engine's standalone model (deal.invoice is now a denormalized summary plus invoice_refs[]). Structured money terms added additively to deal (v0.3.0) and contract schemas: payment_terms_structured (net days, anchor, deposit, late penalty type/rate/grace, kill fee), revenue_share, commission, ip_license_fee, all filled only from quoted evidence; playbook gained pricing_and_rates and revenue_share_and_commission families. tools/finance.py is the second offline compute lane instance (imports obligations.py date machinery; Decimal ROUND_HALF_UP; 44-check selftest): AR aging with left-inclusive buckets and rolled chase dates (contractual due dates never rolled), late-penalty accrual (flat / percent-per-month, full elapsed months, unsupported structures refused), revenue-share/commission clamps from reported basis figures only, cost rollups with expense/capex split, proposal price floors (max of cost floor and negotiation floor), deterministic invoice ids, sha256 manifest, CREATOR_OS_ROOT sandbox; writes gated on finance_management + invoice_generation. New finance-desk spoke with invoice-generate, ar-review, cost-estimate, proposal-price atoms; four hub classifications; document-studio invoice artifact type; invoice-status upgraded to standalone records and six states. G8 closed deliberately (structured benchmark rows, metric rows sourced-or-null; suite at 7 gaps). Personal rate card template with deal-debrief proposal-only feedback loop. Fifth agent role cost-researcher (envelope schema, web-intel L2/L3, observed-or-null prices) with the cost library and homedepot/lowes vendor sources registered via source_currency.py. Five MCP tools (32 total). Verbatim financial boundary (NOT TAX, ACCOUNTING, OR INVESTMENT ADVICE) in finance-engine.md and protocols/safety.md, with a consequential-action gate before any external money commitment.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P30-accounting-bucket`.
