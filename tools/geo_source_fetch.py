#!/usr/bin/env python3
"""geo_source_fetch.py -- grab the real government GIS files/pages a jurisdiction lookup needs.

Two jobs:
  1. THE UNIVERSAL PATH (example): every public endpoint below does point-in-polygon SERVER-SIDE, so
     any caller that can make an HTTPS request -- an MCP tool, a Custom GPT Action, a Gemini function,
     this script, or a human with curl -- gets the same overlay answer for an address. The offline
     engine (tools/geo_overlay.py) is the privacy path when a local Python runtime exists; this is the
     fetch path that also works to cache real boundaries for that engine.
  2. THE BUILD-TIME CACHER: `--cache-orlando` writes the real historic-district + zoning boundary
     polygons (GeoJSON, EPSG:4326) into canonical-sources/jurisdiction/orlando-boundaries/ with a
     provenance sidecar per file and a MANIFEST.json, so the offline overlay records can resolve
     against real boundaries with no runtime network call.

Stdlib only. Honors the env HTTPS proxy + CA bundle (like tools/geo_fetch.py). No API key. All data is
public-records government GIS; every output carries the advisory-not-legal-determination boundary.

Usage:
  python3 tools/geo_source_fetch.py resolve "809 E Amelia St, Orlando FL 32803"   # universal-path demo
  python3 tools/geo_source_fetch.py --cache-orlando                               # cache all boundaries
"""
from __future__ import annotations

import hashlib
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") or "/root/.ccr/ca-bundle.crt"
CACHE_DIR = os.path.join(ROOT, "canonical-sources", "jurisdiction", "orlando-boundaries")

ADVISORY = ("Advisory planning information only, derived from public government GIS; NOT a legal, "
            "survey, or permitting determination. Boundaries may be simplified or lag the source. "
            "Verify with the authority having jurisdiction.")

CENSUS_GEOCODER = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

# Authoritative public endpoints (verified live). Each does point-in-polygon via /query.
HISTORIC_LAYER = "https://services5.arcgis.com/mMuoPCaIYD4wEgDl/arcgis/rest/services/OrlandoHistoricLocalDistricts/FeatureServer/0"
ZONING_LAYER = "https://services5.arcgis.com/mMuoPCaIYD4wEgDl/arcgis/rest/services/OrlandoLUZoning/FeatureServer/0"
FEMA_NFHL_28 = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
SJRWMD_WMD = "https://services.arcgis.com/s8wtJX9suxFen6TA/arcgis/rest/services/Florida_Water_Management_Districts/FeatureServer/0"

HISTORIC_LICENSE = ("City of Orlando open data / public records. The City disclaims legal-boundary "
                    "accuracy ('not legally binding', 'spatially inaccurate', 'as is'). Advisory only.")
ZONING_LICENSE = "City of Orlando open data / public records. Advisory only; setback values live in the Ch.58 code (not cached)."


def _ctx():
    ctx = ssl.create_default_context()
    if os.path.exists(CA_BUNDLE):
        try:
            ctx.load_verify_locations(CA_BUNDLE)
        except Exception:  # noqa: BLE001
            pass
    return ctx


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "creator-os-geo-source-fetch",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        return r.read().decode("utf-8")


def geocode(address):
    q = urllib.parse.urlencode({"address": address, "benchmark": "Public_AR_Current", "format": "json"})
    data = json.loads(_get(CENSUS_GEOCODER + "?" + q))
    matches = (data.get("result") or {}).get("addressMatches") or []
    if not matches:
        raise SystemExit(f"No geocoder match for: {address}")
    c = matches[0]["coordinates"]
    return c["x"], c["y"], matches[0].get("matchedAddress")


def _query(layer_url, params):
    return json.loads(_get(layer_url.rstrip("/") + "/query?" + urllib.parse.urlencode(params)))


def point_query(layer_url, lon, lat, out_fields="*", return_geometry=False):
    return _query(layer_url, {
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "outFields": out_fields,
        "returnGeometry": "true" if return_geometry else "false", "outSR": "4326", "f": "geojson"})


def _slug(s):
    return "".join(c if c.isalnum() else "_" for c in (s or "").lower()).strip("_")


