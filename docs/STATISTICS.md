# Statistical Analysis Tools

Creator OS supports 8 statistical computation engines, each individually toggleable via
`creator-os-config.json` capability flags. All are optional — when none is connected, statistical
atoms produce guidance-only output with runnable Python or R code the user can execute locally.

---

## Available tools

| Tool | Flag | Transport | API key? | Best for |
|---|---|---|---|---|
| Wolfram Alpha | `wolfram_alpha` | `uvx mcp-wolfram-alpha` | Yes (free, 2000/month) | Exact symbolic math, unit conversion, distribution lookups |
| E2B Code Interpreter | `e2b_sandbox` | `npx @e2b/mcp-server` | Yes (free tier) | Sandboxed Python with scipy, numpy, pandas, matplotlib |
| stats-compass | `stats_compass` | `python3 -m stats_compass_mcp` | No | 50+ pandas-based tests: t-test, ANOVA, chi-square, correlation |
| DuckDB | `duckdb_analytics` | `npx @motherduckdb/mcp-server-motherduck` | No (local) | Analytical SQL over CSV, Parquet, JSON files |
| Jupyter Notebook | `jupyter_notebook` | `python3 -m jupyter_mcp_server` | No | Persistent notebook sessions with full scientific stack |
| R Statistics (rmcp) | `r_statistics` | rmcp | No (R required) | 52 R statistical tools for advanced modeling |
| Monte Carlo (MCS-MCP) | `monte_carlo` | MCS-MCP | No | Probabilistic modeling, risk analysis, revenue forecasting |
| scikit-learn | `scikit_learn` | mcp-server-scikit-learn | No | ML classification, regression, clustering |

---

## Quick setup

Use the `configure-stats-tool` atom to set up any tool:

> "Set up Wolfram Alpha for me."

The atom detects your OS, checks prerequisites, generates the exact Claude Desktop config JSON,
and enables the flag in `creator-os-config.local.json`. You can also use the `configure_tool`
MCP tool directly to toggle flags.

Or set up manually:

1. Install the tool (see the `requires` field in `creator-os-config.json`).
2. Add the MCP server block from `implementation/claude/desktop/claude_desktop_config_snippet.json`
   to your Claude Desktop config.
3. Set the env var if required (e.g., `WOLFRAM_APP_ID`, `E2B_API_KEY`).
4. Enable the flag: edit `creator-os-config.local.json` or use the `configure_tool` MCP tool.
5. Restart Claude Desktop.

---

## Tool selection matrix

When multiple tools are connected, `shared/compute-engine.md` selects the best one per task:

| Task | Preferred tool | Fallback chain |
|---|---|---|
| Exact arithmetic, unit conversion | Wolfram Alpha | E2B Python |
| Hypothesis tests (t-test, ANOVA) | stats-compass | E2B scipy.stats, R statistics |
| Regression, time-series | E2B sandbox, Jupyter | R statistics |
| Large dataset SQL queries | DuckDB | E2B pandas |
| Monte Carlo simulation | MCS-MCP | E2B numpy.random |
| ML classification / clustering | scikit-learn MCP | E2B scikit-learn |
| Multi-step stateful analysis | Jupyter notebook | E2B (per-turn) |

---

## Atoms

| Atom | What it does |
|---|---|
| `hypothesis-test` | t-test, chi-square, ANOVA, Mann-Whitney, proportion test |
| `regression-analysis` | Linear, multiple, logistic regression |
| `forecast` | Time-series forecasting with confidence intervals |
| `ab-test` | A/B test design (sample size, power) and analysis (winner, effect size) |
| `data-query` | SQL queries over CSV/Parquet/JSON via DuckDB |
| `configure-stats-tool` | Setup guidance for any statistical MCP server |

All atoms route through the `analytics-compute` spoke, which the hub dispatches to when it
classifies a request as `statistical_analysis`, `forecasting`, `data_query`, or `ab_test_design`.

---

## Output labeling

Every statistical output is labeled with its computation source:

- `[computed via wolfram_alpha]` — result from a connected engine
- `[estimated — verify with computation tool]` — Claude's own arithmetic (use with caution)
- `[guidance-only — no computation engine connected]` — describes the test and provides
  runnable code, but does not compute a result

---

## Checking what is connected

Use the `get_stats_tools` MCP tool to see which tools are enabled:

> "Which stats tools do I have?"

Or from the command line:

```bash
python3 shared/connectors/connectors.py --plan | grep -E "wolfram|e2b|stats|duckdb|jupyter|monte|scikit"
```
