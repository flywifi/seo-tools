---
file: skills/atoms/seasonal-map/SKILL.md
name: seasonal-map
description: Map a topic or content idea to its seasonal window, peak interest period, and urgency for a home decor/DIY YouTube channel using static seasonal knowledge only.
load:
  - canonical-sources/seasonal-aesthetic.md
  - shared/brand-engine.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# seasonal-map

Given a topic and an optional current month, this atom classifies the topic as evergreen, seasonal,
or recurring annual, then returns the peak interest window, a recommended publish-by date range, and
an urgency signal. All reasoning is from static seasonal knowledge baked into the atom. No live
retrieval is performed.

## Purpose

Content-strategy spokes and idea-generate need to know whether a topic is time-sensitive before
scheduling it. This atom answers that question in one call without touching the web. Seasonal
timing is owned by `canonical-sources/seasonal-aesthetic.md` (prose) and
`canonical-sources/seasonal-aesthetic/seasonal.json` (machine-readable ISO dates); the rows
below derive from that canonical table and must stay reconciled with it.

Moody/vintage home decor seasonal peaks used by this atom (derived from the canonical
eight-window table; the four windows most relevant to this niche):

| Season | Peak window | Ideal publish-by |
|---|---|---|
| Fall mantel and autumn decor | September 15 to October 20 | September 1 (pins by August 15) |
| Holiday tablescapes and winter decor | November 20 to December 15 | November 10 (pins by October 31) |
| Spring refresh and light interiors | March 1 to April 15 | February 20 (pins by February 10) |
| Summer outdoor and backyard | May 1 to June 30 | April 25 (pins by April 10) |

Evergreen topics (thrift-haul walkthroughs, budget room makeovers, furniture flips, organization
systems) carry no publish-by constraint and receive urgency "off_season" unless they incidentally
align with a seasonal window.

## Inputs

```json
{
  "topic": "string -- the video idea or subject to classify",
  "current_month": "integer 1 to 12 -- optional; if omitted the atom cannot compute urgency and sets it to plan_ahead",
  "channel_niche": "string -- optional; defaults to 'home decor'"
}
```

## Output

```json
{
  "tool": "seasonal-map",
  "topic": "string",
  "seasonal_type": "evergreen | seasonal | recurring_annual",
  "peak_window": "string -- e.g. 'September to October' or null for evergreen",
  "publish_by": "string -- e.g. 'August 20 to 31' or null for evergreen",
  "urgency": "immediate | upcoming | plan_ahead | off_season",
  "rationale": "string -- one to two sentences explaining the classification and any timing logic applied"
}
```

Urgency definitions:

- `immediate` -- publish-by date is within 14 days of current_month start
- `upcoming` -- peak window begins within the next 6 weeks
- `plan_ahead` -- peak window is 6 weeks or more away, or current_month was not provided
- `off_season` -- topic is evergreen, or the peak window has already passed for this calendar year

## Do NOT use for

- Checking whether a topic is currently trending or has search momentum (use trend-check for that).
- Generating keyword volume or difficulty estimates (use keyword-cluster).
- Building a full content calendar with scheduled slots (use content-strategy).
- Any niche other than home decor and DIY without updating the seasonal peak table in
  canonical-sources/seasonal-aesthetic.md first; do not silently extrapolate peaks to unrelated
  niches.
- Live or real-time retrieval of any kind. This atom is intentionally offline. If the caller needs
  current trend validation, chain trend-check after this atom.

## Pipeline note

Reads seasonal peaks from `canonical-sources/seasonal-aesthetic.md`. Obeys
`protocols/no-fabrication.md`: if the topic does not map cleanly to a known seasonal window, set
`seasonal_type` to `evergreen` and explain in `rationale` rather than fabricating a window. Obeys
`protocols/formatting-metadata.md`: no em dashes; ranges expressed as "X to Y". Pass output to
govern-artifact before it surfaces to the user.

## Cross-modality
Inherits its calling spoke's class (Class B); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
