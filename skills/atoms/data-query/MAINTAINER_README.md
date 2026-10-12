# data-query — Maintainer Reference

## What this atom does

Runs analytical SQL queries over the creator's local data files (CSV, Parquet, JSON, XLSX) via
DuckDB MCP. Generates SQL from natural-language questions, infers schema, executes read-only
queries, and returns structured columnar results. Falls back to emitting the SQL for local
execution when DuckDB is not connected.

The DuckDB connection Creator OS sets up (`skills/atoms/configure-stats-tool/SKILL.md`) is an
in-memory database started with `--read-write`, because the server refuses an in-memory database
without it. That connection accepts writes, and a `COPY ... TO` statement writes a file on the
computer. The read-only rule below is this atom's own check, not the server's.

## Invariants

1. data-query is **read-only** by its own check: its instructions refuse SQL containing INSERT,
   UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, MERGE, COPY, EXPORT, IMPORT, ATTACH, INSTALL,
   LOAD, SET, PRAGMA or CALL (COPY, EXPORT, ATTACH, INSTALL, LOAD and the logging settings are
   among the statements that write files or fetch extensions); eval dq-003 covers DROP. User-
   supplied SQL is validated before execution. A first read of an `.xlsx` file still installs
   DuckDB's excel extension, which this statement list does not catch, since that read is a
   plain SELECT.
2. `rows` is empty (not populated with example data) when `computation_source` is `guidance_only`.
   Never fabricate result rows.
3. `sql_executed` always reflects the actual SQL — whether executed or emitted for local use.
   It is never simplified or idealized.

## Failure modes

1. **Invalid file path.** The file does not exist, is not a supported format, or is named by a
   bare file name or a relative path. Noted in `retrieval_gaps`; for a path that is not
   absolute the atom asks the creator for the absolute path. The atom proceeds with the
   remaining valid files.
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
| 4 | Bare file name: asks for the absolute path | dq-004 |

## Update checklist

1. If DuckDB MCP server API changes, update Step 4 execution logic in SKILL.md.
2. If new file formats are supported, update Step 1 validation.
3. Re-run all evals after any change.
4. Run `python3 tools/sync_check.py`.
