# ADR 0057 — Pointing the machinery outward: closing the ChatGPT/OpenAI audit

- Status: accepted
- Date: 2026-09-12
- Phase: P82 (remediation of the 2026-09-07 ChatGPT/OpenAI usage audit)

## Context

Every ChatGPT-facing artifact was reviewed; nineteen standing misalignments turned up: four
live contract defects, a cluster of stale product facts behind fetch-blocked authorities, and an
enforcement class whose checks all pointed inward. The repo's effective ChatGPT knowledge cutoff
was the P72 parity pass; several OpenAI product changes landed after it with no mechanism in the
repo that could notice.

Two defects were the reason to act quickly. The jurisdiction Action's geocode operation composed
a URL that returned 404, which killed the entry point for all three GIS operations. Its flood
operation composed a URL that returned HTTP 200 carrying layer metadata and no flood zone at all,
so a GPT asking about flood hazard received a success with nothing in it and was primed to invent
an answer.

## Decisions

1. **Blocked-source escalation clock, without CI coupling.** The P36 decision that no CI job
   fetches or reports on live source freshness stands. The clock ships instead as report fields
   (`days_blocked`, `overdue`, `blocked_overdue`, plus per-source recommended actions) and as a
   non-blocking advisory embedded in drift invariant 43, which already runs in CI. Advisory
   volume is bounded deliberately: one summary line plus per-source lines for T1 sources only,
   because 112 sources were blocked when this landed and enumerating them all would drown the
   signal. The same lesson applies here: a drowned advisory is an unread advisory.
2. **The function specs carry no `strict` flag.** Strict mode requires `additionalProperties`
   false and every property listed as required; these schemas deliberately use optional
   parameters with defaults. The fix was to remove the undocumented `returns` key instead, whose
   prose moved into `description` where the model actually reads it.
3. **The MCP spec registry entry was swapped, not edited in place.** The old entry's id, name and
   url all encoded the superseded revision, so an in-place url change would have nulled the
   content stamps anyway and left a lying id behind. The superseded seed entry remains in
   `ai-surface-spec-seed.json` as history: re-seeding that file blindly would resurrect the dead
   id, so do not.
4. **Apps SDK packaging is deferred.** The registry claimed two consumers for the Apps SDK
   changelog that do not exist anywhere in the tree; `used_by` is now empty. The repo already
   ships the MCP server that ChatGPT Apps build on, which makes this the smallest-gap absent
   surface if a future phase wants it.
5. **Agent mode stays a tagged bullet.** Promoting it to a modeled surface waits until its
   read and write scope is verified in a browser rather than inferred.
6. **Facts behind fetch-blocked authorities were corrected and tagged, not withheld.** The plan
   caps, memory scope, settings path and desktop merge rest on secondary reporting because the
   help center refuses automated fetches. Each carries a NEEDS VERIFICATION tag naming what a
   human should confirm, which is honest about the confidence without leaving a known-false claim
   in place.

## Verification

Both corrected Action endpoints were probed live on 2026-09-12 before and after the edit: the
geocoder path returned coordinates for the example address, and the flood query returned zone X
with the SFHA flag at the example point. The dual connector envelope was proven under both
installed SDK majors before the wrapper change landed, including the detail that the 2.x result
attribute is `structured_content` rather than the camelCase spelling, which would have made the
new wire assertion silently vacuous. The widened citation scan was dry-run over every tracked
markdown, python and json file: exactly one unregistered citation existed, and it was seeded
before the scan armed. The new surface-budget fixture was mutation-tested by sabotaging the cap
comparison, which turned the selftest red as intended.
