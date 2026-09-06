# 4. No Fabrication Null And Flag

- Date: 2026-06-01
- Status: Accepted

## Context

A creator-facing tool that invents a metric, rate, brand, source, or transcript is worse than one that admits a gap.

## Decision

Never fabricate data. When a value is unavailable, emit null plus a gap that names the fix, and label every estimate. Provenance and freshness envelopes wrap values that leave the machine. Enforced by `protocols/no-fabrication.md`, the freshness overlay, and drift checks.

## Consequences

Outputs are honest by construction; a blocked or missing source is surfaced, never guessed. Cost: more plumbing (envelopes, gap objects, truncation sentinels) on every data path.
