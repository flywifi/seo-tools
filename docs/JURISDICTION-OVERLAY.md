# Jurisdictional Overlay (P37/P38)

An advisory add-on to the construction knowledge base. It answers "does this build site fall inside a
flood zone / historic district / hurricane zone / steep-slope / watershed overlay, and when two rules
collide, which governs?" for Florida and North Carolina. It is **advisory planning information, never a
legal or permitting determination** -- genuine legal conflicts escalate to human review, never
auto-resolved. See `docs/JURISDICTION-OVERLAY-PLAN.md` for the full design + cited source list.

## Configuration + the consent model (in `creator-os-config.json`)
- **`jurisdictional_overlay`** -- the master feature switch. **On by default** (P38); the
  `canonical-sources/jurisdiction/` bucket ships with the download and loads when this is on. On-by-
  default means *available*, never a determination: every output still carries the advisory boundary
  and still escalates genuine conflicts to human review.
- **`jurisdictional_overlay_live`** -- the **live-network consent policy** (P38), governing both the
  FEMA flood lookup (`geo_fetch.py`) and address geocoding (`geo_geocode.py`). Default-on but
  **ask-first, once per session** (`mode: ask`, `cadence: per_session`, enforced by `geo_consent.py`):
  the first live lookup in a session asks the human; nothing is fetched until granted; a grant covers
  the session; a decline **or a headless run** (no interactive prompt) falls back with **no network
  call**. Set `mode: never` (or `enabled: false`) to disable live lookups entirely; `mode: always` to
  pre-grant. The "never a surprise network call" guarantee holds -- it asks instead of staying dark.

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
- `tools/geo_consent.py` -- the unified live-network consent policy (default-on, ask-first per
  session; headless/declined falls back with no call). `--selftest`.
- `tools/geo_geocode.py` -- address to lon/lat via the keyless U.S. Census geocoder, consent-gated.
  `--selftest` (offline, injected getter).
- `tools/geo_fetch.py` -- the live FEMA connector, routed through the consent policy: FEMA NFHL point
  flood-zone query (ArcGIS REST, `inSR=4326`, `f=geojson`) + the `editingInfo.lastEditDate` freshness
  read. stdlib urllib, env proxy + CA bundle, no API key. `--selftest` (offline).
- `tools/geo_source_fetch.py` -- the universal-path fetcher / build-time cacher: resolve an address
  against public ArcGIS/FEMA/Census endpoints (server-side point-in-polygon), and
  `--cache-orlando` writes the real boundary polygons (with provenance) into `orlando-boundaries/`.
- `tools/geo_e2e_proof.py` -- synthetic + real-record architecture proof (consent, no-fabrication,
  conflict escalation, cache-ref boundaries).
- `canonical-sources/jurisdiction/*.json` -- the overlay records (cache-indexed via `text`), FL, NC,
  and Orlando/Orange. `*.example.json` are schema demos, never loaded for production resolution.
- `canonical-sources/jurisdiction/orlando-boundaries/*.geojson` -- real City of Orlando boundary
  polygons (with `.provenance.json` sidecars); records reference them via `geometry_ref: "cache:..."`.
- MCP tools: `jurisdiction_resolve(lon, lat, facts_json)` and `overlay_conflict(id_a, id_b)` -- advisory,
  human-gated.

## Coverage today
- **Florida (statewide/regional):** FL Building Code edition (8th/2023), HVHZ (Miami-Dade/Broward),
  SB 4D milestone, SLR freeboard (SE FL Compact counties), FEMA flood zone (live, nationwide).
- **Orlando / Orange County (real, cached within ~2 mi of Lake Eola):** all 6 City local historic
  districts (real boundary polygons; COA per City Code Ch. 62 sec. 62.200), R-2B/Traditional
  City/Historic Preservation zoning (real boundary; front-setback value null-flagged, lives in the
  Ch. 58 Municode tables), Orange County design wind speed + Wind-Borne Debris Region (safety
  versioned-facts, values null-flagged pending an official ASCE 7 point read), and SJRWMD watershed
  (live).
- **North Carolina:** MRPA protected ridge (statutory test + screening ridgeline), Buncombe
  steep-slope/high-elevation + geotech trigger, Asheville historic/design review, NC water-supply
  watersheds, and the Rutherford "no steep-slope ordinance / no countywide zoning" correction (scoped
  to Rutherford County FIPS).

## Currency (regular updates)
Every source is seeded into `source-registry.json` (categories `jurisdiction-gis` + `legal-authority`)
with a change-detection signal and license, and each overlay file is watched in
`data-currency-map.json`. Baselines are stamped (`last_checked` + sha256) so
`python3 tools/source_currency.py check --detect-changes --apply` catches future drift token-free; GIS
layers also expose `editingInfo.lastEditDate`. Refresh the cached Orlando boundaries any time with
`python3 tools/geo_source_fetch.py --cache-orlando`. Values behind ToS-limited code portals (Municode
setback tables, ICC/FBC text) are tracked as the adopted-edition fact, never scraped.

## Cross-modality access (the universal path)
Every endpoint does point-in-polygon server-side, so any surface that can make an HTTPS request gets
the same answer: Claude Desktop/Code (native, offline engine + consent-gated live), claude.ai
web/mobile (hosted remote-MCP connector), Custom GPT (a GPT Action over the public REST), the Gemini
API (function calling), or a human with `curl`. The one dead end is the consumer Gemini "Gems" UI (no
custom-tool surface). Full per-surface access matrix + packaging: **`docs/CROSS-MODALITY.md`**, the GPT
Action `implementation/gpt/actions/jurisdiction_overlay_action.yaml`, and the Gemini declarations
`implementation/gemini/jurisdiction-function-declarations.json`.

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
python3 tools/geo_overlay.py --selftest       # offline engine
python3 tools/geo_consent.py --selftest       # consent policy
python3 tools/geo_geocode.py --selftest       # address->point (offline test)
python3 tools/geo_fetch.py --selftest         # FEMA connector (offline test)
python3 tools/geo_e2e_proof.py                # end-to-end architecture proof
# Universal path (any surface / a human): resolve an address against the public endpoints
python3 tools/geo_source_fetch.py resolve "809 E Amelia St, Orlando FL 32803"
# In Claude Desktop: jurisdiction_resolve(lon, lat, facts_json) and overlay_conflict(id_a, id_b).
# The first live lookup in a session asks for consent; decline/headless -> config gap, nothing fetched.
```

## Non-goals / boundary
- Advisory only; never a legal or permitting determination. Genuine legal conflicts (e.g. a
  historic-frame requirement vs an HVHZ impact-window requirement, or a safety floor vs an aesthetic
  rule) return `human_review_required`; a safety floor is never silently discarded.
- Offline-first; the live tier is default-on but ask-first, and never called without per-session
  consent (or at all when headless).
- No heavy C GIS deps in the required path (stdlib + EPSG:4326; reprojection deferred via server-side
  `outSR=4326`). No scraping of Municode/AmLegal or caching of copyrighted code text; ToS-limited
  values are null-flagged, not fabricated.
