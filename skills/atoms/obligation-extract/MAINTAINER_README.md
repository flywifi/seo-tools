---
file: skills/atoms/obligation-extract/MAINTAINER_README.md
purpose: keep obligation-extract a source-grounded extractor that emits one row per duty, quotes evidence, never computes dates, and never gives legal advice.
---

# obligation-extract: Maintainer README

## Purpose
Pull deliverables, deadlines, and payment terms from a SIGNED brand contract into obligation rows for
the offline date-math tool. Read-only. Legal information only, never legal advice.

## Non-negotiable invariants
- Emits the verbatim RESEARCH NOTES header (em-dash-free) as the first line.
- One row per distinct duty, using the obligation-row columns in shared/contract-engine.md; preserves the direction of each duty.
- timing_or_deadline is the contract's own date or phrase; the atom NEVER computes or infers a date (that is tools/obligations.py, run offline).
- evidence_text is quoted from the source; missing terms are null and flagged, never invented.
- Only extracts from a signed contract; before signing, defers to contract-review.
- Reuses usage-rights-check for rights/exclusivity/FTC extraction; does not re-parse those.
- human_review_required true; recommend_counsel true when a term is ambiguous.
- Never writes the register or any pipeline record; never rules on enforceability.
- Gated by contract_obligations.

## Known failure modes
- Computing a send-by date or urgency band in the atom instead of deferring to tools/obligations.py.
- Merging two duties into one row, or inventing a payment date the contract does not state.
- Extracting from an unsigned draft.
- Emitting a legal conclusion instead of a quoted obligation.

## Regression cases to preserve
1. Signed contract with dated deliverables + net-30 payment: one row per duty, timing_or_deadline carries the ISO date or the exact "net 30 from delivery" phrase, quoted evidence.
2. Missing payment date: row emitted with timing_or_deadline null and listed in missing; no invented date.
3. Unsigned draft: empty obligations with a flag pointing to contract-review.
4. Neither contract_text nor deal_id: `{ "error": "no_source" }`.
5. Output names tools/obligations.py --build as the next step and never contains a computed date.

## Update checklist
- Run python3 tools/sync_check.py.
- Verify the atom is composed by skills/contract-desk/workflow.json (action obligations).
- Verify shared/contract-engine.md still defines the obligation-row schema this atom emits, and that tools/obligations.py consumes the same row fields.
