# 21. P37 Jurisdictional Overlay

- Date: 2026-07-06
- Status: Accepted

## Context

The construction base knew what the code says but nothing about WHERE a project is; the user pasted a six-level jurisdictional-overlay architecture (GIS ingestion, CRS, point-in-polygon, overrides, conflict resolution) and asked for a plan to fold the applicable parts into an optional scoop-style bucket. Six cited research agents established that a correct multi-format point-in-polygon is fully doable offline in stdlib + EPSG:4326 (no shapely/geopandas/pyproj), that not every overlay is a polygon (HVHZ and SB 4D are statutory attribute rules; SLR is a versioned fact), that the authoritative conflict model is floor/ceiling preemption + Dillon/Home-Rule authority + lex specialis (LegalRuleML/ACCORD/OpenFisca), and that government GIS is largely public-domain and ArcGIS-REST/OGC queryable with editingInfo/ETag freshness signals. The whole thing reuses the existing cache + currency + construction record/drift patterns and stays advisory + cite-only, matching the repo's discipline.

## Decision

Add an optional, advisory jurisdictional-overlay bucket on top of the construction knowledge base: given a project location, resolve whether it falls inside a flood zone / historic district / hurricane zone / steep-slope / watershed overlay (geometry, attribute, or versioned-fact) and, when two rules collide, which governs -- escalating genuine legal conflicts to human review. Offline stdlib engine in EPSG:4326, a live FEMA connector behind a second default-off flag, FL + NC data, plugged into the scoop cache and the P36 freshness system. Advisory planning information only, never a legal or permitting determination.

## Consequences

**Explicitly not done:** Advisory only; never a legal or permitting determination. No heavy C GIS dependencies in the required path (stdlib + EPSG:4326; reprojection deferred via server-side outSR=4326). No scraping of Municode/American Legal, and no caching of copyrighted model-code text or NOAs (facts/citations only). Live GIS queries are default-off behind a separate flag; the whole core works fully offline. Rutherford County modeled honestly (no steep-slope ordinance / no countywide zoning) so the engine never falsely applies one.

Ledger status at record time: `shipped`. Source: `ledger/ledger.json` id `P37-jurisdictional-overlay`.
