---
file: skills/atoms/deal-stage-advance/MAINTAINER_README.md
purpose: keep deal-stage-advance as a validation gate; it emits a transition record but never writes directly to pipeline/deals/.
---

# deal-stage-advance: Maintainer README

## Purpose
Validate a stage transition and emit a stage_change_record. Never writes directly to pipeline/deals/; pipeline-engine applies the record.

## Non-negotiable invariants
- transition_allowed: false when required evidence is missing; never bypassed.
- The 9-stage order is enforced: no skipping stages except identified to in-discussion when outreach was implicit.
- stage_change_record is only present in the output when transition_allowed: true.

## Known failure modes
- Allowing contract-negotiating to signed without a signed_contract_date in evidence.
- Emitting a stage_change_record when transition_allowed: false.
- Skipping the FTC disclosure check on the identified to outreach-sent transition.

## Regression cases to preserve
1. Missing signed_contract_date: transition_allowed: false; missing_evidence lists signed_contract_date.
2. Valid transition with all evidence: transition_allowed: true; stage_change_record is complete.

## Update checklist
- Run python3 tools/sync_check.py.
