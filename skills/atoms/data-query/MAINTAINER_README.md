# data-query — Maintainer Reference

## What this atom does

Runs analytical SQL queries over the creator's local data files (CSV, Parquet, JSON, XLSX) via
DuckDB MCP. Generates SQL from natural-language questions, infers schema, executes read-only
queries, and returns structured columnar results. Falls back to emitting the SQL for local
execution when DuckDB is not connected.

## Invariants

1. data-query is **read-only**. It never generates or executes INSERT, UPDATE, DELETE, DROP, or
   CREATE statements. User-supplied SQL is validated for write operations before execution.
2. `rows` is empty (not populated with example data) when `computation_source` is `guidance_only`.
   Never fabricate result rows.
3. `sql_executed` always reflects the actual SQL — whether executed or emitted for local use.
   It is never simplified or idealized.

## Failure modes

1. **Invalid file path.** The file does not exist or is not a supported format. Noted in
   `retrieval_gaps`; the atom proceeds with remaining valid files.
2. **DuckDB not connected.** Guidance-only output: SQL is emitted, rows are empty. The user can
   run the SQL locally.
3. **Large result set.** If row_count > 100, results are truncated to 100 rows with the total
   count noted in `retrieval_gaps`.

## Regression cases (map to evals/evals.json)

| # | Case | Eval ID |
|---|---|---|
| 1 | Natural-language query generates valid SQL | dq-001 |
| 2 | DuckDB not connected — guidance-only SQL | dq-002 |
| 3 | Write operation in user SQL rejected | dq-003 |

## Update checklist

1. If DuckDB MCP server API changes, update Step 4 execution logic in SKILL.md.
2. If new file formats are supported, update Step 1 validation.
3. Re-run all evals after any change.
4. Run `python3 tools/sync_check.py`.
