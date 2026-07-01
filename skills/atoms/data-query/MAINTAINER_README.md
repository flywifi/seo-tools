---
file: skills/atoms/data-query/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for data-query so it stays stable under iteration.
---

# data-query: Maintainer README

## Purpose

The data-query atom translates natural-language analytics questions into DuckDB SQL,
executes queries over creator-supplied data files (CSV, Parquet, JSON exports from
YouTube Studio, Google Analytics, or manual spreadsheets), and returns structured
result sets with column metadata. Its job ends at query result delivery -- it does not
perform statistical tests (use hypothesis-test), fit models (use regression-analysis),
or forecast (use forecast).

## Non-negotiable invariants

1. **Shared:** references the pipeline (`shared/method.md`); self-checks against
   `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
   `protocols/formatting-metadata.md`.
2. **SQL preview required:** the generated SQL must be shown to the user before
   execution. Never run a query silently.
3. **No destructive SQL:** never execute DROP, DELETE, UPDATE, INSERT, ALTER, or
   TRUNCATE statements. Reject them with a `destructive_statement_blocked` error.
4. **Result metadata:** every query result must include `row_count` and
   `column_names` in the output metadata object.
5. **File path validation:** file paths must be validated for existence before the
   query is assembled. Return a clear error if the file is missing.
6. **Row cap:** results are capped at 1,000 rows. If the underlying result set
   exceeds that limit, include a `truncation_warning` in the output.
7. **No fabrication:** never fabricate query results, row values, or column names.
   If DuckDB is not connected, return the generated SQL as guidance only.

## Known failure modes

1. Executing destructive SQL without user confirmation because the statement was
   embedded inside a CTE or subquery that bypassed keyword scanning.
2. Attempting to query a nonexistent file path, producing a cryptic DuckDB error
   instead of a user-friendly message.
3. Returning fabricated result rows when DuckDB is not connected, rather than
   falling back to guidance-only mode with the raw SQL string.
4. Unbounded `SELECT *` on large files without a LIMIT clause, causing memory
   pressure or timeouts.

## Regression cases to preserve

1. A basic SELECT with GROUP BY on a CSV produces a correct result set with
   `row_count` and `column_names` in metadata. (eval: `data-query-basic-select`)
2. A query containing `DROP TABLE` is rejected with a
   `destructive_statement_blocked` error and no SQL is executed.
   (eval: `data-query-destructive-blocked`)
3. A result set exceeding 1,000 rows triggers `truncation_warning` and the
   returned rows are capped at 1,000. (eval: `data-query-truncation`)
4. When no DuckDB tool is connected, the atom returns guidance-only output
   containing the generated SQL string but no result set.
   (eval: `data-query-no-tool`)

## Update checklist

1. Edit the canonical source in `skills/atoms/data-query/`.
2. Run evals: confirm all cases in `evals/evals.json` pass.
3. Verify destructive-SQL keyword list covers any newly added SQL verbs.
4. Verify row cap and truncation logic if output schema changed.
5. Update `STATE.md` if this change crosses a phase boundary.
6. Run `python3 tools/sync_check.py` -- must exit 0.
