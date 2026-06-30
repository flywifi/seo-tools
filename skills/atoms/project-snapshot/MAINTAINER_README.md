---
id: project-snapshot
maintainer: Matt Slason
last_reviewed: 2026-06-30
---

# project-snapshot - Maintainer Notes

## Purpose

This atom produces a one-page project brief (concept level only). It is the first step in the
project-builder spoke and is also callable as a shortcut from document-studio when the source
file is a notes document or project outline.

## Composition

- Input: free-text project idea + optional adaptation axes
- Output: structured snapshot with transformation arc, pillar, aesthetic grounding, and content angles
- Called by: project-builder (step 1), document-studio (step 2, conditional on artifact_type is project_brief)

## What this atom does NOT do

It does not write materials, steps, scripts, or captions. Those are separate atoms composed
downstream by the spoke.

## Testing

Run evals with:
- A clear project idea (e.g., "moody fall mantel makeover with vintage candle holders")
- An ambiguous idea (e.g., "clean up the living room") - expect flags in output
- A renter-ambiguous project (e.g., "add shiplap accent wall") - expect renter_friendly: null + flag
- A project touching electrical (e.g., "install vintage sconce wiring") - expect a safety flag

Verify: no em dashes in output, all ranges use "to", no fabricated product names, pillar matches
expected classification.

## Updating

If Alex's pillar definitions change, update shared/brand-engine.md (source of truth). This atom
reads pillar definitions from that engine at runtime; no update to this SKILL.md is needed unless
the pillar list itself changes.

## Known constraints

- `estimated_time_hours` is always an estimate; drift guard will flag if a maintainer writes a
  specific number without a range.
- Do not add real product SKUs or brand names to evals fixtures; they violate no-fabrication.
