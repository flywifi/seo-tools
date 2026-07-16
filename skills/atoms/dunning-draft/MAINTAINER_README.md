---
file: skills/atoms/dunning-draft/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for dunning-draft so it stays stable under iteration.
---

# dunning-draft: Maintainer README

## Purpose
Escalating payment-reminder drafts for one overdue invoice, tone keyed to the aging bucket,
figures strictly from the ar-review row and the invoice's frozen terms. The atom drafts; the
human sends. The math lives in `tools/finance.py`; the matching in `payment-reconcile`.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md`, `protocols/safety.md`
  (financial boundary + consequential gate), and `protocols/formatting-metadata.md` (no em
  dashes, ranges with "to" in the user-facing draft).
- NEVER sends. `sent: false` always; the consequential-action gate (amount, counterparty,
  tone, explicit yes) precedes the human sending from their own client.
- Every figure and date restates the ar_scan row verbatim; the model computes nothing.
- Penalty language exists only when the terms_snapshot contains a penalty clause, quoted; no
  penalty is implied that the agreement does not state, and no legal threat exceeds the
  contract's own remedies.
- Tone ladder is bucket-bound: gentle (current, 1 to 30), firm (31 to 60), final (61 plus).
  Escalation is never applied early.
- Drafts are written ONLY to gitignored `.local.md` paths under pipeline/finance/ (covered by
  the allowlist-invert gitignore); a draft is never committed or pasted unredacted into
  anything that leaves the machine.
- Disputed invoices are refused (resolve the dispute first).

## Known failure modes
- A stale ar_scan row (invoice paid since) producing a wrong chase: re-run the scan immediately
  before drafting.
- Tone drift under user pressure ("make it scary"): the final tone is the ceiling; anything
  beyond routes to contract-desk escalation, not this atom.

## Fragile fallbacks that must not become defaults
- Drafting from memory of a prior scan instead of a fresh row.
- Softening `sent: false` into auto-send convenience of any kind.

## Regression cases to preserve
1. Bucket-to-tone mapping exact at the edges (30/31, 60/61).
2. No-penalty terms produce firm/final drafts with zero penalty language.
3. Disputed invoice refused with the dispute pointer.
4. Draft file lands at a `.local.md` path only; nothing tracked (invariants 19/20 hold).
5. Figures in the draft match the ar_scan row string for string.
Mapped to evals/evals.json; the row math is pinned by `python3 tools/finance.py --selftest`.

## Approval-gated changes
The tone ladder and its bucket edges, the never-sends rule, the penalty-quoting rule, output
schema, and the .local-only save path.

## Minority-report policy
When the account contact and the invoice brand disagree (renamed brand, new contact), surface
both and let the human address the letter; never guess the recipient.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/finance.py --selftest` passes 99 of 99.
3. `python3 tools/sync_check.py` exits 0 (invariants 19/20 cover the draft path).
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
