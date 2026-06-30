---
name: pillar-classify
description: classify a single idea or piece into one of the creator's five content pillars with a confidence and rationale. Use when a spoke needs to tag content by pillar. Do NOT use to generate ideas (use idea-generate) or to map personas (use audience-engine directly).
---

# pillar-classify

Tag one idea with its content pillar.

## Input
```json
{ "idea": "a working title or short description" }
```

## Output
```json
{
  "tool": "pillar-classify",
  "pillar": "DIY and room makeovers | thrifting and antiques | organization | seasonal and holiday | backyard and outdoor",
  "confidence": "high | medium | low",
  "rationale": "one line"
}
```

## Do NOT use this atom for
- Generating ideas (use idea-generate).
- Assigning a persona (read `shared/audience-engine.md`).

## Pipeline note
Follows `shared/method.md`. Pillars are defined in `shared/brand-engine.md`. If an idea spans two
pillars, return the primary with medium confidence and name the secondary in the rationale.
