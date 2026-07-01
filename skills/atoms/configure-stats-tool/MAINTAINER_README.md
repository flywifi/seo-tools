# configure-stats-tool — Maintainer Reference

## What this atom does

Guides the user through configuring a statistical MCP server for Creator OS. Detects OS, checks
prerequisites, generates a Claude Desktop config JSON block, emits environment variable instructions,
writes an enabled flag to `creator-os-config.local.json`, and suggests a verification prompt.
Supports 8 tools: Wolfram Alpha, E2B, DuckDB, stats-compass, Jupyter, R, Monte Carlo, scikit-learn.

## Invariants

1. This atom **never writes to `shared/connectors/connectors.json`**. It writes only to
   `creator-os-config.local.json` (gitignored). The canonical connector registry is maintained
   separately.
2. The atom never asks the user to paste API keys into the chat. It instructs them to set
   environment variables instead.
3. Config blocks are always valid JSON that can be merged into Claude Desktop config without
   modification (except for placeholder values like `<your_app_id>`).

## Failure modes

1. **Prerequisites not met.** Node.js, Python, or R not installed. The atom lists what is missing
   and provides installation commands — it does not skip silently.
2. **Unknown tool name.** If the user requests a tool not in the supported list, the atom returns
   an error with the list of supported tools.
3. **`all` mode with partial prerequisites.** The atom configures tools whose prerequisites are
   met and lists skipped tools with reasons.

## Regression cases (map to evals/evals.json)

| # | Case | Eval ID |
|---|---|---|
| 1 | Configure wolfram_alpha on macOS | cst-001 |
| 2 | Configure duckdb_analytics — no API key needed | cst-002 |
| 3 | Configure all tools — partial prerequisites | cst-003 |

## Update checklist

1. If a new MCP server package is released or renamed, update the relevant tool configuration
   section in SKILL.md.
2. If Claude Desktop config file paths change, update Step 1.
3. If `creator-os-config.local.json` schema changes, update Step 5.
4. Re-run all evals after any change.
5. Run `python3 tools/sync_check.py`.
