---
file: skills/atoms/persona-map/SKILL.md
name: persona-map
description: Map a content topic or request to the most relevant audience persona(s) from the creator's five-persona model, returning primary and secondary personas, fit rationale, adaptation notes, and a confidence score. Use when a spoke needs to target or adapt content by audience segment. Do NOT use to generate content, write hooks, or assign keywords.
load:
  - shared/audience-engine.md
  - shared/brand-engine.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# persona-map

Given a content topic, this atom identifies which of the creator's five audience personas the topic
serves most strongly, which personas are secondary fits, and what adaptation considerations apply
per persona. No content is generated; mapping only.

## Purpose

Content-strategy and adaptation spokes need to know who a piece is for before writing hooks,
selecting formats, or adjusting budget and skill-level framing. This atom answers that question in
one call by reasoning against the five canonical personas defined in `shared/audience-engine.md`.

It is the authoritative persona-assignment step inside Creator OS. Every spoke that needs to target
or differentiate by audience segment must route through this atom rather than reasoning about
personas inline.

The five personas this atom recognizes:

| Persona | Core identity | Primary pain point |
|---|---|---|
| Renter | Small apartment, aspirational, budget-constrained, no permanent changes allowed | "My rental does not allow paint or holes." |
| Vintage Hunter | Thrift and antique seeker, wants sourcing strategy and authenticity | "Thrifting overwhelms me." |
| Organizer | System-seeker, loves checklists, labeled zones, and declutter workflows | "I have no storage in my tiny kitchen." |
| Holiday Maximalist | Seasonal decor enthusiast, goes big on fall and Christmas, wants impact without looking cheap | Wants moody nostalgia that does not read as budget. |
| New Homeowner | First home, overwhelmed, eager, modest budget, builder-basic starting point | "How do I make this feel like mine without a renovation." |

## Inputs

```json
{
  "topic": "string -- the video idea, working title, or short content description (required)",
  "pillar": "string -- optional; one of: DIY and room makeovers, thrifting and antiques, organization, seasonal and holiday, backyard and outdoor",
  "platform": "string -- optional; one of: YouTube long-form, YouTube Shorts, Instagram Reels, TikTok, Pinterest",
  "format": "string -- optional; e.g. tutorial, haul, room tour, checklist, Q and A, transformation"
}
```

All optional fields narrow the mapping. If omitted, the atom maps against the topic alone and
notes reduced confidence where platform or format context would have strengthened the call.

## Output

```json
{
  "tool": "persona-map",
  "topic": "string -- echoed from input",
  "primary_persona": "Renter | Vintage Hunter | Organizer | Holiday Maximalist | New Homeowner",
  "secondary_personas": ["string", "..."],
  "confidence": "high | medium | low",
  "fit_rationale": "string -- one to two sentences explaining why the primary persona is the strongest fit for this topic",
  "adaptation_notes": {
    "Renter": "string or null -- budget ceiling, reversibility framing, landlord-safe angle; null if this persona is not relevant",
    "Vintage Hunter": "string or null -- sourcing angle, authenticity cues, mix-and-match guidance; null if not relevant",
    "Organizer": "string or null -- system or checklist framing, storage constraint angle; null if not relevant",
    "Holiday Maximalist": "string or null -- seasonal window, impact-to-cost framing, nostalgia or moody aesthetic angle; null if not relevant",
    "New Homeowner": "string or null -- tenure framing, skill level entry point, high-impact-low-reno angle; null if not relevant"
  },
  "confidence_note": "string or null -- explains any factor that reduced confidence below high, e.g. missing platform or format context"
}
```

`secondary_personas` may be an empty list if the topic maps cleanly to one persona only.
`adaptation_notes` keys are always present; set the value to `null` for personas that are not
relevant rather than omitting the key.

## Do NOT use for

- Generating content, hooks, titles, or scripts (use hook-write, title-generate, or idea-generate).
- Assigning a content pillar (use pillar-classify).
- Mapping seasonal timing or urgency (use seasonal-map).
- Selecting platform-specific format specs or posting parameters (use platform-engine directly).
- Producing audience analytics or engagement predictions; this atom uses static persona definitions
  only. If real analytics override the defaults, the calling spoke must apply them after this atom
  returns.
- Any audience other than the creator's home decor and DIY audience. Do not
  extrapolate these personas to a different creator or niche.

## Pipeline note

Reads persona definitions from `shared/audience-engine.md`. Obeys `protocols/no-fabrication.md`:
if a topic does not map cleanly to any persona, set `confidence` to `low`, return the closest fit
as `primary_persona`, and explain in `fit_rationale` rather than fabricating a strong match. Obeys
`protocols/formatting-metadata.md`: no em dashes; ranges expressed as "X to Y". Pass output to
govern-artifact before it surfaces to the user.

## Cross-modality
Inherits its calling spoke's class (Class B); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
