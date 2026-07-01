# Content Pipeline Workflow

## Purpose
Multi-step content production from initial research through quality review.

## Steps

1. **Research** -- seo-researcher agent runs keyword-cluster and search-intent
   atoms to identify the target topic, primary keyword, and supporting long-tails.
2. **Keyword analysis** -- seo-keywords spoke expands the cluster, checks SERP
   features, and produces the keyword brief.
3. **Script draft** -- content-writer agent invokes hook-write, script-section,
   and title-generate atoms to produce the first draft.
4. **Quality review** -- quality-review spoke scores the draft against the
   quality-gates rubric. Any failing dimension triggers a revision loop back
   to step 3 (maximum 2 revision cycles).

## Agents and atoms used
- seo-researcher agent: keyword-cluster, search-intent, long-tail-expand
- content-writer agent: hook-write, script-section, title-generate, caption-write
- quality-review spoke: govern-artifact atom

## Expected output
A scored script draft with keyword brief, hook variants, title options, and a
quality-gate pass/fail result. All outputs honor formatting-metadata (no em
dashes in user-facing text, ranges with "to").
