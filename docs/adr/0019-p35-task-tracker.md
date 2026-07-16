# 19. P35 Task Tracker

- Date: 2026-07-05
- Status: Accepted

## Context

Brand deals run on event-triggered, multi-party obligations the creator tracks in their head. The defining constraint the creator set is anti-phantom: there must never be a task the tool identifies that it cannot cite to a specific contract clause, email, user statement, or a named rule grounded in a human artifact. The design reuses the strongest existing assets (obligations date math, finance invoicing/cashflow, docintel transcripts+WER, the verification envelope, connectors/ingest-route, the append-only registry conventions) rather than rebuilding them, and the append-only event log makes a shared Google Drive store concurrency-safe by union-merge rather than last-writer-wins, which is what unlocks the same tasks on claude.ai web, the Claude desktop app, and mobile for a non-technical Mac user with no hosting.

## Decision

Add an offline, source-cited, human-gated project task and obligation tracker for brand deals: event-triggered tasks per deal and contract, backwards-planning from deadlines, a seven-state lifecycle with a first-class waiting-on state, recurrence, two-party approval ping-pong, live/manual shipment tracking as the delivered_at planning anchor, multi-transcript coverage verification of required talking points, payment-milestone billable-readiness into the finance lane, and a pluggable store adapter (local_fs / google_drive / remote_mcp) for cross-surface and cross-AI continuity.

## Consequences

**Explicitly not done:** No auto-send of any email, invoice, nudge, or post (human-gated throughout). No webhook endpoints (carrier polling only). No hosted remote MCP server (the transport option and deploy runbook ship; standing one up is user/host work). Carrier API keys are read from the environment only, never committed or logged. Semantic/NLI coverage tiers are optional and flag-gated; the stdlib core abstains rather than guesses. No legal advice and no judgment of disclosure sufficiency. No blockchain chain of custody; a sha256 content hash is the tamper-evidence.

Ledger status at record time: `shipped`. Source: `ledger/ledger.json` id `P35-task-tracker`.
