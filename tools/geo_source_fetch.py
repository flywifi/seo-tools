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
  python3 tools/geo_source_fetch.py --rehash-from-disk    # re-stamp MANIFEST/provenance sha256 from disk bytes
  python3 tools/geo_source_fetch.py --selftest            # offline
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


def _vertex_count(geometry_or_fc):
    """Total coordinate pairs across ALL rings/polygons. P79 A1c: the previous
    len(coordinates[0]) counted the outer ring only, so a polygon with a hole under-reported
    (the zoning cache recorded 128 for a [128, 5]-ring polygon = 133 pairs)."""
    g = geometry_or_fc
    if g.get("type") == "FeatureCollection":
        g = (g.get("features") or [{}])[0].get("geometry") or {}
    elif g.get("type") == "Feature":
        g = g.get("geometry") or {}
    t, c = g.get("type"), g.get("coordinates") or []
    if t == "Polygon":
        return sum(len(r) for r in c)
    if t == "MultiPolygon":
        return sum(len(r) for poly in c for r in poly)
    if t in ("LineString", "MultiPoint"):
        return len(c)
    if t == "MultiLineString":
        return sum(len(l) for l in c)
    return 1 if t == "Point" else 0


def _write_geojson(name, feature_collection, source_url, license_str, extra=None):
    os.makedirs(CACHE_DIR, exist_ok=True)
    # P79 A1a: serialize ONCE, hash the written bytes, write the hashed bytes. The previous form
    # hashed a sort_keys-compact dump but wrote an indent=2 dump, so no stored sha ever matched
    # a file on disk (P78 audit F2, 14/14). indent=2 without sort_keys reproduces the existing
    # cache byte-for-byte, so this is byte-compatible with every committed boundary file.
    body = json.dumps(feature_collection, indent=2)
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    with open(os.path.join(CACHE_DIR, name + ".geojson"), "w", encoding="utf-8") as f:
        f.write(body)
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
        vtx = _vertex_count(feat)
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
        vtx = _vertex_count(z)
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


def rehash_from_disk(cache_dir=None):
    """P79 A1b: repair the F2 defect. Re-stamp MANIFEST.json + every provenance sidecar from the
    bytes actually on disk (and re-count vertices with _vertex_count). No network. Returns the
    number of files re-stamped."""
    cache_dir = cache_dir or CACHE_DIR
    man_path = os.path.join(cache_dir, "MANIFEST.json")
    with open(man_path, encoding="utf-8") as f:
        man = json.load(f)
    for rec in man.get("files", []):
        gj = os.path.join(cache_dir, rec["name"] + ".geojson")
        with open(gj, "rb") as f:
            raw = f.read()
        rec["sha256"] = hashlib.sha256(raw).hexdigest()
        rec["vertices"] = _vertex_count(json.loads(raw.decode("utf-8")))
        prov_path = os.path.join(cache_dir, rec["name"] + ".provenance.json")
        if os.path.exists(prov_path):
            with open(prov_path, encoding="utf-8") as f:
                prov = json.load(f)
            prov["sha256"] = rec["sha256"]
            prov["vertices"] = rec["vertices"]
            prov["rehashed_from_disk"] = datetime.now(timezone.utc).date().isoformat()
            with open(prov_path, "w", encoding="utf-8") as f:
                json.dump(prov, f, indent=2)
    man["rehashed_from_disk"] = datetime.now(timezone.utc).date().isoformat()
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=2)
    return len(man.get("files", []))


def selftest():
    """Offline. Proves the writer's stored sha is the sha of the file it wrote (fails on the
    pre-P79 writer by construction), that _vertex_count counts every ring, and that
    rehash_from_disk restores agreement after a corrupted sidecar."""
    import tempfile
    global CACHE_DIR
    checks = []
    ok = lambda name, cond: checks.append((name, bool(cond)))
    ring_outer = [[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]
    ring_hole = [[0.2, 0.2], [0.2, 0.4], [0.4, 0.4], [0.2, 0.2]]
    fc = {"type": "FeatureCollection", "features": [{"type": "Feature",
          "properties": {"HistoricDistricts": "Fixture"},
          "geometry": {"type": "Polygon", "coordinates": [ring_outer, ring_hole]}}]}
    ok("_vertex_count counts every ring (5 + 4 = 9)", _vertex_count(fc) == 9)
    ok("_vertex_count handles MultiPolygon", _vertex_count(
        {"type": "MultiPolygon", "coordinates": [[ring_outer], [ring_outer, ring_hole]]}) == 14)
    ok("_vertex_count degrades to 0 on an empty geometry", _vertex_count({}) == 0)
    saved = CACHE_DIR
    with tempfile.TemporaryDirectory() as td:
        CACHE_DIR = td
        try:
            m = _write_geojson("fixture", fc, "https://example.com/layer/0", "fixture license",
                               extra={"vertices": _vertex_count(fc)})
            with open(os.path.join(td, "fixture.geojson"), "rb") as f:
                disk = f.read()
            ok("stored sha == sha256 of the written file bytes",
               m["sha256"] == hashlib.sha256(disk).hexdigest())
            with open(os.path.join(td, "fixture.provenance.json"), encoding="utf-8") as f:
                prov = json.load(f)
            ok("provenance sidecar carries the same sha", prov["sha256"] == m["sha256"])
            # corrupt the sidecar + manifest, then repair from disk
            prov["sha256"] = "0" * 64
            with open(os.path.join(td, "fixture.provenance.json"), "w", encoding="utf-8") as f:
                json.dump(prov, f)
            with open(os.path.join(td, "MANIFEST.json"), "w", encoding="utf-8") as f:
                json.dump({"files": [{"name": "fixture", "sha256": "0" * 64, "vertices": 1}]}, f)
            n = rehash_from_disk(td)
            with open(os.path.join(td, "MANIFEST.json"), encoding="utf-8") as f:
                man = json.load(f)
            with open(os.path.join(td, "fixture.provenance.json"), encoding="utf-8") as f:
                prov2 = json.load(f)
            ok("rehash_from_disk re-stamps the manifest sha from disk bytes",
               n == 1 and man["files"][0]["sha256"] == hashlib.sha256(disk).hexdigest())
            ok("rehash_from_disk re-stamps the sidecar sha", prov2["sha256"] == man["files"][0]["sha256"])
            ok("rehash_from_disk re-counts vertices with every ring", man["files"][0]["vertices"] == 9)
            ok("selftest wrote nothing outside the tempdir",
               not os.path.exists(os.path.join(saved, "fixture.geojson")))
        finally:
            CACHE_DIR = saved
    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    print(f"geo_source_fetch selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    if "--rehash-from-disk" in argv:
        n = rehash_from_disk()
        print(json.dumps({"rehashed_from_disk": n, "cache_dir": CACHE_DIR}))
        return 0
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
