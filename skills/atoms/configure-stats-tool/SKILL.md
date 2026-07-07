---
name: configure-stats-tool
atom: true
description: "Guides the user through configuring a statistical analysis MCP server (Wolfram Alpha, E2B, stats-compass, DuckDB, Jupyter, R, Monte Carlo, or scikit-learn). Detects OS, checks prerequisites, generates Claude Desktop config block, and updates creator-os-config.local.json. Do NOT use to run statistical computations (use hypothesis-test, regression-analysis, forecast, or ab-test)."
load:
  - shared/compute-engine.md
  - protocols/no-fabrication.md
---

# configure-stats-tool

Walk the user through installing and configuring a statistical computation MCP server so that the
statistical atoms (hypothesis-test, regression-analysis, forecast, ab-test, data-query) can
delegate computation instead of producing guidance-only output.

## Purpose

Statistical atoms in Creator OS produce their best output when a computation MCP tool is connected.
Without one, they fall back to guidance-only mode — emitting runnable code instead of computed
results. This atom closes that gap by detecting the user's OS, checking prerequisites, generating
the correct Claude Desktop configuration block, and writing the enabled flag to
`creator-os-config.local.json` so the compute engine knows the tool is available.

## When to invoke

- "Set up Wolfram Alpha for my stats."
- "Configure DuckDB so I can query my CSV exports."
- "I want to run hypothesis tests — what do I need to install?"
- "Set up all the stats tools."
- "How do I connect E2B to Claude Desktop?"
- The hub or a statistical atom detects no computation tool is connected and suggests configuration.

## Do NOT use for

- Running statistical computations. Use `hypothesis-test`, `regression-analysis`, `forecast`,
  `ab-test`, or `data-query`.
- Configuring non-statistical MCP servers (e.g., Google Drive, GitHub). Use the relevant
  connector setup process.
- Editing `shared/connectors/connectors.json` directly — that file is the canonical registry.
  This atom writes only to `creator-os-config.local.json` (gitignored).

## Inputs

```json
{
  "tool": "wolfram_alpha | e2b_sandbox | duckdb_analytics | stats_compass | jupyter_notebook | r_statistics | monte_carlo | scikit_learn | all"
}
```

- `tool`: required. The tool to configure. Use `"all"` to configure every supported tool in
  sequence (the atom will skip tools whose prerequisites are not met and note them in output).

## Tool configurations

### wolfram_alpha
- Prerequisites: Wolfram Alpha API key (from developer.wolframalpha.com).
- Env vars: `WOLFRAM_APP_ID`.
- MCP server: `@anthropic/wolfram-alpha-mcp` (npm package).
- Config block:
  ```json
  {
    "mcpServers": {
      "wolfram-alpha": {
        "command": "npx",
        "args": ["-y", "@anthropic/wolfram-alpha-mcp"],
        "env": { "WOLFRAM_APP_ID": "<your_app_id>" }
      }
    }
  }
  ```

### e2b_sandbox
- Prerequisites: E2B API key (from e2b.dev), Node.js 18+.
- Env vars: `E2B_API_KEY`.
- MCP server: `@e2b/mcp-server` (npm package).
- Pre-installed packages in sandbox: numpy, scipy, statsmodels, scikit-learn, pandas, matplotlib.

### duckdb_analytics
- Prerequisites: DuckDB CLI or Python duckdb package.
- Env vars: none.
- MCP server: `@anthropic/duckdb-mcp` or community `duckdb-mcp-server`.
- Config note: point the server at the creator's data directory for automatic file discovery.

### stats_compass
- Prerequisites: Node.js 18+.
- Env vars: none.
- MCP server: `stats-compass-mcp` (npm package).
- Supports: t-test, chi-square, ANOVA, Mann-Whitney U, proportion test, correlation, descriptive
  statistics.

### jupyter_notebook
- Prerequisites: Python 3.10+, jupyter, ipykernel.
- Env vars: none.
- MCP server: `jupyter-mcp-server`.
- Config note: the Jupyter server must be running before Claude Desktop connects.

