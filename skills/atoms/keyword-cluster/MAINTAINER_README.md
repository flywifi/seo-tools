---
file: skills/atoms/keyword-cluster/MAINTAINER_README.md
purpose: keep keyword-cluster honest about volume and difficulty, and scoped to a cluster, not copy.
---

# keyword-cluster: Maintainer README

## Purpose
Produce one keyword cluster (primary, secondary, long-tail) with a difficulty note.

## Non-negotiable invariants
- Distinguish high-volume competitive terms (context in description) from medium-volume
  low-competition terms (primary in title).
- Never state exact volume as fact; verify and present as a range.

## Known failure modes
- Recommending a high-competition primary for a new channel without noting difficulty.
- Inventing search volume.

## Regression cases to preserve
1. New channel, broad topic: primaries are medium-volume low-competition, with the competitive terms moved to context.
2. Pinterest platform: primaries are front-loaded keyword-rich pin phrases.

## Update checklist
- Run python3 tools/sync_check.py.
