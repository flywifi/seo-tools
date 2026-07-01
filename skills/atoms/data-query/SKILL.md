---
name: data-query
atom: true
description: "Executes SQL queries over local CSV, Parquet, and JSON files via DuckDB to answer creator data questions — top-performing videos, engagement breakdowns, revenue summaries. Returns structured result sets with provenance. Do NOT use for statistical testing (use hypothesis-test), regression modeling (use regression-analysis), or time-series forecasting (use forecast)."
load:
  - shared/compute-engine.md
  - protocols/no-fabrication.md
---

# data-query

Execute a SQL query over local data files (CSV, Parquet, JSON) using DuckDB and return a structured
result set with column names, rows, row count, and computation provenance.

## Purpose

The creator exports data from YouTube Studio, affiliate dashboards, and sponsorship trackers as
CSV or JSON files. This atom lets the creator ask plain-language data questions — "What are my top
10 videos by watch time?" or "Total revenue by month this year" — translates those into SQL, and
executes them against the local files via DuckDB. When DuckDB is not connected, it produces the
SQL and guidance for the creator to run it themselves.

## When to invoke

- "What are my top 10 videos by views?"
- "Show me engagement rate by content pillar."
- "Total revenue by month for 2026."
- "How many videos did I publish each quarter?"
- "Filter my data to only Shorts with over 10K views."
- "Join my YouTube export with my sponsorship tracker."
- Invoke directly or from a spoke that needs to query structured creator data.

## Do NOT use for

- Statistical hypothesis testing — comparing groups for significance. Use `hypothesis-test`.
- Regression modeling — fitting relationships between variables. Use `regression-analysis`.
- Time-series forecasting — projecting future metrics. Use `forecast`.
- A/B test design or analysis. Use `ab-test`.
- Querying external APIs or live platform data. Use web-intel or platform-specific spokes.

## Inputs

```json
{
  "query_description": "string — plain-language description of what the creator wants to know",
  "data_files": [
    {
      "path": "string — relative or absolute path to the data file",
      "format": "csv | parquet | json",
      "alias": "string — table alias for SQL (e.g., 'videos', 'revenue')"
    }
  ],
  "sql": "optional string — explicit SQL query if the creator provides one"
}
```

- `query_description`: required. Plain-language description of the data question. Used to generate
  SQL if `sql` is not provided.
- `data_files`: required. Array of one or more data file references. Each entry needs:
  - `path`: path to the file on the creator's local system.
  - `format`: the file format — `csv`, `parquet`, or `json`.
  - `alias`: the table name to use in the SQL query.
- `sql`: optional. If the creator provides an explicit SQL query, use it directly (after
  validation). If omitted, generate SQL from `query_description`.

## Procedure

### Step 1: validate inputs and inspect data files

Confirm that `data_files` is non-empty and each entry has `path`, `format`, and `alias`.

If DuckDB is connected, run a schema inspection query on each file to discover column names and
types:
```sql
DESCRIBE SELECT * FROM read_csv_auto('path/to/file.csv');
```
Use the discovered schema to validate or generate the SQL query.

If DuckDB is not connected, ask the creator to describe the columns or infer from the
`query_description`.

### Step 2: generate or validate SQL

If `sql` is provided:
- Parse and validate syntax.
- Confirm all referenced table aliases match entries in `data_files`.
- Check for dangerous operations (DROP, DELETE, UPDATE, INSERT) — refuse and explain that this
  atom is read-only.

If `sql` is not provided:
- Translate `query_description` into a DuckDB-compatible SQL query.
- Use `read_csv_auto()`, `read_parquet()`, or `read_json_auto()` functions matching each file's
  format.
- Prefer explicit column names over `SELECT *` when the schema is known.
- Add `LIMIT 1000` if the query has no explicit limit to prevent unbounded result sets.

### Step 3: check compute-engine tool selection

Read `shared/compute-engine.md` Section 1 to identify the preferred tool for SQL queries:
DuckDB analytics (preferred), E2B Python with pandas (alternative).

Check connector availability. Set `computation_source` based on which tool is connected.

### Step 4: execute query

If DuckDB is connected:
- Execute the SQL query against the data files.
- Capture column names, all result rows, and the total row count.
- Set `computation_source` to `"duckdb"`.

If DuckDB is not connected but E2B Python is available:
- Generate equivalent pandas code: `pd.read_csv()` plus pandas query operations.
- Execute via E2B and capture the result.
- Set `computation_source` to `"e2b"`.

### Step 5: fallback to guidance-only if no tool

If no computation tool is connected (Level 4 in compute-engine fallback chain):
- Set `computation_source` to `"guidance_only"`.
- Emit the generated SQL query and instructions for running it locally with DuckDB CLI or Python.
- Set `rows` to null and `row_count` to null.
- Label the output `[guidance-only — no computation engine connected]`.

### Step 6: format and return

Present results in a structured format. If the result set has more than 20 rows, summarize in the
interpretation and include the full data in the `rows` array. Never truncate without noting it.

## Output

```json
{
  "columns": ["video_title", "views", "watch_time_hours"],
  "rows": [
    ["DIY Vintage Mirror Restoration", 45200, 312.5],
    ["Moody Kitchen Makeover", 38100, 287.3]
  ],
  "row_count": 2,
  "sql_executed": "SELECT title AS video_title, views, watch_time_hours FROM read_csv_auto('videos.csv') ORDER BY views DESC LIMIT 10",
  "computation_source": "duckdb | e2b | guidance_only",
  "interpretation": "plain-language summary of the result anchored to the creator's question",
  "data_files_used": ["videos.csv"],
  "retrieval_gaps": []
}
```

- `columns`: array of column names in the result set.
- `rows`: array of row arrays. Null when `computation_source` is `guidance_only`.
- `row_count`: number of rows returned. Null when `computation_source` is `guidance_only`.
- `sql_executed`: the exact SQL that was run (or would be run in guidance-only mode).
- `computation_source`: provenance label per `shared/compute-engine.md`.
- `interpretation`: plain-language summary of results. Always present even in guidance-only mode
  (describes what the query will return).
- `data_files_used`: list of file paths that were queried.
- `retrieval_gaps`: notes on anything that could not be queried or verified.

## Fabrication rules

Inherited from `protocols/no-fabrication.md` and `shared/compute-engine.md` Section 4:
- Never invent query results, row counts, or aggregated values.
- If no computation tool is connected, produce guidance-only output — never guess what the data
  contains.
- This atom is strictly read-only. Never generate SQL that modifies data.
- If the creator's question cannot be answered from the provided data files, say so and describe
  what additional data would be needed.
