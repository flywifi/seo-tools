---
file: skills/jurisdiction-desk/MAINTAINER_README.md
purpose: keep jurisdiction-desk advisory-only and offline-first, and keep genuine legal conflicts routed to human review instead of auto-resolved.
---

# jurisdiction-desk: Maintainer README

## Purpose
Given a Florida or North Carolina project location, resolve which ADVISORY jurisdictional overlays
apply (flood, historic, HVHZ, steep-slope/ridge, watershed, SB 4D milestone) and, when two overlays
collide, which governs. It composes `overlay-resolve` and `conflict-check` over the offline
EPSG:4326 engine (`tools/geo_overlay.py`), then hands off to `govern-artifact`. Its job ends at
advisory planning information; it never issues a legal, permitting, engineering, or code-compliance
determination.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Skill-specific:
  - Every output opens with the verbatim advisory boundary line; overlays are never presented as a
    determination.
  - Two-tier gating: the whole desk is off unless `jurisdictional_overlay` is enabled; a live FEMA
    flood boundary is fetched only when the SEPARATE `jurisdictional_overlay_live` flag is on. With
    the live flag off, a geometry overlay needing a live boundary returns a config gap and points to
    cached/manual data; it never makes a surprise network call.
  - A genuine legal conflict returns `human_review_required` with its W3C PROV audit, never an
    auto-decided winner.
  - Offline-first: attribute and cached-geometry overlays resolve with no network. No heavy C GIS
    deps in the required path (EPSG:4326 only).
  - No fabricated boundaries or values; no copyrighted code text or NOAs (facts/citations only).

## Known failure modes
- Presenting a resolved overlay as authoritative instead of advisory.
- Auto-resolving a historic-frame-vs-HVHZ-window style conflict rather than escalating it.
- Fetching a live boundary while `jurisdictional_overlay_live` is off.
- Assuming applicability when a required fact (FIPS, stories, CO age, elevation) is missing instead
  of null-and-flagging.

## Fragile fallbacks that must not become defaults
- A cached geometry's illustrative bbox is a schema placeholder, not a real boundary; it must be
  resolved against the live connector or user-supplied data before it drives a real answer.

## Regression cases to preserve
1. Live flag off, geometry overlay needing a live boundary -> config gap, no network call.
2. Historic-frame vs HVHZ-window at equal specificity -> `human_review_required`, winner null.
3. `jurisdictional_overlay` off -> the desk says the capability is off rather than answering.

## Update checklist
- Run `python3 tools/geo_overlay.py --selftest` and `python3 tools/geo_fetch.py --selftest`.
- Run `python3 tools/sync_check.py` (invariant 27 covers the jurisdiction records).
