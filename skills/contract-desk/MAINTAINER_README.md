---
file: skills/contract-desk/MAINTAINER_README.md
purpose: keep contract-desk a read-and-review spoke that composes the contract atoms, enforces the non-advisory boundary, and never signs, sends, or writes binding language.
---

# contract-desk: Maintainer README

## Purpose
Pipeline/CRM spoke that reviews the contract document (triage, clause review, legal-requirement
checks, escalation brief), complementing deal-pipeline which manages the deal record. Legal
information only, never legal advice.

## Non-negotiable invariants
- Gated behind the contract_management master flag; when off, deal-pipeline behavior is unchanged and this spoke does not run.
- Every artifact carries the verbatim RESEARCH NOTES header (em-dash-free), human_review_required true, and recommend_counsel true when anything is unclear.
- Composes contract-triage, contract-review, legal-requirement-check, escalation-brief, and reuses usage-rights-check, exclusivity-check, and govern-artifact.
- Never rules on enforceability, drafts binding language, signs, or sends anything; escalation-brief output is draft-only (ready_to_send false).
- No new connector: intake reuses the existing uploaded_file / google_drive document connectors.
- Phase 2 (drafting, amendment tracing) and Phase 3 (obligation register) are not built; requests degrade honestly per creator-os-config.json.

## Known failure modes
- Running when contract_management is off.
- Emitting an output without the RESEARCH NOTES header or without passing govern-artifact.
- Treating a drafting or obligation request as available in Phase 1 instead of degrading.
- Advancing a deal stage or sending a counter (that belongs to deal-pipeline and a human send path).

## Regression cases to preserve
1. action full on a standard contract: triage GREEN, review + legal-check run, escalation-brief empty or minimal, govern-artifact passes.
2. action full on a perpetual-rights flat-fee contract: triage RED, legal-requirement-check flags perpetual_usage_flat_fee, escalation-brief drafts accept/counter/walk, ready_to_send false.
3. Null playbook: atoms run in provisional mode, labeled.
4. Drafting requested in Phase 1: degrades to plain-language summary + recommend counsel, no binding language.
5. contract_management off: spoke does not run; deal-pipeline handles contract-negotiating as before.

## Update checklist
- Run python3 tools/sync_check.py (spoke listed in hub downstream; workflow atoms resolve; routing table complete).
- Verify skills/contract-desk/workflow.json names only installed atoms.
- Verify creator-core routes contract_review / contract_draft / contract_amendment / contract_obligations to contract-desk.
