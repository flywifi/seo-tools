---
file: skills/atoms/inbox-routing/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for inbox-routing so it stays stable under iteration.
---

# inbox-routing: Maintainer README

## Purpose
The drop-folder sorter (P60): classify every new file in the Drive hub Inbox and propose, in ONE
reviewable batch, where each belongs. Its job ends at the proposal; approval, file moves, handler
execution, and the ledger write all happen after a human says yes (wizard `/inbox` screen or an
explicit confirmation), on the local machine only.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Proposal-only: the atom never writes a store, never moves a file, never writes the ledger.
- Untrusted always: every dropped file runs the injection guard as `untrusted_external`
  (the Inbox is reachable from phones and shared devices); QUARANTINE/BLOCK is never routed.
- Never guess: no confident category or no matching rule means `unknown`, listed and left in place.
- The rules table is data: routing lives in `shared/docintel/inbox_rules.json`, not in prose or
  code, so adding a category is a reviewed data change.
- Idempotent by sha256: a file already in `pipeline/inbox/inbox-ledger.local.json` is skipped.

## Known failure modes
- A plausible-but-wrong category routing a file to the wrong desk: mitigated by the per-file
  provenance on the approval screen (category + rule shown) and the human gate.
- Rules-table drift (a rule naming a handler atom that was renamed): the drift guard's path checks
  cover the table's `handler` values via the scenario fixture; extend the fixture when adding rules.

## Fragile fallbacks that must not become defaults
- "Ledger unreadable, treating all files as new" is acceptable ONLY as a labeled degrade; the
  approve step must still refuse to double-route files whose target already holds them.

## Regression cases to preserve
1. A mixed drop (contract + pitch + video + unknown binary) yields one proposal batch with the
   three known files routed per the rules table and the unknown flagged in place — mapped to
   evals/evals.json case 1 and the `inbox_scan` scenario fixture.
2. A file whose injection scan returns QUARANTINE appears only in the `quarantined` section and is
   never routed — evals case 2 and the scenario fixture.
3. Re-scanning an unchanged Inbox proposes nothing (ledger idempotency by sha256) — evals case 3.

## Approval-gated changes
Adding or removing a category or rule in `shared/docintel/inbox_rules.json`; changing the
proposal schema; letting any path write a store, move a file, or touch the ledger before approval;
weakening the untrusted-by-default scan posture.

## Minority-report policy
When the format classifier and the content categorizer disagree (for example a `.csv` that reads
like a contract), record both signals in the proposal entry, route by the CONTENT category, and
show the disagreement on the approval screen; the human's approval is the resolution.

## Update checklist
Edit `SKILL.md` and this file together with any rules-table change; update
`shared/docintel/inbox_rules.json` and its scenario fixture in the same commit; run
`python3 tools/handoff/inbox.py --selftest` and `python3 tools/scenario_check.py`; always end with
`python3 tools/sync_check.py`. Verify all backticked path references in this file and SKILL.md
resolve to real files on disk.
