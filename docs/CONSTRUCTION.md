# Residential Construction Knowledge Base (Florida + North Carolina)

The offline, cited, on-demand guide to residential construction and the trades. It answers "what is the
dimension, what are the steps, what does code say, and what is the number" for one- and two-family
dwellings, scoped to Florida and North Carolina, and it always carries the verify-locally boundary.

## What it is
- **Offline dictionary** (`canonical-sources/construction/*.json`): one file per trade (framing, stairs,
  decks, foundations, roofing, electrical, plumbing, HVAC, drywall, insulation, egress, siding/flashing)
  plus `glossary.json`, `assemblies.json`, `fl-nc-specifics.json`, `edition-status.json`, and
  `diagram-index.json`. Each record carries dimensions, ordered steps, common mistakes, code citations
  (section + edition + free-viewer link), FL/NC jurisdiction notes, diagram references, source ids, and
  the boundary. Every record has a packed `text` field, so the scoop FTS5 cache indexes it and it is
  answerable offline and token-free via `cache_query` / `construction_lookup`.
- **Calculators** (`tools/build_calc.py`): first-principles stair, egress, R-value-by-zone, NEC box fill,
  drain slope, roof pitch, board feet, and an advisory-only deck-span flag. No copyrighted table is
  reproduced; every result cites its code section and carries the boundary.
- **Atoms and spoke**: `construction-lookup` (technique and dimensions), `code-lookup` (governing section
  and adopted edition), `build-calc` (calculations), composed by the `construction-desk` spoke and routed
  from the hub as `construction_question`, `code_lookup`, and `build_calc`. `project-builder` consults
  these atoms for its materials list, step sequence, and safety notes.
- **Diagrams** (`canonical-sources/construction/diagrams/`): five original, license-clean (CC0) SVG
  details (stair geometry, deck ledger, egress opening, wall framing, R-value-by-zone map), indexed with
  license and attribution in `diagram-index.json`.
- **MCP tools**: `construction_lookup`, `code_lookup`, `build_calc`.

## The legal / redistribution model (the defining constraint)
The building codes are copyrighted, even where adopted into law. IRC, IECC, IPC, IMC, IFGC (ICC), the
NEC/NFPA 70 (NFPA), and the AWC/APA/ACCA trade standards are free to read online but not redistributable;
APA's terms even forbid AI training. So the knowledge base is built like the contract engine handles
legal sources:

**Author our own plain-English explanation, key it to the code section number, link the free viewer, and
quote only short passages under fair use with citation. Never bulk-copy code text or a copyrighted
figure.**

Reusable public-domain / open material we build from and may cache: U.S. government works (DOE Building
America, OSHA via eCFR, FEMA, CPSC, HUD, NIST/USDA-FPL, energycodes.gov), state statutes and amendments,
FL/Miami-Dade product approvals, NREL openstudio-standards (BSD-3, attribution), Wikidata (CC0), and
Wikimedia Commons (per-file CC/PD). `tools/construction_fetch.py` downloads only these and structurally
refuses copyrighted hosts. See `shared/construction-engine.md` for the full model.

## Adopted code editions (verify with the AHJ)
- **Florida**: 2023 Florida Building Code, 8th Edition (2021 I-Codes + ASCE 7-22), effective 2023-12-31.
  9th Edition (2026) in draft. Single statewide code; local amendments may add stringency. HVHZ
  (Miami-Dade and Broward) requires Miami-Dade NOAs. Climate zones 1 to 2.
- **North Carolina**: the 2018 NC Residential Code (2015 IRC) is enforced today. The 2024 NC Residential
  Code (2021 IRC) is adopted but its effective date is postponed (earliest around 2027), gated on the new
  Residential Code Council and OSFM certification. Coastal counties use Chapter 45 high-wind provisions.
  Climate zones 3A (coast) to 4A (piedmont) to 5A (mountains).

The dictionary cites the 2021 I-Codes as the base; jurisdiction notes flag where the enforced NC 2018
(2015 IRC) values or section numbers differ. `edition-status.json` records the adopted edition and the
pending transitions; the currency report surfaces it.

## Currency and updates
- Sources register under two categories: `building-code` (FL/NC/model portals, cite-only, ~365-day
  cadence since code cycles run three years) and `construction-authority` (AWC/APA/ACCA plus the
  public-domain government and open sources, ~180-day). Registered via
  `python3 tools/source_currency.py seed-sources canonical-sources/building-code-sources-seed.json` and
  `...construction-authority-sources-seed.json`.
- `canonical-sources/data-currency-map.json` classifies every construction data file as watched (by which
  source ids), so an upstream change flags the file for review rather than a future audit re-flagging it.
  The `edition-status.json` row is the deliberate watch for the NC 2024 and FL 9th-Edition transitions.
- Routine checks:
  ```bash
  python3 tools/source_currency.py report --category building-code
  python3 tools/source_currency.py report --category construction-authority
  ```
- Fetch public-domain/open assets (user-run, with crawling permissions):
  ```bash
  python3 tools/construction_fetch.py --list       # the fetch plan and host allow/refuse sets
  python3 tools/construction_fetch.py              # downloads into pipeline/construction-library/ (gitignored)
  ```
  The crawler refuses copyrighted hosts structurally, so it can never bundle copyrighted material.

## Boundary (on every output)
GENERAL CONSTRUCTION GUIDANCE, NOT ENGINEERING, CODE-COMPLIANCE, OR DESIGN ADVICE. Verify against your
locally adopted code edition and permit office; use a licensed professional for electrical, gas and
plumbing, structural or load-bearing work, roofing, and HVAC design; pull permits and get inspections.
Electrical, plumbing, and HVAC answers lead with the licensed-professional requirement. See
`protocols/safety.md`.

## How to verify
```bash
python3 shared/cache/cache.py --build
python3 shared/cache/cache.py --query "stair riser" --json           # dictionary is offline-queryable
python3 tools/build_calc.py --selftest                                # calculator math (24 checks)
python3 tools/construction_fetch.py --selftest                        # host refusal + manifest (12 checks)
python3 tools/sync_check.py                                           # drift, including invariant 22
python3 tools/scenario_check.py
```

## Non-goals
Commercial (IBC) content; redistributing any copyrighted code text or AWC/APA/ICC figures;
per-address wind or flood values (link the FEMA Map Service Center and the ASCE Hazard Tool);
jurisdictions beyond Florida and North Carolina in this phase; and code-compliance or engineering advice.
