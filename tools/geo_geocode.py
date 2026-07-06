#!/usr/bin/env python3
"""geo_geocode.py -- address -> coordinate geocoding for jurisdictional overlays (P38, optional).

Turns a street address into a lon/lat point (EPSG:4326) so an overlay lookup can run from an address
instead of raw coordinates. Uses the U.S. Census Bureau Geocoder (public, keyless, free). It is a
LIVE network call and is routed through the unified consent policy (geo_consent): default-on but
ASK-FIRST, once per session. With consent not granted (or no interactive prompt available), it
returns a consent/config gap and makes NO network call -- the offline path is a user-supplied point.

Advisory / accuracy note: Census geocoding is rooftop-or-interpolated and NOT survey-grade; it is a
planning convenience, never a legal or survey determination. Network posture mirrors geo_fetch.py:
stdlib urllib honoring the env proxy + CA bundle; no API key. All network is injected (getter) so
the selftest runs offline.
"""
from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import date

import geo_consent  # noqa: E402  (sibling tool module)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") or "/root/.ccr/ca-bundle.crt"

ADVISORY = ("Advisory planning information only. Address geocoding is rooftop-or-interpolated (U.S. "
            "Census Geocoder), NOT survey-grade and NOT a legal or boundary determination. Verify "
            "the location locally.")

# U.S. Census Geocoder (public, keyless). Current address ranges benchmark.
CENSUS_ONELINE = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
CENSUS_BENCHMARK = "Public_AR_Current"


def load_config(root=ROOT):
    """Read creator-os-config.json deep-merged with creator-os-config.local.json (local wins)."""
    base = {}
    for name in ("creator-os-config.json", "creator-os-config.local.json"):
        p = os.path.join(root, name)
        if os.path.exists(p):
            try:
                data = json.loads(open(p, encoding="utf-8").read())
            except (OSError, json.JSONDecodeError):
                continue
            for k, v in data.items():
                if isinstance(v, dict) and isinstance(base.get(k), dict):
                    base[k].update(v)
                else:
                    base[k] = v
    return base


def _http_get_json(url, timeout=15):
    ctx = ssl.create_default_context()
    if os.path.exists(CA_BUNDLE):
        try:
            ctx.load_verify_locations(CA_BUNDLE)
        except Exception:  # noqa: BLE001
            pass
    req = urllib.request.Request(url, headers={"User-Agent": "creator-os-geo-geocode",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))


def _oneline_url(address):
    params = {"address": address, "benchmark": CENSUS_BENCHMARK, "format": "json"}
    return CENSUS_ONELINE + "?" + urllib.parse.urlencode(params)


def census_geocode(address, getter=None):
    """Query the Census one-line geocoder for `address`. Returns a result dict. Pure query helper
    (no consent gate here) -- callers must gate on consent first. getter(url)->parsed JSON injected
    in tests."""
    getter = getter or _http_get_json
    url = _oneline_url(address)
    data = getter(url) or {}
    matches = (((data.get("result") or {}).get("addressMatches")) or [])
    if not matches:
        return {"resolved": False, "address": address, "point": None,
                "note": "no address match returned by the Census geocoder", "source": CENSUS_ONELINE,
                "as_of": date.today().isoformat(), "boundary": ADVISORY}
    m = matches[0]
    coords = m.get("coordinates") or {}
    lon, lat = coords.get("x"), coords.get("y")
    if lon is None or lat is None:
        return {"resolved": False, "address": address, "point": None,
                "note": "match returned without coordinates", "source": CENSUS_ONELINE,
                "as_of": date.today().isoformat(), "boundary": ADVISORY}
    return {"resolved": True, "address": address, "matched_address": m.get("matchedAddress"),
            "point": [lon, lat], "crs": "EPSG:4326", "source": CENSUS_ONELINE,
            "benchmark": CENSUS_BENCHMARK, "as_of": date.today().isoformat(),
            "human_review_required": True, "boundary": ADVISORY,
            "note": "rooftop-or-interpolated; planning convenience, not survey-grade"}


