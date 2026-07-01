---
file: skills/atoms/exclusivity-check/MAINTAINER_README.md
purpose: keep exclusivity-check focused on factual conflict detection from pipeline/deals/ records; never fabricate deal terms or make binding legal conclusions.
---

# exclusivity-check: Maintainer README

## Purpose
Cross-reference a deal's exclusivity clause against all active deals in pipeline/deals/ to detect
category conflicts with overlapping date ranges. Read-only — never modifies deal records.

## Non-negotiable invariants
- All deal data is read from pipeline/deals/ records. Never fabricated.
- human_review_required: true whenever conflict_count > 0.
- Null exclusivity fields are reported as null, not inferred or guessed.
- The atom reads deal records but never writes or modifies them.
- Fuzzy category matches (full_scan mode) are labeled with match_type: "fuzzy".
- Obeys protocols/no-fabrication.md: no invented terms, dates, or brand names.

## Known failure modes
- Inventing deal terms, brand names, or dates not present in the deal record.
- Reporting zero conflicts when overlapping exclusivity clauses exist but categories use different
  terminology (e.g., "home furnishings" vs. "furniture"). Mitigated by full_scan fuzzy matching.
- Setting human_review_required: false when conflicts exist.
- Modifying pipeline/deals/ records (this atom is read-only).

## Regression cases to preserve
1. Two deals in same category with overlapping dates and one has exclusivity: conflict detected,
   severity "hard", human_review_required: true.
2. Deal with no exclusivity clause checked against a deal that HAS one: conflict detected from
   the other deal's clause, exclusivity_source: "other".
3. Deal record missing or malformed: error returned, not a fabricated result.
4. No active deals in pipeline: zero conflicts, clean output.
5. Partial exclusivity clause (end_date null): conflict flagged with retrieval_gap noting the
   missing field.
6. Full_scan fuzzy match: "home furnishings" vs. "furniture" detected as potential overlap,
   labeled match_type: "fuzzy".
7. Deal in archived or closed stage: excluded from active deal scan.

## Update checklist
- Run python3 tools/sync_check.py.
- Verify the atom is listed in deal-pipeline spoke's workflow.json.
- Verify `.claude/agents/deal-reviewer.md` and `.claude/workflows/deal-review.js` reference it correctly.
