---
name: data-query
atom: true
description: "Runs analytical SQL queries over local data files (CSV exports from YouTube Studio, Google Analytics, spreadsheets) via DuckDB MCP. Do NOT use for live API queries (use platform APIs) or keyword cache lookups (use cache_query MCP tool)."
load:
  - shared/compute-engine.md
  - protocols/no-fabrication.md
---

# data-query

Run analytical SQL queries over the creator's local data files — YouTube Studio CSV exports, Google
Analytics exports, spreadsheets, or any tabular file — using DuckDB MCP. Returns structured
columnar results ready for downstream atoms (hypothesis-test, regression-analysis, forecast) or
direct creator review.

## Purpose

The creator exports data from YouTube Studio, Google Analytics, and spreadsheets regularly. This
atom turns natural-language questions into SQL, executes the query via DuckDB, and returns clean
results. It handles file discovery, schema inference, and query generation so the creator does not
need to write SQL. When DuckDB is not connected, it emits the SQL for the user to run locally.

## When to invoke

- "What are my top 10 videos by watch time this quarter?"
- "Show me average CTR by content pillar."
- "How many Shorts did I publish each month?"
- "Sum my revenue by month for the last year."
- "Which videos have more than 10K views but less than 5% CTR?"
- "Join my YouTube data with my Google Analytics export."
- Invoke directly or from a spoke that needs filtered or aggregated data before analysis.

## Do NOT use for

- Live API queries — fetching current data from YouTube, Instagram, or Pinterest APIs. Use the
  platform's API connector or relevant spoke.
- Keyword cache lookups — querying the scoop cache. Use the `cache_query` MCP tool directly.
- Statistical testing — analyzing the data after querying. Use `hypothesis-test`, `regression-analysis`,
  or `forecast` on the query results.
- Data visualization — creating charts. Downstream spokes or tools handle charting from
  data-query output.

## Inputs

```json
{
  "query_description": "string — natural-language description of what the user wants to know",
  "data_files": ["path/to/file1.csv", "path/to/file2.csv"],
  "sql": "string | null"
}
```

- `query_description`: required. The user's question in plain language. Used to generate SQL if
  `sql` is null, and always included in the output for traceability.
- `data_files`: required. One or more paths to local data files (CSV, TSV, Parquet, JSON, or
  Excel). DuckDB reads these directly. If a path is invalid, report it in `retrieval_gaps`.
- `sql`: optional. If provided, execute this SQL directly (after safety validation). If null,
  generate SQL from `query_description` and the inferred schema.

## Procedure

### Step 1: validate data files

For each path in `data_files`:
- Check that the file exists and is a supported format (CSV, TSV, Parquet, JSON, XLSX).
- If a file does not exist or is unsupported, note it in `retrieval_gaps` and proceed with the
  remaining files.
- If no valid files remain, return an error with `retrieval_gaps` explaining the issue.

### Step 2: infer schema

If DuckDB is connected:
- Use DuckDB's `DESCRIBE SELECT * FROM read_csv_auto('path')` to infer column names and types.
- Present the schema to the query generator.

If DuckDB is not connected:
- Read the first 5 rows of each CSV to infer column names and approximate types.
- Note that type inference is approximate in `retrieval_gaps`.

### Step 3: generate or validate SQL

If `sql` is null:
- Generate a DuckDB-compatible SQL query from `query_description` and the inferred schema.
- Use `read_csv_auto('path')` for CSV files, `read_parquet('path')` for Parquet, etc.
- Prefer explicit column names over `SELECT *` for clarity.

If `sql` is provided:
- Validate that the SQL does not contain write operations (INSERT, UPDATE, DELETE, DROP, CREATE).
  data-query is read-only.
- Validate that file paths in the SQL match `data_files`.

### Step 4: execute query

If DuckDB MCP is connected:
- Execute the SQL query via DuckDB.
- Capture column names, row data, and row count.
- Set `computation_source` to `"duckdb"`.

If DuckDB is not connected:
- Set `computation_source` to `"guidance_only"`.
- Emit the generated SQL as `sql_executed` so the user can run it locally with DuckDB CLI
  (`duckdb < query.sql`) or Python (`import duckdb; duckdb.sql("...")`).
- Set `rows` to an empty array and `row_count` to 0.
- Note in `retrieval_gaps`: "DuckDB MCP not connected. SQL provided for local execution."

### Step 5: format output

Structure the result as a clean columnar response. If `row_count` exceeds 100, return the first
100 rows and note the truncation in `retrieval_gaps` with the total count.

## Output

```json
{
  "query_description": "top 10 videos by watch time this quarter",
  "columns": ["video_title", "watch_time_hours", "views", "ctr"],
  "rows": [
    ["DIY Dark Moody Bathroom", 142.5, 28400, 0.072],
    ["Thrift Flip: Vintage Dresser", 98.3, 19200, 0.065]
  ],
  "row_count": 10,
  "sql_executed": "SELECT video_title, watch_time_hours, views, ctr FROM read_csv_auto('youtube_export.csv') WHERE upload_date >= '2026-04-01' ORDER BY watch_time_hours DESC LIMIT 10",
  "schema": {
    "video_title": "VARCHAR",
    "watch_time_hours": "DOUBLE",
    "views": "INTEGER",
    "ctr": "DOUBLE"
  },
  "computation_source": "duckdb | guidance_only",
  "retrieval_gaps": []
}
```

- `columns`: array of column names in the result set.
- `rows`: array of arrays, each inner array is one row matching the column order.
- `row_count`: total rows returned (or total rows available if truncated).
- `sql_executed`: the SQL that was run (or would be run in guidance-only mode). Always included
  for transparency and reproducibility.
- `schema`: inferred schema of the source data (column names and types).
- `computation_source`: `"duckdb"` when the query was executed, `"guidance_only"` when SQL was
  generated but not run.

## Fabrication rules

Inherited from `protocols/no-fabrication.md`:
- Never invent query results. Every row in `rows` must come from actual query execution.
- In guidance-only mode, `rows` is empty — never populate it with example or placeholder data.
- Never fabricate a schema. If schema inference fails, set `schema` to null and note it in
  `retrieval_gaps`.
- The `sql_executed` field must reflect the actual SQL, not a simplified or idealized version.
