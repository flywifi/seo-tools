#!/usr/bin/env python3
"""geo_overlay.py -- offline jurisdictional-overlay engine (P37, optional).

Pure stdlib. Answers "does this project location fall inside this overlay, and when two overlays
collide, which rule governs?" -- for the optional canonical-sources/jurisdiction/ bucket that sits on
top of the construction base. Everything is advisory PLANNING information, NEVER a legal or permitting
determination (see ADVISORY).

Design (from the P37 research, docs/JURISDICTION-OVERLAY-PLAN.md):
- All geometry is EPSG:4326 (WGS84) lon/lat degrees. No reprojection here -- request outSR=4326 from a
  server, or supply 4326 data. This keeps the engine PROJ/GEOS-free (stdlib only).
- Point-in-polygon = ray casting with the half-open vertex rule (no double-count), hole-aware
  (exterior AND-NOT interior rings), multipolygon-aware. A bounding-box pre-filter rejects cheaply
  before the true ring test; the result reports which tier decided.
- Three overlay kinds: `geometry` (point-in-polygon), `attribute` (a FIPS/rule predicate, e.g. HVHZ =
  county in {Miami-Dade, Broward}; SB 4D = stories>=3 and age>=30), `versioned-fact` (a dated value +
  its source, e.g. an SLR projection or an adopted code edition).
- Inter-overlay conflict resolution as cited data: floor/ceiling preemption + Dillon/Home-Rule local
  authority + lex specialis, with a mandatory human-review escape for genuine legal conflicts. Each
  decision is wrapped in a W3C PROV-style audit record.

Coordinate convention: internally every point/ring vertex is (lon, lat) = (x, y), matching GeoJSON
RFC 7946 order. Callers passing (lat, lon) MUST flip first.
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime

ADVISORY = ("Advisory planning information only. Derived from third-party government GIS/legal "
            "sources; NOT an official or legal determination. Flood, zoning, and jurisdiction "
            "overlays are not a substitute for an authoritative determination (e.g. a FEMA flood "
            "determination or the AHJ's ruling); boundaries may be simplified and may lag the source. "
            "Verify locally.")

# Authority rank: lower ordinal = higher authority (federal is highest).
LEVEL_ORDER = {"federal": 1, "state": 2, "regional": 3, "county": 4, "municipal": 5, "community": 6}


# ---- point-in-polygon (ray casting, half-open vertex rule) -------------------
def point_in_ring(pt, ring):
    """True if pt=(lon,lat) is inside the ring (list of (lon,lat)). Ray-casting with the half-open
    convention `(y0 > y) != (y1 > y)` so a ray through a vertex is not double-counted. On-boundary is
    treated as inside (see point_on_segment)."""
    x, y = pt
    n = len(ring)
    if n < 3:
        return False
    inside = False
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        if point_on_segment(pt, (x0, y0), (x1, y1)):
            return True  # explicit boundary policy: on-edge counts as inside
        if (y0 > y) != (y1 > y):
            x_cross = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < x_cross:
                inside = not inside
    return inside


def point_on_segment(pt, a, b, eps=1e-12):
    """True if pt lies on segment a-b (collinear + within bounds), within eps."""
    x, y = pt
    ax, ay = a
    bx, by = b
    cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
    if abs(cross) > eps:
        return False
    if min(ax, bx) - eps <= x <= max(ax, bx) + eps and min(ay, by) - eps <= y <= max(ay, by) + eps:
        return True
    return False


def point_in_polygon(pt, polygon):
    """polygon = list of rings; ring[0] is the exterior, rings[1:] are holes. Inside = inside the
    exterior AND not inside any hole."""
    if not polygon:
        return False
    if not point_in_ring(pt, polygon[0]):
        return False
    for hole in polygon[1:]:
        if point_in_ring(pt, hole):
            return False
    return True


def point_in_multipolygon(pt, multipolygon):
    """multipolygon = list of polygons; inside if inside ANY member polygon."""
    return any(point_in_polygon(pt, poly) for poly in multipolygon)


def bbox_of(multipolygon):
    """Axis-aligned [min_lon, min_lat, max_lon, max_lat] over all rings."""
    xs, ys = [], []
    for poly in multipolygon:
        for ring in poly:
            for x, y in ring:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return [min(xs), min(ys), max(xs), max(ys)]


def in_bbox(pt, bbox):
    x, y = pt
    return bbox is not None and bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]


def contains(pt, multipolygon, bbox=None):
    """Two-tier containment: cheap bbox reject, then the true ring test. Returns
    {contained, decided_by} where decided_by is 'bbox' (fast reject) or 'ring' (exact)."""
    bb = bbox or bbox_of(multipolygon)
    if bb is not None and not in_bbox(pt, bb):
        return {"contained": False, "decided_by": "bbox"}
    return {"contained": point_in_multipolygon(pt, multipolygon), "decided_by": "ring"}


# ---- ingest: GeoJSON (stdlib json) + KML (stdlib xml.etree) -------------------
def geojson_geometry_to_multipolygon(geom):
    """Normalize a GeoJSON geometry dict (Polygon | MultiPolygon) to a list-of-polygons, each a
    list-of-rings of (lon,lat) tuples. Other geometry types return []. Coordinates stay [lon,lat]."""
    if not isinstance(geom, dict):
        return []
    t = geom.get("type")
    coords = geom.get("coordinates")
    if t == "Polygon":
        return [[[tuple(pt[:2]) for pt in ring] for ring in coords]]
    if t == "MultiPolygon":
        return [[[tuple(pt[:2]) for pt in ring] for ring in poly] for poly in coords]
    return []


def parse_geojson(obj):
    """Accept a GeoJSON dict or JSON string; return a list of {properties, multipolygon, bbox}."""
    if isinstance(obj, str):
        obj = json.loads(obj)
    feats = []
    if isinstance(obj, dict) and obj.get("type") == "FeatureCollection":
        items = obj.get("features", [])
    elif isinstance(obj, dict) and obj.get("type") == "Feature":
        items = [obj]
    elif isinstance(obj, dict) and obj.get("type") in ("Polygon", "MultiPolygon"):
        items = [{"type": "Feature", "properties": {}, "geometry": obj}]
    else:
        items = []
    for f in items:
        mp = geojson_geometry_to_multipolygon(f.get("geometry"))
        if mp:
            feats.append({"properties": f.get("properties", {}), "multipolygon": mp, "bbox": bbox_of(mp)})
    return feats


def _localname(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _parse_coord_string(s):
    """KML <coordinates> = whitespace-separated 'lon,lat[,alt]' tuples -> [(lon,lat), ...]."""
    ring = []
    for tok in s.replace("\n", " ").split():
        parts = tok.split(",")
        if len(parts) >= 2:
            try:
                ring.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    return ring


def parse_kml(text):
    """Extract polygons from KML using stdlib xml.etree (namespace-agnostic via local names). Returns
    a list of {properties, multipolygon, bbox}. Each <Polygon> becomes one polygon with an outer ring
    and any innerBoundary rings as holes. Trusted-input only (no external entity handling here)."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    feats = []
    for pm in root.iter():
        if _localname(pm.tag) != "Placemark":
            continue
        name = ""
        polygons = []
        for el in pm.iter():
            ln = _localname(el.tag)
            if ln == "name" and el.text:
                name = el.text.strip()
            if ln == "Polygon":
                outer, holes = [], []
                for sub in el.iter():
                    sln = _localname(sub.tag)
                    if sln == "outerBoundaryIs":
                        for c in sub.iter():
                            if _localname(c.tag) == "coordinates" and c.text:
                                outer = _parse_coord_string(c.text)
                    elif sln == "innerBoundaryIs":
                        for c in sub.iter():
                            if _localname(c.tag) == "coordinates" and c.text:
                                holes.append(_parse_coord_string(c.text))
                if outer:
                    polygons.append([outer] + holes)
        if polygons:
            feats.append({"properties": {"name": name}, "multipolygon": polygons,
                          "bbox": bbox_of(polygons)})
    return feats


