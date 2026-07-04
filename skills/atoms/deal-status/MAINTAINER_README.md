---
file: skills/atoms/deal-status/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for deal-status so it stays stable under iteration.
---

# deal-status: Maintainer README

## Purpose
Report a deal's lifecycle status verbatim from the record: stage, latest stage_history event,
payment_due_date, denormalized invoice.status. Resolution and the read are `tools/accounts.py`
(`deal_status()`, offline, deterministic); this atom is the thin contract. It reads only.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/pipeline-engine.md`) and obeys
  `protocols/no-fabrication.md` (never invent a stage or date; null and gap instead).
- READ-ONLY. No stage transition happens here; advancing a deal is `deal-stage-advance` in
  deal-pipeline, which is evidence-gated (`shared/pipeline-engine.md`).
- No money math. Aging, penalties, and totals are `ar-review` / `tools/finance.py`. This atom
  reports lifecycle fields only, so a status read never re-derives a figure.
- Every field is quoted from the record; the model computes nothing.
- Resolves the brand first via the shared resolver; an unresolved brand returns no deals, only the
  resolver candidates.

## Known failure modes
- Ambiguous or unknown brand: no deals, candidates surfaced.
- Account with no deals, or an unknown deal_id: a gap, no fabricated stage.

## Fragile fallbacks that must not become defaults
- Inferring a "probably signed by now" stage from dates.
- Computing days-to-due or overdue amounts (that crosses into finance.py's lane).

## Regression cases to preserve
1. Alias-resolved brand lists its deal with the verbatim stage.
2. Explicit deal_id returns that deal.
3. Latest stage_history event is the last entry, verbatim.
4. Unknown deal_id returns a gap and no deals.
Mapped to evals/evals.json; the read is pinned by `python3 tools/accounts.py --selftest`.

## Approval-gated changes
The read-only rule, the no-money-math boundary, the verbatim-fields rule, and the output schema.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/accounts.py --selftest` passes.
3. `python3 tools/sync_check.py` exits 0; `python3 tools/scenario_check.py` stays green.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
