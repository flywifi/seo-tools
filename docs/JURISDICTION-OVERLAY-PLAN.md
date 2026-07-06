# Plan: Jurisdictional Overlay as an Optional Scoop-Style Bucket (P37)

Status: PLAN (research complete; Phase 1 building). This document is the durable record of the
research and the design for adding an OPTIONAL jurisdictional-overlay bucket on top of the existing
`canonical-sources/construction/` building-code base. It is advisory planning information, never a
legal or permitting determination.

Research base: 6 agents (offline-GIS feasibility; internal scoop/construction architecture map; FL
overlay data sources; NC overlay data sources; rules-as-data/conflict-resolution prior art;
geospatial data currency + caching), all URL-cited; key citations preserved in Section 8.

## 1. Verdict
Most of the pasted six-level overlay matrix can become an optional `canonical-sources/jurisdiction/`
bucket that plugs into the scoop cache, the construction base, and the P36 freshness system, entirely
offline-first. The one honest caveat: **true geospatial capability is 100% net-new** — today
"jurisdiction" is only a string key (`"FL"/"NC"`) plus hand-authored county to climate-zone tables;
there is no lat/lon, bbox, or polygon anywhere in the repo.

## 2. Incorporate / adapt / defer
- **Incorporate:** the 6-level hierarchy as the record data model; multi-format GIS ingest +
  point-in-polygon (stdlib, EPSG:4326); AUTO/FORCE_OFF overrides (via the P36 user overlay, since they
  are personal state); inter-overlay conflict resolution as cited data + a cascade; the seed data
  registry via `source-registry` + P36 currency.
- **Adapt:** the live-print pipeline into an atom/spoke + MCP tool, human-gated + disclaimered.
- **Defer to an optional flag-gated tier:** CRS reprojection (EPSG:2236/32119 to 4326) — requires PROJ
  (C); avoid by requesting `outSR=4326` server-side.

## 3. Overlay-kind taxonomy (key design insight)
Not every overlay is a polygon. Three kinds:
- **geometry** (point-in-polygon): FEMA flood zones, historic districts, MRPA ridgelines, Buncombe
  steep-slope/ridge overlays, NC water-supply watersheds, river basins.
- **attribute** (no polygon; a FIPS/rule test): HVHZ = all of Miami-Dade + Broward (statutory,
  F.S. 553; ASCE 7-22); SB 4D milestone inspection = stories + ownership + certificate-of-occupancy
  age (F.S. 553.899).
- **versioned-fact** (a dated number/edition): SE-FL Compact SLR projection; adopted code editions.

## 4. Bucket design (plugs into existing machinery)
- **Data bucket** `canonical-sources/jurisdiction/*.json`: auto-indexed by the scoop cache (records are
  a JSON array of `{id, title, text, ...}` with a non-empty `text`); zero cache-code change.
- **Record schema** (synthesized from open standards): a LegalRuleML-shaped envelope (source citation,
  `jurisdiction_level`, temporal validity, defeasibility) + ACCORD AEC3PO internal decomposition
  (`feature_of_interest` applicability -> `property`/constraint -> `check_method` -> and/or) + an
  OpenFisca-style `{value, effective_date, source_reference}` on every numeric threshold (the same
  provenance envelope P36 ships) + `overlay_kind` + `geometry_ref` (cached simplified GeoJSON path or a
  live-query endpoint id) + `boundary: "advisory-not-legal-determination"` + `source_ids[]` +
  `code_refs[{section,edition,url}]`.
- **Offline GIS engine** `tools/geo_overlay.py` (stdlib + optional `pyshp`): pure-Python
  ray-casting/winding point-in-polygon in EPSG:4326 only, with the documented edge cases (half-open
  vertex rule, holes, multipolygon, antimeridian, `[lon,lat]` normalization per RFC 7946); bbox
  pre-filter then true ring test (report which tier decided). Ingest GeoJSON (stdlib json), KML (stdlib
  xml.etree), Shapefile (pyshp, optional), WFS/ArcGIS/OGC (stdlib urllib requesting GeoJSON). Heavy
  ops (reprojection, buffer, metric area) flag-gated + degrade. If pyshp is used, register it as a
  `software-dependency` (invariant 23). Offline selftest.
