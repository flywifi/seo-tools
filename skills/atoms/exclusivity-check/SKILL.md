---
name: exclusivity-check
atom: true
description: "Scans a deal record for category exclusivity clauses and cross-references all active deals in pipeline/deals/ to detect conflicts in the same product category or niche. Do NOT use for usage-rights auditing (use usage-rights-check) or deal stage advancement (use deal-stage-advance)."
load:
  - shared/pipeline-engine.md
  - protocols/no-fabrication.md
---

# exclusivity-check

Scan a brand partnership deal for category exclusivity clauses and cross-reference every active deal
in `pipeline/deals/` to detect conflicts — two deals in the same product category with overlapping
date ranges.

## Purpose

Brand partnerships often include exclusivity windows: "no competing home decor brand partnerships
for 90 days." This atom reads the deal record, extracts the exclusivity clause (category, duration,
geographic scope), and compares it against every other active deal to surface conflicts before the
creator signs. Without this check, the creator risks breaching a prior exclusivity agreement — a
contract violation that damages both the brand relationship and the creator's reputation.

## When to invoke

- "Does this deal conflict with any of my other partnerships?"
- "Check exclusivity for the West Elm deal."
- "Can I take this HomeGoods deal while my Wayfair partnership is active?"
- "Scan my active deals for category conflicts."
- The deal-pipeline spoke calls this during deal advancement to contract-negotiating or signed stages.
- The deal-review workflow calls this as step 4 after usage-rights-check.

## Do NOT use for

- Usage rights auditing (content ownership, licensing duration, platform restrictions). Use
  `usage-rights-check`.
- Deal stage advancement or evidence gating. Use `deal-stage-advance`.
- Account health or renewal signals. Use `account-health` or `renewal-signal`.
- Rate negotiation or benchmark comparison. Use `rate-card-fill` or `benchmark-compare`.

## Inputs

```json
{
  "deal_id": "string — the deal record ID in pipeline/deals/",
  "scope": "category_only | full_scan"
}
```

- `deal_id`: required. The deal to check for exclusivity conflicts.
- `scope`: optional, defaults to `"category_only"`. When `"full_scan"`, also checks for geographic
  and temporal overlap even when categories do not match exactly (catches "home decor" vs.
  "furniture" fuzzy overlaps).

## Procedure

### Step 1: load the target deal

Read the deal record from `pipeline/deals/<deal_id>.json` (or the appropriate deal file).
Extract:
- `brand_name`
- `product_category` (e.g., "home decor," "paint," "furniture," "organization products")
- `exclusivity_clause` (object or null): `{ "category", "duration_days", "start_date",
  "end_date", "geographic_scope" }`
- `stage` (current deal stage)
- `deal_dates` (start, end, or expected timeline)

If the deal record does not exist or is malformed, return an error and stop.
If `exclusivity_clause` is null, note "no exclusivity clause in this deal" but still proceed to
check whether OTHER deals have exclusivity clauses that this deal might violate.

### Step 2: scan active deals

Read all deal records in `pipeline/deals/` where `stage` is one of: `in-discussion`,
`contract-negotiating`, `signed`, `in-production`, `delivered`, `invoiced` (any non-archived,
non-closed stage).

For each active deal (excluding the target deal):
- Extract its `exclusivity_clause`, `product_category`, `brand_name`, and date range.

### Step 3: detect conflicts

A conflict exists when:
1. Two deals share the same `product_category` (exact match or, in `full_scan` mode, fuzzy match
   on related categories).
2. Their date ranges overlap (any day where both deals are active).
3. At least one of the two deals has an `exclusivity_clause` covering that category.

For each conflict found, record:
- `conflicting_deal_id`
- `conflicting_brand_name`
- `conflict_category` (the overlapping category)
- `overlap_start` and `overlap_end` (the date range of the overlap)
- `exclusivity_source` (which deal's clause creates the conflict — `"target"`, `"other"`, or `"both"`)
- `severity`: `"hard"` if a signed deal has a binding exclusivity clause; `"soft"` if the deal is
  still in discussion and the clause is not yet binding.

### Step 4: emit output

Return the structured result. Set `human_review_required: true` if any conflicts are found.

## Output

```json
{
  "deal_id": "west-elm-2026-q4",
  "brand_name": "West Elm",
  "product_category": "home decor / furniture",
  "exclusivity_clause": {
    "category": "home furnishings",
    "duration_days": 90,
    "start_date": "2026-10-01",
    "end_date": "2026-12-30",
    "geographic_scope": "US"
  },
  "conflicts": [
    {
      "conflicting_deal_id": "wayfair-2026-fall",
      "conflicting_brand_name": "Wayfair",
      "conflict_category": "home furnishings",
      "overlap_start": "2026-10-01",
      "overlap_end": "2026-11-15",
      "exclusivity_source": "target",
      "severity": "hard"
    }
  ],
  "conflict_count": 1,
  "human_review_required": true,
  "recommendation": "The West Elm exclusivity clause (home furnishings, 90 days) overlaps with the active Wayfair deal by 46 days. Negotiate a narrower category scope or adjust timing before signing.",
  "retrieval_gaps": []
}
```

- `conflicts`: array of conflict objects. Empty if no conflicts detected.
- `conflict_count`: integer count of detected conflicts.
- `human_review_required`: always true when `conflict_count > 0`.
- `recommendation`: plain-English summary of the situation and suggested next step. One to two
  sentences.

## Engines and protocols loaded

- `shared/pipeline-engine.md` — deal schema, stage definitions, CRM read rules.
- `protocols/no-fabrication.md` — never invent deal terms, dates, or brand names.

## Failure modes

- **Deal record missing or malformed:** return `{ "error": "deal_not_found" }` and stop.
- **No active deals in pipeline:** return zero conflicts (no comparison possible).
- **Exclusivity clause fields partially null:** proceed with available fields; note missing fields
  in `retrieval_gaps` (e.g., "exclusivity end_date is null — cannot verify temporal overlap").
- **Fuzzy category matching (full_scan mode):** false positives possible. Label fuzzy matches
  with `"match_type": "fuzzy"` so the creator can judge relevance.

## Fabrication rules

Inherited from `protocols/no-fabrication.md`:
- Never invent deal terms, brand names, dates, or category labels. Read them from `pipeline/deals/`.
- If a field is null, report it as null — do not infer or guess.
- The `recommendation` field must be grounded in the actual conflict data, not hypothetical scenarios.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
