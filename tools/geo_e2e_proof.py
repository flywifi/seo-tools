#!/usr/bin/env python3
"""geo_e2e_proof.py -- synthetic end-to-end architecture proof for the jurisdictional overlay
pipeline (P38-2 verification gate).

Exercises the WHOLE pipeline on SYNTHETIC, clearly-labeled fixture records held in code only (never
written to canonical-sources/, so nothing here can be mistaken for real data): address -> point
(geocode, consent-gated, injected getter) -> attribute overlay -> cached-geometry overlay ->
versioned-fact with applicability gate -> live-geometry overlay (consent gate) -> inter-overlay
conflict. It asserts the architecture is correct BEFORE any real Orlando data is loaded:
  - no fabricated values (a null value stays null),
  - the advisory boundary rides on every result,
  - versioned facts are scoped by applicability (the SLR-over-fire class of bug cannot recur),
  - NO network call happens without per-session consent,
  - a genuine legal conflict escalates to human review rather than an invented winner.

All network is injected. Run offline: python3 tools/geo_e2e_proof.py
"""
from __future__ import annotations

import json
import os
import sys

import geo_consent
import geo_fetch
import geo_geocode
import geo_overlay as go

# A synthetic project point (near, but NOT asserted to be, downtown Orlando). Fixture only.
SYN_POINT = [-81.3730, 28.5450]

# Synthetic overlay records -- SHAPE mirrors the real Orlando slice to come, VALUES are fake.
SYN_ATTR = {  # attribute overlay: applies for a county FIPS
    "id": "syn-orange-attr", "overlay_kind": "attribute", "jurisdiction_level": "county",
    "predicate": [{"field": "county_fips", "op": "eq", "value": "12095"}],
    "source_ids": ["syn-source"], "boundary": "advisory-not-legal-determination"}

SYN_GEOM_CACHED = {  # geometry overlay with an inline cached boundary (a small square around SYN_POINT)
    "id": "syn-cached-district", "overlay_kind": "geometry", "jurisdiction_level": "municipal",
    "geometry": {"type": "Polygon", "coordinates": [[
        [-81.375, 28.543], [-81.371, 28.543], [-81.371, 28.547], [-81.375, 28.547], [-81.375, 28.543]]]},
    "bbox": [-81.375, 28.543, -81.371, 28.547],
    "source_ids": ["syn-source"], "boundary": "advisory-not-legal-determination"}

SYN_VF_ORANGE = {  # versioned-fact scoped to Orange County -> must apply here, value stays null (no fabrication)
    "id": "syn-vf-orange", "overlay_kind": "versioned-fact", "value": None, "effective_date": "2024",
    "source_reference": "synthetic", "as_of": "2026-07-06",
    "applicability": [{"field": "county_fips", "op": "in", "value": ["12095"]}],
    "boundary": "advisory-not-legal-determination"}

SYN_VF_MIAMI = {  # same fact scoped to Miami-Dade -> must NOT apply here (the over-fire guard)
    "id": "syn-vf-miami", "overlay_kind": "versioned-fact", "value": 12.0, "effective_date": "2019",
    "source_reference": "synthetic", "as_of": "2026-07-06",
    "applicability": [{"field": "county_fips", "op": "in", "value": ["12086"]}],
    "boundary": "advisory-not-legal-determination"}

SYN_GEOM_LIVE = {  # geometry overlay whose boundary is only resolvable live (FEMA-like)
    "id": "syn-live-flood", "overlay_kind": "geometry", "jurisdiction_level": "federal",
    "geometry_ref": "live:fema-nfhl-flood-zones", "source_ids": ["syn-source"],
    "boundary": "advisory-not-legal-determination"}

# A genuine conflict pair (equal specificity, no preemption path) -> human review.
SYN_CONFLICT_A = {"id": "syn-historic", "jurisdiction_level": "municipal", "preemption_type": "none",
                  "local_authority": "home_rule", "specificity_scope": 5}
SYN_CONFLICT_B = {"id": "syn-hvhz-like", "jurisdiction_level": "municipal", "preemption_type": "none",
                  "local_authority": "home_rule", "specificity_scope": 5}

ON = {"capabilities": {"jurisdictional_overlay": {"enabled": True}}}  # live absent -> ask/per_session


def _has_boundary(res):
    b = res.get("boundary") or res.get("source_citation")
    return isinstance(b, str) and "advisory" in b.lower()