def _write_geojson(name, feature_collection, source_url, license_str, extra=None):
    os.makedirs(CACHE_DIR, exist_ok=True)
    body = json.dumps(feature_collection, sort_keys=True).encode("utf-8")
    sha = hashlib.sha256(body).hexdigest()
    with open(os.path.join(CACHE_DIR, name + ".geojson"), "w", encoding="utf-8") as f:
        json.dump(feature_collection, f, indent=2)
    prov = {"file": name + ".geojson", "source_url": source_url, "license": license_str,
            "fetched_at": datetime.now(timezone.utc).isoformat(), "sha256": sha, "boundary": ADVISORY}
    if extra:
        prov.update(extra)
    with open(os.path.join(CACHE_DIR, name + ".provenance.json"), "w", encoding="utf-8") as f:
        json.dump(prov, f, indent=2)
    return {"name": name, "sha256": sha, "source_url": source_url}


def cache_orlando():
    """Fetch + cache all 6 Orlando local historic-district boundaries and the R-2B/T/HP zoning polygon
    at the Lake Eola / 809 E Amelia point. Returns a manifest list."""
    manifest = []

    # All 6 historic districts, each saved as its own single-feature GeoJSON.
    fc = _query(HISTORIC_LAYER, {"where": "1=1", "outFields": "HistoricDistricts",
                                 "returnGeometry": "true", "outSR": "4326", "f": "geojson"})
    feats = fc.get("features") or []
    print(f"historic districts returned: {len(feats)}")
    for feat in feats:
        district = (feat.get("properties") or {}).get("HistoricDistricts", "district")
        one = {"type": "FeatureCollection", "features": [feat]}
        vtx = len((feat.get("geometry") or {}).get("coordinates", [[]])[0])
        m = _write_geojson("hist_" + _slug(district), one, HISTORIC_LAYER, HISTORIC_LICENSE,
                           extra={"district": district, "vertices": vtx, "layer": "OrlandoHistoricLocalDistricts/0"})
        m["district"] = district
        m["vertices"] = vtx
        manifest.append(m)
        print(f"  cached hist_{_slug(district)}.geojson  ({vtx} vertices)  {district}")

    # Zoning polygon at the 809 E Amelia point (R-2B/T/HP).
    lon, lat, _ = geocode("809 E Amelia St, Orlando FL 32803")
    zfc = point_query(ZONING_LAYER, lon, lat, out_fields="Zoning,OverlayA,OverlayB,OverlayC,OverlayD",
                      return_geometry=True)
    if zfc.get("features"):
        z = zfc["features"][0]
        zoning = (z.get("properties") or {}).get("Zoning", "zoning")
        vtx = len((z.get("geometry") or {}).get("coordinates", [[]])[0])
        m = _write_geojson("zoning_" + _slug(zoning) + "_lake_eola",
                           {"type": "FeatureCollection", "features": [z]}, ZONING_LAYER, ZONING_LICENSE,
                           extra={"zoning": zoning, "vertices": vtx, "at_point": [lon, lat],
                                  "layer": "OrlandoLUZoning/0"})
        m["zoning"] = zoning
        m["vertices"] = vtx
        manifest.append(m)
        print(f"  cached zoning_{_slug(zoning)}_lake_eola.geojson  ({vtx} vertices)  {zoning}")

    with open(os.path.join(CACHE_DIR, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump({"generated_by": "tools/geo_source_fetch.py --cache-orlando",
                   "generated_at": datetime.now(timezone.utc).isoformat(),
                   "boundary": ADVISORY, "files": manifest}, f, indent=2)
    print(f"\nwrote {len(manifest)} boundary files + MANIFEST.json to {CACHE_DIR}")
    return manifest


def resolve(address):
    """Universal-path demo: geocode + which overlays contain the point (server-side point-in-polygon)."""
    print(f"# {ADVISORY}\n# Resolving: {address}\n")
    lon, lat, matched = geocode(address)
    print(f"geocoded (US Census) -> lon={lon}, lat={lat}  [{matched}]\n")
    for label, layer, field in [("historic", HISTORIC_LAYER, "HistoricDistricts"),
                                ("zoning", ZONING_LAYER, "Zoning"),
                                ("flood", FEMA_NFHL_28, "FLD_ZONE"),
                                ("water_district", SJRWMD_WMD, "NAME")]:
        try:
            fc = point_query(layer, lon, lat, out_fields=field)
            vals = [(f.get("properties") or {}).get(field) for f in (fc.get("features") or [])]
            print(f"[{label}] {field} = {', '.join(str(v) for v in vals) if vals else '(none here)'}")
        except Exception as exc:  # noqa: BLE001
            print(f"[{label}] query failed: {type(exc).__name__}: {exc}")


def main(argv):
    if "--cache-orlando" in argv:
        cache_orlando()
        return 0
    if argv and argv[0] == "resolve":
        resolve(argv[1] if len(argv) > 1 else "809 E Amelia St, Orlando FL 32803")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
