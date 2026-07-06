#!/usr/bin/env python3
"""geo_fetch.py -- live GIS point queries for jurisdictional overlays (P37, optional, default OFF).

Resolves a project point's overlay membership against LIVE government GIS services (primarily the
FEMA National Flood Hazard Layer) via ArcGIS REST. Strictly gated behind the config flag
`jurisdictional_overlay_live` (separate from and stricter than `jurisdictional_overlay`): with the
flag OFF, this tool makes NO network call -- it returns a config gap and points to cached / manual
data. Advisory planning information only, NEVER an official or legal determination.

Network posture (mirrors source_currency.py / shipments.py): stdlib urllib honoring the env proxy +
CA bundle; no API key (FEMA public endpoint). All network is injected (getter) so the selftest runs
offline.
"""
from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") or "/root/.ccr/ca-bundle.crt"

ADVISORY = ("Advisory planning information only. Derived from a third-party government GIS service; "
            "NOT an official or legal determination and not a substitute for an authoritative "
            "determination (e.g. a FEMA flood determination). Boundaries and zones may lag the source. "
            "Verify with the authority having jurisdiction.")

# FEMA National Flood Hazard Layer (public ArcGIS REST; no token). Layer 28 = Flood Hazard Zones;
# layer 1 = LOMRs (the change signal, since layer 28 has no editingInfo).
FEMA_NFHL_ZONES = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
FEMA_NFHL_LOMRS = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/1"


# ---- config flag -------------------------------------------------------------
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


def live_enabled(config):
    """True only if BOTH jurisdictional_overlay and jurisdictional_overlay_live are on."""
    caps = (config or {}).get("capabilities", {})
    def on(name):
        return bool(caps.get(name, {}).get("enabled")) if isinstance(caps.get(name), dict) else bool(caps.get(name))
    return on("jurisdictional_overlay") and on("jurisdictional_overlay_live")


# ---- ArcGIS REST point query (stdlib urllib, env proxy + CA bundle) ----------
def _http_get_json(url, timeout=15):
    ctx = ssl.create_default_context()
    if os.path.exists(CA_BUNDLE):
        try:
            ctx.load_verify_locations(CA_BUNDLE)
        except Exception:  # noqa: BLE001
            pass
    req = urllib.request.Request(url, headers={"User-Agent": "creator-os-geo-fetch", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))


def _point_query_url(layer_url, lon, lat, out_fields):
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "geojson",
    }
    return layer_url.rstrip("/") + "/query?" + urllib.parse.urlencode(params)


def arcgis_point_query(layer_url, lon, lat, out_fields="*", getter=None):
    """Query an ArcGIS REST layer for features intersecting a point (lon,lat in EPSG:4326). Returns a
    list of feature property dicts. getter(url)->parsed JSON is injected in tests."""
    getter = getter or _http_get_json
    url = _point_query_url(layer_url, lon, lat, out_fields)
    data = getter(url)
    feats = (data or {}).get("features", []) or []
    return [f.get("properties", {}) for f in feats]


def layer_freshness(layer_url, getter=None):
    """Return the ArcGIS layer's editingInfo.lastEditDate (epoch ms) if present, else None. FEMA NFHL
    layer 28 omits it; callers fall back to the LOMRs layer."""
    getter = getter or _http_get_json
    meta = getter(layer_url.rstrip("/") + "?f=json") or {}
    ei = meta.get("editingInfo") or {}
    return ei.get("lastEditDate")


# ---- FEMA flood zone (the flagship live overlay) -----------------------------
def fema_flood_zone(lon, lat, getter=None):
    """Return the FEMA flood zone for a point: {flood_zone, sfha, static_bfe, source, as_of, boundary}.
    Pure query helper (no flag gate here) -- callers must gate on live_enabled first."""
    props = arcgis_point_query(FEMA_NFHL_ZONES, lon, lat,
                               out_fields="FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE", getter=getter)
    if not props:
        return {"flood_zone": None, "sfha": None, "static_bfe": None, "in_sfha": False,
                "source": FEMA_NFHL_ZONES, "as_of": date.today().isoformat(), "boundary": ADVISORY,
                "note": "point returned no NFHL polygon (unmapped or outside a flood zone)"}
    p = props[0]
    sfha = p.get("SFHA_TF")
    return {"flood_zone": p.get("FLD_ZONE"), "zone_subtype": p.get("ZONE_SUBTY"),
            "sfha": sfha, "in_sfha": str(sfha).upper() in ("T", "TRUE", "1"),
            "static_bfe": p.get("STATIC_BFE"), "source": FEMA_NFHL_ZONES,
            "as_of": date.today().isoformat(), "boundary": ADVISORY, "human_review_required": True}


