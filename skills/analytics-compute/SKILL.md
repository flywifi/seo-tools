---
name: analytics-compute
description: "Performs computational statistical analysis on creator data using connected MCP tools: hypothesis testing, regression modeling, time-series forecasting, and A/B test analysis. Routes to the appropriate statistical atom based on the analysis type requested. Do NOT use for benchmark comparisons without computation (use analytics-insights). Do NOT use when no statistical MCP tool is connected -- this spoke requires at least one stats tool and will emit a gap-record if none is available."
load:
  - shared/compute-engine.md
  - shared/seo-intelligence-engine.md
  - shared/platform-engine.md
  - protocols/no-fabrication.md
  - protocols/quality-gates.md
---

# analytics-compute

## Purpose
Perform real statistical computation on creator data -- hypothesis tests, regressions, forecasts,
and A/B test evaluations -- by routing to the correct statistical atom and executing against a
connected MCP stats tool. This spoke does not summarize or interpret dashboards; it computes.

## When to invoke

Use this spoke when the user asks for quantitative analysis that requires statistical computation.
Example prompts:

- "Is there a significant difference in watch time between my tutorials and hauls?"
- "Predict my subscriber growth for the next 6 months."
- "Design a thumbnail A/B test for my next video."
- "Query my analytics CSV and run a regression on views vs. publish time."
- "Which content pillar drives the most engagement -- run the numbers."

Implicit signals: the user provides a data file (CSV, JSON, export), references hypothesis testing,
regression, correlation, forecasting, or A/B testing, or asks "is the difference real?"

## Do NOT use for
- Dashboard interpretation or metric summaries without computation -- use `analytics-insights`.
- Benchmark comparisons that rely on industry data rather than the creator's own stats -- use
  `analytics-insights`.
- Audience persona mapping -- use `audience-research`.
- SEO keyword analysis -- use `seo-keywords`.
- Competitor metric comparisons -- use `competitor-analysis`.

## Engines required
| Engine | Why |
|---|---|
| `shared/compute-engine.md` | Statistical method selection, test parameters, output schema |
| `shared/seo-intelligence-engine.md` | Metric definitions, keyword performance context |
| `shared/platform-engine.md` | Platform-specific metric semantics and thresholds |

## Protocols enforced
- `protocols/no-fabrication.md` -- never invent statistical results; if computation fails, emit a
  gap-record with the reason.
- `protocols/quality-gates.md` -- every output artifact passes the rubric before release.

## Workflow overview
The spoke composes atoms via `workflow.json`:

1. **data-query** -- ingest and validate the data source (CSV, JSON, or connected analytics API).
   Runs only when `data_files_provided` is true.
2. **hypothesis-test** -- run the appropriate statistical test (t-test, chi-square, ANOVA) when the
   user asks whether a difference is significant. Condition: `comparison_requested`.
3. **regression-analysis** -- fit a regression model (linear, logistic, or polynomial) when the user
   asks about relationships between variables. Condition: `relationship_requested`.
4. **forecast** -- produce a time-series forecast (ARIMA, exponential smoothing, or linear
   projection) when the user asks about future performance. Condition: `forecast_requested`.
5. **ab-test** -- design or evaluate an A/B test (sample size, power analysis, significance check).
   Condition: `ab_test_requested`.
6. **govern-artifact** -- run the quality gate rubric on the final output.

The `shortcut_atoms` list also includes `configure-stats-tool` for MCP tool setup.

## Atoms used
| Atom | Purpose |
|---|---|
| `data-query` | Data ingestion, validation, and querying |
| `hypothesis-test` | Statistical significance testing |
| `regression-analysis` | Regression model fitting and interpretation |
| `forecast` | Time-series forecasting |
| `ab-test` | A/B test design and evaluation |
| `configure-stats-tool` | Connect or reconfigure the MCP stats tool |
| `govern-artifact` | Quality gate scoring |

## Standalone usability
When invoked without a downstream consumer, this spoke returns a structured JSON result containing
the statistical output, confidence intervals, p-values or forecast ranges, and a plain-language
interpretation suitable for the creator.

## Failure modes
- **No MCP stats tool connected**: emits a gap-record with `tool_missing: true` and instructions
  for connecting a supported stats tool. Does not attempt to fabricate results.
- **Insufficient data**: if the provided dataset has fewer rows than the minimum required for the
  requested test (e.g., fewer than 30 observations for a t-test), the spoke emits a
  `sample_size_warning` and downgrades to a descriptive summary.
- **Ambiguous analysis type**: if the request does not clearly map to one atom, the spoke returns a
  clarifying question listing the available analysis types.
- **Computation error**: if the stats tool returns an error, the spoke surfaces the raw error,
  does not retry silently, and flags the output as `computation_failed`.

## Cross-modality
Class: C.
Runs on: Claude Desktop/Code (native, MCP + the tool module); claude.ai via a hosted remote-MCP connector; Custom GPT / Gemini only when the tool is hosted behind a remote MCP or an Action; Gems: no.
Mechanism: Delegates the statistics to a connected external compute MCP (E2B/scipy, Wolfram, DuckDB, R, ...) per shared/compute-engine.md; ships no tools/*.py of its own (mcp_server.py exposes only get_stats_tools discovery + configure_tool).
Fallback: No compute MCP connected -> emit guidance-only output (the test/formula/assumptions + runnable Python/R) labelled computation_source=guidance_only; never use model arithmetic for tests/regression/forecasting, never fabricate a result.
See `shared/cross-modality-engine.md`.