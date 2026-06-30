---
file: skills/audience-research/SKILL.md
name: audience-research
description: research and profile Alex Slason's target audience by mapping comments, engagement patterns, and platform signals to the five-persona model; surfaces audience insights to inform content strategy. Content lane spoke.
load: always
---

# audience-research

Content lane spoke that transforms raw audience signals (comments, analytics exports, platform data)
into a verified persona profile and actionable audience insights for Alexandra Slason's
moody-vintage home decor and DIY channel.

## Purpose

audience-research answers the question: "Who is actually watching, engaging, and converting, and
what do they need?" It does not generate content. It does not guess at demographics or fabricate
engagement figures. It maps only what is present in the provided data or confirmed through flagged
live retrieval, records every gap explicitly, and produces a profile that downstream spokes
(content-strategy, seo-keywords, video-development) can consume to target the right persona at the
right moment.

The five canonical personas this spoke maps against:

| Persona | Core identity |
|---|---|
| Renter | Small-space, budget-constrained renter; no permanent changes allowed |
| Vintage Hunter | Thrift and antique seeker; wants sourcing strategy and authenticity |
| Organizer | System-seeker; loves checklists, labeled zones, and declutter workflows |
| Holiday Maximalist | Seasonal decor enthusiast; wants moody impact without looking cheap |
| New Homeowner | First home, overwhelmed, modest budget, builder-basic starting point |

Persona definitions are authoritative in `shared/audience-engine.md`. This spoke reads them from
there and never redefines them inline.

All retrieval follows `shared/web-intel-engine.md` acquisition levels. Any field that cannot be
confirmed by provided data or live retrieval is recorded via gap-record and flagged, never filled
with an estimate or invented figure, per `protocols/no-fabrication.md`.

## Inputs

```json
{
  "data_source": {
    "type": "comments_export | analytics_export | platform_url | paste",
    "file_path": "absolute local path (if type is comments_export or analytics_export)",
    "source": {
      "provider": "youtube | instagram | tiktok | pinterest",
      "identifier": "URL or content ID (if type is platform_url)"
    },
    "raw_text": "pasted comment block or analytics snippet (if type is paste)"
  },
  "analysis_scope": {
    "persona_targets": ["Renter", "Vintage Hunter", "Organizer", "Holiday Maximalist", "New Homeowner"],
    "time_window": "string -- e.g. last 90 days; null if not available",
    "content_sample": "string -- video title or topic the data is drawn from (optional)"
  }
}
```

- `data_source`: at least one of `file_path`, `source`, or `raw_text` must be provided. If none
  is provided, the spoke records a gap and returns a `needs_more_info` prompt.
- `persona_targets`: defaults to all five personas if omitted. Restrict to a subset to narrow the
  mapping pass.
- `time_window`: used to assess data freshness. If the export predates the freshness window in
  `protocols/research-citation.md`, results are labeled stale rather than suppressed.
- `content_sample`: helps persona-map weight the mapping. Omit when the analysis is channel-wide.

## Primary outputs

