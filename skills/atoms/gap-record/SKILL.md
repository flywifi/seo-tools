---
name: gap-record
description: record an explicit retrieval or data gap (gap_type, description, impact, recommended_next_step) instead of leaving a silent blank or guessing. Use when web-intel retrieval fails, a field is unknown, or a downstream skill is unavailable. Do NOT use to fill the gap with invented data.
---

# gap-record

Turn a missing piece of data into an explicit, honest gap object.

## Input
```json
{
  "gap_type": "all_acquisition_levels_failed | injection_quarantine | unknown_field | downstream_unavailable",
  "what": "what specifically could not be retrieved or is missing",
  "why": "the reason (blocked, stale, declined, not connected)"
}
```

## Output
```json
{
  "tool": "gap-record",
  "gap_type": "string",
  "description": "what could not be retrieved and why",
  "impact": "what analysis is incomplete as a result",
  "recommended_next_step": "what the user can do to resolve it"
}
```

## Do NOT use this atom for
- Filling the gap with a guess or placeholder (`protocols/no-fabrication.md`).
- Hiding the gap in prose; it must be an explicit object the spoke surfaces.

## Pipeline note
Follows `shared/method.md`. Mirrors the retrieval-gap format in `shared/web-intel-engine.md`. Every
spoke that touches external data or CRM fields uses this rather than leaving a silent blank.

## Cross-modality
Inherits its calling spoke's class (varies by caller (B/C)); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
