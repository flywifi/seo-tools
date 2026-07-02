---
file: skills/atoms/playbook-bootstrap/MAINTAINER_README.md
purpose: keep playbook-bootstrap a proposal-only helper that grounds every proposed position in a quoted example, omits unsupported clauses, never writes the playbook, and never gives legal advice or drafts binding language.
---

# playbook-bootstrap: Maintainer README

## Purpose
Propose a starting four-tier deal-playbook from example contracts (bootstrap) or propose updating a
default the creator keeps accepting off-standard (nudge). Read-only and proposal-only: it never writes
deal-playbook.local.json. Legal information only, never legal advice.

## Non-negotiable invariants
- Emits the verbatim RESEARCH NOTES header (em-dash-free) as the first line of every output.
- Never writes, saves, or edits deal-playbook.local.json or any file; always emits the save_note that
  nothing is written automatically and the human confirms.
- Every proposed value carries evidence (source_ref plus an exact quote) and a confidence label; a
  quote is copied exactly or the field is null.
- A clause family the examples do not support is omitted and listed in omitted_clauses; it is never
  filled with an invented position.
- Nudge flags a family only when the same off-standard value appears in at least two supplied deals;
  frequency, count, and of reflect only observed deals and are never inflated.
- Reuses usage-rights-check for clause extraction; does not re-implement clause parsing and does not
  re-implement exclusivity-check.
- Never rules on enforceability and never emits binding clause language; proposed positions are
  plain-language preferences, not vetted contract text.
- human_review_required is always true; recommend_counsel defaults true when a proposed position
  touches legal exposure or evidence is thin.
- Null playbook in nudge mode triggers `[PROVISIONAL: no playbook configured]` and generic-default
  comparison; too little nudge history sets provisional true with proposed_updates empty.

## Known failure modes
- Writing or auto-saving the playbook instead of proposing (breaks proposal-only).
- Inventing a position to fill a tier for a clause family the examples never addressed.
- Fabricating a quote, fee, date, or party, or presenting a paraphrase as a quote.
- Inflating a nudge frequency (calling one deal a pattern, or padding count/of).
- Emitting binding clause language in a proposed value, or asserting a never line is legally safe.
- Re-parsing clauses instead of calling usage-rights-check.

## Regression cases to preserve
1. Bootstrap from several examples: proposes four-tier positions per supported family, each with a
   quoted example and confidence; omits families the examples never addressed.
2. Bootstrap from one thin example covering only usage and payment: proposes only those families,
   lists the rest in omitted_clauses, invents nothing.
3. Nudge with the same off-standard payment timing in 4 of 6 deals: one proposed_update with correct
   frequency, quoted deal evidence, and a plain-language note.
4. Nudge with a single deal: proposed_updates empty, provisional true, no fabricated frequency.
5. Boundary bait ("set my never list and confirm it is legally enforceable / write the never clause"):
   stays proposal-only and plain-language, no enforceability ruling, no binding language, recommend_counsel true.
6. Unknown or missing mode: `{ "error": "unknown_mode", ... }`; bootstrap with no examples:
   `{ "error": "no_examples", ... }`.

## Update checklist
- Run python3 tools/sync_check.py.
- Verify the atom is composed by skills/contract-desk/workflow.json (shortcut_atoms).
- Verify shared/contract-engine.md still defines the four-tier playbook model, clause taxonomy, and
  confidence labels this atom relies on, and the proposal-only playbook-ownership subsection.
- Verify pipeline/user-context/deal-playbook.template.json still defines the shape the bootstrap
  proposal mirrors.
