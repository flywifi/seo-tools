---
name: configure-stats-tool
atom: true
description: "Generates setup guidance for connecting a statistical MCP server to Creator OS. Detects the operating system, checks prerequisites, produces a Claude Desktop config block, and updates the connector registry flag. Do NOT use for running statistical tests (use hypothesis-test), regression (use regression-analysis), forecasting (use forecast), or querying data (use data-query)."
load:
  - shared/compute-engine.md
---

# configure-stats-tool

Guide the creator through connecting a statistical MCP server to Creator OS and produce the
configuration artifacts needed to enable it.

## Purpose

The statistical atoms (hypothesis-test, regression-analysis, forecast, ab-test, data-query) all
delegate computation to MCP tools. Before any of them can produce computed results, the tool must
be installed and registered. This atom handles that setup: it detects the creator's OS, checks
prerequisites (API keys, runtimes, packages), generates the Claude Desktop config block, and
updates the connector registry in `creator-os-config.local.json` so the compute-engine knows the
tool is available.

## When to invoke

- "How do I connect DuckDB to Creator OS?"
- "Set up Wolfram Alpha for my stats."
- "I want to use E2B for Python computation."
- "Enable the stats-compass tool."
- "Configure Jupyter notebook as a computation backend."
- "What do I need to run Monte Carlo simulations?"
- Invoke directly or from a spoke or atom that detects no computation tool is connected and
  wants to help the creator fix it.

## Do NOT use for

- Running statistical tests or analyses. Use `hypothesis-test`, `regression-analysis`, `forecast`,
  `ab-test`, or `data-query`.
- General MCP server configuration unrelated to statistical computation. Handle manually.
- Troubleshooting MCP connection errors after setup. Diagnose via Claude Desktop logs.

## Inputs

```json
{
  "tool": "wolfram_alpha | e2b_sandbox | duckdb_analytics | stats_compass | jupyter_notebook | r_statistics | monte_carlo | scikit_learn"
}
```

- `tool`: required. The MCP server the creator wants to connect. Must be one of the eight
  supported tools listed in `shared/compute-engine.md` Section 1.

## Procedure

### Step 1: identify the tool and its requirements

Map the requested `tool` to its prerequisites:

| Tool | Runtime | API key required | Package/binary |
|---|---|---|---|
| wolfram_alpha | Node.js 18+ | Yes (WOLFRAM_APP_ID) | @wolfram/mcp-server |
| e2b_sandbox | Node.js 18+ | Yes (E2B_API_KEY) | @e2b/mcp-server |
| duckdb_analytics | Python 3.10+ | No | duckdb, duckdb-mcp |
| stats_compass | Node.js 18+ | No | stats-compass-mcp |
| jupyter_notebook | Python 3.10+ | No | jupyter, jupyter-mcp |
| r_statistics | R 4.0+ | No | r-mcp-server |
| monte_carlo | Python 3.10+ | No | mcs-mcp |
| scikit_learn | Python 3.10+ | No | scikit-learn-mcp |

### Step 2: detect operating system and check prerequisites

Determine the creator's OS (macOS, Windows, Linux) to generate the correct config file path:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

For each prerequisite, provide a check command:
- Node.js: `node --version`
- Python: `python3 --version`
- R: `R --version`
- API key: instructions for obtaining the key from the provider's website.

### Step 3: generate Claude Desktop config block

Produce the JSON block to add to (or merge into) the creator's `claude_desktop_config.json`. The
block follows the Claude Desktop MCP server format:

```json
{
  "mcpServers": {
    "<tool_name>": {
      "command": "<runtime>",
      "args": ["<package-or-script>"],
      "env": {
        "API_KEY_NAME": "<placeholder>"
      }
    }
  }
}
```

- Use the correct command (`node`, `npx`, `python3`, `uvx`, `Rscript`) for the tool's runtime.
- Include environment variables only when an API key is required.
- Use placeholder values for API keys (e.g., `"your-wolfram-app-id-here"`).

### Step 4: update connector registry flag

Generate the update to `creator-os-config.local.json` that sets the tool's `enabled` flag to
`true`. This file is gitignored and deployment-specific per the project conventions.

The update targets the connector entry matching the tool name in
`shared/connectors/connectors.json`. Do not edit `connectors.json` directly — only update the
local config overlay.

### Step 5: verify and report

Provide the creator with:
1. The prerequisites checklist (what to install, what keys to obtain).
2. The config block to paste into Claude Desktop config.
3. The local config update to enable the connector.
4. A verification step: "Restart Claude Desktop, then ask me to run a simple test with [tool]."

## Output

```json
{
  "tool": "wolfram_alpha",
  "config_block": {
    "mcpServers": {
      "wolfram_alpha": {
        "command": "npx",
        "args": ["@wolfram/mcp-server"],
        "env": {
          "WOLFRAM_APP_ID": "your-wolfram-app-id-here"
        }
      }
    }
  },
  "env_vars_needed": ["WOLFRAM_APP_ID"],
  "prerequisites": [
    "Node.js 18+ installed (check: node --version)",
    "Wolfram Alpha API key (obtain from developer.wolframalpha.com)"
  ],
  "config_file_path": "~/Library/Application Support/Claude/claude_desktop_config.json",
  "local_config_update": {
    "connectors": {
      "wolfram_alpha": { "enabled": true }
    }
  },
  "flag_enabled": true,
  "verification_step": "Restart Claude Desktop, then ask: 'What is the integral of x^2?'",
  "retrieval_gaps": []
}
```

- `config_block`: the JSON to merge into the Claude Desktop config file.
- `env_vars_needed`: array of environment variable names the creator must set. Empty array if no
  API key is required.
- `prerequisites`: human-readable checklist of what must be installed or obtained.
- `config_file_path`: OS-specific path to the Claude Desktop config file.
- `local_config_update`: the JSON to merge into `creator-os-config.local.json`.
- `flag_enabled`: always `true` — this atom's purpose is to enable a tool.
- `verification_step`: a simple test the creator can run to confirm the tool works.
- `retrieval_gaps`: notes on anything that could not be determined (e.g., OS detection failed).

## Fabrication rules

- Never invent package names, API endpoint URLs, or config syntax. Use only verified MCP server
  package names and documented config formats.
- If the requested tool is not in the supported list, refuse and list the supported tools.
- Never set `flag_enabled` to `true` in committed files — only in `creator-os-config.local.json`
  which is gitignored.
