# ADR 0081 — The drift guard keeps em dashes out of the local tools' creator-facing text

- Status: accepted
- Date: 2026-10-11
- Phase: P102

## Context

`protocols/formatting-metadata.md` forbids em dashes in user-facing output. Drift invariant 4
checked the committed `examples/` content alone, so the wizard's pages, the setup and update
output, the MCP server's tool descriptions and replies, the dashboard and the two settings files
whose strings those show (`creator-os-config.json`, `shared/connectors/connectors.json`) carried
76 em dashes, written as the character or as `&mdash;`, and the programs and scripts those reach
carried 5 more. Push 4d of P102 replaced them; a guard keeps new ones out.

## Decision

Drift invariant 62 (`sync_check.check_creator_text_dashes`
<!-- verify: tools/sync_check.py::check_creator_text_dashes -->) reads a scan set derived from the
tree (`_creator_text_scan`), not a list of files:

1. Pages: modules under `tools/` with a top-level class deriving from a `*RequestHandler`, and the
   files of a `static/` folder beside one.
2. MCP replies: modules under `tools/` with top-level functions decorated `<server>.tool`; their
   docstrings are the tool descriptions a client shows, so they are read.
3. Programs: the `.py` files a page or MCP module builds a path to from `ROOT` or `HERE` (what it
   runs and shows the output of).
4. Commands: the `tools/<x>.py` files a page or MCP literal names (what it tells the creator to
   run).
5. Data: the `.json` files a page or MCP module builds a path to, and the `.json` files a program
   builds from its own folder.

Python files are read for their string literals as written in the source, outside docstrings
(tool descriptions aside) and test code. The character and its HTML entities (`&mdash;`,
`&#8212;`, `&#x2014;`) count. An em dash a program uses as data, a detector constant or a
placeholder some exports write for "no value", is written as the escape `\u2014`, which the guard
reads as data. Docstrings, comments, test code, escapes and `.local.` files are the cuts; each is a
case in the self-proof that runs before the scan. `_CREATOR_TEXT_FLOOR` lists the places the
formatting rule names for the local tools, and the build fails when the derived set no longer
reaches one.

## Consequences

- A new page server, MCP tool, program a page runs, or command a page names is scanned without
  anyone listing it.
- The derived set reaches more than the places first named: the drift guard's own messages (the
  `drift_check` tool returns them), the connector resolver's plan text, and the scripts the pages
  name, such as `profile_mirror.py` and `update_check.py`.
- Limits: a program reached through a path built another way (a variable, `os.path.join`) and a
  second hop (a program that a program runs) are not followed, and a Markdown page the wizard
  reads is not scanned.
- Maintainer text (docstrings, comments, internal docs) keeps its em dashes.
