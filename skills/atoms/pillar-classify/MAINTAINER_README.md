---
file: skills/atoms/pillar-classify/MAINTAINER_README.md
purpose: keep pillar-classify a single deterministic tag against the five canonical pillars.
---

# pillar-classify: Maintainer README

## Purpose
Classify one idea into a single content pillar with confidence and rationale.

## Non-negotiable invariants
- The five pillars come from `shared/brand-engine.md`; never invent a sixth.
- A spanning idea returns the primary pillar at medium confidence and names the secondary.

## Known failure modes
- Forcing a high-confidence single pillar on a genuinely cross-pillar idea.

## Regression cases to preserve
1. "Thrifted brass lamp restoration for a rental": primary thrifting, secondary DIY noted.
2. "Fall mantel tablescape": seasonal and holiday at high confidence.

## Update checklist
- Run python3 tools/sync_check.py.
