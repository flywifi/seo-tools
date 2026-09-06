---
file: skills/finance-desk/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for finance-desk so it stays stable under iteration.
---

# finance-desk: Maintainer README

## Purpose
The accounting bucket's spoke: invoice drafting, portfolio AR, cost estimates, and proposal
price floors, all realized by `tools/finance.py` offline. Deal lifecycle stays with
deal-pipeline; contract documents with contract-desk; per-deal production planning (and its
trigger-based invoice schedule) with deal-resourcing. This spoke never sends anything.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md`, `protocols/safety.md`
  (financial boundary), and `protocols/formatting-metadata.md`.
- All arithmetic is `tools/finance.py`; the model never adds, rounds, ages, or accrues by hand.
- Reads are flag-free; record writes gate on `finance_management` (invoices additionally on
  `invoice_generation`). Gates live in the tool, never re-implemented in prose.
- The consequential-action gate precedes any external money commitment; invoices are drafted,
  never sent.
- Tax-adjacent outputs carry the verbatim boundary line from `shared/finance-engine.md`.
- No figure enters any artifact except from a record or an explicit input; missing data is a
  gap naming the fix.

## Known failure modes
- Deals with free-text-only payment terms stall due-date and penalty math until normalization.
- The deal's denormalized invoice summary going stale against the standalone records (the
  standalone record is authoritative; flag divergence).

## Fragile fallbacks that must not become defaults
- Reporting computed-but-unwritten drafts as if persisted.
- Prose money summaries drifting from the tool's exact-decimal strings.

## Regression cases to preserve
1. Invoice happy path: subtotal 3000.00 / total 2750.00 / due anchor+30 (finance selftest).
2. AR: 32 days past due in 31_to_60; disputed excluded from outstanding; empty book honest.
3. Write gates: finance_management alone insufficient for an invoice write; both flags in a
   sandbox write and manifest-verify.
4. Penalty accrual: full elapsed months past grace only, end-of-month clamped.
5. Every action's artifact passes govern-artifact before release.
Mapped to evals/evals.json and `python3 tools/finance.py --selftest` (99 checks).

## Approval-gated changes
The action set, atom composition order, the gate pairing, output schemas, and any change that
lets this spoke send, publish, or write outside `pipeline/finance/`.

## Minority-report policy
When records disagree (deal summary vs standalone invoice, estimate vs actuals), surface both
figures with sources and flag the divergence; never reconcile silently.

## Update checklist
1. Edit SKILL.md / workflow.json / this file.
2. `python3 tools/finance.py --selftest` passes 105 of 105.
3. `python3 tools/sync_check.py` exits 0 (hub downstream + routing rows + atom resolution).
4. `python3 tools/scenario_check.py` exits 0.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