```json
{
  "skill": "audience-research",
  "data_source_summary": {
    "type": "string",
    "record_count": 0,
    "time_window": "string or null",
    "injection_scan_result": "CLEAN | REVIEW | QUARANTINE | BLOCK",
    "ingestion_status": "content_ingested | metadata_only | quarantined | send_back"
  },
  "persona_profile": {
    "Renter": {
      "signal_volume": "integer -- count of comments or data points mapped to this persona",
      "engagement_signals": ["verbatim themes or patterns drawn from the provided data; no invented text"],
      "confidence": "high | medium | low",
      "confidence_note": "string or null -- explains any factor that reduced confidence"
    },
    "Vintage Hunter": { "signal_volume": 0, "engagement_signals": [], "confidence": "low", "confidence_note": null },
    "Organizer": { "signal_volume": 0, "engagement_signals": [], "confidence": "low", "confidence_note": null },
    "Holiday Maximalist": { "signal_volume": 0, "engagement_signals": [], "confidence": "low", "confidence_note": null },
    "New Homeowner": { "signal_volume": 0, "engagement_signals": [], "confidence": "low", "confidence_note": null }
  },
  "dominant_persona": "string -- persona with highest signal volume and confidence",
  "underserved_personas": ["personas with low signal volume relative to their share in shared/audience-engine.md"],
  "top_themes": [
    {
      "theme": "string -- pattern or recurring question from the data",
      "persona_fit": ["Renter", "..."],
      "frequency": "integer -- approximate count; labeled [estimated] if not exact",
      "content_opportunity": "string -- specific video angle or format this theme suggests"
    }
  ],
  "platform_signals": {
    "provider": "youtube | instagram | tiktok | pinterest | null",
    "engagement_patterns": ["string -- observed patterns from analytics data; null if not available"],
    "freshness": "string -- data date range or 'stale' if outside research-citation window"
  },
  "retrieval_gaps": [
    {
      "tool": "gap-record",
      "gap_type": "string",
      "description": "string",
      "impact": "string",
      "recommended_next_step": "string"
    }
  ],
  "fabrication_flags": ["any field that could not be confirmed and is marked [unverified]"],
  "source_artifacts": [],
  "human_review_required": true
}
```

Key output guarantees:

- `engagement_signals` contains only themes or patterns drawn from the provided data. No comment
  text is invented, paraphrased beyond recognition, or presented as a direct quote unless it appears
  verbatim in the source. Per `protocols/no-fabrication.md`, invented audience statements are a
  hard-fail violation.
- `signal_volume` counts are exact where the data allows and labeled `[estimated]` where the
  ingested record reports approximate counts.
- `confidence` is set to `low` whenever the underlying signal volume is fewer than 10 data points
  for a persona, or the ingestion status is `metadata_only`.
- `human_review_required` is always `true`. govern-artifact must pass before any audience profile
  is used in a published planning artifact.

## Atoms composed

1. ingest-route: ingests comments exports, analytics exports, or platform URLs; runs inject-scan;
   returns a structured ingestion record. Called first for every non-paste data source.
2. web-acquire (via `shared/web-intel-engine.md`): used when a platform URL is provided or when
   the ingestion record's routing hint indicates live retrieval is needed to supplement thin data.
   Acquisition level starts at Level 2 and falls through per the web-intel escalation rules.
3. persona-map: maps ingested content and observed themes to the five-persona model; returns primary
   and secondary personas per topic cluster surfaced in the data.
4. gap-record: called for every field or retrieval path that returns no usable data. Produces an
   explicit gap object rather than a silent blank.
5. govern-artifact: gates the completed audience profile through quality-review before it is
   returned to the user or a downstream spoke.

## Engines required

- `shared/audience-engine.md`: authoritative five-persona definitions; persona signal thresholds;
  engagement pattern taxonomy.
- `shared/web-intel-engine.md`: acquisition-level escalation rules; freshness windows; retrieval
  gap handling.

## References

- `shared/audience-engine.md`
- `shared/web-intel-engine.md`
- `protocols/no-fabrication.md`
- `protocols/research-citation.md`
- `protocols/quality-gates.md`

## Do NOT use for

- Generating content ideas, hooks, titles, or scripts. Use content-strategy or video-development.
- Fabricating or estimating comment sentiment, demographic breakdowns, or engagement figures when
  no source data is provided. Null and record a gap instead.
- Competitor audience research. This spoke profiles Alex's own audience only. Use
  competitor-analysis for competitor channel profiling.
- Producing final editorial decisions. Outputs are research inputs requiring human review before
  any publishing action.
- Any audience outside Alexandra Slason's moody-vintage home decor and DIY channel. These persona
  definitions and signal thresholds are calibrated for that specific niche and creator.
