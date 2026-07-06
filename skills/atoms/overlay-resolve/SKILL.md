---
name: overlay-resolve
atom: true
standalone: true
description: "resolves which ADVISORY jurisdictional overlays apply to a project location: flood zone, historic district, hurricane zone (HVHZ), steep-slope/ridge, watershed, and statutory rules like the SB 4D milestone inspection, for Florida and North Carolina. Evaluates attribute overlays (county FIPS, stories, elevation) offline against the project facts and geometry overlays by point-in-polygon (EPSG:4326) against a cached or user-supplied boundary; live boundaries (e.g. FEMA flood) are fetched only when jurisdictional_overlay_live is on. Triggers: 'is my build site in a flood zone', 'does HVHZ apply here', 'is this in a historic district', 'does the steep-slope overlay apply', 'what jurisdictional rules affect this location'. Advisory planning information only, never a legal or permitting determination. Do NOT use to resolve a conflict between two overlays (conflict-check), to answer what the code text says (code-lookup), or to give engineering, code-compliance, or legal advice."
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/research-citation.md
  - protocols/formatting-metadata.md
---

# overlay-resolve

Given a project location (and known facts about the building), returns the ADVISORY jurisdictional
overlays that apply, each cited to its government GIS or statutory source. Requires the
`jurisdictional_overlay` capability; the optional live tier (`jurisdictional_overlay_live`) is what
lets a geometry overlay be resolved against a live FEMA/municipal boundary instead of a cached one.

## First line of every output (verbatim)

```
ADVISORY PLANNING INFORMATION ONLY, NOT A LEGAL OR PERMITTING DETERMINATION. FLOOD, ZONING, AND JURISDICTION OVERLAYS ARE NOT A SUBSTITUTE FOR AN AUTHORITATIVE DETERMINATION (E.G. A FEMA FLOOD DETERMINATION) OR THE AUTHORITY HAVING JURISDICTION. VERIFY LOCALLY.
```

## When to use this skill
- "Is my build site in a flood zone / historic district / hurricane zone / steep-slope area?"
- "Which jurisdictional rules affect a project at this location?"
- "Does the SB 4D milestone inspection apply to this condo?"

Do NOT use for:
- Resolving which of two conflicting overlays governs: that is `conflict-check`.
- What the code text says or which edition is enforced: that is `code-lookup` / `construction-desk`.
- Engineering, code-compliance, or legal advice: out of scope; refer to the AHJ or a licensed professional.

## Inputs
A project location (longitude and latitude in EPSG:4326) and any known facts (county FIPS, ownership
form, habitable stories, certificate-of-occupancy age, elevation, slope). No network is required for
attribute and cached-geometry overlays; a live boundary needs `jurisdictional_overlay_live` on.

## Core procedure
Follow `shared/method.md`. Uses `tools/geo_overlay.py` (offline EPSG:4326 point-in-polygon plus overlay
evaluation) and, only when the live flag is on, `tools/geo_fetch.py` (FEMA NFHL point query). Reads the
optional `canonical-sources/jurisdiction/` overlay records.

### Step 1: gather the location and facts
Collect the point and the project facts. Null-and-flag anything unknown; never guess a value.

### Step 2: evaluate each overlay and cite it
Evaluate attribute overlays against the facts and geometry overlays by containment (cached or, with the
live flag, fetched). Return each applicable overlay with its source citation and the advisory boundary.
Hand the result to `govern-artifact`.

## Output contract
A cited list of applicable advisory overlays (kind, source, and how it was decided) plus the boundary.
No fabricated boundaries or values (`protocols/no-fabrication.md`); geometry whose real boundary is
unverified is labeled and resolved via the live connector or user-supplied data. Honor
`protocols/formatting-metadata.md`.

## Standalone usability
Resolves a location's advisory overlays offline (attribute plus cached geometry), cited and bounded,
with no downstream skill; the live flag adds FEMA flood resolution.

## Failure modes
- `jurisdictional_overlay` off: says the capability is off rather than answering.
- A geometry overlay needing a live boundary while `jurisdictional_overlay_live` is off: returns a
  config gap and points to cached/manual data; never fetches.
- Missing facts: null-and-flags the affected overlay rather than assuming applicability.
