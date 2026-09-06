---
file: skills/seasonal-trends/SKILL.md
name: seasonal-trends
description: "builds a seasonal content strategy for a defined window by mapping topics to pillars, checking trend momentum, and scheduling them; does NOT generate production packages or scripts."
load: always
---

# seasonal-trends

## Purpose

Builds a seasonal content strategy for a defined planning window in the moody/vintage home decor and DIY niche. The skill maps topic seeds to the four recurring seasonal peaks that drive audience engagement for this channel:

- Seasonal decor: September to October
- Holiday tablescapes: November to December
- Spring refresh: March to April
- Summer outdoor: May to June

For each peak, the skill clusters ideas around content pillars, verifies trend momentum via web intelligence, assigns personas, and produces a publish schedule. Output is a structured plan ready for downstream production skills, not a finished production package.

## Inputs

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| season_or_window | string | yes | none | e.g. "fall 2026" or "November to December" |
| topic_seeds | list of strings | no | none | Optional starting ideas; if omitted, the skill derives seeds from the seasonal window |
| pillar_focus | list of strings | no | all 5 pillars | Restricts output to named pillars only |
| idea_count | integer | no | 5 | Target number of ideas in the output cluster |

## Primary outputs

Returns a `seasonal_plan` object with the following structure:

```
seasonal_plan
  window               string    the resolved season label (e.g. "Fall 2026")
  peak_dates           string    the canonical date range for the window (e.g. "September to October 2026")
  idea_cluster         list
    working_title      string    draft title for the idea
    pillar             string    one of the 5 content pillars
    persona_served     string    primary audience persona from audience-engine
    seasonal_urgency   string    "high" | "medium" | "low" based on proximity to peak
    trend_status       object    output from trend-check atom (momentum, direction, source citations)
    publish_schedule   object    output from calendar-slot atom (recommended publish date, slot rationale)
  retrieval_gaps       list      topics where web-intel returned no usable signal; flagged, not fabricated
  quality_gate_result  object    pass/fail result from govern-artifact with any blocking issues listed
```

All fields with no retrievable data are set to null and surfaced in `retrieval_gaps`. No metric, rate, or trend claim is fabricated (see `protocols/no-fabrication.md`).

## Atoms composed

Atoms are invoked in the order listed. `trend-check` is conditional and runs once per idea.

1. **seasonal-map** -- resolves `season_or_window` to canonical peak dates and retrieves the matching seasonal aesthetic profile from `canonical-sources/seasonal-aesthetic/seasonal.json`
2. **idea-generate** -- expands `topic_seeds` (or derives seeds from the seasonal profile) into a candidate idea list sized to `idea_count`
3. **trend-check** *(per idea, conditional)* -- queries web intelligence for each candidate idea; marks momentum direction; cites sources; sets `trend_status`; skips if web-intel returns no signal and logs to `retrieval_gaps`
4. **keyword-cluster** -- attaches keyword groups to each idea using platform-engine keyword norms and any trend-check signal
5. **calendar-slot** -- assigns a recommended publish date and rationale for each idea within the resolved peak window
6. **govern-artifact** -- runs the Quality Gates protocol against the assembled plan and populates `quality_gate_result`

## Engines required

- `shared/platform-engine.md` -- pillar definitions, keyword norms, platform publishing constraints
- `shared/web-intel-engine.md` -- trend signal retrieval, source citation rules, null-and-flag behavior

## References

- `canonical-sources/seasonal-aesthetic/seasonal.json` -- authoritative seasonal window dates and aesthetic profile data
- `protocols/research-citation.md` -- citation formatting rules for all trend and source claims
- `protocols/no-fabrication.md` -- null-and-flag requirement; no trend data, metric, or date may be invented
- `protocols/quality-gates.md` -- gate criteria that `govern-artifact` enforces before the plan is released

## Do NOT use for

- Generating scripts, hooks, B-roll lists, or production packages -- use `video-development` for that
- SEO keyword strategy or keyword research as a standalone deliverable -- use `seo-keywords`
- Competitor research or gap analysis -- use `competitor-analysis`
- Content outside the moody/vintage home decor and DIY niche -- this skill's seasonal windows, aesthetic profiles, and persona assumptions are niche-specific and will produce invalid output for other niches
- Producing a plan that bypasses the Quality Gates -- `govern-artifact` is non-optional; a plan that does not pass the gate is not released

## Cross-modality
Class: B.
Runs on: Claude Desktop/Code (native); claude.ai via a hosted remote-MCP connector; Custom GPT via an Action and the Gemini API via function calling when the data endpoint is wired; Gems: knowledge-only (data may be stale unless supplied).
Mechanism: Reasoning over canonical-sources/seasonal-aesthetic/seasonal.json (seasonal-map) and scoop-cache keyword/persona data via cache_query (keyword-cluster, idea-generate), with live web retrieval through shared/web-intel-engine.md for trend-check; calendar-slot and govern-artifact are model reasoning against protocols/quality-gates.md — no tools/*.py compute module runs.
Fallback: Off a runtime, supply seasonal.json and the relevant scoop-cache slices as knowledge; skip live trend-check, set trend_status to null with the topic logged in retrieval_gaps, and flag as_of on all seasonal data. Never fabricate a trend. On ChatGPT this runs knowledge-only from the pasted pack; the desktop app can reach live data via a deployed remote MCP connector in developer mode (implementation/gpt/mcp-connector/README.md).
See `shared/cross-modality-engine.md`.