- **Live-query vs cached-boundary:** live-query FEMA NFHL and anything large or license-restricted;
  cache small public-domain slow-changing polygons in-repo, simplified (topology-aware, ~5-decimal
  precision) with provenance stored alongside.
- **Currency (reuse P36):** seed FL/NC endpoints into the registry; add each `jurisdiction/*.json` to
  `data-currency-map.json`; a GIS freshness ladder OGC ETag/304 -> ArcGIS `editingInfo.lastEditDate`
  -> data.gov DCAT `modified` -> sha256 metadata -> sha256 response. (FEMA NFHL layer 28 has no
  lastEditDate; poll the LOMRs layer 1 instead.) New category `jurisdiction-gis` in traversal-config.
- **Conflict resolution as cited data + cascade:** per-rule `jurisdiction_level` (ordinal),
  `preemption_type in {floor, ceiling, field, none}` (Buzbee), `local_authority in {home_rule,
  dillon_expressly_granted, dillon_denied}`, `specificity_scope`. Cascade: (1) field/ceiling -> higher
  governs; (2) floor + local authority -> most-stringent governs; (3) lex specialis -> most-specific
  scope; (4) genuine legal conflict -> `human_review_required`, never auto-resolved. Each decision
  wrapped as a W3C PROV activity for audit.
- **Flag-gated + drift-clean + consumer glue:** capability `jurisdictional_overlay` (default off,
  master-gate pattern; read-only lookups degrade-not-fail); a sibling `check_jurisdiction()` drift
  invariant (invariant 22 is hard-coded to the construction path); a `jurisdiction-desk` spoke + atoms
  + MCP tools interoperating with construction-desk / code-lookup.

## 5. Licensing tiers (hard boundary)
- **Cache freely (public domain / open):** FEMA NFHL, the 5 FL Water Management District ArcGIS hubs +
  FGDL + FL GIO + FDEP, NC OneMap, MRPA ridgelines, Buncombe & Rutherford county GIS, all statute text
  (17 U.S.C. 105; per-layer metadata).
- **Cache the FACT, not the PLATFORM:** Municode / American Legal ToS bar scraping, but the ordinance
  text is public-domain law (Georgia v. Public.Resource.Org, 2020). Store citation + adopted-edition +
  "current-through" date; fetch text from the municipality. (They also 403 automated fetchers.)
- **Cache the FACT, not the TEXT:** ICC/FBC code + Miami-Dade NOAs are copyrighted; store the
  adopted-edition fact / NOA-number+expiration only.
- **Every overlay carries the advisory disclaimer**, aligned to FEMA's: "advisory and for planning
  only; not an official or legal determination; not a substitute for a FEMA flood determination;
  boundaries may be simplified and may lag the source."

## 6. Research corrections to the source payload (verified)
- Rutherford County has NO steep-slope ordinance and no countywide zoning; there is no "Chapter 150 -
  Steep Slope Construction Controls." Controls reduce to Watershed/Flood/Subdivision/Solar ordinances;
  county GIS exposes parcels+flood only, so slope must be DEM-derived.
- Asheville historic/design overlay is Code Sec. 7-9-2, not 7-9-3.
- HVHZ and SB 4D are attribute/statutory rules, not polygons.
- MRPA ridgeline layer is topo-map-digitized (screening only); true determination needs the statutory
  test (>=3,000 ft AND >=500 ft above valley) + LiDAR.

## 7. Phasing (each optional; each lands independently, verified, pushed)
1. **Engine + data model** (zero network): `tools/geo_overlay.py` + the `jurisdiction/` record schema +
   `jurisdictional_overlay` flag + `check_jurisdiction()` invariant + selftest.
