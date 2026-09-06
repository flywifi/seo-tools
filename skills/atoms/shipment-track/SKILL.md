---
name: shipment-track
atom: true
standalone: true
description: "records a product shipment (from a live carrier lookup or manual entry) and derives the delivered_at anchor that starts a deal's backwards-planning clock. Triggers: 'the product shipped, track it', 'when did the sample arrive', 'the box was delivered yesterday'. Do NOT plan the downstream tasks (task-plan) or bill (milestone-bill). Live tracking is optional and flag-gated; the API key is read from the environment only. delivered_at comes only from the delivered checkpoint, never the estimate."
engines_required:
  - shared/tasks-engine.md
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# shipment-track

Turns a tracking number (or a manual note) into a normalized shipment with a trustworthy delivered date, so
the "draft due N days after the product arrives" clock starts on the real event.

## First line of every output (verbatim)

```
SHIPMENT STATUS FROM THE CARRIER OR YOUR ENTRY. The delivered date anchors backwards-planning; verify it against the actual product receipt. Nothing is billed or scheduled automatically.
```

## When to use this skill
- "the product shipped, here's the tracking number", "did the sample arrive yet", "the box was delivered
  yesterday, start the clock", routed as `shipment_update`.

Do NOT use for:
- Scheduling the downstream tasks (use `task-plan` once delivered_at is known).
- Billing (use `milestone-bill`).

## Inputs
A tracking number (+ optional carrier) for a live lookup, or the fields entered manually (carrier, status,
delivered date). Live lookup requires `shipment_tracking` on and an API key in the environment.

## Core procedure
Follow `shared/method.md`. Call `tools/shipments.py` / the `shipment_track` MCP tool.

### Step 1: fetch or enter
Poll the aggregator (EasyPost default, Ship24 alternative) with the env key, or accept the manual record;
normalize the status to the canonical enum. No key means manual entry, never a guessed status.

### Step 2: set the anchor
Set `delivered_at` only from the delivered checkpoint's timestamp (never the estimate). Before delivery, show
a clearly-labeled provisional date off the estimate. Hand `delivered_at` to `task-plan` as the trigger event.

## Output contract
The normalized shipment (status, checkpoints, est_delivery, delivered_at) and the planning anchor. Honor
`protocols/no-fabrication.md`; `human_review_required`.

## Engines and protocols loaded
`shared/tasks-engine.md`; `protocols/safety.md`, `protocols/no-fabrication.md`,
`protocols/formatting-metadata.md`.

## Atoms used
None. Directly callable and used by `task-desk`; its delivered_at feeds `task-plan`.

## Standalone usability
Records a shipment and derives the delivered anchor offline (manual) or via the flag-gated carrier connector.

## Failure modes
- No API key: falls back to manual entry, never a fabricated status.
- Not yet delivered: the clock is unstarted; only a labeled provisional estimate is shown.
- A carrier reshuffle after delivery: delivered_at is immutable once set from the delivered checkpoint.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
