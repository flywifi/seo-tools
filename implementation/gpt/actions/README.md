# Creator OS — GPT Actions (public-endpoint capabilities)

Unlike `implementation/gpt/api/` (OpenAI **function specs**, where your backend executes the call),
these are **GPT Actions**: OpenAPI schemas a no-code Custom GPT imports so the GPT calls a public
endpoint itself. This is the "universal path" (see `docs/CROSS-MODALITY.md`).

## Files
| File | What it does |
|---|---|
| `jurisdiction_overlay_action.yaml` | ADVISORY jurisdictional overlays: geocode an address (US Census) and resolve local historic district / zoning (City of Orlando) + FEMA flood zone at the point. Keyless (auth = none). |

## Add it to a Custom GPT
1. GPT builder → Configure → **Create new Action**.
2. Paste the contents of `jurisdiction_overlay_action.yaml` into the schema box.
3. Authentication = **None** (all endpoints are public/keyless).
4. In the GPT instructions, require the advisory line on every answer and route genuine
   safety-vs-aesthetic conflicts to human review (never auto-decide).

## Notes
- The schema uses per-operation `servers` overrides for the three hosts (Census, Orlando ArcGIS, FEMA).
  If a GPT importer rejects that, split into one Action per host.
- ArcGIS/FEMA/Census run server-side point-in-polygon, so the GPT needs no GIS engine.
- Coverage of local historic/zoning here is City of Orlando; flood + geocoding are nationwide.
- ADVISORY ONLY; not a legal/permitting/engineering determination. Setback numbers behind ToS-limited
  code portals are not returned; cite the ordinance and verify locally.

## Consent asymmetry (read before adding the Action)

On your computer, live jurisdiction lookups are gated by an ask-first consent step
(`tools/geo_consent.py`); a headless run or a decline makes no network call. A GPT Action
has no such seam: the GPT calls the public geocoder and GIS endpoints directly from
OpenAI's infrastructure, so whatever the user types (for example a street address) goes to
OpenAI and to those public endpoints with no local ask-first step. Say so in the GPT's
description, and see docs/PASTE-SAFETY.md for what should never be typed into a GPT.
