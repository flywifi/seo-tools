# ADR 0075 — Job origins name the computer's system; the Cowork surfaces and origin are retired

- Status: accepted
- Date: 2026-10-05
- Phase: P102

## Context

A job ticket's `origin` records where a job was queued (`shared/schemas/compute-job.json`). In P101
the value for this computer was `mac` on every system, and `docs/DRIVE-HUB.md` explained that `mac`
meant "this computer", while the Outbox tag (`runner._platform_tag`) named the system that ran the
job. A ticket queued from the wizard on Windows was therefore named `job.<stamp>.mac.<id8>.json`.

Claude Cowork and chat became one Claude in a staged rollout from 2026-09-16: "What you could
previously only do in Claude Cowork is available from any conversation" (support article 16761823).
Work on this computer runs in Claude Desktop with its trusted folders, and longer tasks run in the
cloud from a claude.ai conversation. The surface model still carried two Cowork rows
(`cowork_local`, `cowork_remote`, ADR 0047) and the queue still accepted the `cowork` origin.

## Decision 1: mac, windows and linux each name the computer by its system

`ALLOWED_ORIGINS` gains `windows` and `linux` beside `mac`, in the queue, the schema enum, drift
invariant 55's affinity table (each mapped to the two local Claude apps) and the surfaces that claim
them in `shared/cross-modality/transitions.json` (appended after `desktop` and `mac`, so a surface's
first origin is unchanged). The wizard queues a follow-up job with `runner._platform_tag()`, the
mapping the Outbox tag already uses: a Cygwin, MSYS2 or MINGW Python on Windows gives `windows`, a
Python under WSL gives `linux` (`wizard._queue_followup`). `queue.submit` keeps `mac` as its default
for callers that pass no origin. The suite keeps simulating the person at home as `mac` on every
system, so its file names do not depend on the computer it runs on.

This replaces the P101 rule that `mac` names this computer on any system.

## Decision 2: the Cowork rows and the cowork origin are retired, and a cowork ticket is refused

The two Cowork rows leave the surface model, the wizard's surface options and drift invariant 32's
key list; the claude.ai row gains the cloud-sandbox caveat the remote row carried. The `cowork`
origin leaves the enum and the affinity table, and `validate_ticket` refuses a ticket that still
carries it with the reason (`queue.RETIRED_ORIGINS`), rather than accepting it as a legacy value.
The S10 scenario leg now checks that the two rows stay absent. ADR 0047's surface decision is
superseded; its input-hardening and audit decisions stand.

The vendor's organization settings still name a Cowork switch ("Cowork and Skills must both be
enabled for your organization before you can use plugin marketplaces", support article 13837433),
so `docs/UPDATING.md` keeps that quote; it describes an admin control, not a Creator OS surface.

## Consequences

- A computer on code older than P102 that runs jobs from the same hub refuses a `windows` or
  `linux` ticket ("not in ALLOWED_ORIGINS"), writes a refused result and moves the ticket to
  `Jobs/archive/`, so that job must be queued again once the computer updates.
- A `cowork` ticket queued before P102 is refused after it.
- Tickets already in a hub keep their names; nothing renames them.
- Docs that described the Cowork rows now describe Claude Desktop and claude.ai agentic tasks;
  CHANGELOG history, the ledger and earlier ADRs keep their wording.

```sources
[
  {"id": "claude-cowork-chat-merge", "name": "Claude Cowork and chat are one Claude (help center)", "url": "https://support.claude.com/en/articles/16761823-claude-cowork-and-chat-are-one-claude", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "claude-cowork-plugins-org", "name": "Manage plugins for your organization (help center)", "url": "https://support.claude.com/en/articles/13837433-manage-plugins-for-your-organization", "category": "ai-surface-spec", "tier": "T1"}
]
```
