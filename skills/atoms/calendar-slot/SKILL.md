---
file: skills/atoms/calendar-slot/SKILL.md
name: calendar-slot
description: assign a content idea to a concrete publishing slot given a publish window and cadence, and emit a short-form drop schedule for the same project. Use when content-strategy or video-development needs to place an idea on the calendar. Do NOT use to generate content, build a full multi-project calendar, or pick ideas.
load:
  - shared/platform-engine.md
---

# calendar-slot

Given a working title, a publish window, and a cadence, calculate and return one recommended
long-form publish date plus a staggered short-form drop schedule (Shorts, Reels, TikToks) for
the same project. This atom assigns dates only; it does not generate outlines, scripts, or clips.

## Purpose

Content scheduling inside Creator OS requires pinning an idea to a specific date before production
begins. This atom handles that single operation so that video-development and content-strategy can
hand off to it without duplicating scheduling logic. It respects already-taken slots and surfaces
a rationale the creator can act on or override.

The output is consistent with the creator's ecosystem ratio: one long-form anchor plus 3 to 5
short-form drops per project, spread across the window to sustain algorithmic momentum without
clustering on the same day.

## Inputs

```json
{
  "working_title": "string (the content idea or working title being scheduled)",
  "publish_by_window": "string (deadline or window, e.g. 'before October 1' or 'week of Sept 22')",
  "cadence": "weekly | biweekly",
  "existing_slots": ["YYYY-MM-DD", "YYYY-MM-DD"]
}
```

Field notes:
- `working_title` is required. Use the most descriptive title available even if still provisional.
- `publish_by_window` is required. It anchors the calculation. Accepts natural-language strings;
  the atom resolves them to a target date range before computing the recommendation.
- `cadence` is required. Determines how far apart successive long-form uploads are spaced and
  sets the baseline spacing for short-form drops.
- `existing_slots` is optional. Pass as a list of ISO-8601 dates already taken by other projects.
  The atom avoids those dates. If omitted, no conflict-checking is performed.

## Output

```json
{
  "tool": "calendar-slot",
  "working_title": "string",
  "recommended_publish_date": "YYYY-MM-DD",
  "short_form_drop_dates": [
    {
      "drop_number": 1,
      "date": "YYYY-MM-DD",
      "platform_priority": "Shorts | Reels | TikTok",
      "timing_note": "string (e.g. 'teaser drop 5 days before long-form')"
    }
  ],
  "rationale": "string (why this date was chosen, cadence logic, any conflict avoidances)",
  "conflicts_avoided": ["YYYY-MM-DD"],
  "human_review_required": true
}
```

Output notes:
- `short_form_drop_dates` will contain 3 to 5 entries per project, spaced across the window.
  A typical pattern: 1 teaser drop before the long-form date, 2 to 3 highlight drops in the
  3 to 7 days after, and 1 repurpose drop 10 to 14 days after for longtail reach.
- `rationale` must reference the cadence, the window, and any seasonal urgency implied by the
  working title. Do not fabricate engagement data or historical performance claims.
- `human_review_required` is always `true`. the creator confirms or overrides before the date is locked.

## Do NOT use for

- Generating content: scripts, outlines, hooks, thumbnails, or clip extracts belong to other atoms.
- Building a full multi-project calendar across a season (use content-strategy spoke instead).
- Choosing or evaluating ideas (use idea-generate or pillar-classify).
- Trend or keyword validation (use trend-check or keyword-cluster before calling this atom).
- Resolving conflicts across more than one project at once; pass each project separately.

## Pipeline note

Follows `shared/method.md` at the Scheduling step. Platform-specific cadence guidance and
short-form platform priority order come from `shared/platform-engine.md`. Seasonal window
awareness is informed by `canonical-sources/` seasonal aesthetic data. Output must pass
`protocols/quality-gates.md` before a date is committed to the live calendar.

## Cross-modality
Inherits its calling spoke's class (varies by caller (B/C)); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
