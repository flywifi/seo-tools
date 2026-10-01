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
allows, and the mode must agree with the surface's row in the matrix. Every computer step calls the
repo function itself in a per-workflow sandbox: module globals and arguments point at the sandbox,
a preflight refuses to run while any points elsewhere, and the job runner gets a literal `allow`
so the real config is never read. After the run, the reachable files on the machine are compared
with a snapshot; an unconfigured or unreadable hub is reported as SKIP.

Rejected: driving the vendor apps (no supported automation path, and it would put real accounts in
a test); and folding these into `tools/scenario_check.py`, whose scenarios are single requests,
not a sequence of surfaces.

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
- Registers that already hold duplicated events keep them; new merges add none.
- Facts that depend on a plan, region or rollout (Gemini custom MCP apps, ChatGPT developer mode on
  desktop, Codex writing outside the folder it opened) stay marked for verification.
