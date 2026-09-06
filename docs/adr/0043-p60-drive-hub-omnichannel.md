# 43. P60 Omnichannel Drive Hub (shared store, drop folder, compute hand-off, Projects projection)

- Date: 2026-07-17
- Status: Accepted

## Context

The three Claude modalities have unequal powers: Desktop with local MCP sees the real files and
runs every tool; web and mobile chat cannot touch the local disk; a Cowork remote session runs in
a sandbox. Before P60, working state lived on one machine, the Projects knowledge pack went stale
between re-uploads, and heavy compute (transcription, library analysis) happened only in a Desktop
session. The requirement was a genuinely omnichannel Creator OS: one shared place every surface
can reach through its own honest mechanism, a drag-and-drop inbox that gets sorted with review, an
async path handing compute to the local machine, and Projects that stay current. Two choices were
made explicitly during planning: build ALL THREE hand-off transports with Drive-for-desktop sync
as the default, and build BOTH Projects projections (the Docs-in-Drive live-sync lane and the
static pack) from day one.

## Decision

**One hub, append-only.** A single Drive folder ("Creator OS": Inbox, Store, Jobs/{queue, results,
archive}, Knowledge, Profile, Outbox) specified in `docs/DRIVE-HUB.md`. Every machine-written
artifact is a NEW dated file (`<kind>.<date>T<time>Z.<origin>.json`); nothing edits a shared file
in place; only the local machine moves or archives. This matches what the surfaces can actually
do: the claude.ai Drive connector reads and creates files but cannot update or move them, and
Drive for desktop resolves conflicting edits by keeping both copies, which the event-log
union-merge (`tools/tasks.py`) absorbs as extra inputs.

**Three transports, one queue, one runner.** Job tickets conform to
`shared/schemas/compute-job.json` (hard job-type allowlist, lowercase-UUID idempotency keys,
hub-confined `input_refs`, strict key set). `tools/handoff/queue.py` + `runner.py` are the single
execution path: per-type timeouts, atomic tmp+rename writes, duplicate/conflict-copy suppression,
structural refusal of anything outside the allowlist, and honest `failed`/`refused` results with a
log tail. Transport A (default) is a folder poller over the Drive-for-desktop mirror
(`watcher.py`, scheduled per the cron/launchd convention); Transport B (`drive_api.py`, opt-in
`drive_api_polling`) polls the Drive API under the narrow `drive.file` scope with create-only
uploads; Transport C (opt-in `remote_compute_endpoint`) adds `submit_compute_job`/`job_status` to
the remote MCP server, doubly gated. All three are inert until `compute_handoff_enabled` is turned
on; publishing, posting, sending, and credential access are structurally not job types.

**The drop folder composes the existing ingest chain.** `Inbox/` is scanned
(`tools/handoff/inbox.py`, read-only) against the dispatch table
`shared/docintel/inbox_rules.json` (data, not code). Format-unambiguous categories (transcripts,
media, export archives) route from the offline scan; content categories (contracts, pitches,
invoices) wait for a Claude session running the new `inbox-routing` atom with the injection guard;
unknowns are flagged in place and never guessed; QUARANTINE verdicts are never routed. `approve`
is the only writer (sha256 re-verify, move to `Inbox/Processed/<date>/`, gitignored ledger), with
a single-use batch token on the wizard `/inbox` screen. The atom is standalone (the
`profile-import` precedent) and deliberately has NO hub routing row; scenario S10 pins
`inbox_scan`/`inbox_routing` as absent classifications so a future row must be a deliberate act.

**Projects dual projection.** `tools/project_docs.py` projects the ten pack files two ways: the
local lane copies them into the hub's `Knowledge/` folder (stamps preserved; any Drive-connector
chat reads the current copy at question time), and the opt-in API lane creates real Google Docs
via the Drive import conversion, updating the SAME doc id on re-projection so a private Project
that references them live-syncs. Staleness is split deliberately: engines-to-pack stays drift
invariant 47 (runs in CI); pack-to-Drive is the tool's own `check` from locally recorded sha256s,
because CI cannot see Drive and a fail-closed invariant must never depend on out-of-repo state.
The static pack and its export path continue unchanged.

## Alternatives rejected

- **Drive push notifications (`files.watch`)** for Transport B: requires a public HTTPS webhook, a
  hosting requirement a local tool must not impose. Polling `changes.list`-style reads suffice.
- **A resident daemon** for the watcher: the repo's convention is cron/launchd calling a `--once`
  CLI (the freshness scheduler precedent); a daemon adds a supervision problem with no capability.
- **Registering the Drive copies in `PROJECTIONS` (invariant 47):** `reconcile` would bless keys
  it cannot read and CI cannot observe Drive; the pack-to-Drive check therefore lives in
  `project_docs.py` against local state.
- **A hub routing row for `inbox-routing`:** hub rows route to spokes; standalone atoms trigger on
  their own descriptions, and the pinned-absent scenario makes any future change deliberate.

## External facts relied on (each checked 2026-07-16)

- Claude Drive connector reads Docs/Sheets/Slides/PDFs/images/Office files and can create files
  (code execution + file creation enabled), but cannot update in place; Google Docs added to
  private Projects sync live from Drive; text-only extraction. Confirmed first-hand against a live
  connector toolset (create/copy/read/search tools present, no update tool).
  https://support.claude.com/en/articles/10166901-use-google-workspace-connectors
- Projects auto-switch to retrieval (RAG) at roughly 150K tokens of knowledge, about 10x capacity,
  30MB per file. https://support.claude.com/en/articles/9517075-what-are-projects
- Drive for desktop mirror mode keeps full local copies; stream mode uses Apple's File Provider on
  macOS 12.1+; conflicting concurrent edits keep both copies.
  https://support.google.com/drive/answer/13401938 and
  https://support.google.com/drive/answer/12178485
- The three research subagents launched for this phase died at start (empty output, unregistered
  task ids); every fact above was gathered and verified directly instead.

## Consequences

- 22 spokes, 106 atoms, 130 skills, 10 scenarios, 52 invariants; MCP server at 58 tools; 61
  capabilities with degraded-behavior parity. All three hub capabilities default off; with them
  off, behavior is identical to pre-P60.
- The queue/runner is the one place to audit for hand-off safety; transports carry no execution
  logic of their own.
- `keyword_offline` remains an allowlisted-but-refused job type until a future phase wires it.

## Hands-on Mac checklist (mechanism verified in this Linux sandbox; real-Mac behavior pending)

1. Drive for desktop mirror-mode sync latency for `Jobs/queue` tickets (create on phone, time to
   local visibility).
2. Stream-mode File Provider behavior: does the watcher's plain `open()` materialize placeholder
   ticket files reliably.
3. The launchd snippet in `tools/freshness-scheduler.example` fires `watcher.py --once` on
   schedule with the Mac awake, and the pmset/caffeinate guidance reads true.
4. End to end: phone photo dropped in `Inbox/` -> next scan -> proposal on `/inbox` -> approve ->
   file lands in `Inbox/Processed/<date>/` and the ledger records it.
5. Transport B against a real Google OAuth desktop client: the `drive.file` visibility caveat (the
   hub may be invisible until this app creates a file in it) reads true on a fresh credential.
6. The Google Docs lane: markdown import conversion fidelity on a real pack file, and a private
   Project referencing the Doc showing the new content after a re-projection with no re-upload.