def geocode_address(address, config=None, getter=None, session=None, asker=None):
    """Consent-gated address geocoding. With consent not granted (or headless), returns a gap and
    makes NO network call; the caller falls back to a user-supplied point."""
    config = config if config is not None else load_config()
    decision = geo_consent.gate(config, purpose=f"geocoding the address '{address}'",
                                service="U.S. Census Geocoder", session=session, asker=asker)
    if not decision["proceed"]:
        return {"resolved": False, "address": address, "point": None, "code": decision["code"],
                "reason": decision["reason"], "prompt": decision.get("prompt"),
                "hint": "supply a longitude/latitude directly to run overlays without geocoding",
                "boundary": ADVISORY}
    try:
        res = census_geocode(address, getter=getter)
    except Exception as exc:  # noqa: BLE001
        return {"resolved": False, "address": address, "point": None, "code": "error",
                "reason": f"{type(exc).__name__}: {str(exc)[:160]}", "boundary": ADVISORY}
    return {**res, "code": "ok"}


# ---- selftest (offline; injected getter) -------------------------------------
def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    ON = {"capabilities": {"jurisdictional_overlay": {"enabled": True}}}

    # URL construction
    url = _oneline_url("809 E Amelia St, Orlando FL 32803")
    ok("oneline URL has onelineaddress + benchmark + urlencoded address",
       "onelineaddress" in url and f"benchmark={CENSUS_BENCHMARK}" in url and "Amelia" in url)

    # injected getter -> parse a match
    def match_getter(u):
        return {"result": {"addressMatches": [
            {"matchedAddress": "809 E AMELIA ST, ORLANDO, FL, 32803",
             "coordinates": {"x": -81.3728, "y": 28.5449}}]}}
    r = census_geocode("809 E Amelia St, Orlando FL 32803", getter=match_getter)
    ok("match parsed to lon/lat EPSG:4326",
       r["resolved"] is True and r["point"] == [-81.3728, 28.5449] and r["crs"] == "EPSG:4326")
    ok("geocode result carries advisory boundary + human review",
       r["boundary"] == ADVISORY and r["human_review_required"] is True)

    # no match
    r2 = census_geocode("nowhere at all", getter=lambda u: {"result": {"addressMatches": []}})
    ok("no match -> resolved False + note", r2["resolved"] is False and "no address match" in r2["note"])

    # CONSENT: master off -> feature_off, NO network
    def exploding(u):
        raise AssertionError("network must not be called without consent")
    d0 = geocode_address("x", config={"capabilities": {"jurisdictional_overlay": {"enabled": False}}},
                         getter=exploding, session={}, asker=lambda p: True)
    ok("master off -> feature_off, no network", d0["resolved"] is False and d0["code"] == "feature_off")

    # CONSENT: ask + no asker (headless) -> consent_required, NO network
    d1 = geocode_address("x", config=ON, getter=exploding, session={}, asker=None)
    ok("ask + no asker -> consent_required, no network",
       d1["resolved"] is False and d1["code"] == "consent_required" and d1.get("prompt"))

    # CONSENT: ask + grant -> resolves via injected getter
    sess = {}
    d2 = geocode_address("809 E Amelia St, Orlando FL 32803", config=ON, getter=match_getter,
                         session=sess, asker=lambda p: True)
    ok("ask + grant -> resolved", d2["resolved"] is True and d2["point"] == [-81.3728, 28.5449])
    ok("grant recorded in session", sess.get("granted_live") is True)

    # CONSENT: second call same session -> no re-ask (exploding asker must not fire)
    d3 = geocode_address("809 E Amelia St, Orlando FL 32803", config=ON, getter=match_getter,
                         session=sess, asker=lambda p: (_ for _ in ()).throw(AssertionError("no re-ask")))
    ok("granted session -> geocodes without re-asking", d3["resolved"] is True)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(__doc__)
    print("\nAdvisory boundary:\n  " + ADVISORY)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
