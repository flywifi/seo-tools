---
file: shared/construction-engine.md
role: Canonical knowledge for the residential construction / DIY guide — the legal-redistribution model,
  the non-negotiable safety boundary, the offline-dictionary schema, Florida and North Carolina code
  editions, the trade taxonomy, the citation discipline, and the first-principles calculator rule.
load: whenever a request concerns residential construction, a building code, a trade dimension, a permit,
  or a DIY build question (framing, decks, stairs, foundations, roofing, electrical, plumbing, HVAC,
  drywall, insulation, siding, windows/egress).
scope: RESIDENTIAL only — IRC-based one- and two-family dwellings and townhouses. Not commercial (IBC).
---

# Construction Engine (residential, FL + NC)

The on-demand, offline, cited guide to residential construction and the trades. It answers "what is the
stair riser max," "how do I attach a deck ledger," "what R-value does my ceiling need in North Carolina"
with the dimension, the required steps, the common mistakes, and the exact code citation — verifiable
offline through the scoop cache, always carrying the verify-locally boundary.

## The boundary (non-negotiable, on every answer)

Reproduce this verbatim on any construction output (it is also in `protocols/safety.md`):

> GENERAL CONSTRUCTION GUIDANCE — NOT ENGINEERING, CODE-COMPLIANCE, OR DESIGN ADVICE. Building codes vary
> by jurisdiction and edition and are amended locally. Verify every requirement against your locally
> adopted code edition and your permit office before you build. Use a licensed professional for
> electrical, gas and plumbing, structural or load-bearing work, roofing, and HVAC design. Pull permits
> and get inspections where required.

Electrical, gas/plumbing, structural/load-bearing, roofing, and HVAC-design entries state the
licensed-professional requirement plainly and up front. Nothing here presents unlicensed service-panel,
gas, or structural work as casual DIY. This mirrors the contract-engine's legal-notice discipline.

## The legal / redistribution model (the defining constraint)

The building codes are copyrighted, even though they are law. This shapes everything.

- **CITE-AND-LINK-ONLY (never redistribute the text or figures):** the model I-Codes (IRC, IECC, IPC,
  IMC, IFGC — © ICC), the National Electrical Code / NFPA 70 (© NFPA), and the trade standards used for
  dimensions — AWC (Wood Frame Construction Manual, DCA6 deck guide, span tables), APA, ACCA (Manual
  J/S/D). ICC Digital Codes and UpCodes offer free *reading*; the text is not ours to copy. APA's terms
  additionally forbid AI training on their material. For these we reference the **section number** (e.g.
  "IRC R311.7.5.1," "NEC 210.52(A)," "IPC 704.1") and **link the free viewer**; we author our own plain
  explanation; we quote only short passages under fair use with citation.
- **REDISTRIBUTABLE / CACHEABLE (public domain or open license):** U.S. government works — DOE Building
  America Solution Center, OSHA 29 CFR 1926 (via eCFR), FEMA residential guides, CPSC safety handbooks,
  HUD, NIST / USDA Forest Products Lab (Wood Handbook, PS 20 lumber sizing); state statutes and the code
  amendments the states themselves author; Florida and Miami-Dade product-approval records;
  NREL/openstudio-standards (BSD-3, with attribution); Wikidata (CC0); Wikimedia Commons (per-file CC/PD).
  These we may ingest, cache, and cite with attribution.

Rule of thumb: **derive the number from first principles or a public-domain government restatement, cite
the governing code section, link the free viewer — never paste code text or a copyrighted figure.**

## Offline dictionary (cache-native)

The dictionary lives in `canonical-sources/construction/*.json`, one file per trade plus `glossary.json`,
`assemblies.json`, and `fl-nc-specifics.json`. Every record is a dict with a packed `text` field, so
`shared/cache/cache.py` indexes it into the FTS5 scoop cache automatically and it is answerable offline,
token-free, through `cache_query`. Record schema:

```json
{
  "id": "stairs-riser-run",
  "title": "Stair riser and tread limits",
  "text": "packed searchable summary combining the dimension, the rule, and the citation",
  "trade": "stairs",
  "topic": "geometry",
  "dimensions": [{"item": "max riser", "value": "7 3/4 in", "note": "variation within a flight <= 3/8 in"}],
  "steps": ["...ordered how-to..."],
  "common_mistakes": ["inconsistent riser heights (>3/8 in variance) — the #1 failed-inspection item"],
  "code_refs": [{"code": "IRC", "section": "R311.7.5.1", "edition": "2021", "url": "https://codes.iccsafe.org/..."}],
  "jurisdiction_notes": {"fl": "FBC-R 8th Ed (2023) mirrors IRC 2021", "nc": "NC RC 2018 uses IRC 2015 values; confirm"},
  "diagram_refs": ["stair-geometry"],
  "source_ids": ["icc-irc-2021", "cpsc-playground-handbook"],
  "boundary": "verify-locally"
}
```

