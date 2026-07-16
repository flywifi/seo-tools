# 25. P40 Brand Deal Flow Hardening

- Date: 2026-07-11
- Status: Accepted

## Context

The end-to-end test proved the safety spine held but the orchestration made the user do the chaining, pricing ergonomics forced dummy zeros, and benchmark levers had no records to cite. Structure-only benchmark records keep the no-fabrication line: named nulls beat invented ranges.

## Decision

Fixed all 10 flaws from the fictional CoolBreeze inbound-pitch test run. Finance: proposal_price accepts rate-floor-only (no_cost_basis gap) and one-of-two cost inputs never guesses (partial_cost_inputs); price_package sums per-item floors, excludes unpriceable items with a gap (never 0), flags the sum against a package benchmark. Rate card: pipeline/finance/rate-card.template.json committed (real card is gitignored rate-card.local.json; the P30-5 user-context template was merged in and removed), format-based floor resolution with rate_floor_source provenance, benchmark_tier_assumed/mismatch gaps. Benchmarks: five structure-only lever records (usage-rights/exclusivity uplifts, TikTok/Reel tier rates) with null values, source null, needs_research true, do-not-quote text; values arrive only via a later cited research pass. New atoms: product-fit (mandatory data_basis, exclusivity red flag caps the verdict) and pitch-extract (untrusted body, envelope-stamped citation, verbatim compensation, stage identified with inbound_pitch origin in stage_history; the 9-stage machine was deliberately NOT extended). Hub: pitch_triage classification routed to deal-pipeline chaining extract -> fit -> package price -> gap-record -> govern-artifact; contract drafting stays human-requested. Wizard: /brand-deals readiness screen with one-click local flag enable; contract-desk/finance-desk degraded messages name the exact flag and the wizard route; contract-draft output gains mandatory profile_gaps[]. Acceptance: 10/10 assertions (live CLI on a throwaway sandboxed rate card, removed after) plus scenario S7-coolbreeze-pitch with finance.price/finance.price_package ops added to scenario_check.py. Runbook docs/BRAND-DEALS.md.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P40-brand-deal-flow-hardening`.
