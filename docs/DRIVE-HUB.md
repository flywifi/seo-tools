# The Drive Hub: one folder every surface shares

The Drive hub is a single Google Drive folder ("Creator OS" by default, configurable via the
`drive_hub` section of `creator-os-config.json`) that makes Creator OS work the same across Claude
Desktop, Cowork, and web/mobile chat. Each surface reads and writes the hub through its own honest
mechanism, and the local machine acts as the compute engine. This document is the authoritative
convention: the layout, the naming rule, who writes what and when, and the async job contract.

Status: the hub is **opt-in**. All three related capabilities (`compute_handoff_enabled`,
`drive_api_polling`, `remote_compute_endpoint`) default to off; without them Creator OS behaves
exactly as before this feature existed.

## Why a Drive hub (the problem it solves)

The three modalities have unequal powers. A Desktop session with local MCP sees the real files and
can run every tool. Web and mobile chat cannot touch the local disk at all; a Cowork remote session
runs in a sandbox. Before the hub, working state lived on one machine, the Project knowledge pack
went stale between re-uploads, and heavy compute happened only when someone was physically in a
Desktop session. The hub gives every surface one shared place that each can genuinely reach:

- The **claude.ai Google Drive connector** can search and read Docs, Sheets, Slides, PDFs, images,
  and MS Office files, and can **create** files in Drive (with code execution and file creation
  enabled). It cannot edit files in place or move them. Google Docs added to a **private** Project
  sync live from Drive, so a Project referencing hub Docs is always current. Text content only;
  embedded images are not processed. (Source: the Claude Help Center article "Use Google Workspace
  connectors", checked 2026-07-16.)
- **Google Drive for desktop** on macOS syncs the hub to a real local folder (mirror mode keeps
  full local copies; stream mode uses Apple's File Provider). On conflicting concurrent edits it
  keeps both copies rather than merging or destroying. (Source: Google Drive Help, "Stream and
  mirror files with Drive for desktop" and "Use Drive for desktop on macOS", checked 2026-07-16.)

Those two facts drive the design rule that makes everything below safe:

> **Append-only, create-only.** Every machine-written artifact in the hub is a NEW dated file.
> Nothing edits a shared file in place; nothing but the local machine moves or archives files.
> Divergent copies of a register merge by event-log union (the `tools/tasks.py` merge model), and
> Drive conflict copies are just extra inputs to the same union.

## Layout

```
Creator OS/                     (the hub root, in My Drive)
  Inbox/                        drop anything here, from any device
    Processed/<YYYY-MM-DD>/     where handled files land after an APPROVED routing (moved locally)
  Store/                        the shared JSON registers (tasks, freshness overlay, obligations)
  Jobs/
    queue/                      job tickets awaiting the local machine (one JSON file each)
    results/                    result JSONs and small output artifacts
    archive/                    completed tickets (moved by the local machine only)
  Knowledge/                    the Projects knowledge pack projection (Docs-compatible files)
  Profile/                      dated profile exports/imports for the paste-back flow
  Outbox/                       deliverables for the human: reports, dashboards, calendars
```

Who does what, where, when, and why:

| Area | Written by | Read by | When | Why it exists |
|---|---|---|---|---|
| `Inbox/` | The human, from any device | The local inbox scan | Anytime | One drag-and-drop target reachable from every surface, including a phone |
| `Store/` | Any surface (new dated files); local machine (canonical merges) | Every surface | On change / on schedule | The cross-surface source of shared registers, per the store mode chosen in the wizard |
| `Jobs/queue/` | Any surface (create-only) | The local watcher | On submit | Lets a cloud session hand compute to the local machine |
| `Jobs/results/` | The local runner | Any surface | On completion | Results visible everywhere, including status for pending jobs |
| `Jobs/archive/` | The local machine only | Audit | After completion | Keeps the queue directory small without deleting history |
| `Knowledge/` | The local projection tool | claude.ai Projects (live-sync) | On re-projection | A Project referencing these files stays current automatically |
| `Profile/` | Any surface (dated exports) | The profile-import flow | On transfer | Cross-surface profile moves stay propose-then-confirm |
| `Outbox/` | The local machine | The human, any surface | On delivery | Finished artifacts, one place to look |

**Naming rule** for every machine-written file:
`<kind>.<YYYY-MM-DD>T<HHMMSS>Z.<origin>.json` where `origin` is `web`, `desktop`, `cowork`, or
`mac`. Names sort chronologically, never collide without coordination, and carry their provenance.

## The async job contract

A cloud session submits work by **creating one JSON ticket** in `Jobs/queue/`, valid against
`shared/schemas/compute-job.json`. The local machine's watcher validates it, runs the job through
the existing tool CLIs, and **creates** a result file in `Jobs/results/`. The ticket is never
edited; completion is expressed by the existence of the result. Rules the runner enforces
structurally (not by convention):

1. **Job-type allowlist.** Only the types enumerated in the schema run. Publishing, posting,
   sending, credential access, and shell passthrough are not job types and must never become ones
   without an approval-gated change (`tools/handoff/MAINTAINER_README.md`).
2. **Idempotency.** A `job_id` that already has a result is never re-run, so duplicate deliveries
   and double-watchers are harmless.
3. **Path confinement.** `input_refs` resolve inside the hub root only; anything that escapes is
   refused (the same realpath containment rule the setup wizard applies to folders).
4. **Untrusted input.** Tickets are data, not instructions: params are validated per job type and
   passed as fixed arguments, never interpreted as text to follow or shell to run.
5. **Timeouts and honest failure.** Every job type has a time budget; a failure produces a result
   with `status: failed` and a short log tail, never a raw traceback and never a silent hang.
6. **Human review.** Results report; humans decide. Any result a downstream action could follow
   carries `human_review_required: true`.

### The three transports (how a ticket reaches the local machine)

| Transport | How | Default? | Requirements | Trade-off |
|---|---|---|---|---|
| A. Drive for desktop | The hub syncs to a local folder; the watcher polls that folder on a schedule | **Yes** | Google Drive for desktop (mirror mode recommended for the hub), machine awake | No API code, no OAuth, no server; latency = sync + schedule interval |
| B. Drive API polling | The watcher polls `changes.list` with a desktop OAuth client (`drive.file` scope) | Opt-in (`drive_api_polling`) | A Google OAuth client connected in the wizard | Works without the sync app; adds a credential and API quotas |
| C. Remote MCP live | Cloud sessions call `submit_compute_job` / `job_status` on the deployed remote MCP endpoint | Opt-in (`remote_compute_endpoint`) | The endpoint deployed behind TLS + auth per `implementation/gpt/mcp-connector/README.md` | Synchronous, no Drive latency; you host and secure an endpoint |

All three feed the same queue and the same runner; there is exactly one execution path to audit.

**Transport B honest walls.** The polling credential is a Google OAuth *Desktop app* client with
only the `drive.file` scope, which sees just the files this app created or that were opened with
it: the watcher may report the hub folder "not found" until a file has been created in it through
this credential at least once. Like the YouTube publishing credential, a Cloud Console app left in
Testing mode expires its grants periodically, so an occasional reconnect on the wizard
`/drive-hub` screen is expected. This credential is never used by the publishing path, and with
Google Drive for desktop installed you do not need it at all.

## The drop folder ("divvy up")

Drop any file into `Inbox/` from any device. On the next scan (a scheduled `inbox_scan` job or the
wizard's Inbox screen), Creator OS classifies each new file (format first, then content category),
runs the injection guard treating every dropped file as untrusted, and assembles ONE proposal
batch: which file goes to which store or tool. Nothing is written to any store and nothing is moved
until the human approves the batch. Unknown files are flagged and left in place, never guessed.
Files that the injection guard quarantines are never routed. Approved files are recorded in the
inbox ledger (`pipeline/inbox/`, template committed, real ledger local-only) so re-scans are
idempotent.

## Boundaries

- **Credentials never enter the hub.** `api-credentials.local.json` and everything the secret
  scanner recognizes stay on the local machine, in every configuration.
- **Nothing posts from a job.** The publishing path keeps its own separate gates
  (`live_publishing_enabled` + human confirmation); no job type touches it.
- **The hub is per Google account, per install.** One hub pairs with one Creator OS clone and one
  profile. A second user gets their own clone and their own hub.
- **Putting data in Drive is a choice.** The hub holds only what the chosen store mode already
  shares; the local-first mode remains the default posture of the repo.

## Keeping this document honest

This spec is bound to the job schema (and, as they ship, the handoff tools) in
`tools/doc_freshness.py`; when the bound code moves, drift invariant 51 flags this document for
re-reading. External claims above carry their source and check date inline; the sources are
declared below and registered in the source registry, so the currency system re-checks them
(drift invariant 52 fails the build if a declared source is unregistered).

```sources
[
  {"id": "claude-google-workspace-connectors", "url": "https://support.claude.com/en/articles/10166901-use-google-workspace-connectors"},
  {"id": "google-drive-desktop-sync-modes", "name": "Google Drive Help - Stream and mirror files with Drive for desktop", "url": "https://support.google.com/drive/answer/13401938", "category": "os-platform", "tier": "T1", "extraction_hint": "Stream vs mirror: mirrored files are stored locally and in the cloud; on conflicting content Drive for desktop keeps both copies."},
  {"id": "google-drive-desktop-macos", "name": "Google Drive Help - Use Drive for desktop on macOS", "url": "https://support.google.com/drive/answer/12178485", "category": "os-platform", "tier": "T1", "extraction_hint": "Drive for desktop on macOS; streaming uses Apple's File Provider on macOS 12.1 and later."}
]
```
