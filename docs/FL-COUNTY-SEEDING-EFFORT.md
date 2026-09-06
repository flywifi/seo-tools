# Florida County Seeding: Effort Estimate

Status: research memo (advisory). Date: 2026-07-06. Scope: what it would take to seed the optional
jurisdictional-overlay bucket (P37) for all 67 Florida counties. Sourced from three cited research
passes; every material claim carries a source URL in the citations section.

## Question
How much effort is it to "seed every county in Florida" for the advisory jurisdictional-overlay
bucket (attribute rules keyed on county FIPS, geometry rules resolved against GIS boundaries, and
versioned-facts)?

## Headline
"Every county" is two very different jobs:

1. **County-and-statewide layer** (flood, water district, wind region, HVHZ, code edition, SB 4D,
   NRHP historic, land use): cheap and largely automatable. About **2 to 4 weeks** of engineering,
   after which all 67 counties resolve these overlays, because most are single statewide layers or
   one nationwide endpoint.
2. **Local zoning + historic-district design-review layer**: a months-long, partly manual
   data-curation program. No statewide dataset can shortcut it, and platform Terms of Service bar
   bulk scraping of the code text.

Which interpretation is meant changes the effort by an order of magnitude.

## The cost model (three tiers)

| Tier | Overlay | How it scales to 67 counties | Effort |
|---|---|---|---|
| 0. Statewide-uniform | FL Building Code (8th/2023), SB 4D milestone | 1 record each, covers all 67 | ~done, trivial |
| 0. Nationwide live | FEMA flood (NFHL layer 28) | 1 endpoint, every county, zero per-county setup | done (P37) |
| 1. Small fixed set | HVHZ (2 counties), 5 Water Management Districts, Wind-Borne Debris Region, SLR | a handful of records; WMD/WBDR need geometry, not FIPS | ~1 week |
| 2. Per-county, statewide-backed | county FIPS scaffold (67), NRHP historic (points), land use / future land use | ~6 to 8 statewide endpoints + a generated 67-row scaffold | ~1 to 2 weeks |
| 3. Long tail | local zoning + setbacks, local historic districts (design review) | ~478 distinct jurisdictions; setbacks per zoning district = thousands of rows; no statewide roll-up; ToS-limited | months, partly manual |

## What is cheap: statewide aggregators cover all 67 in one fetch each
- **Flood**: one nationwide FEMA endpoint, NFHL layer 28, already wired in P37. No per-county work.
- **Building code and SB 4D**: genuinely uniform statewide. The Florida Building Code is a single
  statewide standard, 8th Edition (2023), mandatory effective 2023-12-31. SB 4D / Fla. Stat. 553.899
  applies by building attributes (condo/co-op, 3+ stories, 30 years old, or 25 within 3 miles of
  coast), not by county. 1 record each.
- **Water districts, land use, transportation, NRHP historic**: the Florida Geographic Data Library
  (FGDL), the State GIO portal (geodata.floridagio.gov), FDOT, FDEP, and NPS/FNAI publish these as
  single statewide layers covering all 67 counties.

## Three modeling traps (where naive seeding breaks)
1. **WMD and WBDR are not county attributes.** Water Management District boundaries follow
   watersheds, so roughly 12 to 18 counties are split across two or more districts; a county-FIPS
   lookup misassigns them. The Wind-Borne Debris Region is a wind-speed contour (ultimate design
   wind speed at or above 140 mph, plus a coastal 130 mph band), not a county list. Both must be
   geometry rules. Only HVHZ (Miami-Dade and Broward) is legitimately county-keyed.
2. **Local zoning has no statewide dataset, by law.** Zoning is home rule: 67 counties plus about
   411 municipalities is roughly 478 separate zoning jurisdictions, and setbacks vary per zoning
   district (dozens of rows each), so the real unit count is in the thousands, not 67.
3. **Local historic districts are the true long tail.** The districts that trigger design review /
   a Certificate of Appropriateness are locally designated. Florida lists 88 Certified Local
   Governments, a reasonable floor for jurisdictions with an active program. Each holds its boundary
   only in its own GIS, with no open statewide aggregation.

## The licensing wall (confirmed)
Municode and American Legal Publishing host most jurisdictions' codes, but their Terms of Service bar
bulk reproduction. The workable boundary (unchanged from P37): cite the adopted-edition fact and the
ordinance number/section (facts and citations are not copyrightable), but pull setback values from
each jurisdiction's own published land-development-code table or GIS, never by scraping the platform
text. The Florida Master Site File (statewide historic inventory) is also gated: no self-service
download, and precise archaeological locations are Sunshine-law exempt.

## Data-availability reality for the long tail
Only about 35 of 67 counties, plus the large cities (Orlando, Tampa, St. Petersburg, Miami-Dade),
publish queryable open ArcGIS zoning/overlay services. The other roughly 32, mostly small or rural,
are PDF-map or records-request only, so they need manual sourcing or a statewide-layer fallback for
those specific local layers. This county count is a planning estimate, not a verified enumeration.

