# ADR 0081 — The drift guard keeps em dashes out of the local tools' creator-facing text

- Status: accepted
- Date: 2026-10-11
- Phase: P102

## Context

`protocols/formatting-metadata.md` forbids em dashes in user-facing output. Drift invariant 4
checked the committed `examples/` content alone, so the wizard's pages, the setup and update
output, the MCP server's tool descriptions and replies, the dashboard and the two settings files
whose strings those show (`creator-os-config.json`, `shared/connectors/connectors.json`) carried
76 em dashes, written as the character or as `&mdash;`, the programs and scripts those reach
carried 5 more, the paste-in instructions the wizard shows in its copy boxes (the claude.ai
system prompt and both versions of the ChatGPT custom instructions) carried 8, and six more tools
carried 13 (help text, a privacy report, block advice and a detector constant, now written as the
escape). Push 4d of P102 replaced them; a guard keeps new ones out.

## Decision

Drift invariant 62 (`sync_check.check_creator_text_dashes`
<!-- verify: tools/sync_check.py::check_creator_text_dashes -->) reads a scan set derived from the
tree (`_creator_text_scan`), not a list of files:

1. Pages: modules under `tools/` with a top-level class whose base is written as a name ending in
   `RequestHandler` (`BaseHTTPRequestHandler`, `http.server.BaseHTTPRequestHandler`), and the
   files of a `static/` folder beside one, at any depth.
2. MCP replies: modules under `tools/` with top-level functions decorated `<server>.tool` or
   `<server>.tool(...)`; their docstrings are the tool descriptions a client shows, so they are
   read.
3. Programs: the `.py` files a page or MCP module builds a path to from `ROOT` or `HERE` (what it
   runs and shows the output of), and the local modules it imports (`import a.b`,
   `from a.b import c`, found under `tools/` or the repository root), whose text it shows.
4. Commands: the `tools/<x>.py` files a page or MCP literal names (what it tells the creator to
   run).
5. Data: the `.json` files a page or MCP module builds a path to, and the `.json` files a program
   or a command builds from its own folder.
6. Text: the other files a page or MCP module reads into what it shows: `read_text()` on a path it
   builds from `ROOT` or `HERE`, and the `.md` and `.txt` files named in another tools module's
   literal table that it reads (`surface_budgets.BOX_FILES`, the custom instructions the wizard
   shows). A file it only copies, such as the knowledge files the wizard stages for upload, is not
   read.

Python files are read for their string literals as written in the source, outside docstrings and
test code. Two docstrings are read: a tool function's (its description) and a module docstring the
module prints or gives argparse as its help text (`__doc__`). Test code is a top-level function
whose name, leading underscores aside, starts with `selftest`, and the lines from a
`# --- selftest` marker at the start of a line down. Static and text files are read whole, comments
included; a static file with a NUL byte in its first 8 KiB is taken as binary and not read. JSON is
read for its strings, keys and values at any depth. The character and its HTML entities count:
`&mdash;`, and `&#8212;` and `&#x2014;` with or without the semicolon, as HTML reads a numeric
entity. An em dash a program uses as data, a detector constant or a placeholder some exports write
for "no value", is written as the escape `\u2014`, which the guard reads as data. Docstrings,
comments in Python, test code, escapes and `.local.` files are the cuts; each is a case in the
self-proof that runs before the scan. A file in the scan set that cannot be read (not UTF-8, or
Python that does not parse) is reported, not skipped. `_CREATOR_TEXT_FLOOR` lists the places the
formatting rule names for the local tools, and the build fails when the derived set no longer
reaches one of them or cannot read it.

## Consequences

- A new page server, MCP tool, program a page runs, module a page imports, or command a page
  names is scanned without anyone listing it, when it is written in the forms above.
- The derived set reaches more than the places first named: the drift guard's own messages (the
  `drift_check` tool returns them), the connector resolver's plan text, and the scripts the pages
  name, such as `profile_mirror.py` and `update_check.py`.
- Limits: a handler base imported under another name, a handler class defined inside a function,
  a tool registered with `add_tool` instead of the decorator, a program reached through a path
  built another way (a variable, `os.path.join`), and a second hop (a module or program that a
  program imports or runs, and a script a program's output names) are not followed. The
  character built when a program runs (`chr(0x2014)`, `\N{EM DASH}`) is not seen, and a JavaScript
  or CSS escape for it in a static file is not read as one. In a Python file, a test
  helper with another name, and code under a `# --- selftest` marker that is indented, are read
  like the rest. The knowledge files the wizard copies into the upload folder are not scanned.
  The wizard's selftest renders each screen and fails on an em dash, or one of its entities, in
  its HTML, which also covers text a screen takes from another module when it renders.
- Maintainer text (docstrings a module does not print, comments in Python, internal docs) keeps
  its em dashes.
