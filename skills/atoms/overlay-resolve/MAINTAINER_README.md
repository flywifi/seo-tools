---
file: skills/atoms/overlay-resolve/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for overlay-resolve so it stays stable under iteration.
---

# overlay-resolve: Maintainer README

## Purpose
Given a project location (lon/lat, EPSG:4326) and known building facts, return the ADVISORY
jurisdictional overlays that apply, each cited to its government GIS or statutory source. Attribute
overlays evaluate offline against the facts; geometry overlays resolve by point-in-polygon against a
cached or user-supplied boundary (or, with the live flag, a fetched FEMA/municipal boundary). Its
job ends at "which overlays apply"; resolving a conflict between two of them is `conflict-check`.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Skill-specific:
  - Requires `jurisdictional_overlay`; a live boundary requires the separate
    `jurisdictional_overlay_live`. With the live flag off, a geometry overlay needing a live
    boundary returns a config gap and never fetches.
  - Every applicable overlay is returned with its citation and how it was decided (bbox vs ring, or
    which attribute rule matched); nothing is presented as a determination.
  - Missing facts are null-and-flagged; applicability is never assumed.
  - No fabricated boundaries or values; an unverified geometry is labeled illustrative and resolved
    via the live connector or user-supplied data.

## Known failure modes
- Treating an illustrative bbox as a real boundary and reporting containment as fact.
- Assuming an attribute overlay applies when a required fact is unknown.
- Fetching a live boundary while `jurisdictional_overlay_live` is off.

## Fragile fallbacks that must not become defaults
- The cached/illustrative geometry path is a schema placeholder for real boundaries; acceptable only
  when labeled illustrative, never presented silently as a real boundary.

## Regression cases to preserve
1. HVHZ (attribute, Miami-Dade/Broward FIPS) applies for a matching FIPS, not for a non-HVHZ county.
2. Live flag off + geometry overlay needing a live boundary -> config gap, no network call.
3. Unknown habitable stories or CO age for SB 4D -> null-and-flag, not "applies".
4. `jurisdictional_overlay` off -> reports the capability is off rather than answering.
5. An applicable overlay is always returned with its source citation and decided-by basis.

## Approval-gated changes
The output schema, the set of overlay kinds, the flag gating, and any change that would let a live
fetch happen without `jurisdictional_overlay_live`.

## Minority-report policy
When two source interpretations of applicability disagree (for example a boundary edge case), record
the chosen interpretation, the conflict, why it was chosen, and what evidence would overturn it.

## Update checklist
1. `python3 tools/geo_overlay.py --selftest`.
2. `python3 tools/sync_check.py` (invariant 27).
3. Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
