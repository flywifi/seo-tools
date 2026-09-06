---
file: skills/atoms/contract-review/MAINTAINER_README.md
purpose: keep contract-review a source-grounded, dual-severity clause reviewer that quotes evidence, suggests plain-language changes, and never gives legal advice or drafts binding language.
---

# contract-review: Maintainer README

## Purpose
Clause-by-clause review of a brand contract against the creator's playbook, deal-breakers first.
Read-only. Legal information only, never legal advice.

## Non-negotiable invariants
- Emits the verbatim RESEARCH NOTES header (em-dash-free) as the first line.
- One finding per clause family in shared/contract-engine.md.
- Each finding carries independent legal_risk and business_friction severities; they are never averaged or collapsed.
- contract_says and evidence_text are quoted from the source or null; never paraphrased into a quote, never invented.
- A missing clause is a finding with contract_says null, gap "missing", and appears in missing_clauses.
- redline_suggestion is plain-language and framed as a request; never binding, never presented as vetted.
- Reuses usage-rights-check (extraction) and exclusivity-check (cross-deal conflict); does not duplicate them.
- human_review_required true; recommend_counsel true unless every clause is present, unambiguous, and within the playbook.
- Null playbook triggers `[PROVISIONAL: no playbook configured]` and generic-default comparison.

## Known failure modes
- Averaging the two severity axes into one score.
- Fabricating clause text or presenting a paraphrase as a quote.
- Emitting binding language in redline_suggestion, or asserting enforceability.
- Dropping missing clauses instead of reporting them as findings.
- Re-parsing rights instead of calling usage-rights-check.

## Regression cases to preserve
1. Full contract with all families present: one finding per family, deal-breakers ordered first.
2. Perpetual usage clause: high legal_risk finding, quoted evidence_text, plain-language redline.
3. Five-round approval loop with a bounded fee: low legal_risk, high business_friction (axes differ).
4. Missing kill-fee clause: finding with contract_says null, listed in missing_clauses.
5. Null playbook: output prefixed provisional, findings still produced against generic defaults.
6. Neither contract_text nor deal_id: `{ "error": "no_source" }`.

## Update checklist
- Run python3 tools/sync_check.py.
- Verify the atom is composed by skills/contract-desk/workflow.json.
- Verify shared/contract-engine.md still defines the clause taxonomy, dual-severity axis, and confidence labels this atom relies on.