### r_statistics
- Prerequisites: R 4.0+, Rscript on PATH.
- Env vars: none.
- MCP server: `r-mcp-server`.
- Pre-installed R packages recommended: stats (built-in), car, effectsize, ggplot2.

### monte_carlo
- Prerequisites: Node.js 18+ or Python 3.10+.
- Env vars: none.
- MCP server: `mcs-mcp` (Monte Carlo Simulator MCP).

### scikit_learn
- Prerequisites: Python 3.10+, scikit-learn.
- Env vars: none.
- MCP server: `sklearn-mcp-server`.

## Procedure

### Step 1: detect OS

Determine the user's operating system (macOS, Windows, Linux) to provide the correct Claude Desktop
config file path:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

### Step 2: check prerequisites

For the requested tool, verify:
- Required runtime is installed (Node.js, Python, R).
- Required package manager is available (npm, pip).
- Required API key is obtainable (provide the signup URL, do not ask the user to paste keys into
  chat — instruct them to set env vars).

If prerequisites are not met, list what is missing and provide installation commands.

### Step 3: emit config JSON block

Generate the Claude Desktop config block for the tool. Present it as a JSON snippet the user can
merge into their existing `claude_desktop_config.json`.

### Step 4: emit env var instructions

If the tool requires environment variables (API keys):
- Provide platform-specific instructions for setting them (export on macOS/Linux, setx on Windows).
- Remind the user not to commit API keys to the repo.

### Step 5: write flag to local config

Write the tool's enabled flag to `creator-os-config.local.json`:
```json
{
  "compute_tools": {
    "<tool_name>": { "enabled": true, "configured_at": "ISO timestamp" }
  }
}
```

This file is gitignored. The compute engine reads it to determine tool availability.

### Step 6: suggest verification

Provide a verification step the user can run to confirm the tool is working:
- Wolfram Alpha: "Ask Claude to compute 'integral of x^2 from 0 to 1' — it should return 1/3."
- E2B: "Ask Claude to run 'print(2+2)' in a sandbox — it should return 4."
- DuckDB: "Ask Claude to query a small CSV file — it should return results."
- stats-compass: "Ask Claude to run a t-test on two small arrays — it should return a p-value."
- Jupyter: "Ask Claude to create a notebook cell with 'import pandas as pd; print(pd.__version__)'"
- R: "Ask Claude to run 'summary(lm(mpg ~ wt, data = mtcars))' — it should return coefficients."
- Monte Carlo: "Ask Claude to simulate 1000 coin flips — it should return approximately 500 heads."
- scikit-learn: "Ask Claude to fit a KMeans(n_clusters=2) on a small dataset — it should return
  cluster labels."

## Output

```json
{
  "tool": "wolfram_alpha",
  "config_block": {
    "mcpServers": {
      "wolfram-alpha": {
        "command": "npx",
        "args": ["-y", "@anthropic/wolfram-alpha-mcp"],
        "env": { "WOLFRAM_APP_ID": "<your_app_id>" }
      }
    }
  },
  "env_vars_needed": {
    "WOLFRAM_APP_ID": "Wolfram Alpha App ID from developer.wolframalpha.com"
  },
  "prerequisites": ["Node.js 18+", "Wolfram Alpha API key"],
  "prerequisites_met": true,
  "config_file_path": "~/Library/Application Support/Claude/claude_desktop_config.json",
  "flag_enabled": true,
  "verification_prompt": "Ask Claude to compute 'integral of x^2 from 0 to 1'",
  "retrieval_gaps": []
}
```

- `config_block`: ready-to-merge JSON for Claude Desktop config.
- `env_vars_needed`: map of environment variable name to description. Empty object if none needed.
- `prerequisites`: list of required software and keys.
- `prerequisites_met`: true if all prerequisites were detected, false if any are missing.
- `flag_enabled`: true if the flag was written to `creator-os-config.local.json`.
- `verification_prompt`: a test prompt the user can try to confirm the tool works.

## Cross-modality
Inherits its calling spoke's class (the calling spoke's class); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
