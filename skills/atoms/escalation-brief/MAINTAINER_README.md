---
file: skills/atoms/escalation-brief/MAINTAINER_README.md
purpose: keep escalation-brief a draft-only decision aid that quotes evidence, offers accept/counter/walk, passes the consequential-action gate, and never sends or commits anything.
---

# escalation-brief: Maintainer README

## Purpose
Turn flagged contract findings into a one-page, decision-ready brief with accept/counter/walk options
and a decide-by date. Draft only. Legal information only, never legal advice.

## Non-negotiable invariants
- Emits the verbatim RESEARCH NOTES header (em-dash-free) as the first line.
- ready_to_send is always false; the atom never sends, emails, counters, or advances a deal stage.
- Includes the consequential_action_note on every output (the consequential-action gate).
- Each item gives accept, counter, and walk with a trade-off; counter is plain-language, never binding.
- recommended_path is a labeled suggestion grounded in the playbook, never a directive or legal advice.
- evidence_text is quoted from the source finding, never paraphrased into a quote.
- decide_by never invents the brand's deadline; a suggested date is labeled decide_by_source suggested.
- human_review_required true; recommend_counsel true.

## Known failure modes
- Emitting a send-ready message or implying the ask was sent.
- Recommending a path as the legally correct choice.
- Inventing a brand response deadline.
- Drafting binding counter language instead of a plain-language change request.
- Empty findings input producing a fabricated escalation.

## Regression cases to preserve
1. One RED finding: item with accept/counter/walk, quoted evidence, ready_to_send false.
2. No brand deadline provided: decide_by suggested from urgency band, decide_by_source suggested.
3. Brand deadline provided: decide_by uses it, decide_by_source brand_stated.
4. Empty findings: `{ "note": "no flagged findings to escalate" }`, no fabricated items.
5. Consequential-action note present on every output.

## Update checklist
- Run python3 tools/sync_check.py.
- Verify the atom is composed by skills/contract-desk/workflow.json.
- Verify shared/contract-engine.md still defines the consequential-action gate and urgency bands this atom relies on.