2. **Cached FL slice**: a couple of public-domain FL overlays as simplified in-repo GeoJSON; seed
   sources; currency wiring; conflict cascade + PROV audit; a worked FL fixture (historic vs HVHZ).
3. **Live-query connector**: FEMA NFHL point flood-zone query (flag-gated, env proxy/CA bundle,
   advisory disclaimer) + the ArcGIS/OGC freshness ladder.
4. **NC slice**: MRPA ridgelines + Buncombe overlays (cached); Rutherford as attribute/DEM-derived; NC
   watersheds.
5. **Spoke + MCP + docs**: `jurisdiction-desk`, MCP tools, docs, ledger/STATE, full battery.

## 8. Cited source list (verified as of 2026-07-05)

### Offline GIS feasibility
- Point-in-polygon: https://en.wikipedia.org/wiki/Point_in_polygon ; Haines, Graphics Gems IV,
  https://erich.realtimerendering.com/ptinpoly/
- GeoJSON RFC 7946 (WGS84-only, [lon,lat], holes, antimeridian): https://datatracker.ietf.org/doc/html/rfc7946
- pyshp (MIT, pure Python): https://pypi.org/project/pyshp/ ; fastkml (LGPL): https://pypi.org/project/fastkml/ ;
  OWSLib (BSD): https://github.com/geopython/OWSLib
- EPSG:4326 https://epsg.io/4326 ; 2236 https://epsg.io/2236 ; 32119 https://epsg.io/32119
- Heavy stack (why optional): shapely/GEOS https://libgeos.org/ ; fiona/GDAL https://fiona.readthedocs.io/ ;
  pyproj/PROJ https://proj.org/ ; geospatial native-deps https://pypackaging-native.github.io/key-issues/native-dependencies/geospatial_stack/
- Simplification: mapshaper https://mapshaper.org/docs/guides/simplification.html ; RDP https://rosettacode.org/wiki/Ramer-Douglas-Peucker_line_simplification

### GIS query + currency
- ArcGIS REST query: https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/ ;
  layer editingInfo/lastEditDate: https://developers.arcgis.com/rest/services-reference/layer-feature-service-.htm
- OGC API - Features (ETag/304, bbox): https://docs.ogc.org/is/17-069r3/17-069r3.html ; overview https://ogcapi.ogc.org/features/overview.html
- WFS (GeoServer): https://docs.geoserver.org/stable/en/user/services/wfs/reference.html
- FEMA NFHL MapServer: https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer (layer 28 flood zones; layer 1 LOMRs)
- 17 U.S.C. 105 (public domain): https://www.law.cornell.edu/uscode/text/17/105 ; OpenFEMA terms https://www.fema.gov/about/openfema/terms-conditions

### Florida sources
- FEMA MSC https://msc.fema.gov/ ; NFHL metadata https://hazards.fema.gov/filedownload/metadata/NFHL/NFHL_metadata.xml
- Miami-Dade product approval/NOA https://www.miamidade.gov/global/economy/board-and-code/product-approval-notices.page ;
  statewide https://floridabuilding.org
- SB 4D / F.S. 553.899 https://www.flsenate.gov/Laws/Statutes/2025/553.899
- WMDs: SFWMD https://geo-sfwmd.hub.arcgis.com/ ; SWFWMD https://data-swfwmd.opendata.arcgis.com/ ;
  SJRWMD https://www.sjrwmd.com/data/gis/ ; NWFWMD https://nwfwmd-open-data-nwfwmd.hub.arcgis.com/ ;
  statewide ERP https://hub.arcgis.com/datasets/FDEP::erp-permits-current-sfwmd
