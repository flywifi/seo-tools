---
name: build-calc
atom: true
standalone: true
description: "runs an offline first-principles residential construction calculation: stair rise and run, egress net-clear opening area, insulation R-value by climate zone (FL and NC), NEC box fill, drain slope, roof pitch, board feet, and a deck-span sanity flag. All math runs in tools/build_calc.py (geometry and physics, no copyrighted tables); every result cites the governing code section and carries the verify-locally boundary. Triggers: 'what riser height for these stairs', 'is this window big enough for egress', 'what R-value do I need in Wake County', 'box fill for these wires', 'drain slope', 'roof pitch angle'. Do NOT use to look up a code requirement in prose (code-lookup), to explain a technique or its steps (construction-lookup), or to size a structural member authoritatively (that requires a licensed engineer and the actual span table)."
engines_required:
  - shared/construction-engine.md
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# build-calc

Offline construction math. Give it a dimension question and it returns the computed value, the governing
code section, and the boundary. It never invents a number and never reproduces a copyrighted span,
ampacity, or fixture-unit table: it computes from geometry and physics, or restates a public-domain
government value.

## First line of every output (verbatim)

```
GENERAL CONSTRUCTION GUIDANCE, NOT ENGINEERING OR CODE-COMPLIANCE ADVICE. VERIFY AGAINST YOUR LOCALLY ADOPTED CODE EDITION AND PERMIT OFFICE. USE A LICENSED PROFESSIONAL FOR STRUCTURAL, ELECTRICAL, GAS/PLUMBING, AND HVAC DESIGN.
```

## When to use this skill
- "how many risers for a 9 foot rise", "is this window a legal egress opening", "what ceiling R-value
  in climate zone 4 / Wake County NC", "box fill for three 14 gauge plus a device", "drain slope for a
  2 inch line", "what angle is a 6:12 roof", "board feet in this lumber", routed as `build_calc`.

Do NOT use for:
- Looking up a code requirement in words (use `code-lookup`).
- Explaining how to do a task, its steps, or common mistakes (use `construction-lookup`).
- Authoritatively sizing a joist, beam, header, or footing. The `deck-span` calculator returns a
  labeled rough ceiling only and points to the AWC DCA6 table; real structural sizing needs the code
  span table or a licensed engineer.

## Inputs
The calculation name and its numeric inputs (for example total rise for stairs; net-clear width and
height for egress; component and climate zone for R-value). Climate zone can be given as a number or a
county the model maps via `fl-nc-specifics.json`.

## Core procedure
Follow `shared/method.md`. Call `tools/build_calc.py` (or the `build_calc` MCP tool) with the calculation
and inputs; return its JSON result verbatim (value, code_ref, boundary) with a one-line plain reading.

### Step 1: pick the calculation
Map the request to one of: stair, egress, rvalue, boxfill, drain-slope, roof-pitch, board-foot,
deck-span.

### Step 2: run and report
Run the tool offline. Report the computed value, whether it passes the checked limit, the governing
code section, and the boundary. For egress, remind that the input is the NET CLEAR opening (window
open), not the rough opening. For deck-span, state plainly that the number is a rough ceiling and the
real span comes from DCA6.

## Output contract
The tool's JSON result plus a plain-language reading. Honor `protocols/formatting-metadata.md` (no em
dashes, ranges with "to"). Never guess a number the tool returns as an error or null; surface the gap.

## Engines and protocols loaded
`shared/construction-engine.md`; `protocols/safety.md`, `protocols/no-fabrication.md`,
`protocols/formatting-metadata.md`.

## Atoms used
None. This atom is called directly or by the `construction-desk` spoke and by `project-builder`.

## Standalone usability
Produces a valid calculation with citation and boundary with no downstream skill and no network.

## Failure modes
- Out-of-range or missing inputs return a structured error, not a guessed value.
- The deck-span result is advisory only and says so; it must not be built to.
- Climate zone or edition ambiguity is surfaced, not silently resolved.
