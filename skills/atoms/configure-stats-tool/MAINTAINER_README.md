---
file: skills/atoms/configure-stats-tool/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for configure-stats-tool so it stays stable under iteration.
---

# configure-stats-tool: Maintainer README

## Purpose

The configure-stats-tool atom guides the creator through connecting and configuring
statistical computation tools for Creator OS. It checks the current connector status
in `shared/connectors/connectors.json`, identifies which tools are available (stats-compass
MCP, E2B Python sandbox, R statistics, DuckDB), and provides step-by-step setup
instructions including a verification step for each tool. Its job ends at configuration
guidance -- it does not run computations (use hypothesis-test, regression-analysis,
forecast, or data-query) or manage non-stats connectors.

## Non-negotiable invariants

1. **Shared:** references the pipeline (`shared/method.md`); self-checks against
   `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
   `protocols/formatting-metadata.md`.
2. **No secrets in tracked files:** never write API keys, tokens, or secrets to any
   committed file. All credentials go in `creator-os-config.local.json` or
   `creator-os-connectors.local.json` (both gitignored).
3. **Connector registry read:** must check `shared/connectors/connectors.json` for
   current tool status before generating setup guidance. Never assume availability.
4. **Verification step required:** every setup instruction sequence must include a
   verification step that confirms the tool is reachable and functional.
5. **No fabricated status:** never fabricate tool availability or connection status.
   Report exactly what the connector registry shows.

## Known failure modes

1. Writing an API key or token to a tracked file (e.g., `connectors.json` or a
   skill config), exposing credentials in version control.
2. Claiming a tool is connected when the connector registry shows it is offline or
   not configured, misleading downstream atoms.
3. Providing setup steps for a deprecated tool version that no longer matches the
   current connector interface.
4. Skipping the verification step, leaving the creator with a tool that appears
   configured but cannot actually execute queries or computations.

## Regression cases to preserve

1. When no tools are connected, the atom produces a full setup guide listing all
   available options with verification steps for each.
   (eval: `configure-stats-no-tools`)
2. When one tool (e.g., stats-compass) is already connected, the atom returns a
   status summary for that tool and only provides setup steps for unconfigured
   tools. (eval: `configure-stats-partial`)
3. When the user provides an API key, the atom writes it exclusively to a
   `.local.json` file and never to `connectors.json` or any other tracked file.
   (eval: `configure-stats-credential-safety`)

## Update checklist

1. Edit the canonical source in `skills/atoms/configure-stats-tool/`.
2. Run evals: confirm all cases in `evals/evals.json` pass.
3. Verify that `shared/connectors/connectors.json` schema has not drifted from
   what the atom expects.
4. Confirm credential-write paths still target only gitignored `.local.json` files.
5. Update `STATE.md` if this change crosses a phase boundary.
6. Run `python3 tools/sync_check.py` -- must exit 0.