def proof():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # canned injected getters (no real network anywhere in this proof)
    def geocode_getter(u):
        return {"result": {"addressMatches": [
            {"matchedAddress": "SYNTHETIC ADDRESS", "coordinates": {"x": SYN_POINT[0], "y": SYN_POINT[1]}}]}}

    def flood_getter(u):
        return {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"FLD_ZONE": "X", "SFHA_TF": "F"}}]}

    def exploding(u):
        raise AssertionError("network must not be called without consent")

    session = {}  # ONE session object threaded through the whole run (per-session consent)

    # 1) address -> point, consent-gated (granted once)
    g = geo_geocode.geocode_address("809 synthetic st", config=ON, getter=geocode_getter,
                                    session=session, asker=lambda p: True)
    ok("geocode resolves to the fixture point", g["resolved"] and g["point"] == SYN_POINT)
    ok("geocode carries advisory boundary", _has_boundary(g))
    point = g["point"]
    facts = {"county_fips": "12095"}  # Orange County

    # 2) attribute overlay applies
    a = go.eval_overlay(SYN_ATTR, {"point": point, "facts": facts})
    ok("attribute overlay applies for Orange FIPS", a["applies"] is True)
    ok("attribute result advisory-bounded", _has_boundary(a))

    # 3) cached-geometry overlay contains the point
    gc = go.eval_overlay(SYN_GEOM_CACHED, {"point": point, "facts": facts})
    ok("cached geometry contains the point", gc["applies"] is True and gc["decided_by"] in ("ring", "bbox"))

    # 4) versioned-fact applicability gate (the SLR-over-fire class)
    vfo = go.eval_overlay(SYN_VF_ORANGE, {"facts": facts})
    ok("versioned-fact IN scope applies, value stays null (no fabrication)",
       vfo["applies"] is True and vfo["value"] is None)
    vfm = go.eval_overlay(SYN_VF_MIAMI, {"facts": facts})
    ok("versioned-fact OUT of scope does not apply, value nulled",
       vfm["applies"] is False and vfm["value"] is None)

    # 5) live-geometry overlay WITHOUT prior consent in a fresh session -> config gap, NO network
    fresh = {}
    live_off = geo_fetch.resolve_live("fema-nfhl-flood-zones", point[0], point[1], config=ON,
                                      getter=exploding, session=fresh, asker=None)
    ok("live geometry without consent -> gap, no network",
       live_off["enabled"] is False and live_off["consent"] == "consent_required")

    # 6) live-geometry overlay WITH consent (same session already granted) -> resolves via injected getter
    live_on = geo_fetch.resolve_live("fema-nfhl-flood-zones", point[0], point[1], config=ON,
                                     getter=flood_getter, session=session)  # session already granted in step 1
    ok("live geometry with session consent -> resolves, no re-ask",
       live_on["enabled"] is True and live_on["result"]["flood_zone"] == "X")
    ok("live flood result advisory-bounded", _has_boundary(live_on["result"]))

    # 7) genuine conflict -> human review, no invented winner
    d = go.resolve_conflict(SYN_CONFLICT_A, SYN_CONFLICT_B)
    ok("equal-specificity genuine conflict -> human review, winner null",
       d["human_review_required"] is True and d.get("winner") in (None, ""))

    # 8) consent policy invariant: a fresh session with no asker never touches the network
    d2 = geo_consent.gate(ON, "a flood lookup", session={}, asker=None)
    ok("fresh session, no asker -> consent_required (belt-and-suspenders)", d2["code"] == "consent_required")

    # 9) REAL-record conflict regression (P38-2 adversarial finding): the SHIPPED canonical records
    # must escalate a safety-floor vs lower-purpose-rule collision to human review, never auto-resolve
    # by an unrelated specificity integer. This runs against the real files (not synthetic) so the
    # silent-discard bug can never come back unnoticed.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _load_recs(fname):
        p = os.path.join(root, "canonical-sources", "jurisdiction", fname)
        try:
            return {r["id"]: r for r in json.load(open(p, encoding="utf-8"))
                    if isinstance(r, dict) and r.get("id")}
        except (OSError, ValueError):
            return {}

    real_pairs = [
        ("fl-overlays.json", "fl-hvhz", "fl-miami-historic-district"),
        ("fl-overlays.json", "fl-hvhz", "fl-historic-frame-requirement"),
        ("nc-overlays.json", "nc-mrpa-protected-ridge-statutory", "asheville-historic-design-review"),
        ("nc-overlays.json", "buncombe-steep-slope-high-elevation", "asheville-historic-design-review"),
    ]
    tested = 0
    for fname, ida, idb in real_pairs:
        recs = _load_recs(fname)
        if ida in recs and idb in recs:
            tested += 1
            dd = go.resolve_conflict(recs[ida], recs[idb])
            ok(f"REAL {ida} vs {idb} -> human review, no auto-winner",
               dd["human_review_required"] is True and dd.get("winner") is None)
    ok("real-record conflict regression actually ran (>=1 shipped safety-vs-other pair)", tested >= 1)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"e2e-proof: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(proof())
