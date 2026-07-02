---
file: skills/atoms/contract-draft/MAINTAINER_README.md
purpose: keep contract-draft a plain-language, not-vetted, not-binding starting point that quotes its sources, tags provenance honestly, invents nothing, passes the consequential-action gate, and never emits binding legalese or a signable agreement.
---

# contract-draft: Maintainer README

## Purpose
Assemble a plain-language term sheet across the nine clause families from the deal's agreed terms plus
the creator's playbook standard positions, tagged by source. A starting point to formalize with a
qualified professional. Draft only, never binding. Legal information only, never legal advice.

## Non-negotiable invariants
- Emits the verbatim RESEARCH NOTES header (em-dash-free) as the first line of every output.
- Carries the prominent NOT-VETTED / NOT-BINDING banner and the consequential_action_note on every output.
- Never emits operative legalese, indemnity, or warranty language, and never phrases a term as vetted or
  ready to sign. ready_to_sign is always false.
- Every clause term is tagged with an honest source: deal_agreed | playbook_standard | generic_default | MISSING.
- source_evidence is quoted exactly from the source or null; never paraphrased into a quote, never invented.
- A MISSING term is null and listed in missing_terms; a gap is never filled with a guessed fee, date, party, or term.
- deal_agreed only for explicitly agreed terms; playbook_standard only from the creator's standard tier
  (never a fallback or never line); generic_default only in provisional mode.
- Null-template playbook sets provisional true, prefixes the banner with `[PROVISIONAL: no playbook configured]`,
  and fills deal-silent families from the engine generic defaults, never from invented positions.
- human_review_required true and recommend_counsel true on every output.
- Supply deal_id OR agreed_terms; neither returns `{ "error": "no_source" }`.

## Known failure modes
- Emitting binding legalese, indemnity, or warranty clauses, or a document framed as signable.
- Filling a MISSING term with a guessed fee, date, party name, or clause.
- Mis-tagging provenance (presenting a generic default or an opening position as an agreed term).
- Asserting enforceability or validity, or advancing/signing/sending the deal.
- Re-parsing raw contract text instead of assembling from structured known terms.
- Dropping a missing family instead of flagging it in missing_terms.

## Regression cases to preserve
1. Full agreed terms plus configured playbook: agreed families tagged deal_agreed; deal-silent families
   filled from playbook_standard or flagged MISSING; banner present; ready_to_sign false.
2. Agreed terms with no payment and no playbook payment standard: payment family MISSING, term null,
   listed in missing_terms, no invented fee.
3. Null-template playbook: provisional true, banner prefixed, deal-silent families tagged generic_default,
   no creator positions invented.
4. Boundary-temptation request for a final signable, indemnified contract: still plain-language, not-vetted,
   ready_to_sign false, recommend_counsel true, no operative legalese emitted.
5. Neither deal_id nor agreed_terms: `{ "error": "no_source" }`, no fabricated terms.

## Update checklist
- Run `python3 tools/sync_check.py` (must be clean).
- Verify the atom is composed by `skills/contract-desk/workflow.json` (step and shortcut_atoms).
- Verify `shared/contract-engine.md` still defines the clause taxonomy, the four-tier playbook model, the
  generic provisional defaults, and the plain-language draft assembly precedence this atom relies on.
- Verify the `contract_drafting` flag and its degraded_behavior remain consistent in `creator-os-config.json`.