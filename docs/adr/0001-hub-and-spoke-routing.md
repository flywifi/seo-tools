# 1. Hub And Spoke Routing

- Date: 2026-06-01
- Status: Accepted

## Context

A single monolithic assistant prompt could not enforce lane-specific protocols or load only the engines a request needs; every request would pay for every capability.

## Decision

Route each request through a hub (`creator-core`) that classifies it into one of three lanes (Content, Document, Pipeline/CRM), loads only that lane's engines and protocols, and dispatches to a capability spoke. Spokes are thin orchestrators; they never re-implement engine logic.

## Consequences

Engines stay the single source of truth (referenced by repo-root path, no per-skill copies); adding a capability means adding a spoke, not editing the hub's core logic; the drift guard enforces that every spoke the hub names exists. Cost: a routing layer that must be kept in sync with the spoke inventory (enforced by drift invariants).
