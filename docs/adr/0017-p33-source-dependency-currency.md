# 17. P33 Source Dependency Currency

- Date: 2026-07-04
- Status: Accepted

## Context

A two-agent audit found the registry seeded but dormant (all entries never checked), real cadence bugs (legal/cost categories missing from traversal-config so treated as 7-day-due; stale MCP-spec and TikTok URLs; duplicate and placeholder entries), and a structural blind spot: pip packages, system binaries, and MCP servers added across P8-P32 were untracked and drifted silently. The user required accurate checks and token-free mundane updating.

## Decision

Audit and modernize the source-currency system: fix its config bugs, close the dependency blind spot, and add a token-free periodic-update lane.

## Consequences

**Explicitly not done:** No auto-upgrading of pins (drift reported, human bumps); CI is report-only (no registry auto-write); no scraping where a structured API exists; intentionally-static creator-local files stay static; the web-content baseline --apply runs on first deployment (proxy-dependent reachability).

Ledger status at record time: `shipped`. Source: `ledger/ledger.json` id `P33-source-dependency-currency`.