# ---- gated entry point -------------------------------------------------------
def resolve_live(endpoint_id, lon, lat, config=None, getter=None):
    """Resolve a live overlay for a point, GATED by the live flag. endpoint_id names the source
    (e.g. 'fema-nfhl-flood-zones'). With the flag OFF, returns a config gap and makes NO network call."""
    config = config if config is not None else load_config()
    if not live_enabled(config):
        return {"enabled": False, "endpoint_id": endpoint_id, "result": None,
                "config_gap": "jurisdictional_overlay_live is off",
                "hint": "enable jurisdictional_overlay + jurisdictional_overlay_live, or use a cached/"
                        "user-supplied boundary; nothing was fetched", "boundary": ADVISORY}
    if endpoint_id == "fema-nfhl-flood-zones":
        try:
            res = fema_flood_zone(lon, lat, getter=getter)
        except Exception as exc:  # noqa: BLE001
            return {"enabled": True, "endpoint_id": endpoint_id, "result": None,
                    "error": f"{type(exc).__name__}: {str(exc)[:160]}", "boundary": ADVISORY}
        return {"enabled": True, "endpoint_id": endpoint_id, "result": res, "boundary": ADVISORY}
    return {"enabled": True, "endpoint_id": endpoint_id, "result": None,
            "error": f"no live resolver registered for '{endpoint_id}'", "boundary": ADVISORY}


# ---- selftest (offline; injected getter) -------------------------------------
def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # URL construction
    url = _point_query_url(FEMA_NFHL_ZONES, -80.19, 25.77, "FLD_ZONE,SFHA_TF")
    ok("query URL has point geometry + inSR=4326 + geojson",
       "geometry=-80.19%2C25.77" in url and "inSR=4326" in url and "f=geojson" in url
       and "returnGeometry=false" in url)

    # injected getter -> flood zone parse
    def gj_getter(u):
        return {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"FLD_ZONE": "AE", "ZONE_SUBTY": "", "SFHA_TF": "T", "STATIC_BFE": 9.0}}]}
    fz = fema_flood_zone(-80.19, 25.77, getter=gj_getter)
    ok("flood zone parsed (AE, SFHA true, BFE 9)",
       fz["flood_zone"] == "AE" and fz["in_sfha"] is True and fz["static_bfe"] == 9.0)
    ok("flood result carries advisory boundary + human review",
       fz["boundary"] == ADVISORY and fz["human_review_required"] is True)

    # no feature -> unmapped/outside
    fz2 = fema_flood_zone(-100.0, 40.0, getter=lambda u: {"type": "FeatureCollection", "features": []})
    ok("no polygon -> in_sfha False + note", fz2["in_sfha"] is False and "no NFHL polygon" in fz2["note"])

    # freshness parse
    ld = layer_freshness(FEMA_NFHL_LOMRS, getter=lambda u: {"editingInfo": {"lastEditDate": 1700000000000}})
    ok("layer_freshness reads lastEditDate", ld == 1700000000000)
    ok("layer_freshness None when absent", layer_freshness(FEMA_NFHL_ZONES, getter=lambda u: {}) is None)

    # GATE: flag off -> config gap, NO network (getter that raises must never be called)
    def exploding_getter(u):
        raise AssertionError("network must not be called when the live flag is off")
    off = resolve_live("fema-nfhl-flood-zones", -80.19, 25.77,
                       config={"capabilities": {"jurisdictional_overlay": {"enabled": True},
                                                "jurisdictional_overlay_live": {"enabled": False}}},
                       getter=exploding_getter)
    ok("flag off -> config gap, no network", off["enabled"] is False and off["result"] is None and "config_gap" in off)

    # GATE: requires BOTH flags
    off2 = resolve_live("fema-nfhl-flood-zones", -80.19, 25.77,
                        config={"capabilities": {"jurisdictional_overlay": {"enabled": False},
                                                 "jurisdictional_overlay_live": {"enabled": True}}},
                        getter=exploding_getter)
    ok("needs jurisdictional_overlay too -> off", off2["enabled"] is False)

    # GATE: both on -> queries via injected getter
    on = resolve_live("fema-nfhl-flood-zones", -80.19, 25.77,
                      config={"capabilities": {"jurisdictional_overlay": {"enabled": True},
                                               "jurisdictional_overlay_live": {"enabled": True}}},
                      getter=gj_getter)
    ok("both flags on -> result returned", on["enabled"] is True and on["result"]["flood_zone"] == "AE")

    # unknown endpoint
    unk = resolve_live("no-such", 0, 0,
                       config={"capabilities": {"jurisdictional_overlay": {"enabled": True},
                                                "jurisdictional_overlay_live": {"enabled": True}}},
                       getter=gj_getter)
    ok("unknown endpoint -> error, no crash", unk["result"] is None and "error" in unk)

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
    print(f"\nLive enabled right now: {live_enabled(load_config())}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
