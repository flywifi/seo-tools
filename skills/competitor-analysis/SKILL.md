---
file: skills/competitor-analysis/SKILL.md
name: competitor-analysis
description: "researches competitors in the moody/vintage home decor and DIY niche, surfaces content gaps and differentiation angles, and produces a gap report; does NOT fabricate competitor data."
load: always
---

# competitor-analysis

## Purpose

Delivers competitive intelligence to support content positioning for the creator's moody-vintage
home decor and DIY channel. The skill scans publicly visible content across specified platforms,
clusters observed content angles, identifies overserved and underserved topics, and returns a
structured gap report.

This skill never fabricates competitor metrics. When subscriber counts, view figures, or engagement
rates cannot be confirmed through live retrieval, each affected field is marked `[unverified]` and
a manual-check recommendation is appended. Confidence is reported honestly at the report level as
`high`, `medium`, or `low` based on retrieval coverage.

## Inputs

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `topic` | string | yes | none | Seed keyword or content topic to anchor the scan |
| `platforms` | list of strings | no | `[youtube, pinterest, tiktok]` | Platforms to scan; any combination of `youtube`, `pinterest`, `tiktok`, `instagram` |
| `competitor_count` | integer | no | `5` | Target number of distinct competitor channels or accounts to surface |
| `include_keyword_gaps` | boolean | no | `true` | When true, runs keyword-cluster and gap-record atoms to produce `keyword_gaps` |

## Primary outputs

Returns a single `competitive_report` object with the following fields:

```
competitive_report:
  competitors_found:          # list; each entry below
    - name: string
      url_if_found: string    # omit if not retrieved; do not guess
      scale_tier: string      # "micro", "mid", or "large"; mark [unverified] if not confirmed
      content_angle: string   # observed dominant angle (e.g. "dark academia styling on a budget")
      note: string            # append "[unverified]" where any field is not confirmed by retrieval
  overserved_topics: list     # topics with dense, high-volume competitor coverage
  underserved_topics: list    # topics with thin or low-quality competitor coverage
  keyword_gaps: list          # present only when include_keyword_gaps is true
  differentiation_summary: string  # 3 to 5 sentence positioning recommendation grounded in gaps
  confidence: enum            # "high" | "medium" | "low"
  retrieval_gaps: list        # platforms or competitors where retrieval returned no usable data
  quality_gate_result: object # pass/fail + any flags from protocols/quality-gates.md
```

Confidence levels:
- `high`: retrieval succeeded on all requested platforms and at least `competitor_count` accounts
  were found with enough observable content to characterize angles.
- `medium`: one platform returned sparse results or fewer than `competitor_count` accounts were
  confirmed.
- `low`: two or more platforms returned no usable data or fewer than half the target competitor
  count was confirmed.

## Atoms composed

The following atoms are orchestrated in sequence. `trend-check` is conditional.

1. **competitor-scan** (per_platform) -- runs once per platform in `platforms`; collects publicly
   visible channel or account data and recent content titles.
2. **keyword-cluster** -- groups observed content titles into topic clusters; required before
   gap-record.
3. **search-intent** -- classifies cluster intents (informational, inspirational, transactional)
   to sharpen differentiation angles.
4. **trend-check** (conditional) -- runs only when `topic` matches a seasonal or trending
   signal in shared/platform-engine.md; appends trend context to underserved topics.
5. **gap-record** -- compares clusters against the creator's existing content footprint and outputs
   `overserved_topics`, `underserved_topics`, and `keyword_gaps`.
6. **govern-artifact** -- validates the assembled report against protocols/quality-gates.md and
   sets `quality_gate_result`.

## Engines required

- `shared/web-intel-engine.md` -- governs all retrieval operations: recency windows, source
  credibility tiers, null-and-flag behavior when data is unavailable.
- `shared/platform-engine.md` -- supplies platform-specific content norms, format constraints,
  and seasonal aesthetic signals used by competitor-scan and trend-check.
- `shared/seo-intelligence-engine.md` -- entity SEO rules and entity keyword seed list;
  topical authority model used to frame gap analysis in terms of cluster architecture.

## References

- `protocols/no-fabrication.md` -- binding. Competitor subscriber counts, view figures, and
  engagement rates must never be invented. Mark `[unverified]` and recommend manual check.
- `protocols/research-citation.md` -- recency window for home decor content: 6 to 18 months.
  Competitor content older than 18 months may be included for angle mapping but must be flagged
  as potentially stale.
- `shared/web-intel-engine.md` -- retrieval and confidence rules.
- `shared/seo-intelligence-engine.md` -- entity SEO and topical authority model.
- `protocols/quality-gates.md` -- governs `quality_gate_result`; report is not releasable until
  govern-artifact returns pass.

## Do NOT use for

- Fabricating competitor subscriber counts or view figures. If retrieval does not return a
  confirmed figure, mark the field `[unverified]` and include a recommendation to check manually
  via YouTube Studio, Social Blade, or the platform's public page.
- Analyzing paid advertising strategies or sponsored content performance. This skill covers only
  organic, publicly visible content.
- Accessing competitor private analytics, backend dashboards, or any data that is not publicly
  viewable without authentication.
- General web research outside the moody-vintage home decor and DIY niche. Use
  `shared/web-intel-engine.md` directly for broad research tasks.
- Producing final editorial decisions. The gap report informs content strategy; it does not
  replace the creator's judgment.
