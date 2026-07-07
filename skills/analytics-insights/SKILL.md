---
file: skills/analytics-insights/SKILL.md
name: analytics-insights
description: "analyzes the creator's channel and post metrics, compares them to industry benchmarks, and surfaces prioritized recommendations; does NOT fabricate data and returns a gap-record if no analytics data is provided."
load: always
---

# analytics-insights

## Purpose

Reads provided analytics data (exported CSV, screenshot, or structured object) for the creator's YouTube, Instagram, TikTok, or Pinterest presence. Performs benchmark comparison against canonical rate benchmarks. Returns a prioritized insights report with data-quality flags.

If no analytics data is provided or the data is insufficient for meaningful analysis, this skill invokes the `gap-record` atom and returns a structured gap record instead of fabricating or estimating values. No metrics, rates, or benchmarks are invented; all comparisons draw from `canonical-sources/rate-benchmarks/benchmarks.json`.

## Inputs

| Field | Type | Required | Notes |
|---|---|---|---|
| `analytics_source` | object, file_path (CSV or screenshot), or null | yes | Pass null to trigger gap_record mode |
| `platform` | string: youtube, instagram, tiktok, pinterest, or all | yes | Scopes benchmark lookup and metric set |
| `time_period` | string | no | Example: "last 90 days". Defaults to whatever the source covers |
| `comparison_metrics` | list of strings | no | Defaults: ctr, avd, engagement_rate, subscribers |

## Primary outputs

Returns an `insights_report` object with the following fields:

- `metrics_analyzed` (list): the metrics successfully extracted from the analytics source
- `benchmark_comparisons` (list): per-metric comparison produced by the `benchmark-compare` atom, drawn from `canonical-sources/rate-benchmarks/benchmarks.json`
- `top_performers` (list): videos or posts with the highest metric values in the analyzed window
- `underperformers` (list): videos or posts that fall below benchmark thresholds
- `recommendations` (list): prioritized action items, each with a rationale field; ordered by estimated impact
- `data_quality` (string enum): real | estimated | partial
- `retrieval_gaps` (list): fields that could not be extracted or were absent from the source
- `quality_gate_result` (object): output of the `govern-artifact` atom; includes pass/fail and any blocking findings

## Atoms composed

| Atom | When invoked |
|---|---|
| `ingest-route` | Parses an uploaded CSV or screenshot into a structured analytics object |
| `benchmark-compare` | Compares extracted metrics against benchmarks from canonical-sources |
| `roi-metric` | Invoked when the content being analyzed is linked to a deal in the pipeline |
| `gap-record` | Invoked when `analytics_source` is null or data is too sparse to analyze |
| `govern-artifact` | Always invoked last; enforces Quality Gates before the report is returned |

## Engines required

- `shared/platform-engine.md`: platform-specific metric definitions, normal ranges, and posting norms
- `shared/audience-engine.md`: audience segment context used when interpreting engagement signals

## References

- `canonical-sources/rate-benchmarks/benchmarks.json`: authoritative benchmark values for all supported platforms
- `protocols/no-fabrication.md`: prohibits inventing any metric, rate, or benchmark value
- `protocols/research-citation.md`: governs how benchmark sources are attributed in the report
- `protocols/quality-gates.md`: defines pass/fail criteria applied by `govern-artifact`

## Do NOT use for

- Fabricating analytics data when none is provided. Use the `gap-record` atom instead and return an honest gap record.
- Generating content recommendations that are not grounded in the provided analytics data.
- Accessing live platform APIs directly. If fresh data is needed from a live source, route through `shared/web-intel-engine.md` Level 1 fetch; this skill does not call platform APIs itself.
- Producing a final deliverable that has not passed the Quality Gates enforced by `govern-artifact`.

## Cross-modality
Class: C.
Runs on: Claude Desktop/Code (native, MCP + the tool module); claude.ai via a hosted remote-MCP connector; Custom GPT / Gemini only when the tool is hosted behind a remote MCP or an Action; Gems: no.
Mechanism: Local compute via composed atoms: ingest-route (shared/docintel CSV/screenshot parsing), benchmark-compare (canonical-sources/rate-benchmarks), roi-metric (CPM/CPC/effective-hourly money math), then the shared govern-artifact gate (score.py); no dedicated analytics MCP tool.
Fallback: Off a runtime, the user must supply already-structured metrics (no CSV/screenshot parsing) and benchmark/ROI degrade to reasoning over cached benchmarks; flag unverified; never fabricate a computed metric.
See `shared/cross-modality-engine.md`.