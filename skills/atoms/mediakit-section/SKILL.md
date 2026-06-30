---
file: skills/atoms/mediakit-section/SKILL.md
name: mediakit-section
description: >
  Write one section of Alexandra Slason's brand partnership media kit in published-to-audience,
  brand-facing voice. Sections available: channel_overview, audience_demo, content_pillars,
  partnership_formats, case_study, rates_summary. Uses real channel data when supplied; falls back
  to clearly labeled industry benchmark ranges from canonical-sources/rate-benchmarks/benchmarks.json,
  or marks fields as placeholders when neither is available. Do NOT use for full media kit assembly
  (use a spoke that sequences this atom), email outreach copy, or any CRM record write.
load: on_demand
---

# mediakit-section

Write one section of Alex Slason's brand partnership media kit.

## Purpose

Produce a single, self-contained media kit section that brands and agencies can read directly.
Each section is professional, confident, and accurate. If real channel data is not provided, the
atom surfaces benchmark ranges from `canonical-sources/rate-benchmarks/benchmarks.json` with
explicit source labeling, or emits null fields with `placeholders_to_fill` entries rather than
inventing any figure.

Voice follows the published-to-audience mode defined in `shared/brand-engine.md`: warm but
professional, confident, brand-facing. Content pillars, aesthetic description, and channel identity
come from `shared/brand-engine.md`. No fabrication under any circumstance; see
`protocols/no-fabrication.md`.

## Inputs

```json
{
  "section_name": "channel_overview | audience_demo | content_pillars | partnership_formats | case_study | rates_summary",
  "channel_data": {
    "subscribers": "integer or null",
    "avg_views_per_video": "integer or null",
    "engagement_rate_pct": "number or null",
    "avg_monthly_views": "integer or null",
    "top_demographics": "object or null",
    "recent_case_study": "object or null"
  },
  "brand_name": "string or null (used for personalization where appropriate)"
}
```

- `channel_data` is optional. Any field within it may be null; the atom will flag missing fields.
- `brand_name` is optional. When provided, personalizes partnership_formats and rates_summary
  sections with the brand name. When null, sections use generic brand-facing language.

## Output

```json
{
  "tool": "mediakit-section",
  "section_name": "the section_name echo",
  "section_title": "display heading for the section",
  "section_body": "markdown-formatted section body ready to paste into the media kit document",
  "data_source": "real | benchmark | placeholder | mixed",
  "benchmark_label": "string describing the benchmark source and tier if data_source is benchmark or mixed, else null",
  "placeholders_to_fill": [
    "list of field names or inline placeholder tokens that require real data before publishing"
  ],
  "fabrication_check": "PASS if no data was invented; FLAG:<reason> if the atom had to omit or null a requested field"
}
```

### data_source values

| Value | Meaning |
|---|---|
| `real` | All figures come from `channel_data` supplied by the user. |
| `benchmark` | No real figures supplied; all metrics use labeled industry benchmark ranges from `canonical-sources/rate-benchmarks/benchmarks.json`. |
| `placeholder` | No real figures and no applicable benchmark; fields are marked `[needs real data]` and listed in `placeholders_to_fill`. |
| `mixed` | Some fields from real data, some from benchmarks, some placeholders. |

### Section guidance

**channel_overview**
Introduce Alex, her channel, its aesthetic (moody, vintage, collected-over-time), and her primary
content niche (moody vintage home decor and DIY). Draw identity language from `shared/brand-engine.md`.
Subscriber count and average views are real data only; emit null and flag if not supplied.

**audience_demo**
Describe the core audience. Pull any real demographic data from `channel_data.top_demographics`.
Planning assumptions in `shared/audience-engine.md` may be referenced as niche-typical context only;
they must be labeled as planning assumptions, never as Alex's measured data.

**content_pillars**
List the five content pillars from `shared/brand-engine.md` with brief descriptions contextualizing
each for a brand reader. No invented performance data attached to pillars.

**partnership_formats**
Describe available collaboration formats (dedicated video, integrated mention, short-form, haul
feature, seasonal spotlight). Personalize with `brand_name` when provided. Do not attach rate
figures here; rates belong in rates_summary.

**case_study**
Populate from `channel_data.recent_case_study` when present. When absent, emit a structured
placeholder block with all required fields in `placeholders_to_fill` and set `data_source` to
`placeholder`. Do not invent a brand, campaign outcome, or performance figure.

**rates_summary**
Emit real rates only if the user supplies them via `channel_data`. If no real rates are supplied,
present industry benchmark ranges from `canonical-sources/rate-benchmarks/benchmarks.json` with
explicit labeling:
- Source: Creator OS handoff market-analysis reference; verify against current data before quoting.
- Tier labeled as the subscriber tier the range applies to (e.g., 50K to 100K subscribers).
Include a note that final rates are quoted individually based on deliverable scope and brand fit.

## Do NOT use for

- Assembling a complete multi-section media kit document (use a spoke that sequences this atom
  across all sections).
- Writing brand outreach or pitch emails.
- Writing or updating CRM account or deal records in `pipeline/`.
- Any section that requires inventing subscriber counts, engagement rates, CPMs, audience
  demographics, brand names, or case study outcomes. If real data is absent and no benchmark
  applies, emit null and flag rather than filling the gap.
- Producing final publishable output without human review of all `placeholders_to_fill` fields.

## References

- `shared/brand-engine.md` -- channel identity, aesthetic, content pillars, voice (published mode)
- `shared/audience-engine.md` -- planning-assumption audience profile (label as niche-typical, not
  Alex's measured data)
- `protocols/no-fabrication.md` -- hard rule; no invented figures under any circumstance
- `canonical-sources/rate-benchmarks/benchmarks.json` -- industry benchmark ranges (benchmark tier
  only, always labeled)
