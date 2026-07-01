# Competitor Deep-Dive Workflow

## Purpose
Comprehensive competitive analysis from initial scan through gap identification.

## Steps

1. **Snapshot fetch** -- competitor-analyst agent runs competitor-scan atom to
   pull the target channel's public metadata (titles, descriptions, upload
   cadence, subscriber range).
2. **Metadata extraction** -- deep-competitor-scan atom extracts content pillars,
   keyword patterns, posting schedule, and format mix from the snapshot.
3. **Entity mapping** -- entity-extract atom identifies brand partners, product
   categories, and recurring topics across the competitor's recent content.
4. **Gap analysis** -- keyword-compare and benchmark-compare atoms surface
   keyword gaps, content format gaps, and audience overlap opportunities.

## Agents and atoms used
- competitor-analyst agent: competitor-scan, deep-competitor-scan, entity-extract,
  keyword-compare, benchmark-compare, gap-record
- seo-researcher agent (optional): keyword-cluster for cross-referencing gaps

## Expected output
Structured JSON report containing: competitor profile, content pillar map,
entity list, keyword gap table, and actionable opportunity list. All competitor
metrics marked [unverified] unless sourced from a confirmed API response.