Numbers come only from records — never invented (`protocols/no-fabrication.md`); a missing value is null
plus a gap. Ranges use "to" (`protocols/formatting-metadata.md`).

## Edition awareness (Florida and North Carolina differ — and NC is mid-transition)

- **Florida:** the **2023 Florida Building Code, 8th Edition** (Residential volume FBC-R), effective
  Dec 31 2023, based on the 2021 I-Codes and **ASCE 7-22** for wind. A **9th Edition (2026)** is in
  draft. Florida is a single statewide code; local governments may add more-stringent amendments.
- **North Carolina:** the **2018 NC Residential Code, based on the 2015 IRC, is what is enforced today.**
  The **2024 NC Residential Code (2021 IRC base)** is adopted but its effective date is **postponed**
  (earliest ~2027, gated on the new NC Residential Code Council and OSFM certification). Always confirm
  which edition the Authority Having Jurisdiction is enforcing. NC also has state-specific chapters a
  homeowner hits (notably **Chapter 45 High Wind Zones** for the coast).

Every `code_ref` records its `edition`. The currency system (P33) watches the NC 2024 transition and the
FL 9th-edition draft as explicit items.

### Florida residential specifics
- **High-Velocity Hurricane Zone (HVHZ):** all of Miami-Dade and Broward; stricter product approval via
  **Miami-Dade NOA** (Notice of Acceptance); large-/small-missile impact protocols (TAS 201/202/203).
- **Wind-borne debris region (WBDR):** opening protection (impact glazing or shutters) per FBC §1609.2.
- **Product approval:** statewide Florida Product Approval; HVHZ requires Miami-Dade NOA.
- **Termite protection:** FRC R318 (soil treatment, 6-mil vapor retarder, Certificate of Compliance).
- **Flood / elevation:** FBC flood provisions (R322 / ASCE 24), build to or above Base Flood Elevation
  per the FEMA FIRM; coastal V-zones require open/breakaway foundations. Per-site values: link the FEMA
  Map Service Center and the ASCE Hazard Tool, never guess.

### North Carolina residential specifics
- **Climate zones:** NC spans **CZ 3A (coastal/southeast) to 4A (piedmont, majority) to 5A (mountains)**;
  this drives the insulation R-value table. FL is **CZ 1 to 2** (cooling/humidity-dominated).
- **Coastal high-wind:** **NC RC Chapter 45 (High Wind Zones)** prescriptive path; Outer Banks design
  winds ~140 to 150 mph.
- **Radon:** NC uses Appendix F radon-control methods (adoptable); coastal plain mostly EPA Zone 3.

## Trade taxonomy (residential)

framing/carpentry, stairs & railings, decks, foundations/concrete, roofing, electrical (licensed),
plumbing (licensed), HVAC (design boundary), drywall, insulation & building science, windows/egress,
siding & weather barrier / flashing. Each trade file carries the dimensions, steps, common mistakes,
code citations, FL/NC notes, and the boundary.

## Calculators (first principles only)

`tools/build_calc.py` computes from geometry and physics and public-domain restatements — never by
copying a copyrighted span/ampacity/fixture-unit table. Covered: stair rise/run and flight geometry,
egress net-clear-opening area (IRC R310 5.7 / 5.0 sq ft), R-value by FL/NC climate zone, NEC box fill
(314.16), drain slope (IPC 704.1 quarter-inch-per-foot), deck-span sanity, roof-pitch angle. Every result
carries `computed_by`, the governing code section, and the boundary. Where authoritative numbers are
needed the tool prefers a U.S.-government public-domain restatement (DOE BASC, energycodes.gov) over the
copyrighted table.

## Sources and currency

Sources register into `canonical-sources/source-registry.json` under two categories:
`building-code` (FL/NC/model codes and permit authorities — cite-only, ~365-day cadence since code cycles
are three years) and `construction-authority` (AWC/APA/BSC/ACCA and the public-domain government and open
datasets — ~180-day). They are checked by the P33 currency tools (`source_currency.py`, the token-free
content-change detector). Diagrams and public-domain PDFs are pulled by `tools/construction_fetch.py`,
which downloads only public-domain/CC assets and structurally refuses copyrighted hosts.
