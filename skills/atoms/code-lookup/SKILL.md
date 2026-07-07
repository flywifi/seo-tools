---
name: code-lookup
atom: true
standalone: true
description: "resolves a residential code requirement by topic and jurisdiction: returns the governing IRC/NEC/IPC section, a link to the free official viewer, the adopted code edition for Florida (2023 FBC 8th Edition, 2021 I-Codes) or North Carolina (2018 NC RC, 2015 IRC, with the pending 2024 transition), and the verify-locally boundary. Triggers: 'what does Florida code say about egress', 'which code edition does North Carolina enforce', 'what section covers deck ledgers', 'is my county FL or NC edition current'. Never reproduces copyrighted code text or tables. Do NOT use to explain a technique or its steps (construction-lookup) or to compute a value (build-calc)."
engines_required:
  - shared/construction-engine.md
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/research-citation.md
  - protocols/formatting-metadata.md
---

# code-lookup

Which code applies, which edition is in force, and where to read it. Given a topic and a jurisdiction,
it returns the governing section number, the adopted edition, and a link to the free official viewer.
It never copies code text or tables: the codes are copyrighted, so it cites the section and links the
viewer.

## First line of every output (verbatim)

```
GENERAL CONSTRUCTION GUIDANCE, NOT CODE-COMPLIANCE OR LEGAL ADVICE. CODES VARY BY JURISDICTION AND EDITION; VERIFY THE ADOPTED EDITION AND SECTION WITH YOUR PERMIT OFFICE.
```

## When to use this skill
- "what does Florida code require for egress windows", "which residential code edition is enforced in
  North Carolina", "what IRC section covers deck ledger attachment", "is the county on the 2021 or 2015
  IRC", routed as `code_lookup`.

Do NOT use for:
- Explaining how to do the work, its steps, or common mistakes (use `construction-lookup`).
- Computing a number (use `build-calc`).

## Inputs
The topic (for example egress, deck ledger, stair riser) and the jurisdiction (`fl`, `nc`, or `both`).

## Core procedure
Follow `shared/method.md`.

### Step 1: resolve edition and section
Call `code_lookup` with the topic and jurisdiction. It returns the adopted-edition status (from
`canonical-sources/construction/edition-status.json`) and the matching dictionary entries with their
`code_refs` (section + free-viewer link).

### Step 2: answer with edition, section, and boundary
State the adopted edition for the jurisdiction (Florida 8th Edition on the 2021 I-Codes; North Carolina
enforcing the 2018 code on the 2015 IRC, with the 2024 transition pending and its date uncertain). Give
the governing section number and the free-viewer link. Never paste code text or a table; cite and link.
Emit the boundary and tell the reader to confirm the enforced edition with the Authority Having
Jurisdiction.

## Output contract
Adopted edition, governing section(s) with free-viewer links, FL/NC differences where they matter, and
the boundary. Honor `protocols/formatting-metadata.md`. No copyrighted code text or tables are
reproduced (`shared/construction-engine.md` redistribution model).

## Engines and protocols loaded
`shared/construction-engine.md`; `protocols/safety.md`, `protocols/no-fabrication.md`,
`protocols/research-citation.md`, `protocols/formatting-metadata.md`.

## Atoms used
None. Called directly, by `construction-desk`, or by `project-builder`. Hands technique questions to
`construction-lookup` and math to `build-calc`.

## Standalone usability
Returns the adopted edition and governing section with a free-viewer link offline, from the cache and
the edition-status file, with no network.

## Failure modes
- Edition ambiguity (NC 2018 vs pending 2024): states both and says to confirm with the AHJ, never
  guesses which is enforced.
- No mapped section for the topic: says so and points to the code landing page.
- A request to quote the code text: refused; cites the section and links the viewer instead.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
