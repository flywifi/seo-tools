---
name: project-snapshot
description: produce a one-page project brief (transformation arc, pillar, aesthetic grounding, content angles) for a single DIY home decor project. Do NOT use for materials lists, step sequences, scripts, captions, or any output requiring real analytics or CRM data.
version: 1.0.0
lane: content
atom: true
engines: [shared/brand-engine.md, shared/adaptation-engine.md]
protocols: [protocols/no-fabrication.md, protocols/safety.md, protocols/quality-gates.md, protocols/formatting-metadata.md]
---

# project-snapshot

## What this atom does

Produces a one-page project brief for a single DIY home decor project. The snapshot captures the
project title, transformation arc (before, process, after), skill level, estimated time, budget
tier, pillar classification, and any adaptation axes (renter-friendly flag, skill level, season or
occasion). It does NOT produce a materials list or step sequence; those are separate atoms.

## Do NOT use for

- Generating materials lists (use `materials-list`).
- Writing step-by-step instructions (use `step-sequence`).
- Producing scripts or captions (use `script-section`, `caption-write`).
- Evaluating competitor projects or trends (use `competitor-scan`, `trend-check`).
- Any request that requires real analytics or CRM data (use `analytics-insights` or `account-health`).

## Inputs

| Field | Type | Required | Notes |
|---|---|---|---|
| `project_idea` | string | yes | Free-text description of the project (e.g., "moody fall mantel makeover"). |
| `skill_level` | string | no | beginner / intermediate / advanced. Defaults to unspecified. |
| `tenure` | string | no | renter / owner / unspecified. Drives renter_friendly flag. |
| `budget_tier` | string | no | budget / mid_range / premium / unspecified. |
| `season_or_occasion` | string | no | E.g., "fall", "holiday", "spring refresh". |
| `pillar_override` | string | no | Force a pillar assignment if auto-classify is wrong. |

## Output

```json
{
  "project_title": "string",
  "pillar": "DIY and makeovers | thrifting and antiques | organization | seasonal and holiday | backyard and outdoor",
  "transformation_arc": {
    "before": "string - one sentence describing the starting state",
    "process": "string - one sentence summarizing the key transformation steps",
    "after": "string - one sentence describing the finished result and its aesthetic"
  },
  "skill_level": "beginner | intermediate | advanced | unspecified",
  "estimated_time_hours": "string - range using 'to' (e.g. '2 to 4 hours') or null if unspecified",
  "budget_tier": "budget | mid_range | premium | unspecified",
  "renter_friendly": "boolean | null",
  "season_or_occasion": "string | null",
  "aesthetic_notes": "string - one to two sentences grounding the project in Alex's moody-vintage aesthetic",
  "content_angles": ["array of 2 to 4 one-line content angle ideas derived from the transformation arc"],
  "flags": ["array of any missing inputs or design concerns; empty array if none"]
}
```

## Rules

- **Brand alignment.** Ground `aesthetic_notes` in `shared/brand-engine.md` identity language: moody,
  vintage, "collected over time," warm tonality. Do not use words from the forbidden list in that engine.
- **No fabrication.** Do not invent specific product names, SKUs, prices, or brand mentions. Keep
  the snapshot concept-level.
- **Pillar classification.** Classify automatically from `project_idea` using the 5 pillars in
  `shared/brand-engine.md`. Use `pillar_override` only if explicitly supplied.
- **Renter flag.** Set `renter_friendly: true` only when no permanent modification is required for
  the core transformation. When ambiguous, set `null` and add a flag.
- **Time and budget ranges.** Use "to" for all ranges (e.g., "2 to 4 hours", "50 to 150 USD").
  Label all budget figures as estimates.
- **Formatting.** No em dashes anywhere in output. Ranges use "to".

## Data source labels

All fields in this output are derived from the concept description; none are real measured data.
`content_angles` are suggestions only and require human judgment before use.

## References

- `shared/brand-engine.md` (pillar definitions, aesthetic language, forbidden words)
- `shared/adaptation-engine.md` (skill level, tenure, budget tier axes)
- `protocols/no-fabrication.md`
- `protocols/safety.md` (DIY trade boundary check; flag if project touches electrical, gas, or structural work)
- `protocols/formatting-metadata.md`
