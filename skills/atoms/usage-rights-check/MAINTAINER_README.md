---
file: skills/atoms/usage-rights-check/MAINTAINER_README.md
purpose: keep usage-rights-check as legal information only; it never gives legal advice and always recommends counsel for ambiguous terms.
---

# usage-rights-check: Maintainer README

## Purpose
Extract and evaluate usage rights clauses from a deal record or contract text. Legal information only; never legal advice.

## Non-negotiable invariants
- The purpose section explicitly states "legal information only, not legal advice; recommend qualified counsel for binding decisions."
- recommend_counsel: true whenever terms are ambiguous, missing, or high-value.
- ftc_disclosure_required is always evaluated and always present in the output, never skipped.

## Known failure modes
- Giving a definitive legal opinion on a clause instead of flagging it for counsel.
- Setting recommend_counsel: false when the license_grant field is absent or unclear.
- Omitting ftc_disclosure_required from the output entirely.

## Regression cases to preserve
1. Ambiguous "perpetual license" clause: flags is populated; recommend_counsel: true.
2. Sponsored content without FTC disclosure clause: ftc_disclosure_required: true with reason.

## Update checklist
- Run python3 tools/sync_check.py.
