# Jurisdictional Overlay (P37, optional)

An OPTIONAL, advisory add-on to the construction knowledge base. It answers "does this build site fall
inside a flood zone / historic district / hurricane zone / steep-slope / watershed overlay, and when
two rules collide, which governs?" for Florida and North Carolina. It is **advisory planning
information, never a legal or permitting determination** -- genuine legal conflicts escalate to human
review, never auto-resolved. See `docs/JURISDICTION-OVERLAY-PLAN.md` for the full design + cited source
list.

## Two default-off flags (in `creator-os-config.json`)
- **`jurisdictional_overlay`** -- the bucket + engine. Off by default; construction lookups run as
  before without it.
- **`jurisdictional_overlay_live`** -- live GIS queries (FEMA flood lookup). SEPARATE and stricter;
  requires `jurisdictional_overlay` too. With it off, the tool uses only cached / user-supplied
  boundaries and returns a config gap for anything needing a live boundary; **it never makes a surprise
  network call.**

## Overlay kinds
- **geometry** (point-in-polygon): flood zones, historic districts, ridgelines, watersheds. The
  authoritative boundary comes from a live query or user-supplied GeoJSON; any in-repo geometry is a
  labeled illustrative placeholder, never a fabricated real boundary.
- **attribute** (a rule test, no polygon): HVHZ (county FIPS 12086/12011), SB 4D milestone (ownership +
  stories + certificate-of-occupancy age), Buncombe steep-slope (county + elevation), MRPA (elevation
  >= 3000 ft AND >= 500 ft above valley).
- **versioned-fact** (a dated value/edition): SLR projection, adopted code edition, the Rutherford
  "no steep-slope ordinance" correction.

## Components
- `tools/geo_overlay.py` -- offline stdlib engine (EPSG:4326): point-in-polygon (half-open vertex rule,
  holes, multipolygon), bbox pre-filter + true ring test, GeoJSON/KML ingest, overlay-kind evaluation,
  and the conflict-resolution cascade (floor/ceiling preemption + Dillon/Home-Rule authority + lex
  specialis + human-review escape) with a W3C PROV audit. `--selftest`.
- `tools/geo_fetch.py` -- the live connector (gated): FEMA NFHL point flood-zone query
  (ArcGIS REST, `inSR=4326`, `f=geojson`, `returnGeometry=false`) + the `editingInfo.lastEditDate` /
  LOMRs-layer freshness read. stdlib urllib, env proxy + CA bundle, no API key. `--selftest` (offline,
  injected getter).
- `canonical-sources/jurisdiction/*.json` -- the overlay records (cache-indexed via `text`), FL and NC.
- MCP tools: `jurisdiction_resolve(lon, lat, facts_json)` and `overlay_conflict(id_a, id_b)` -- advisory,
  human-gated; resolve honors the flag.
- Currency: sources seeded into `source-registry.json` (category `jurisdiction-gis`); the P36 freshness
  overlay + ArcGIS `lastEditDate` keep them current.

## Coverage today
- **Florida:** HVHZ, SB 4D milestone, SLR freeboard, FEMA flood zone, local historic district.
- **North Carolina:** MRPA protected ridge (statutory test + screening ridgeline), Buncombe
  steep-slope/high-elevation + geotech trigger, Asheville historic/design review (Sec. 7-9-2),
  NC water-supply watersheds, and the Rutherford "no steep-slope ordinance / no countywide zoning"
  correction.

## Licensing (hard boundary)
- **Cache freely (public domain / open):** FEMA NFHL, water-management-district hubs, NC OneMap,
  Buncombe/Rutherford GIS, all statute text.
- **Cache the fact, not the platform:** Municode / American Legal ToS bar scraping; the ordinance text
  is public-domain law (Georgia v. Public.Resource.Org, 2020) -- store the citation + adopted-edition +
  "current-through" date, fetch text from the municipality.
- **Cache the fact, not the text:** ICC/FBC code + Miami-Dade NOAs are copyrighted -- store the
  adopted-edition fact / NOA number + expiration.
- Every overlay and output carries the advisory disclaimer (aligned to FEMA's): advisory and for
  planning only; not an official or legal determination; not a substitute for a FEMA flood
  determination; boundaries may be simplified and may lag the source.

## Using it
```bash
python3 tools/geo_overlay.py --selftest     # engine
python3 tools/geo_fetch.py --selftest       # live connector (offline test)
# In Claude Desktop with both flags on: jurisdiction_resolve(lon, lat, facts_json) and
# overlay_conflict(id_a, id_b). With the live flag off, geometry overlays needing a live boundary
# return a config gap and nothing is fetched.
```

## Non-goals / boundary
- Advisory only; never a legal or permitting determination. Genuine legal conflicts (e.g. a
  historic-frame requirement vs an HVHZ impact-window requirement) return `human_review_required`.
- Offline-first; the live tier is default-off and never called unless both flags are on.
- No heavy C GIS deps in the required path (stdlib + EPSG:4326; reprojection deferred via server-side
  `outSR=4326`). No scraping of Municode/AmLegal or caching of copyrighted code text.
