# ADR 0072 — Cross-surface workflows run as a sandboxed suite; Gemini's web and desktop apps join the matrix

- Status: accepted
- Date: 2026-10-01
- Phase: P100

## Context

Creator OS is used from claude.ai, ChatGPT and Gemini, on the web and in their desktop apps, while
its tools run only on the computer where it is installed. Work moves between them through the
Google Drive hub (ADR 0070, `docs/DRIVE-HUB.md`). Nothing checked, end to end, that a request
starting in one vendor's web chat and continuing in a desktop app still leaves the preference
files, run logs, flag behaviour, minority reports and provenance it should.

The transitions matrix named only the Gemini API and Gems for Google; the Gemini app has run on
macOS since April 2026 and on Windows since 2026-09-10, and on the Mac, Gemini Spark edits,
renames, reorganizes and can permanently delete files in folders a person connects. The ChatGPT
desktop app holds Chat, Work and Codex since July 2026, and Codex works on local files. ChatGPT's
Google Drive app and Claude's Google Drive connector can now move or trash Drive files, which the
hub design had treated as impossible for those surfaces.

## Decision 1: one suite, simulated surfaces, real computer code

`tools/surface_workflow_check.py` runs the 10 workflows in
`skills/creator-core/evals/surface-workflows.json`: each vendor's web chat into each vendor's
desktop app, plus a round trip. A surface step writes only what its declared `drive_write` mode
allows (the mode comes from the vendor help page the contract cites), and only into a place the
surface's row in the matrix can reach, judged by where the file actually is (or, for a new file,
would land; a file name holding a path is refused). Every computer step
calls the repo function itself in a per-workflow sandbox: module globals, `HOME`, the inbox
functions' default ledger arguments and the call arguments point at the sandbox, a preflight
before each computer step refuses it while one of those points elsewhere, and the job runner gets
a literal `allow` so the real config is not read.

The gate against touching the owner's files is a write guard: an audit hook that, while the
workflows and probes run, refuses and records the writes it judges (opening a file for writing,
and the `os` and `shutil` calls that remove, rename, move, copy or create a file or folder) when
they land outside the system temporary folder. The interpreter's own bytecode cache is let
through: creating a `__pycache__` folder and writing this interpreter's cache file inside one,
and, with a configured bytecode prefix, creating the prefix folder, its missing parents and folders
under it and writing such a file there. A refusal fails the suite, and so does a run in which
the guard judged no write. Outside its view are writes by another process, writes made inside a C
library, writes through a file handle opened earlier, `os.mkfifo` and `os.mknod` (no audit event),
`os` calls given a folder handle (skipped), and a file opened relative to a folder handle (judged
as if relative to the current folder). A before-and-after snapshot of the reachable files on the machine is kept as advice only,
because the real mirror agent or a sync client can change those files during a run; an
unconfigured or unreadable hub is reported as SKIP.

Rejected: a snapshot comparison as the gate. It cannot tell the suite's writes from another
program's, so it either fails on unrelated changes or has to excuse the very files the suite could
reach.

Also rejected: driving the vendor apps (no supported automation path, and it would put real
accounts in a test); and folding these into `tools/scenario_check.py`, whose scenarios are single
requests, not a sequence of surfaces.

## Decision 2: gaps are pinned, not fixed, with one exception

The suite pins eleven open gaps (SW-G1 to SW-G8 and SW-G10 to SW-G12 in
`docs/SURFACE-WORKFLOWS.md`), each with a probe that fails the suite once the gap closes, so a fix
is a deliberate change to the contract and the guide. SW-G9 is fixed here: `tools/tasks.py`
`merge_tasks` matched events by a sequence number that the merge renumbers, so a register edited on
both sides gained a duplicate event on every later read. Events are now matched by every field
except that number, as a multiset, and the inputs are copied before renumbering.

## Decision 3: the matrix and the facts follow the vendors' own pages

`gemini_web` and `gemini_desktop` join `shared/cross-modality/transitions.json` (thirteen surfaces),
with drift invariant 32's key list, the wizard table, `docs/TRANSITIONS.md` and the engine matrix
updated together. ChatGPT developer mode is described as documented for ChatGPT web, with the
desktop app marked for verification. The hub's create-only rule is restated as Creator OS policy:
surfaces other than the computer create new dated files and never move, edit or trash a file the
computer manages. The new facts are registered sources, checked 2026-10-01.

## Consequences

- The battery runs one more gate, and CI runs it as a blocking step.
- The live steps for each workflow (what only the owner's devices can show) live in the guide and
  print with `--runbook`.
- Registers that already hold duplicated events keep them; new merges add none. Because an event's
  identity is every field except its sequence number, the same event recorded with identical fields
  on two devices is kept once.
- The runner's selftest and the tasks selftest carry mutation cases chosen by a reviewer who did
  not write the code; a case its checks stop catching, or whose anchor no longer applies, fails
  the selftest. The runner first checks that an unmutated copy passes every group the cases name.
  After each case it restores the module settings the sandbox repoints, the loader stand-ins,
  network spies and job-runner function, and the import path, and empties the copy's write-guard
  stack; the copies' audit hooks stay installed, inert, until the process exits. Another shared
  function a case replaces is not restored.
- Facts that depend on a plan, region or rollout (Gemini custom MCP apps, ChatGPT developer mode on
  desktop, Codex writing outside the folder it opened) stay marked for verification.
