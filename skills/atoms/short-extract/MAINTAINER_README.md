---
file: skills/atoms/short-extract/MAINTAINER_README.md
purpose: keep every extracted clip a standalone piece with its own hook, at least three per video.
---

# short-extract: Maintainer README

## Purpose
Extract standalone short-form clips from a long-form outline.

## Non-negotiable invariants
- Each clip has its own first-3-seconds hook and works with no prior context.
- At least 3 clips per video concept (brand ecosystem ratio in `shared/brand-engine.md`).
- A clip is original short-form content, not an abbreviated video summary.

## Known failure modes
- Clips that reference "earlier in the video."
- Fewer than 3 clips returned.

## Regression cases to preserve
1. clip_count 3: exactly three clips, each with its own hook and a format.
2. Each clip is self-contained with no dependency on the full video.

## Update checklist
- Run python3 tools/sync_check.py.
