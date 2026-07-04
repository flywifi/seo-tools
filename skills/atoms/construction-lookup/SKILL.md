---
name: construction-lookup
atom: true
standalone: true
description: "answers a residential construction or trade question from the offline dictionary: the dimensions, the required steps, the common mistakes, and the code citation, for framing, stairs, decks, foundations, roofing, electrical, plumbing, HVAC, drywall, insulation, egress, and siding/flashing, plus a glossary and FL/NC specifics. Queries canonical-sources/construction via the scoop cache (offline, token-free) and returns entries with their IRC/NEC/IPC section citations and the verify-locally boundary. Triggers: 'how do I attach a deck ledger', 'what is the max stair riser', 'how far apart are studs', 'what is a soffit', 'common framing mistakes'. Do NOT use to compute a number (build-calc), to resolve which code edition a jurisdiction enforces (code-lookup), or to plan a full DIY project end to end (project-builder)."
engines_required:
  - shared/construction-engine.md
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/research-citation.md
  - protocols/formatting-metadata.md
---

# construction-lookup

The offline reference for how residential construction and the trades actually work. Ask it a build
question and it returns the dimensions, the ordered steps, the common mistakes, and the exact code
section, drawn from the cached dictionary and cited, never invented.

## First line of every output (verbatim)

```
GENERAL CONSTRUCTION GUIDANCE, NOT ENGINEERING OR CODE-COMPLIANCE ADVICE. VERIFY AGAINST YOUR LOCALLY ADOPTED CODE EDITION AND PERMIT OFFICE. USE A LICENSED PROFESSIONAL FOR ELECTRICAL, GAS/PLUMBING, STRUCTURAL, ROOFING, AND HVAC DESIGN.
```

## When to use this skill
- "how do I attach a deck ledger", "what is the maximum stair riser height", "stud spacing", "what R
  value do I need in North Carolina", "common mistakes framing a wall", "what is a soffit", "how does
  flashing work", routed as `construction_question`.

Do NOT use for:
- Computing a number (use `build-calc`: stair math, egress area, box fill, drain slope, R-value, pitch).
- Resolving which code edition a jurisdiction enforces or the governing section for a jurisdiction
  (use `code-lookup`).
- Planning a whole DIY project (materials list, steps, styling) end to end (use `project-builder`).

## Inputs
The trade or topic in plain language. The atom searches the offline dictionary; no network is needed.

## Core procedure
Follow `shared/method.md`.

### Step 1: query the dictionary
Call `construction_lookup` (or `cache_query` scoped to `canonical-sources/construction`) with the
topic. Read the matched record(s) for the full dimensions, steps, mistakes, and code_refs.

### Step 2: answer with citations and boundary
Return the dimensions, the required steps, and the common mistakes, each carrying its code section and
the free-viewer link. Add the FL and NC jurisdiction notes when relevant. Lead electrical, plumbing,
and HVAC answers with the licensed-professional requirement. Emit the boundary. If the dictionary has
no entry, say so and point to the cited source rather than inventing a value
(`protocols/no-fabrication.md`).

## Output contract
Dimensions, steps, mistakes, code citations, FL/NC notes, and the boundary. Honor
`protocols/formatting-metadata.md` (no em dashes, ranges with "to"). Every number and rule is traceable
to a dictionary record and its cited section; nothing is fabricated.

## Engines and protocols loaded
`shared/construction-engine.md`; `protocols/safety.md`, `protocols/no-fabrication.md`,
`protocols/research-citation.md`, `protocols/formatting-metadata.md`.

## Atoms used
None. Called directly, by `construction-desk`, or by `project-builder`. Hands numeric questions to
`build-calc` and edition questions to `code-lookup`.

## Standalone usability
Returns a cited answer with the boundary offline, from the cache, with no downstream skill or network.

## Failure modes
- No dictionary entry for the topic: says so and cites the source to check, never guesses.
- A copyrighted table value is asked for: cites the section and links the free viewer instead of
  reproducing the table.
- Cache not built: instructs to run the cache build rather than answering from memory.
