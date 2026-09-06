---
file: skills/jurisdiction-desk/SKILL.md
name: jurisdiction-desk
description: "the ADVISORY jurisdictional-overlay desk: given a project location in Florida or North Carolina, resolves which location-based rules apply (flood zone, historic district, hurricane zone/HVHZ, steep-slope/ridge, watershed, SB 4D milestone inspection) and, when two overlays collide, which governs, escalating genuine legal conflicts to human review. Composes overlay-resolve and conflict-check over the offline EPSG:4326 engine, then governs the output. On by default (jurisdictional_overlay); live FEMA flood queries and address geocoding are ask-first, once per session (jurisdictional_overlay_live consent). Advisory planning information only, never a legal, permitting, engineering, or code-compliance determination. Do NOT use to answer what the code text says or which edition is enforced (construction-desk / code-lookup), to plan a whole DIY project (project-builder), or to give legal advice."
load: for jurisdiction-overlay requests (does a flood/historic/hurricane/steep-slope/watershed overlay apply at a location, and which conflicting rule governs), when jurisdictional_overlay is enabled
---

# jurisdiction-desk

jurisdiction-desk answers "where am I, and what location-based rules apply?" for a Florida or North
Carolina project. It resolves the applicable ADVISORY overlays and, when overlays conflict, which
governs, always escalating a genuine legal conflict to human review. It is on by default and strictly
advisory; live lookups are ask-first, once per session.

## First line of every output (verbatim)

```
ADVISORY PLANNING INFORMATION ONLY, NOT A LEGAL, PERMITTING, ENGINEERING, OR CODE-COMPLIANCE DETERMINATION. FLOOD, ZONING, AND JURISDICTION OVERLAYS ARE NOT A SUBSTITUTE FOR AN AUTHORITATIVE DETERMINATION (E.G. A FEMA FLOOD DETERMINATION) OR THE AUTHORITY HAVING JURISDICTION. GENUINE CONFLICTS ARE FLAGGED FOR HUMAN REVIEW. VERIFY LOCALLY.
```

## When to use this skill
- "Is my build site in a flood zone / historic district / hurricane zone / steep-slope area?" (routed
  as `jurisdiction_overlay`).
- "Does the SB 4D milestone inspection apply to this condo?"
- "Which rule wins here, the historic-district requirement or the hurricane code?"

Do NOT use for:
- What the code text says or which edition a jurisdiction enforces: that is `construction-desk`
  (`code-lookup`).
- Planning a whole DIY project end to end: that is `project-builder`.
- Legal, permitting, engineering, or code-compliance advice: out of scope; refer to the AHJ or a
  licensed professional.

## Inputs
A project location (longitude and latitude in EPSG:4326) and any known building facts (county FIPS,
ownership form, habitable stories, certificate-of-occupancy age, elevation, slope). No network is
required for attribute and cached-geometry overlays; a live FEMA flood boundary or address geocoding
runs only with per-session live consent (`jurisdictional_overlay_live`, ask-first). Requires the
`jurisdictional_overlay` capability (on by default).

## Core procedure
Follow `shared/method.md`. Compose atoms via `workflow.json`.

### Step 1: resolve the applicable overlays
`overlay-resolve` evaluates each overlay for the location and facts (attribute rules offline; geometry
by containment against a cached or, with per-session live consent, fetched boundary), each cited.

### Step 2: resolve conflicts (only when two applicable overlays collide)
`conflict-check` runs the precedence cascade and returns the governing overlay or
`human_review_required`, with the W3C PROV audit.

### Step 3: govern and emit the boundary
Hand the assembled result to `govern-artifact`; emit the advisory boundary.

## Output contract
The applicable advisory overlays (each cited to its GIS/statutory source and how it was decided), any
conflict decision (or the human-review flag) with its audit, and the boundary. No fabricated boundaries
or values (`protocols/no-fabrication.md`); no copyrighted code text or NOAs; honor
`protocols/formatting-metadata.md`.

## Engines and protocols loaded
`shared/construction-engine.md` (for FL/NC edition context); `protocols/safety.md`,
`protocols/no-fabrication.md`, `protocols/research-citation.md`, `protocols/quality-gates.md`,
`protocols/formatting-metadata.md`.

## Atoms used
`overlay-resolve`, `conflict-check`, and `govern-artifact`. Each is directly callable by the user.

## Standalone usability
Resolves a location's advisory overlays and any conflicts offline, cited and bounded, with no network
unless per-session live consent is granted.

## Cross-modality
Class: C.
Runs on: Claude Desktop/Code (native, MCP + the tool module); claude.ai via a hosted remote-MCP connector; Custom GPT / Gemini only when the tool is hosted behind a remote MCP or an Action; Gems: no.
Mechanism: Class C: MCP `jurisdiction_resolve`/`overlay_conflict` run deterministic local compute in tools/geo_overlay.py — ray-casting point-in-polygon (half-open vertex rule, hole-aware, bbox prefilter) over canonical-sources/jurisdiction/*.json cached geometries plus the floor/ceiling-preemption + authority-rank + comparable-stringency + lex-specialis conflict cascade; live FEMA NFHL ArcGIS queries (tools/geo_fetch.py) and geocoding (tools/geo_geocode.py) are the offloadable Class-B rung.
Fallback: No local runtime -> the geometry question offloads to the public FEMA NFHL / ArcGIS / Census endpoints (server-side point-in-polygon) via the GPT Action / Gemini function declarations, but the conflict cascade degrades to engine-guided reasoning with human_review_required; no network -> cached boundaries + null-flagged values; Gems -> ask the user for a lon/lat and reason over pasted overlay records, advisory boundary always attached. On ChatGPT this is reasoning-only and outputs are labeled provisional (no local tools, no flag enforcement); the desktop app can reach the full tool only via a deployed remote MCP connector in developer mode (implementation/gpt/mcp-connector/README.md).
See `shared/cross-modality-engine.md`.

## Failure modes
- `jurisdictional_overlay` off: says the capability is off rather than answering.
- A geometry overlay needing a live boundary without per-session live consent (declined or headless):
  returns a config gap and points to cached/manual data; never fetches.
- A genuine legal conflict: returns `human_review_required`, never a fabricated winner.
