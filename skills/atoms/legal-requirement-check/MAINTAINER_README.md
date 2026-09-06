---
file: skills/atoms/legal-requirement-check/MAINTAINER_README.md
purpose: keep legal-requirement-check a fixed, US-only checklist that cites real registry sources, flags rather than advises, and never invents terms or citations.
---

# legal-requirement-check: Maintainer README

## Purpose
Check a brand contract against a fixed checklist of creator-relevant US legal requirements and cite
the primary source for each flag. Read-only. Legal information only, never legal advice.

## Non-negotiable invariants
- Emits the verbatim RESEARCH NOTES header (em-dash-free) as the first line.
- The checklist is fixed: FTC disclosure, usage-rights conflict, perpetual-usage-for-flat-fee, exclusivity overlap, missing payment/kill-fee.
- Every FTC flag cites at least one FTC registry id that actually exists in canonical-sources/source-registry.json (ftc-disclosures-101, ftc-endorsement-guides, and the other seeded FTC entries).
- Never cite a source id that is not in the registry; never fabricate a citation.
- Jurisdiction is US only; a non-US governing law sets jurisdiction_warning rather than applying US sources.
- Reuses exclusivity-check (cross-deal overlap) and invoice-status; does not duplicate them.
- evidence_text is quoted or null; a missing status never invents a fee, date, or clause.
- human_review_required true; recommend_counsel true unless every flag is satisfied or not_applicable.

## Known failure modes
- Citing a source id that is not registered, or citing none on an FTC flag.
- Applying US FTC guidance to a contract with a foreign governing law.
- Inventing a fee to clear the missing-payment flag.
- Turning a flag into a legal conclusion about enforceability.

## Regression cases to preserve
1. Sponsored deal, contract silent on disclosure: ftc_disclosure at_risk, cites ftc-disclosures-101.
2. Perpetual worldwide license for a flat fee: perpetual_usage_flat_fee at_risk/missing, usage_rights_conflict flagged.
3. Non-sponsored, non-gifted, non-affiliate deal: ftc_disclosure not_applicable with a stated reason.
4. Missing fee and kill fee: missing_payment_terms missing, no invented figures.
5. Non-US governing law named: jurisdiction_warning present.
6. Neither contract_text nor deal_id: `{ "error": "no_source" }`.

## Update checklist
- Run python3 tools/sync_check.py.
- Verify the atom is composed by skills/contract-desk/workflow.json.
- Confirm the FTC entries in canonical-sources/source-registry.json still list legal-requirement-check in used_by (extended via tools/source_currency.py seed-sources).
