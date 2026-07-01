---
file: skills/atoms/materials-list/SKILL.md
name: materials-list
description: Write a complete, categorized materials and tools list for a DIY home decor project, with estimated cost ranges, safety flags, and renter notes. Use when any project-building skill needs a sourcing and cost reference. Do NOT use for non-DIY content (tutorials, scripts, captions) or to produce a step-by-step build process.
load: when a DIY home decor project requires a materials, tools, or sourcing list
---

# materials-list

Generate a structured materials and tools list for a DIY home decor project in the creator's niche (home decor and DIY). Group items by category, flag safety-required tools, label all cost figures as estimated ranges, and adapt for renter constraints when requested.

## Purpose

Produce a sourcing-ready list a viewer or editor can hand directly to a production checklist or content script. The list must:

- Group materials by category (for example: surface materials, adhesives, hardware, finishes).
- Flag every tool or material that requires personal protective equipment or ventilation as safety-required.
- Present all cost figures as estimated ranges only, never as fixed or guaranteed prices. Always note that prices vary by region and retailer.
- Scale depth and alternatives to the budget tier (low, mid, high).
- When renter_friendly is true, add a renter_notes block and exclude or flag any item that is not reversible or damage-free.

Cost figures are sourced from general knowledge and must be treated as rough orientation only. Never present them as current, exact, or guaranteed.

## Inputs

```json
{
  "project_title": "string (required) -- short name of the DIY project",
  "difficulty": "beginner | intermediate | advanced (required)",
  "budget_tier": "low | mid | high (required)",
  "renter_friendly": "boolean (optional, default false)"
}
```

Field notes:

- `project_title` drives item selection and category grouping.
- `difficulty` controls step-level detail in notes and how many tool alternatives are offered (beginner gets more hand-holding; intermediate gets options).
- `budget_tier` governs which material grades and sourcing paths are surfaced: low surfaces thrift, dollar-store, and DIY alternatives; mid is the default balanced option; high includes splurge upgrades where they meaningfully improve the result.
- `renter_friendly` when true gates every item against reversibility: no permanent paint, no drilling into walls, no items that require landlord consent. Items that have no renter-safe substitute are flagged with a warning note rather than silently omitted.

## Output

```json
{
  "tool": "materials-list",
  "project_title": "string",
  "budget_tier": "low | mid | high",
  "materials": [
    {
      "item": "string",
      "category": "string (e.g. surface material, adhesive, finish, hardware, textile, accent)",
      "quantity": "string (e.g. '1 quart', '6 ft', '4 pieces')",
      "estimated_cost_range": "string (e.g. '$4 to $9') -- estimated range only; prices vary by region and retailer",
      "notes": "string (sourcing tip, substitute, or renter flag if applicable)"
    }
  ],
  "tools": [
    {
      "item": "string",
      "essential": true,
      "safety_required": false,
      "notes": "string (PPE needed, borrow vs buy note, or skill-level caution)"
    }
  ],
  "optional_upgrades": [
    {
      "item": "string",
      "why": "string (what it improves or unlocks)",
      "estimated_cost_range": "string -- estimated range only"
    }
  ],
  "estimated_total_range": "string (e.g. '$35 to $70') -- estimated range only; actual cost depends on what you already own, local pricing, and sourcing choices",
  "buy_vs_borrow_notes": "string -- guidance on which tools or items are worth buying vs borrowing or renting given the budget tier and likely reuse",
  "renter_notes": "string or null -- present only when renter_friendly is true; covers reversibility, damage-free alternatives, and items to skip or substitute"
}
```

Output rules:

- Every `estimated_cost_range` value must be labeled as a range (use "to" not a dash between numbers) and never stated as a fixed price.
- `estimated_total_range` must include a plain-language caveat noting it is an estimate and that actual cost varies.
- `safety_required: true` is set for any tool that involves blades, heat, power, caustic finishes, spray paint, aerosol adhesives, solvents, or items requiring ventilation or eye protection.
- `optional_upgrades` covers items that are not required for the core project but meaningfully improve the result or unlock a more polished finish; keep this list to three items or fewer.
- `buy_vs_borrow_notes` must appear in every output regardless of renter_friendly.
- `renter_notes` appears only when `renter_friendly` is true and is omitted (set to null) otherwise.
- Do not include electrical, gas, plumbing, structural, or hazardous-material tasks in any list. If the project scope implies any of those, add a note in the relevant item's `notes` field directing the reader to a licensed professional and flag it as outside the DIY boundary per protocols/safety.md.

## Do NOT use for

- Full project build instructions or step-by-step tutorials (use project-builder or script-section).
- Content scripts, outlines, or captions (use script-writer, hook-write, or title-generate).
- Any project touching electrical wiring beyond a like-for-like fixture swap, gas, structural or load-bearing work, or hazardous materials such as asbestos or lead paint. Those items must be escalated per protocols/safety.md.
- Generating affiliate links, specific retailer recommendations with prices, or any claim about current market pricing. Ranges are estimates only.
- Non-DIY content requests (platform metadata, pitch emails, rate cards).

## References

- `protocols/safety.md` -- DIY trade boundary; safety_required flags and escalation rules.
- `shared/adaptation-engine.md` -- renter vs owner axis (Axis 2) and budget tier axis (Axis 3); sourcing guidance and the rule against inventing specific prices.
