---
file: skills/atoms/hook-write/MAINTAINER_README.md
purpose: keep hook-write to one hook that front-loads the promise or problem in the right voice.
---

# hook-write: Maintainer README

## Purpose
Write one hook in the published voice that establishes the promise or problem fast.

## Non-negotiable invariants
- Published voice from `shared/brand-engine.md`, not the planning voice.
- Opening window matches the platform (3 seconds short-form, up to 30 long-form).
- A short-form hook works standalone, with no prior context.

## Known failure modes
- Burying the promise behind a long intro.
- Writing in the planning-to-Alex voice instead of the audience voice.

## Regression cases to preserve
1. Shorts, 30 seconds: the first 3 seconds carry the hook with no setup.
2. Long-form: the promise lands inside the first 30 seconds.

## Update checklist
- Run python3 tools/sync_check.py.
