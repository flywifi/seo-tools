# 34. P49 Audit Remediation

- Date: 2026-07-15
- Status: Accepted

## Context

Match the Teacher OS discipline: known things are declared and the build fails on undeclared ones; outputs stay honest about coverage; a source that gets bot-blocked is not silently discarded; and doc counts cannot drift stale unnoticed.

## Decision

Remediated a full-repo audit across nine workstreams. WS9: a bot-blocked source is now classified 'blocked' (inconclusive), never demoted to stale/changed/gone/orphan; source_currency wires fetch_diag.classify_block, records durable last_block_detected, and excludes blocked sources from staleness/SLA; traversal orphan-pruning and dependency_currency/update_check distinguish a rate-limit from an absence; an all-surface human/browser verification handoff plus an opt-in --resilient retry were added. WS1 decodes YouTube categoryId to a label. WS5/6 add a way-home source URL to every knowledge stamp and a single combined knowledge pack. WS8 adds a completeness-contract doc and softens overclaiming GPT Action strings. WS4 adds a persona-audit protocol + read-only harness + first run + low-risk wizard fixes. Three new drift invariants took the count 45->48: 46 URL provenance (ERROR), 47 knowledge-pack projection staleness (advisory), 48 doc-count truth (ERROR). Stale doc counts corrected (22 spokes, 5 agent roles, 48 invariants).

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P49-audit-remediation`.
