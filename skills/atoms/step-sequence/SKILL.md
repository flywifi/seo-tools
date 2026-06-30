---
file: skills/atoms/step-sequence/SKILL.md
name: step-sequence
description: Write the numbered step-by-step build process for a DIY home decor project. Each step includes the action, a brief explanation of why it matters, a safety note when relevant, and a b-roll opportunity tag. Use when any project-building or scripting skill needs a structured process sequence. Do NOT use for materials lists (use materials-list), content hooks or scripts (use hook-write or script-section), or any project that requires a licensed trade as its primary scope.
load: when a DIY home decor project needs a numbered build sequence with safety flags and b-roll cues
---

# step-sequence

Generate a structured, numbered step-by-step build process for a DIY home decor project in Alexandra's niche (moody-vintage home decor and DIY). Each step must explain what to do, briefly explain why it matters for the result, include a safety note when the action carries physical risk, and tag a b-roll filming opportunity so the step can feed directly into a production checklist or script.

## Purpose

Produce a sequenced build guide that a creator, editor, or production assistant can use directly. The sequence must:

- Number every step in execution order and keep each action discrete (one action per step).
- Include a brief "why it matters" detail so the viewer understands the reason, not just the motion.
- Add a safety note for any step involving blades, heat, power tools, spray or solvent products, or items requiring PPE or ventilation. Set `safety_note` to null only when no physical risk is present.
- Tag a b-roll filming opportunity for every step so the editor knows what to capture (for example: overhead pour shot, close-up brush stroke, before-and-after reveal frame).
- Flag any step that touches electrical wiring beyond a like-for-like fixture swap, gas or supply lines, structural or load-bearing work, roofing, foundations, or hazardous materials (asbestos, lead paint, mold) with `licensed_trade_required: true` and replace the action detail with the hard boundary note: "Licensed professional required; this step is out of scope for DIY." Do not provide how-to guidance for those steps.
- When `renter_friendly` is true, adapt every step to reversible, damage-free methods. Flag any step that cannot be made renter-safe with a note in `safety_note` directing the viewer to consult their lease or landlord.

All time estimates are rough ranges only; actual time varies by skill level, materials, and workspace. Never present them as guaranteed.

## Inputs

```json
{
  "project_title": "string (required) -- short name of the DIY project",
  "materials_list": "object (optional) -- output from materials-list atom; used to align step materials with sourced items",
  "difficulty": "beginner | intermediate | advanced (required)",
  "renter_friendly": "boolean (optional, default false)"
}
```

Field notes:

- `project_title` drives step selection, sequencing logic, and the level of explanatory detail per step.
- `materials_list` when provided aligns step-level material references to the sourced items in that list. When absent, steps name materials generically.
- `difficulty` controls the granularity of each step: beginner steps are broken into smaller discrete actions with more hand-holding; intermediate and advanced steps can combine related motions and assume baseline tool familiarity.
- `renter_friendly` when true restricts every step to reversible or damage-free methods. Steps with no renter-safe alternative are not silently omitted; they receive a flag note instead.

## Output

```json
{
  "tool": "step-sequence",
  "project_title": "string",
  "difficulty": "beginner | intermediate | advanced",
  "total_steps": "integer",
  "estimated_time_per_step": "string (e.g. '5 to 10 minutes per step') -- estimated range only; actual time varies by skill level and setup",
  "steps": [
    {
      "step_number": "integer",
      "action": "string -- imperative-voice instruction (e.g. 'Sand the surface with 120-grit sandpaper')",
      "detail": "string -- one to two sentences explaining why this step matters for the final result",
      "safety_note": "string or null -- PPE, ventilation, tool caution, or renter flag if applicable; null when no risk is present",
      "broll_tag": "string -- description of the b-roll filming opportunity for this step (e.g. 'Close-up of sandpaper moving across wood grain')",
      "licensed_trade_required": "boolean -- true only for electrical, gas, structural, load-bearing, or hazardous-material steps"
    }
  ],
  "warnings": [
    "string -- overall safety flags that apply across multiple steps or to the project as a whole (e.g. 'Work in a ventilated space when using spray paint or solvent-based finishes')"
  ]
}
```

Output rules:

- `licensed_trade_required: true` replaces the step's `action` and `detail` with the hard boundary note: "Licensed professional required; this step is out of scope for DIY." The `broll_tag` for that step must be set to null.
- `safety_note` is null only when the step involves no physical hazard (no blades, heat, power tools, spray products, solvents, or structural risk). When in doubt, include a brief note.
- `warnings` covers project-level hazards that span multiple steps, such as overall ventilation requirements, dust management, or the need for a helper on heavy or overhead tasks. Omit the field (empty array) only when no project-level warnings apply.
- `estimated_time_per_step` is a rough range for a single average step and must include a plain-language caveat that actual time varies.
- `broll_tag` must be present and descriptive for every step that is not gated by `licensed_trade_required`. It should name the shot type and subject so an editor can plan the capture without reading the full step.
- Do not fabricate product names, brand timings, or cure rates. Use general guidance ("allow adequate drying time per the manufacturer's instructions") rather than specific claims when the exact figure is not in the input.

## Do NOT use for

- Generating a materials or tools list (use materials-list atom).
- Writing content scripts, outlines, hooks, or captions (use script-section, hook-write, or script-writer).
- Projects whose primary scope is electrical, gas, structural, plumbing, or hazardous-material remediation. Those are outside DIY scope per protocols/safety.md. This atom may include one flagged step within a larger safe project, but it cannot scaffold a project that is fundamentally a licensed-trade job.
- Producing platform metadata, thumbnails, or titles (use title-generate or thumbnail-concept).
- Producing a materials cost estimate or sourcing guide (use materials-list).

## References

- `protocols/safety.md` -- DIY trade boundary; licensed-trade hard stop; PPE, ventilation, and wellbeing rules.
- `shared/adaptation-engine.md` -- renter vs owner axis (Axis 2) for renter-friendly step adaptation.
- `shared/brand-engine.md` -- voice and tone for `action` and `detail` copy (published mode).