## What it would take, by interpretation
**A. Statewide + county-level overlays for every county** (flood, WMD, WBDR, HVHZ, code, SB 4D,
NRHP, land use): about **2 to 4 weeks** of engineering. Build a seeding harness that generates a
67-row county FIPS scaffold, registers about 8 statewide endpoints as geometry references, adds the
WMD and WBDR geometry rules with split-county handling, and wires currency plus the drift invariant.
Mostly automatable.

**B. Full local coverage** (zoning setbacks + local historic design review for every jurisdiction):
**months**, and largely a data-ops effort rather than engineering. About 478 jurisdictions, thousands
of per-district setback rows, 80 to 100 local historic programs with no roll-up, about 32 counties
with no open data, all under a no-scrape ToS. This is an ongoing curation program, not a one-time
seed.

## Recommendation
Do interpretation A as a real phase (P39), and handle the long tail on demand rather than up front.
The on-demand path fits the "users control their own data" principle already in the system: a user
working in a specific jurisdiction supplies, or the deployment caches, that one jurisdiction's
historic/zoning boundary through the existing user-supplied-boundary path when it is actually needed.
That delivers statewide breadth quickly without a multi-month, ToS-constrained scrape of the whole
state.

## Uncertainties (minority report)
- Municipality count is about 411 plus or minus 3; it drifts as jurisdictions incorporate or
  dissolve. The 478 zoning-jurisdiction figure slightly overstates distinct active schemes because a
  few tiny towns defer zoning to the county.
- The 35-versus-32 open-data county split is a reasoned planning estimate; no authoritative
  enumeration of which counties run an open portal was found.
- The split-county count for water districts (about 12 to 18) is directional; verify against the
  actual WMD boundary layer before finalizing.
- A Florida National-Register district-only count could not be isolated (the greater-than-1,900
  figure bundles individual listings with districts), and NPS/FNAI district boundary-polygon
  completeness is unverified (their spatial data is historically point-centroid).
- A 9th-edition Florida Building Code cycle was referenced in one secondary source; not verified as
  adopted. Track as a versioned-fact for currency.

## Source citations
Jurisdiction structure and code:
- https://en.wikipedia.org/wiki/List_of_municipalities_in_Florida
- https://www.floridaleagueofcities.com/wp-content/uploads/2025/06/FL-City-Fact-Sheet.pdf
- https://floridadep.gov/owper/water-policy/content/water-management-districts
- https://en.wikipedia.org/wiki/Water_management_districts_in_Florida
- https://www.swfwmd.state.fl.us/about/floridas-water-management-districts
- https://www.sjrwmd.com/about/maps/
- https://www.floridabuilding.org/bc/bc_default.aspx
- https://up.codes/viewer/florida/fl-building-code-2023
- https://www.flsenate.gov/Laws/Statutes/2025/553.899
- https://www.floridaroof.com/windborne-regions-explained-FL
- https://www.floridabuilding.org/fbc/commission/FBC_0525/HRAC/Final_Report_WBDR.pdf

Statewide GIS aggregators and flood:
- https://fgdl.org/ , https://fgdl.org/explore-data/ , https://www.geoplan.ufl.edu/portfolio/fgdl/
- https://geodata.floridagio.gov/ , https://www.floridagio.gov/
- https://geodata.dep.state.fl.us/ , https://floridadep.gov/otis/enterprise-application-services/gis
- https://gis-fdot.opendata.arcgis.com/ , https://gis.fdot.gov/arcgis/rest/services/Parcels/FeatureServer
- https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer
- https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28
- https://www.fema.gov/flood-maps/national-flood-hazard-layer
- https://www.floridagio.gov/datasets/cb49e353a4274de5b25153411011af97_0/about

Example county and city open-data portals:
- https://gis-mdc.opendata.arcgis.com/
- https://brevard-gis-open-data-hub-brevardbocc.hub.arcgis.com/
- https://hcfl.gov/about-hillsborough/open-data-and-gis/geohub
- https://data-ocpw.opendata.arcgis.com/ , https://ocgis-datahub-ocfl.hub.arcgis.com/
- https://new-pinellas-egis.opendata.arcgis.com/
- https://data-sjcfl.hub.arcgis.com/
- https://city-tampa.opendata.arcgis.com/
- https://orlando-open-data-orl.hub.arcgis.com/ , https://www.orlando.gov/Our-Government/Records-and-Documents/Map-Library/GIS-Data-Download
- https://geohub-csp.opendata.arcgis.com/

Historic preservation and zoning distribution:
- https://dos.fl.gov/historical/about/division-faqs/master-site-file/
- https://dos.fl.gov/historical/preservation/master-site-file/
- https://dos.fl.gov/historical/preservation/national-register/
- https://mapdirect-fdep.opendata.arcgis.com/maps/nps::nps-national-register-of-historic-places-locations/about
- https://www.nps.gov/subjects/nationalregister/data-downloads.htm
- https://dos.fl.gov/historical/preservation/certified-local-governments/
- https://floridapreservationatlas.usf.edu/certified-local-governments
- https://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0100-0199/0163/Sections/0163.3164.html
- https://amlegal.com/terms-of-use
- https://library.municode.com/fl
- https://www.seminolecountyfl.gov/docs/default-source/pdf/zoning-table.pdf
