---
file: skills/deal-pipeline/references/artifact-types.md
role: the artifact types deal-pipeline produces and the required elements of each.
---

# deal-pipeline artifact types

## Deal report
A lifecycle status snapshot for one deal. Required elements: deal_id, brand_name, current_stage, stage_change_record (if a transition was requested and allowed), usage_rights_summary (if at or past contract-negotiating), exclusivity_conflicts list, ftc_disclosure_required (bool), recommended_next_step, and a govern-artifact gate result.

## Stage change record
The output of deal-stage-advance when transition_allowed is true. Required elements: deal_id, from_stage, to_stage, timestamp_utc, evidence_provided, and any warnings (e.g., exclusivity not yet checked).

## Usage rights summary
The output of usage-rights-check for a deal. Required elements: exclusivity (scope, platform, duration), ownership, license_grant, platform_restrictions (list), ftc_disclosure_required (bool, reason), flags (ambiguous or missing clauses), and recommend_counsel (bool).
