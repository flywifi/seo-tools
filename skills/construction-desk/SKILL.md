---
file: skills/construction-desk/SKILL.md
name: construction-desk
description: "the residential construction and DIY reference desk: answers build and trade questions (dimensions, steps, common mistakes) from the offline dictionary, resolves code requirements and the adopted edition for Florida and North Carolina, and runs first-principles construction calculators. Composes construction-lookup, code-lookup, and build-calc, then governs the output. Outputs general construction guidance only (not engineering or code-compliance advice) per protocols/safety.md and shared/construction-engine.md; leads electrical, plumbing, structural, roofing, and HVAC answers with the licensed-professional requirement; never reproduces copyrighted code text or tables. Does NOT plan a whole DIY project end to end (project-builder), estimate cost (finance-desk), or give engineering, code-compliance, or legal advice."
load: for construction-desk requests (construction questions, code lookups, and build calculations)
---

# construction-desk

construction-desk is the on-demand residential construction and DIY reference. It answers "how do I do
this and what are the dimensions" from the offline dictionary, "which code and edition applies here"
for Florida and North Carolina, and "what is the number" from first-principles calculators. It is
general construction guidance only, never engineering or code-compliance advice, and it leads the
licensed trades (electrical, gas and plumbing, structural, roofing, HVAC design) with the requirement
to use a licensed professional.

## First line of every output (verbatim)

```
GENERAL CONSTRUCTION GUIDANCE, NOT ENGINEERING, CODE-COMPLIANCE, OR DESIGN ADVICE. VERIFY AGAINST YOUR LOCALLY ADOPTED CODE EDITION AND PERMIT OFFICE. USE A LICENSED PROFESSIONAL FOR ELECTRICAL, GAS/PLUMBING, STRUCTURAL OR LOAD-BEARING WORK, ROOFING, AND HVAC DESIGN. PULL PERMITS AND GET INSPECTIONS WHERE REQUIRED.
```

## When to use this skill
- Build and trade questions: "how do I attach a deck ledger", "max stair riser", "stud spacing",
  "common framing mistakes", "what is a soffit" (routed as `construction_question`).
- Code and edition questions: "what does Florida code require for egress", "which residential code
  edition is enforced in North Carolina", "what section covers this" (routed as `code_lookup`). <!-- verify: tools/mcp_server.py::code_lookup -->
- Calculations: "how many risers for a 9 foot rise", "is this window a legal egress opening", "what
  R-value in Wake County", "box fill for these wires", "roof pitch angle" (routed as `build_calc`). <!-- verify: tools/mcp_server.py::build_calc -->

Do NOT use for:
- Planning a whole DIY project (materials list, steps, styling, renter-safe version) end to end: that
  is `project-builder`, which calls these atoms for its facts.
- Estimating what a project costs: that is `finance-desk` (`cost-estimate`).
- Engineering, code-compliance, or legal advice: out of scope; refer to a licensed professional.

## Inputs
The question in plain language and, for code questions, the jurisdiction (Florida or North Carolina, or
a county the model maps to a climate zone). No network is required; everything runs from the cache and
the offline calculators.

## Core procedure
Follow `shared/method.md`. Compose atoms via `workflow.json`.

### Step 1: classify the sub-request
Route to `construction-lookup` (technique and dimensions), `code-lookup` (governing section and adopted
edition), or `build-calc` (a computed value). A single request may use more than one (for example,
"what riser height and what does code say" uses build-calc plus code-lookup).

### Step 2: answer, cite, and govern
Return the dimensions, steps, mistakes, governing section with the free-viewer link, and any computed
value, each carrying its citation. State FL vs NC differences and the adopted edition where relevant.
Lead the licensed trades with the professional requirement. Hand the assembled output to
`govern-artifact` and emit the boundary.

## Output contract
A cited construction answer: dimensions, steps, mistakes, code sections with free-viewer links, adopted
edition, and any calculator result, plus the boundary. Honor `protocols/formatting-metadata.md` (no em
dashes, ranges with "to"). No fabricated values (`protocols/no-fabrication.md`); no copyrighted code
text or tables (`shared/construction-engine.md`).

## Engines and protocols loaded
`shared/construction-engine.md`; `protocols/safety.md`, `protocols/no-fabrication.md`,
`protocols/research-citation.md`, `protocols/quality-gates.md`, `protocols/formatting-metadata.md`.

## Atoms used
`construction-lookup`, `code-lookup`, `build-calc`, and `govern-artifact`. Each is directly callable by
the user and by `project-builder`.

## Standalone usability
Answers a construction, code, or calculation question offline, cited and bounded, with no downstream
skill and no network.

## Failure modes
- Cache not built: instructs to build it rather than answering from memory.
- Edition ambiguity in NC: states both the enforced 2018 and pending 2024 codes and defers to the AHJ.
- A structural sizing request: returns the advisory deck-span flag or the code section and refers the
  reader to the span table or a licensed engineer, never an authoritative member size.

## Cross-modality
Class: C.
Runs on: Claude Desktop/Code (native, MCP + the tool module); claude.ai via a hosted remote-MCP connector; Custom GPT / Gemini only when the tool is hosted behind a remote MCP or an Action; Gems: no.
Mechanism: tools/build_calc.py first-principles calculators (stair, egress, rvalue, box_fill, drain_slope, roof_pitch, board_foot, advisory deck_span) exposed as the build_calc MCP tool, plus construction_lookup/code_lookup MCP tools (tools/mcp_server.py) querying the scoop cache (shared/cache/cache.py) over canonical-sources/construction/ dictionary JSONs and edition-status.json.
Fallback: No runtime or hosted seam -> lookups degrade to Class B (answer from the canonical-sources/construction dictionary and edition-status.json provided as knowledge); for calculations, reason over the shared/construction-engine.md "Calculators (first principles only)" formulas, show the arithmetic step by step, flag the result unverified, and name the tools/build_calc.py calc to run; never fabricate a quantity, span, or code figure. On ChatGPT this is reasoning-only and outputs are labeled provisional (no local tools, no flag enforcement); the desktop app can reach the full tool only via a deployed remote MCP connector in developer mode (implementation/gpt/mcp-connector/README.md).
See `shared/cross-modality-engine.md`.
