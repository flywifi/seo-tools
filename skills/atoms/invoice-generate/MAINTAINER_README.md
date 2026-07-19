---
file: skills/atoms/invoice-generate/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for invoice-generate so it stays stable under iteration.
---

# invoice-generate: Maintainer README

## Purpose
Draft a standalone invoice record from a deal's agreed figures, with all arithmetic, id
assignment, and due-date derivation delegated to `tools/finance.py build_invoice`. This atom's
job ends at a reviewed draft; sending is the human's act, always.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md`, `protocols/safety.md`
  (financial boundary), and `protocols/formatting-metadata.md`.
- Nothing is ever sent. `human_review_required: true` on every output; the consequential-action
  gate (amount, counterparty, terms, explicit yes) precedes any send by the human.
- Every figure comes from the deal record or the caller; missing figures become `gaps[]` and the
  invoice says it is incomplete. No estimation, no benchmark substitution.
- Writes require BOTH `finance_management` and `invoice_generation`; a refused write still
  returns the computed draft with the `_gate` reason. The gate is `tools/finance.py`'s
  `_write_allowed`, never re-implemented here. <!-- verify: tools/finance.py::_write_allowed -->
- Invoice ids are deterministic (`INV-<deal_id>-<seq:03d>`) and assigned by the tool.
- `terms_snapshot` freezes the structured terms at issue; later deal edits never mutate an
  issued invoice's meaning.
- The deal's `invoice_refs[]` and denormalized `invoice` summary update only after a successful
  write (the standalone record is authoritative, `shared/pipeline-engine.md`).

## Known failure modes
- Deal has free-text terms but no structured block: due date underivable until normalization.
- Wrong `seq` reuse would collide ids; the tool overwrites nothing silently, but callers should
  read existing `invoice_refs[]` to pick the next sequence.

## Fragile fallbacks that must not become defaults
- Returning a computed draft while flags are off is the degrade path, not a write substitute.
- A document render (document-studio) restating anything not in the record.

## Regression cases to preserve
1. Happy path: two line items plus a negative adjustment produce subtotal 3000.00 and total
   2750.00 with due date anchor+30 (finance.py selftest golden).
2. Missing unit_price yields a missing_amount gap and an incomplete invoice, never a guess.
3. Flags off: `_gate` present, `_written_to` absent, no file under `pipeline/finance/`.
4. Both flags on in a sandbox (`CREATOR_OS_ROOT`): file written, manifest verifies.
5. `terms_snapshot` on the record equals the terms passed at build time.
Mapped to evals/evals.json and `python3 tools/finance.py --selftest`.

## Approval-gated changes
The id scheme, the write gate pair, output schema, and any change that lets a figure enter the
invoice from anywhere but the record/caller.

## Minority-report policy
When the deal record and the caller disagree on a figure, stop and surface both values with
their sources; never pick one silently.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/finance.py --selftest` passes 102 of 102.
3. `python3 tools/sync_check.py` exits 0.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
