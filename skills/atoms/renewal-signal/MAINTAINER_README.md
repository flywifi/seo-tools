---
file: skills/atoms/renewal-signal/MAINTAINER_README.md
purpose: keep renewal-signal to a read-only scan of closed deals; it never advances stages or drafts outreach.
---

# renewal-signal: Maintainer README

## Purpose
Scan pipeline/deals/ for closed/fulfilled deals with renewal potential and return a ranked list. Reads only; no writes.

## Non-negotiable invariants
- Only reads pipeline/deals/ records; never writes, never advances deal stages.
- If account_id is provided and resolves to 0 closed deals, output is an empty list with a note; not an error.
- Priority ranking (high/medium/low) is based on exclusivity expiry proximity and deal performance data in the record; not guessed.

## Known failure modes
- Scanning all deal stages instead of only closed/fulfilled records.
- Ranking candidates by deal value alone without considering exclusivity expiry.
- Drafting outreach copy in the output (out of scope for this atom).

## Regression cases to preserve
1. Exclusivity expires in 30 days: renewal_reason includes "exclusivity window closing"; priority is high.
2. Zero closed deals in lookback_days: empty list returned with note; no fabricated candidates.

## Update checklist
- Run python3 tools/sync_check.py.
