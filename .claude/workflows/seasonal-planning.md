# Seasonal Planning Workflow

## Purpose
Build a seasonal content calendar aligned to trend data and keyword opportunities.

## Steps

1. **Trend check** -- seo-researcher agent runs trend-check atom against the
   target season or time window to identify rising topics and search interest
   patterns in the home decor and DIY niche.
2. **Keyword expansion** -- long-tail-expand and keyword-cluster atoms broaden
   the trend signals into publishable keyword targets with volume estimates.
3. **Calendar slot** -- content-strategy spoke maps keywords to calendar dates,
   respecting lead times (typically 2 to 4 weeks before peak search volume).
4. **Hub-and-cluster mapping** -- topical-authority-map atom groups the calendar
   entries into hub pages and supporting cluster posts for SEO authority building.

## Agents and atoms used
- seo-researcher agent: trend-check, long-tail-expand, keyword-cluster,
  topical-authority-map
- content-strategy spoke: calendar planning logic

## Expected output
A dated content calendar (JSON or table) with: topic, primary keyword, cluster
keywords, recommended publish date, content format, and hub-or-cluster role.
All trend data cited per research-citation protocol.