# ---- overlay-kind evaluation -------------------------------------------------
def _cmp(op, a, b):
    if op == "in":
        return a in b
    if op == "eq":
        return a == b
    if op == "gte":
        return a is not None and a >= b
    if op == "lte":
        return a is not None and a <= b
    if op == "gt":
        return a is not None and a > b
    if op == "lt":
        return a is not None and a < b
    return False


def eval_attribute(predicate, facts):
    """Evaluate an attribute overlay: a list of {field, op, value} clauses, ALL of which must hold
    (AND). Facts is the project's attribute dict (county_fips, stories, ownership_form, co_age_years,
    ...). Returns {applies, evaluated[]}."""
    clauses = predicate if isinstance(predicate, list) else [predicate]
    results = []
    applies = True
    for c in clauses:
        got = facts.get(c.get("field"))
        ok = _cmp(c.get("op", "eq"), got, c.get("value"))
        results.append({"field": c.get("field"), "op": c.get("op"), "value": c.get("value"),
                        "got": got, "ok": ok})
        applies = applies and ok
    return {"applies": applies, "evaluated": results}


def eval_overlay(overlay, context):
    """Dispatch on overlay['overlay_kind']. context supplies point (lon,lat) and/or facts.
    Returns a result dict carrying the advisory boundary and a source citation."""
    kind = overlay.get("overlay_kind")
    base = {"overlay_id": overlay.get("id"), "overlay_kind": kind, "boundary": ADVISORY,
            "source_citation": overlay.get("source_reference") or overlay.get("source_ids"),
            "human_review_required": True}
    if kind == "geometry":
        pt = context.get("point")
        geom = overlay.get("geometry") or context.get("geometry")  # inline GeoJSON geometry dict
        if pt is None or not geom:
            return {**base, "applies": None, "note": "no point and/or geometry supplied; live-query or cache the boundary first"}
        mp = geojson_geometry_to_multipolygon(geom) if isinstance(geom, dict) else geom
        c = contains(tuple(pt), mp, overlay.get("bbox"))
        return {**base, "applies": c["contained"], "decided_by": c["decided_by"]}
    if kind == "attribute":
        r = eval_attribute(overlay.get("predicate", []), context.get("facts", {}))
        return {**base, "applies": r["applies"], "evaluated": r["evaluated"]}
    if kind == "versioned-fact":
        # Optional applicability predicate: a versioned fact only applies where its predicate holds
        # (e.g. an SE-FL-Compact sea-level-rise projection applies only in the compact counties).
        # No predicate -> applies everywhere (back-compat). Predicate present and failing -> does not
        # apply and the value is nulled so it can never leak outside its scope.
        pred = overlay.get("applicability")
        common = {"effective_date": overlay.get("effective_date"),
                  "source_reference": overlay.get("source_reference"), "as_of": overlay.get("as_of")}
        if pred:
            r = eval_attribute(pred, context.get("facts", {}))
            if not r["applies"]:
                return {**base, "applies": False, "evaluated": r["evaluated"], "value": None,
                        "note": "versioned fact out of scope for these facts/location", **common}
            return {**base, "applies": True, "evaluated": r["evaluated"],
                    "value": overlay.get("value"), **common}
        return {**base, "applies": True, "value": overlay.get("value"), **common}
    return {**base, "applies": None, "note": f"unknown overlay_kind '{kind}'"}