- Historic (Miami) https://datahub-miamigis.opendata.arcgis.com/datasets/MiamiGIS::historic-districts/about
- SLR: SE FL Compact https://southeastfloridaclimatecompact.org/sea-level-rise/ ; F.S. 163.3178
- FGDL https://fgdl.org/explore-data/ ; FL GIO https://geodata.floridagio.gov/ ; FDEP https://geodata.dep.state.fl.us/
- Municode ToS https://www.municode.com/code/page/terms-use ; AmLegal ToS https://amlegal.com/terms-of-use ;
  Georgia v. Public.Resource.Org, 590 U.S. 255 (2020)

### North Carolina sources
- NC OneMap https://www.nconemap.gov/ ; FRIS https://fris.nc.gov/
- MRPA (Ch. 113A Art. 14) https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_113A/Article_14.html ;
  MRPA ridgelines FeatureServer https://services1.arcgis.com/YBWrN5qiESVpqi92/arcgis/rest/services/mrpa_ridgelines/FeatureServer
- Buncombe zoning ordinance (Ch.78 Art.VI, secs 78-644 steep-slope / 78-645 ridge)
  https://media.buncombenc.gov/common/planning/zoning/zoning-ordinance.pdf ;
  Buncombe GIS https://gis.buncombecounty.org/arcgis/rest/services/bcmap_vt/MapServer (layer 7 Protected Ridges, 20 County Zoning Overlay)
- Rutherford GIS (parcels/flood only; no zoning/slope) https://gis.rutherfordcountync.gov/server/rest/services/ReferenceLayers/MapServer ;
  planning ordinances https://www.rutherfordcountync.gov/departments/planning/ordinances_and_affidavits.php
- Asheville historic/design overlay Code Sec. 7-9-2 ; data.ashevillenc.gov
- NC OSFM (editions) https://www.ncosfm.gov/

### Rules-as-data / conflict-resolution prior art
- LegalRuleML Core v1.0 (OASIS) https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/legalruleml-core-spec-v1.0-os.pdf
- ACCORD AEC3PO ontology https://accordproject.eu/building-compliance-ontology-released/ ; CHEK https://chekdbp.eu/
- BLDS (open permit schema) https://azavea.gitbooks.io/open-data-standards/content/standards/domain_specific_standards/building_land_development_specification_blds.html
- OpenFisca (value+date+reference) https://openfisca.org/doc/coding-the-legislation/legislation_parameters.html ;
  Catala https://catala-lang.org/
- Floor/ceiling preemption (Buzbee, NYU L Rev 82:6) https://nyulawreview.org/wp-content/uploads/2018/08/NYULawReview-82-6-Buzbee.pdf ;
  Dillon's Rule vs Home Rule https://www.publichealthlawcenter.org/sites/default/files/resources/Dillons-Rule-Home-Rule-Preemption.pdf
- Drools salience https://docs.jboss.org/drools/release/5.3.0.Final/drools-expert-docs/html/ch01.html ;
  ODRL conflict strategy https://www.w3.org/TR/odrl-model/ ; W3C PROV https://www.w3.org/TR/prov-overview/ ;
  Akoma Ntoso https://docs.oasis-open.org/legaldocml/akn-core/v1.0/cs01/part1-vocabulary/akn-core-v1.0-cs01-part1-vocabulary.html

### Internal architecture plug-in points
- Scoop cache indexes canonical-sources/**/*.json list-of-{id,title,text} records (shared/cache/cache.py).
- Construction record schema + drift invariant 22 (construction path hard-coded), invariant 25
  (currency-map), 26 (freshness bundle) in tools/sync_check.py.
- Config-flag master-gate pattern (contract_management) in creator-os-config.json.
- Currency wiring: source_currency.py seed-sources -> source-registry.json -> data-currency-map.json ->
  P36 freshness_overlay.py.

## 9. Non-goals / risks
- Advisory only; not a legal or permitting determination; genuine conflicts route to human review.
- No heavy C GIS deps in the required path; reprojection avoided via server-side outSR=4326.
- No scraping of Municode/AmLegal or copyrighted code text; facts only.
- Large net-new geospatial capability; ship Phase 1 (offline engine + model, zero network) first.
