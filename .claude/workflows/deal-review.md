# Deal Review Workflow

## Purpose
End-to-end pipeline review for a brand partnership deal. This workflow
validates stage evidence, audits usage rights and exclusivity, scores the
review against quality gates, and produces a structured verdict with a
human_review_required flag.

## Prerequisites
- The deal record exists in `pipeline/deals/` with a valid deal ID.
- The associated account record exists in `pipeline/accounts/`.
- The deal-reviewer agent (`.claude/agents/deal-reviewer.md`) is available.
- Engines loaded: `shared/pipeline-engine.md`, `shared/brand-engine.md`.
- Protocols enforced: `protocols/no-fabrication.md`, `protocols/safety.md`,
  `protocols/quality-gates.md`.

## Steps

1. **Load deal context**
   - The deal-reviewer agent reads the deal record from `pipeline/deals/`.
   - The agent reads the linked account from `pipeline/accounts/`.
   - If either record is missing or malformed, halt and return an error.

2. **Stage evidence check**
   - The deal-reviewer agent runs the `deal-stage-advance` atom.
   - The atom verifies that every required evidence field for the current
     stage is present and non-null.
   - Missing evidence blocks advancement; the review lists each gap.

3. **Usage rights audit**
   - The `usage-rights-check` atom reviews deal terms for:
     - Content ownership (who owns the final deliverable).
     - Licensing duration (e.g., 90 days, perpetual, 6 to 12 months).
     - Platform restrictions (where the brand may redistribute).
   - Any ambiguous or missing clause is flagged for human review.

4. **Exclusivity verification**
   - The `exclusivity-check` atom scans the deal for category exclusivity.
   - It cross-references active deals in `pipeline/deals/` to detect
     conflicts in the same product category.
   - Conflicts are listed with the competing deal IDs and date ranges.

5. **Quality scoring**
   - The `quality-review` spoke runs the `govern-artifact` atom.
   - The deal review output is scored against `protocols/quality-gates.md`.
   - Result: pass or fail, with itemized flags for any open issues.

## Error handling
- **Missing deal record**: return `{ "error": "deal_not_found" }` and stop.
- **Missing account record**: return `{ "error": "account_not_found" }` and stop.
- **Incomplete evidence**: continue the review but set stage_ready to false
  and list every missing field in the output.
- **Exclusivity conflict**: do not block the review; flag the conflict and
  set `human_review_required: true`.

## Agents and atoms used
- **deal-reviewer agent** (`.claude/agents/deal-reviewer.md`): orchestrates
  the full review using `deal-stage-advance`, `usage-rights-check`,
  `exclusivity-check`, `account-health`, and `roi-metric` atoms.
- **quality-review spoke**: runs the `govern-artifact` atom for scoring.

## Output contract
The workflow returns a JSON object with these fields:
- `deal_id`: the reviewed deal identifier.
- `stage_ready`: boolean -- true only if all evidence is present.
- `evidence_gaps`: array of missing evidence field names (empty if none).
- `usage_rights_summary`: object with ownership, duration, and restrictions.
- `exclusivity_conflicts`: array of conflicting deal objects (empty if none).
- `quality_gate_score`: numeric score from the govern-artifact rubric.
- `quality_gate_pass`: boolean.
- `open_flags`: array of unresolved issues requiring attention.
- `human_review_required`: boolean -- always true when conflicts or
  ambiguous clauses exist.

All deal data is sourced exclusively from `pipeline/` records.
Never fabricate deal values, brand names, or metrics.
