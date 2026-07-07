---
name: idea-generate
description: generate a small set of pillar-aligned content ideas for a given pillar, persona, and format. Use when content-strategy needs ideas one batch at a time or a user asks for "give me video ideas for thrifting." Do NOT use to build a full calendar (use content-strategy) or to develop one idea into a production package (use video-development).
---

# idea-generate

Generate a few content ideas (not a calendar) for one pillar, anchored to the creator's aesthetic and a
named persona.

## Input
```json
{
  "pillar": "DIY and room makeovers | thrifting and antiques | organization | seasonal and holiday | backyard and outdoor",
  "persona": "The Renter | The Vintage Hunter | The Organizer | The Holiday Maximalist | The New Homeowner",
  "format": "haul | makeover | tutorial | vlog | review",
  "seasonal_context": "string or null",
  "count": 3
}
```

## Output
```json
{
  "tool": "idea-generate",
  "ideas": [
    {
      "working_title": "string, human readable first",
      "pillar": "string",
      "format": "string",
      "persona_served": "string",
      "hook_angle": "the promise or problem in one line",
      "scale": "quick_win | medium | hero"
    }
  ],
  "note": "ideas only; verify any trend claim via trend-check before committing"
}
```

## Do NOT use this atom for
- A full seasonal calendar (use content-strategy).
- Developing one idea into hook, title, outline, and clips (use video-development).
- Inventing trend or search-volume claims (use trend-check and keyword-cluster).

## Pipeline note
Follows `shared/method.md` at the Generation step. Pulls aesthetic and pillars from
`shared/brand-engine.md` and personas from `shared/audience-engine.md`. Obeys
`protocols/formatting-metadata.md`. Pass the batch to govern-artifact before it ships.

## Cross-modality
Inherits its calling spoke's class (varies by caller (A/B)); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
