# 20. P36 Source Currency Freshness

- Date: 2026-07-05
- Status: Accepted

## Context

Research found the existing currency machinery was built but dormant (126 of 139 sources never stamped, no content-hash baseline ever run, CI read-only with no loop closure, no MCP mutating surface) and that facts duplicated in engine/config prose were untracked, and that the four knowledge-only surfaces had no regeneration path and no visible as-of date. The owner set two hard constraints: the freshness system must never push/pull/propose to GitHub or generate homework for anyone, and each user's refreshed data must live only in a store that user controls. The append-only overlay + union-merge (reused from the P35 task store) makes a shared store concurrency-safe and keeps the repo a read-only, download-only baseline the owner updates only by their own manual choice.

## Decision

Turn the dormant source-currency system into an always-fresh, per-user, self-contained freshness system that keeps every deployment's reference data accurate on every modality (Claude Desktop/MCP, claude.ai web/mobile, Custom GPT, Gemini) without the freshness runtime ever touching GitHub. Add a read-only-baseline + user-controlled overlay model, monitors for connector APIs / AI-surface packaging formats / creator content data / compliance sources, embedded-fact tracking, visible per-surface freshness stamps, a wizard store step, MCP tools, and a local scheduler.

## Consequences

**Explicitly not done:** The freshness system performs no GitHub writes of any kind (no commit/push/pull/PR/proposal/update-nag) and no upstream aggregation of any user's findings; the repo is download-only and the owner publishes solely by their own manual choice. No hosted server (remote MCP is opt-in, user-provided). State AI-content law has no unified feed (per-jurisdiction polling, flagged). API keys are env-only, never persisted. Copyrighted code/report text is never cached.

Ledger status at record time: `shipped`. Source: `ledger/ledger.json` id `P36-source-currency-freshness`.
