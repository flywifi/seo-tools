---
file: skills/atoms/styling-variant/SKILL.md
name: styling-variant
description: "generates 2 to 3 aesthetic remixes of a completed home decor project with specific swap suggestions; does NOT fabricate specific product SKUs or prices, and does NOT write step sequences or materials lists."
load:
  - shared/brand-engine.md
  - shared/adaptation-engine.md
  - protocols/no-fabrication.md
---

# styling-variant

## Purpose

This atom takes a finished home decor project and produces 2 to 3 aesthetic variants that rework its look without changing its structure or construction steps. Each variant stays grounded in the home decor aesthetic base that defines the Creator OS brand, then shifts one or more design levers (color palette, texture, hardware finish, fabric weight, patina level) to reach a distinct but believable alternate mood.

Variants deliver actionable swap suggestions written in descriptive sensory language ("aged brass hardware", "linen drop cloth", "deep terracotta limewash") rather than specific product SKUs or prices. The atom surfaces persona alignment and rough effort and budget direction so downstream spokes can route the variants to the right content format or audience segment.

## Inputs

| Field | Type | Required | Notes |
|---|---|---|---|
| `project_title` | string | yes | Human-readable name of the completed project (e.g., "Vintage Arched Mirror Makeover") |
| `base_aesthetic` | string | yes | Starting aesthetic mood of the original project (e.g., "home decor", "rustic farmhouse") |
| `target_personas` | list of strings | no | Persona labels from `shared/audience-engine.md`; when omitted, the atom selects the best-fit personas from the brand roster |

## Output

The atom returns a structured object with the following shape.

```
variants: list of 2 to 3 objects
  aesthetic_name: string
    A short label for this variant mood (e.g., "Rustic Farmhouse", "Maximalist Baroque")
  key_changes: list of objects
    item: string
      The element being swapped (e.g., "hardware", "fabric", "paint finish")
    swap_description: string
      Descriptive language for the replacement (e.g., "swap to aged brass bin pulls with a hand-rubbed patina")
  persona_fit: string
    Which persona or personas this variant serves best, and a one-sentence reason
  difficulty_delta: enum [easier, same, harder]
    Effort shift relative to the original project
  budget_delta: enum [lower, same, higher]
    Spend direction relative to the original project

notes: string (optional)
  Fabrication flags, brand cautions, or adaptation-engine caveats that the calling spoke should surface
```

All descriptive language must follow `shared/brand-engine.md` voice guidelines (warm, specific, tactile) and `shared/adaptation-engine.md` platform tone rules. Any field that cannot be determined without fabricating data must be set to null and flagged in `notes` per `protocols/no-fabrication.md`.

## Do NOT use for

- Writing step-by-step instructions or materials lists (use a construction atom for that).
- Generating product recommendations with specific brand names, SKUs, or prices.
- Producing more than 3 variants in a single call (request a second call if more are needed).
- Aesthetic remixes of non-decor projects (apparel, food, digital design, etc.).
- Validating that a proposed swap is achievable without fabricating sourcing or availability data.

## Pipeline note

`styling-variant` is a pure generation atom. It reads brand and adaptation engines at load time and emits a structured variants object. It does not write to the pipeline CRM, does not call any scoop cache layer, and does not trigger quality review. The calling spoke is responsible for passing the output to `quality-review/` before surfacing variants to the creator or publishing them downstream.

## Cross-modality
Inherits its calling spoke's class (Class A); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
