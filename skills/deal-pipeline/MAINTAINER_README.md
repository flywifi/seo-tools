---
file: skills/deal-pipeline/MAINTAINER_README.md
purpose: keep deal-pipeline enforcing evidence-gated transitions and triggering contract review and FTC checks at the correct stages.
---

# deal-pipeline: Maintainer README

## Purpose
Manage the full deal lifecycle with evidence-gated stage transitions, usage rights checks, and exclusivity conflict detection.

## Non-negotiable invariants
- Stage transitions require evidence per pipeline-engine.md; deal-stage-advance must validate before any record is changed.
- Contract review (protocols/safety.md) triggers at the contract-negotiating stage; never skipped.
- FTC disclosure check fires on every outreach-sent and signed transition.

## Known failure modes
- Advancing a stage without the required evidence (skipping deal-stage-advance validation).
- Missing the FTC disclosure check on a sponsored deal transition.
- Skipping usage-rights-check at the signed stage.

## Fragile fallbacks that must not become defaults
- Skipping contract review when the deal value is below a threshold (it always fires).

## Regression cases to preserve
1. contract-negotiating to signed without signed_contract_date: transition_allowed: false; halt.
2. Sponsored deal at outreach-sent: ftc_disclosure_required: true in the output.

## Approval-gated changes
- Stage transition evidence requirements (must match pipeline-engine.md).

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
