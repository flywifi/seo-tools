---
file: skills/atoms/script-section/MAINTAINER_README.md
purpose: keep script-section in planning-to-the creator voice, one section per call, with an honest duration estimate.
---

# script-section: Maintainer README

## Purpose
Write one script section (hook, intro, body-step, b-roll cue, transition, CTA, or outro) in the planning-to-the creator voice. One section per call; use workflow.json repeat: per_section for full scripts.

## Non-negotiable invariants
- Voice is always planning-to-the creator (second person "you'll say..."), never published-to-audience.
- One section per call; do not combine multiple section types in a single output.
- duration_estimate_seconds reflects the section type and target_duration_seconds if provided.

## Known failure modes
- Writing in published-to-audience voice instead of planning notes.
- Returning two sections (e.g., hook + intro) in a single call.
- Ignoring the platform input when setting duration (Shorts hooks = 3s, long-form hooks up to 30s).

## Regression cases to preserve
1. Shorts platform, hook section: duration_estimate_seconds is 3 to 5; no long intro.
2. body-step section with step_content: the script text walks through that specific step.

## Update checklist
- Run python3 tools/sync_check.py.
