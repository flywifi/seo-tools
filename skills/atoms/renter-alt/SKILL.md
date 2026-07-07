---
file: skills/atoms/renter-alt/SKILL.md
name: renter-alt
description: Rewrite any single DIY step or material to be renter-friendly by proposing a peel-and-stick, removable, or furniture-based alternative that requires no permanent modifications, no drilling into walls, and no painting of permanent surfaces. Use when a project step or material is not reversible and a renter-safe substitute is needed. Do NOT use for full project planning, materials list generation, or content scripting.
load: when a DIY step or material must be adapted to renter-safe, reversible methods
---

# renter-alt

Evaluate a single DIY step or material and return a concrete renter-friendly alternative. The alternative must be fully reversible, damage-free, and landlord-safe per the tenure axis in `shared/adaptation-engine.md`. If no renter-friendly alternative exists, return null and flag the reason rather than inventing a workaround.

## Purpose

Produce a single-step or single-material substitution that a renter can use without risking their security deposit or violating a lease. This atom operates on one step or material at a time and is intended to be called in a loop by spokes that need to adapt an entire project step list or materials list.

The output must:

- Identify the original approach exactly as given.
- Propose one concrete renter alternative using peel-and-stick, removable adhesive, tension hardware, freestanding furniture placement, command strips, removable wallpaper, washi tape, or other deposit-safe methods.
- Describe tradeoffs honestly: what the renter gains (reversibility, portability, ease of removal) and what they give up (durability, load capacity, finished look, permanence).
- Estimate whether the alternative is harder, easier, or the same difficulty to execute compared to the original.
- Estimate whether the alternative costs more, less, or about the same. All cost comparisons are directional ranges only; never invent specific prices.
- Confirm reversible as true. This atom only outputs reversible alternatives; if none exists, it returns null and flags the reason.

If the original step or material is already renter-friendly and reversible, confirm it as-is and note no substitution is needed.

## Inputs

```json
{
  "step_or_material": "string (required) -- the original step instruction or material description exactly as written",
  "project_context": "string (required) -- brief description of the project this step or material belongs to (e.g. 'gallery wall using frames', 'painting an accent wall dark green')"
}
```

Field notes:

- `step_or_material` must be the verbatim or closely paraphrased original so the atom can classify what kind of modification is involved (drilling, painting, adhesive, mounting, etc.).
- `project_context` provides enough background to select a fitting renter alternative. Keep it to one to two sentences. Do not include personal details or PII.

## Output

```json
{
  "tool": "renter-alt",
  "original_approach": "string -- the original step or material as interpreted from the input",
  "renter_alternative": "string or null -- concrete renter-friendly substitute; null if no safe alternative exists",
  "flag": "string or null -- present only when renter_alternative is null; explains why no alternative exists and what the renter should do instead (e.g. consult landlord, skip the step, hire a professional)",
  "tradeoffs": {
    "gained": "string -- what the renter gains by using the alternative (e.g. 'fully reversible, no deposit risk, portable when moving')",
    "lost": "string or null -- what the renter gives up compared to the original (e.g. 'lower weight capacity, visible adhesive tabs at close range, not suitable for heavy mirrors over 20 lb'); null if nothing meaningful is lost"
  },
  "difficulty_delta": "easier | same | harder -- difficulty of the renter alternative compared to the original approach",
  "cost_delta": "lower | same | higher -- directional cost comparison; based on general knowledge only; actual cost varies by region, retailer, and what the user already owns",
  "reversible": true
}
```

Output rules:

- `reversible` is always true. This atom does not produce permanent alternatives. If the only viable path is permanent, set `renter_alternative` to null and populate `flag`.
- `renter_alternative` must name a specific method or product category (for example: "peel-and-stick removable wallpaper panels", "large-format command strips rated for the frame weight", "freestanding leaning ladder shelf"). Do not name specific brands or give guaranteed prices.
- `cost_delta` is a directional signal only. Always treat it as an estimate. Never state a specific dollar figure.
- `tradeoffs.lost` is null only when the renter alternative is genuinely equal to or better than the original on all practical dimensions. This will be rare; be honest.
- If the original step or material is already renter-friendly (for example, "hang a lightweight print using a single nail over an existing hole"), set `renter_alternative` to null, set `flag` to "Original approach is already renter-friendly; no substitution needed.", and set `reversible` to true.
- Do not fabricate load ratings, cure times, adhesive strengths, or product specifications. Use hedged language ("check the manufacturer's weight rating before use") when specific limits are relevant.
- Do not provide guidance on electrical, gas, plumbing, structural, or hazardous-material steps. If the input describes one of those, set `renter_alternative` to null and `flag` to "This step requires a licensed professional and is outside the DIY scope of this atom. See protocols/safety.md."

## Do NOT use for

- Generating a full project materials list or step sequence (use materials-list or step-sequence atoms).
- Adapting content for a platform or surface format (use adaptation-engine via the spoke layer).
- Evaluating whether a project as a whole is renter-friendly; this atom operates on one step or material at a time.
- Producing cost estimates, price lists, or sourcing guides (use materials-list).
- Any request that involves electrical wiring, gas lines, plumbing, load-bearing structures, or hazardous materials. Those are outside DIY scope per protocols/safety.md.
- Non-DIY content such as scripts, hooks, titles, or platform metadata.

## References

- `shared/adaptation-engine.md` -- tenure axis (Axis 2): renter vs owner; defines reversible, damage-free, and landlord-safe methods.
- `protocols/safety.md` -- DIY trade boundary; hard stops for licensed-trade steps.
- `protocols/no-fabrication.md` -- do not invent load ratings, brand specs, or specific prices.

## Cross-modality
Inherits its calling spoke's class (Class A); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
