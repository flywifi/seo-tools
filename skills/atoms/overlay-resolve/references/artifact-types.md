---
file: skills/atoms/overlay-resolve/references/artifact-types.md
role: the artifact types this skill produces and the required elements of each.
---

# overlay-resolve artifact types

## Applicable-overlays report (advisory)
The single artifact overlay-resolve produces.

Required elements:
- The verbatim advisory boundary line as the first line of output.
- The resolved location (lon/lat, EPSG:4326) and the facts used (with any unknown fact
  null-and-flagged, never assumed).
- For each applicable overlay: its id and title, `overlay_kind` (geometry / attribute /
  versioned-fact), the source citation (government GIS URL or statute), and how it was decided
  (attribute rule matched, or geometry decided by bbox vs ring; illustrative geometry labeled as
  such).
- Any overlay that could not be decided because a live boundary is needed while
  `jurisdictional_overlay_live` is off: returned as a config gap pointing to cached/manual data, not
  a guess.

Quality-gate dimensions that most apply: Integrity (no fabricated boundaries/values), Accuracy
(citations resolve), Governance (advisory boundary + flag gating), Safety (never a determination).
