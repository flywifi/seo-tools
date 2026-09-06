---
file: skills/atoms/contract-triage/MAINTAINER_README.md
purpose: keep contract-triage a fast router (GREEN/YELLOW/RED) that quotes evidence and never gives legal advice, negotiates, or invents terms.
---

# contract-triage: Maintainer README

## Purpose
Give an inbound brand contract a fast verdict and route it, surfacing hidden obligations and likely
deal-breakers. Read-only. Legal information only, never legal advice.

## Non-negotiable invariants
- Emits the verbatim RESEARCH NOTES header (em-dash-free) as the first line.
- `human_review_required: true` and `recommend_counsel: true` unless GREEN with zero flags.
- Reuses usage-rights-check for extraction; does not re-parse or duplicate that logic.
- Reads the deal-playbook first; when it is the null template, prefixes `[PROVISIONAL: no playbook configured]` and uses the generic defaults in shared/contract-engine.md.
- Every evidence_text is quoted from the source; missing-term findings have evidence_text null and are labeled missing, never invented.
- Any hidden obligation forces at least YELLOW; any deal-breaker forces RED.
- relevance and importance are scored separately from each other and from the verdict.
- Never rules on enforceability, negotiates, drafts, or writes to pipeline records.

## Known failure modes
- Marking GREEN when a non-compete, perpetual license, or auto-renewal is buried in the terms.
- Inventing a fee or category not present in the input to justify a verdict.
- Collapsing relevance and importance into the verdict.
- Producing legal conclusions instead of flags.

## Regression cases to preserve
1. Standard offer with bounded rights and clear disclosure: GREEN, empty flag arrays.
2. Hidden non-disclosure clause in a sponsorship: YELLOW, hidden_obligations_found populated with quote.
3. Perpetual worldwide rights for a flat fee: RED, deal_breakers_found populated, recommend_counsel true.
4. Neither contract_text nor deal_id: `{ "error": "no_source" }`.
5. Null playbook: output prefixed `[PROVISIONAL: no playbook configured]`, verdict still produced.

## Update checklist
- Run python3 tools/sync_check.py.
- Verify the atom is composed by skills/contract-desk/workflow.json.
- Verify shared/contract-engine.md still defines the GREEN/YELLOW/RED model this atom follows.
