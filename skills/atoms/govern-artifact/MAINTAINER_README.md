---
file: skills/atoms/govern-artifact/MAINTAINER_README.md
purpose: keep govern-artifact a pure gate that defers the verdict to quality-review and its scorer.
---

# govern-artifact: Maintainer README

## Purpose
Run the Quality Gates on a drafted artifact and return the verdict. It never edits the artifact.

## Non-negotiable invariants
- The verdict and arithmetic come from `skills/quality-review/scripts/score.py`, never hand-computed.
- A hard fail (Integrity or Safety at 0 to 1) is never released or softened.
- For CRM artifacts, the verdict is recorded alongside the record.

## Known failure modes
- Releasing on a strong composite while a critical dimension is below 4.
- Editing the artifact inside the gate instead of returning fixes for the spoke to apply.

## Regression cases to preserve
1. A drafted artifact with a fabricated metric returns Not released, hard_fail true.
2. A clean artifact returns Released with the per-dimension scores attached.

## Update checklist
- Run python3 tools/sync_check.py.