# ---- inter-overlay conflict resolution --------------------------------------
def _authority_rank(rule):
    return LEVEL_ORDER.get(rule.get("jurisdiction_level"), 99)


def _more_stringent(a, b):
    """Return the more-stringent of two rules that carry a comparable stringency {value, direction}.
    direction 'higher_is_stricter' -> larger value wins; 'lower_is_stricter' -> smaller wins. Returns
    (winner_rule, note) or (None, note) if not comparable."""
    sa, sb = a.get("stringency"), b.get("stringency")
    if not sa or not sb or sa.get("direction") != sb.get("direction"):
        return None, "stringency not comparable"
    direction = sa.get("direction")
    va, vb = sa.get("value"), sb.get("value")
    if va is None or vb is None:
        return None, "missing stringency value"
    if va == vb:
        return None, "equal stringency"
    if direction == "higher_is_stricter":
        return (a if va > vb else b), "more-stringent value governs"
    return (a if va < vb else b), "more-stringent value governs"


def resolve_conflict(rule_a, rule_b, actor="engine:geo_overlay"):
    """Resolve a conflict between two applicable rules on the same feature. Cascade:
      1. higher rule is field/ceiling preemption -> higher jurisdiction governs (discard stricter local)
      2. higher rule is a floor AND the more-local rule has local authority:
           - stringency comparable  -> most-stringent governs
           - stringency NOT comparable (e.g. a safety floor vs an aesthetic rule) -> human review
             (a genuine, incommensurable conflict; NEVER decided by an unrelated specificity integer)
      3. no preemption asymmetry (both rules preemption_type 'none') -> lex specialis: the more-specific
         scope governs; a tie escalates to human review
      4. otherwise (a preemption rule is involved that 1 to 2 did not cleanly resolve) -> human review
    Returns a decision dict with a W3C PROV-style audit record. Never fabricates a winner; a safety
    floor is never silently discarded for a lower-authority rule."""
    higher, lower = (rule_a, rule_b) if _authority_rank(rule_a) <= _authority_rank(rule_b) else (rule_b, rule_a)
    decision = {"boundary": ADVISORY, "conflicting": [rule_a.get("id"), rule_b.get("id")]}
    winner, basis, human = None, None, True

    hp = higher.get("preemption_type", "none")
    lp = lower.get("preemption_type", "none")
    if hp in ("field", "ceiling"):
        winner, basis, human = higher, f"higher jurisdiction governs ({hp} preemption)", False
    elif hp == "floor" and lower.get("local_authority") in ("home_rule", "dillon_expressly_granted"):
        w, note = _more_stringent(higher, lower)
        if w is not None:
            winner, basis, human = w, f"floor preemption + local authority: {note}", False
        else:
            # A safety floor meets a local rule the engine cannot rank on a common stringency scale
            # (missing/opposing/incommensurable stringency). This is a GENUINE legal conflict and must
            # escalate -- it is never broken by an unrelated specificity integer, which would silently
            # discard a life-safety floor for an aesthetic or lower-purpose local rule.
            winner, basis, human = None, (f"floor preemption vs local rule with non-comparable "
                                          f"stringency ({note}); genuine legal conflict, human review "
                                          f"required"), True
    elif hp == "none" and lp == "none":
        # No preemption asymmetry: two co-equal rules; the more-specific one refines (lex specialis).
        winner, basis, human = _by_specificity(higher, lower)
    else:
        # A preemption rule is in play that branches 1 to 2 did not cleanly resolve (e.g. a floor
        # without local authority to exceed it). Do not guess -> escalate.
        winner, basis, human = None, ("unresolved preemption interaction (a floor/ceiling/field rule "
                                      "is involved); genuine legal conflict, human review required"), True

    decision.update({
        "winner": (winner or {}).get("id"),
        "governing_rule": winner,
        "basis": basis,
        "human_review_required": human,
        "prov": {  # W3C PROV-style audit
            "activity": "conflict_resolution",
            "used": [rule_a.get("id"), rule_b.get("id")],
            "wasAssociatedWith": actor,
            "generated": (winner or {}).get("id"),
            "basis": basis,
        },
    })
    return decision


