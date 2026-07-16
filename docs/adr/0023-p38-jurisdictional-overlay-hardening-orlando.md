# 23. P38 Jurisdictional Overlay Hardening Orlando

- Date: 2026-07-07
- Status: Accepted

## Context

P38: fix the bugs the 809 E Amelia test surfaced, prove the architecture correct before loading real data (tests + adversarial gate), then load accurate Orlando data (real values only within ~2 mi of Lake Eola; ToS-limited setback/wind values null-flagged, not fabricated). Advisory-not-legal-determination throughout; live network stays ask-first with no surprise call.

## Decision

Hardened the jurisdictional-overlay architecture and loaded real, cited Orlando/Orange County data. Unified live-network consent (default-on, ask-first per session; headless-safe) across the FEMA flood lookup + US Census geocoding (geo_consent.py, geo_geocode.py); master jurisdictional_overlay switch default-on. An independent adversarial gate caught and fixed two safety-discard bugs in the conflict cascade (non-comparable stringency, and comparison across incommensurable units, now escalate to human review). Cached all 6 City of Orlando historic-district boundaries + the R-2B/T/HP zoning polygon as real GeoJSON with provenance via tools/geo_source_fetch.py; authored 11 cited overlay records; seeded 6 sources and stamped a currency baseline. Fixed a versioned-fact over-fire (rutherford scoped to its county) and excluded *.example.json schema demos from production resolution; invariant 27 now requires every versioned-fact to declare an applicability predicate.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P38-jurisdictional-overlay-hardening-orlando`.