def _by_specificity(rule_a, rule_b):
    """lex specialis tiebreak by an integer specificity_scope (higher = more specific/narrower). If a
    clear winner, it governs; if tied or unscored, escalate to human review."""
    sa = rule_a.get("specificity_scope")
    sb = rule_b.get("specificity_scope")
    if isinstance(sa, int) and isinstance(sb, int) and sa != sb:
        w = rule_a if sa > sb else rule_b
        return w, "lex specialis: more-specific scope governs", False
    return None, "genuine legal conflict; human review required", True


# ---- selftest ---------------------------------------------------------------
def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # unit square (0,0)-(1,1), CCW
    sq = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]]
    ok("inside square", point_in_polygon((0.5, 0.5), sq))
    ok("outside square", not point_in_polygon((1.5, 0.5), sq))
    ok("on edge counts inside", point_in_polygon((0.0, 0.5), sq))
    ok("ray through vertex not double-counted (point left of shape)",
       not point_in_polygon((-0.5, 1.0), sq))

    # square with a central hole
    holed = [[(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0), (0.0, 0.0)],
             [(1.0, 1.0), (3.0, 1.0), (3.0, 3.0), (1.0, 3.0), (1.0, 1.0)]]
    ok("inside ring but in hole -> outside", not point_in_polygon((2.0, 2.0), holed))
    ok("inside ring outside hole -> inside", point_in_polygon((0.5, 0.5), holed))

    # multipolygon
    mp = [sq, [[(10.0, 10.0), (11.0, 10.0), (11.0, 11.0), (10.0, 11.0), (10.0, 10.0)]]]
    ok("in second polygon of multipolygon", point_in_multipolygon((10.5, 10.5), mp))
    ok("between polygons -> outside", not point_in_multipolygon((5.0, 5.0), mp))

    # two-tier bbox pre-filter
    r1 = contains((100.0, 100.0), mp)
    ok("bbox fast-rejects far point", r1["contained"] is False and r1["decided_by"] == "bbox")
    r2 = contains((0.5, 0.5), mp)
    ok("ring test decides inside", r2["contained"] is True and r2["decided_by"] == "ring")

    # GeoJSON ingest
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"name": "A"},
         "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}}]}
    feats = parse_geojson(gj)
    ok("geojson parsed one feature", len(feats) == 1 and feats[0]["properties"]["name"] == "A")
    ok("geojson containment", contains((1.0, 1.0), feats[0]["multipolygon"])["contained"])

    # MultiPolygon geojson
    gj2 = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    ok("bare geometry parsed", len(parse_geojson(gj2)) == 1)

    # KML ingest
    kml = ("<kml xmlns='http://www.opengis.net/kml/2.2'><Document><Placemark><name>Z</name>"
           "<Polygon><outerBoundaryIs><LinearRing><coordinates>0,0 3,0 3,3 0,3 0,0"
           "</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>")
    kf = parse_kml(kml)
    ok("kml parsed placemark", len(kf) == 1 and kf[0]["properties"]["name"] == "Z")
    ok("kml containment", contains((1.5, 1.5), kf[0]["multipolygon"])["contained"])

    # overlay-kind: geometry
    geo_overlay = {"id": "hist-x", "overlay_kind": "geometry",
                   "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}}
    rg = eval_overlay(geo_overlay, {"point": (0.5, 0.5)})
    ok("geometry overlay applies", rg["applies"] is True and rg["human_review_required"] is True)

    # overlay-kind: attribute (HVHZ = county in {Miami-Dade, Broward}; SB4D = stories>=3 and age>=30)
    hvhz = {"id": "hvhz", "overlay_kind": "attribute",
            "predicate": [{"field": "county_fips", "op": "in", "value": ["12086", "12011"]}]}
    ok("attribute HVHZ applies in Miami-Dade", eval_overlay(hvhz, {"facts": {"county_fips": "12086"}})["applies"])
    ok("attribute HVHZ not in Orange", not eval_overlay(hvhz, {"facts": {"county_fips": "12095"}})["applies"])
    sb4d = {"id": "sb4d", "overlay_kind": "attribute",
            "predicate": [{"field": "stories", "op": "gte", "value": 3},
                          {"field": "co_age_years", "op": "gte", "value": 30}]}
    ok("attribute SB4D applies (3 story, 32yo)",
       eval_overlay(sb4d, {"facts": {"stories": 4, "co_age_years": 32}})["applies"])
    ok("attribute SB4D not for 2-story",
       not eval_overlay(sb4d, {"facts": {"stories": 2, "co_age_years": 40}})["applies"])

    # overlay-kind: versioned-fact
    slr = {"id": "slr", "overlay_kind": "versioned-fact", "value": 12.0, "effective_date": "2019",
           "source_reference": "SE FL Compact 2019 Unified Projection", "as_of": "2026-07-05"}
    vf = eval_overlay(slr, {})
    ok("versioned-fact returns value+source", vf["value"] == 12.0 and "Compact" in vf["source_reference"])

    # versioned-fact WITH an applicability predicate: scoped by county FIPS (SE FL Compact)
    slr_gated = {"id": "slr-gated", "overlay_kind": "versioned-fact", "value": 12.0,
                 "effective_date": "2019", "source_reference": "SE FL Compact 2019 Unified Projection",
                 "as_of": "2026-07-05",
                 "applicability": [{"field": "county_fips", "op": "in", "value": ["12086", "12011"]}]}
    ok("versioned-fact applies inside its counties (Miami-Dade 12086)",
       eval_overlay(slr_gated, {"facts": {"county_fips": "12086"}})["applies"] is True)
    vf_out = eval_overlay(slr_gated, {"facts": {"county_fips": "12095"}})
    ok("versioned-fact does NOT apply outside its counties (Orange 12095), value nulled",
       vf_out["applies"] is False and vf_out["value"] is None)

    # conflict: ceiling preemption -> higher governs
    fed = {"id": "fed-ceiling", "jurisdiction_level": "federal", "preemption_type": "ceiling"}
    loc = {"id": "loc-strict", "jurisdiction_level": "municipal", "preemption_type": "none",
           "local_authority": "home_rule"}
    d1 = resolve_conflict(fed, loc)
    ok("ceiling -> higher governs, no human review", d1["winner"] == "fed-ceiling" and d1["human_review_required"] is False)

    # conflict: floor + home rule -> most stringent (local) governs
    state_floor = {"id": "state-floor", "jurisdiction_level": "state", "preemption_type": "floor",
                   "stringency": {"value": 130, "direction": "higher_is_stricter"}}
    county_strict = {"id": "county-strict", "jurisdiction_level": "county", "preemption_type": "none",
                     "local_authority": "home_rule", "stringency": {"value": 150, "direction": "higher_is_stricter"}}
    d2 = resolve_conflict(state_floor, county_strict)
    ok("floor+authority -> most stringent (county 150) governs", d2["winner"] == "county-strict" and d2["human_review_required"] is False)

    # conflict: genuine legal conflict (historic frame vs HVHZ window) -> human review
    hist = {"id": "historic-frame", "jurisdiction_level": "municipal", "preemption_type": "none",
            "local_authority": "home_rule", "specificity_scope": 5}
    hvhz_rule = {"id": "hvhz-window", "jurisdiction_level": "state", "preemption_type": "floor",
                 "specificity_scope": 5}
    d3 = resolve_conflict(hist, hvhz_rule)
    ok("genuine conflict -> human review required", d3["human_review_required"] is True and d3["winner"] is None)

    # FIX (P38-2 adversarial finding): a safety FLOOR vs a lower-authority rule the engine cannot rank
    # on a common stringency scale is a GENUINE conflict -> human review, NEVER decided by an unrelated
    # specificity integer (which previously let a municipal aesthetic rule silently discard a state
    # safety floor). Unequal specificity (5 vs 6) must NOT auto-resolve here.
    safety_floor = {"id": "safety-floor", "jurisdiction_level": "state", "preemption_type": "floor",
                    "specificity_scope": 5}
    aesthetic_local = {"id": "aesthetic-local", "jurisdiction_level": "municipal", "preemption_type": "none",
                       "local_authority": "home_rule", "specificity_scope": 6}
    d4 = resolve_conflict(safety_floor, aesthetic_local)
    ok("safety floor vs incommensurable local (unequal specificity) -> human review, no winner",
       d4["human_review_required"] is True and d4["winner"] is None)

    # genuine lex specialis: two co-equal (no-preemption) rules -> the more-specific governs
    coeq_broad = {"id": "coeq-broad", "jurisdiction_level": "county", "preemption_type": "none",
                  "specificity_scope": 3}
    coeq_narrow = {"id": "coeq-narrow", "jurisdiction_level": "county", "preemption_type": "none",
                   "specificity_scope": 6}
    d5 = resolve_conflict(coeq_broad, coeq_narrow)
    ok("lex specialis (both non-preemptive) -> narrower scope governs",
       d5["winner"] == "coeq-narrow" and d5["human_review_required"] is False)

    # a floor WITHOUT local authority to exceed it is not silently resolved -> human review
    d6 = resolve_conflict(
        {"id": "state-floor-2", "jurisdiction_level": "state", "preemption_type": "floor", "specificity_scope": 2},
        {"id": "muni-noauth", "jurisdiction_level": "municipal", "preemption_type": "none", "specificity_scope": 8})
    ok("floor without local authority -> human review, no winner",
       d6["human_review_required"] is True and d6["winner"] is None)

    # PROV audit present
    ok("decision carries PROV audit", d1["prov"]["activity"] == "conflict_resolution" and d1["prov"]["used"])

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
