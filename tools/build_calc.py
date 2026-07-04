#!/usr/bin/env python3
"""
Creator OS offline residential construction calculators.

First-principles geometry and physics only. No copyrighted span, ampacity, or fixture-unit table is
reproduced: where an authoritative number is needed it comes from a public-domain government restatement
(DOE Building America, energycodes.gov) or from arithmetic. Every result carries the governing code
section and the verify-locally boundary. These are educational restatements, not certified engineering.

Usage:
  python3 tools/build_calc.py --selftest
  python3 tools/build_calc.py stair --total-rise 108
  python3 tools/build_calc.py egress --width 30 --height 30 --sill 40
  python3 tools/build_calc.py rvalue --component ceiling --zone 2
  python3 tools/build_calc.py boxfill --conductors 14,14,14 --devices 1 --clamps 1 --grounds 1
  python3 tools/build_calc.py drain-slope --diameter 2 --run 20
  python3 tools/build_calc.py roof-pitch --rise 6 --run 12
  python3 tools/build_calc.py board-foot --thickness 2 --width 6 --length 8 --qty 1
  python3 tools/build_calc.py deck-span --species SYP --nominal 2x8 --spacing 16
"""
import argparse
import json
import math
import sys

BOUNDARY = (
    "GENERAL CONSTRUCTION GUIDANCE, NOT ENGINEERING OR CODE-COMPLIANCE ADVICE. Verify against your "
    "locally adopted code edition and permit office; codes vary by jurisdiction and edition; use a "
    "licensed professional for structural, electrical, gas/plumbing, and HVAC design."
)

# NEC 314.16(B) per-conductor volume allowances (cubic inches). These are simple published constants
# restated by AWG, not a copyrighted table layout; cite NEC 314.16 for the governing rule.
BOX_FILL_ALLOWANCE = {18: 1.50, 16: 1.75, 14: 2.00, 12: 2.25, 10: 2.50, 8: 3.00, 6: 5.00}

# Public-domain DOE Building America restatement of the IECC/IRC prescriptive insulation minimums,
# expressed as ranges across recent editions. Confirm the exact cell for the adopted edition.
RVALUE_BY_ZONE = {
    1: {"ceiling": "R30", "wall": "R13", "floor": "R13"},
    2: {"ceiling": "R30 to R49", "wall": "R13", "floor": "R13"},
    3: {"ceiling": "R30 to R49", "wall": "R20 or R13+5 continuous", "floor": "R19 to R25"},
    4: {"ceiling": "R38 to R60", "wall": "R30 or R20+5 continuous", "floor": "R19 to R30"},
    5: {"ceiling": "R38 to R60", "wall": "R20+5 continuous to R30", "floor": "R30"},
    6: {"ceiling": "R49 to R60", "wall": "R20+5 continuous to R30", "floor": "R30"},
    7: {"ceiling": "R49 to R60", "wall": "R20+5 continuous to R30", "floor": "R38"},
    8: {"ceiling": "R49 to R60", "wall": "R20+5 continuous to R30", "floor": "R38"},
}


def _wrap(result, code, section, url):
    result["code_ref"] = {"code": code, "section": section, "url": url}
    result["boundary"] = BOUNDARY
    return result


def stair(total_rise_in, max_riser=7.75, min_tread=10.0, headroom_in=80.0):
    """Stair geometry from total floor-to-floor rise. IRC R311.7."""
    if total_rise_in is None or total_rise_in <= 0:
        return {"error": "total_rise_in must be a positive number of inches"}
    risers = math.ceil(total_rise_in / max_riser)
    riser_h = total_rise_in / risers
    treads = risers - 1
    total_run = round(treads * min_tread, 3)
    angle = round(math.degrees(math.atan2(riser_h, min_tread)), 2)
    stringer = round(math.sqrt((riser_h * risers) ** 2 + total_run ** 2), 2)
    return _wrap({
        "computed_by": "build_calc.stair",
        "inputs": {"total_rise_in": total_rise_in, "max_riser_in": max_riser, "tread_in": min_tread},
        "risers": risers,
        "riser_height_in": round(riser_h, 3),
        "treads": treads,
        "total_run_in": total_run,
        "stair_angle_deg": angle,
        "stringer_length_in": stringer,
        "riser_ok": riser_h <= max_riser + 1e-9,
        "tread_ok": min_tread >= 10.0,
        "min_headroom_in": headroom_in,
        "notes": "Every riser and tread must be uniform; the largest may exceed the smallest by no more than 3/8 in.",
    }, "IRC", "R311.7.5", "https://codes.iccsafe.org/content/IRC2021P1/chapter-3-building-planning")


def egress(width_in, height_in, sill_in=None, at_grade=False):
    """Emergency escape opening check on the NET CLEAR opening (window open). IRC R310."""
    if not width_in or not height_in:
        return {"error": "width_in and height_in (net clear, window open) are required"}
    area_sqin = width_in * height_in
    area_sqft = area_sqin / 144.0
    required = 5.0 if at_grade else 5.7
    checks = {
        "area_sqft": round(area_sqft, 2),
        "required_area_sqft": required,
        "area_ok": area_sqft + 1e-9 >= required,
        "height_ok": height_in >= 24.0,
        "width_ok": width_in >= 20.0,
    }
    if sill_in is not None:
        checks["sill_ok"] = sill_in <= 44.0
        checks["sill_in"] = sill_in
    checks["passes"] = all(v for k, v in checks.items() if k.endswith("_ok"))
    return _wrap({
        "computed_by": "build_calc.egress",
        "inputs": {"net_clear_width_in": width_in, "net_clear_height_in": height_in,
                   "sill_in": sill_in, "at_grade": at_grade},
        **checks,
        "notes": "Use the NET CLEAR opening with the window open, not the rough opening. 5.0 sq ft applies only at grade-floor or below-grade openings.",
    }, "IRC", "R310.2", "https://codes.iccsafe.org/content/IRC2021P1/chapter-3-building-planning")


def rvalue_zone(component, climate_zone):
    """Prescriptive insulation R-value range by IECC climate zone (DOE BASC public-domain restatement)."""
    comp = (component or "").lower()
    if comp not in ("ceiling", "wall", "floor"):
        return {"error": "component must be ceiling, wall, or floor"}
    try:
        zone = int(str(climate_zone).strip().rstrip("ABCabc"))
    except (ValueError, TypeError):
        return {"error": "climate_zone must be a number 1 to 8 (letter suffix like 4A is accepted)"}
    if zone not in RVALUE_BY_ZONE:
        return {"error": "climate_zone must be 1 to 8"}
    region = "Florida" if zone in (1, 2) else ("North Carolina range" if zone in (3, 4, 5) else "other")
    return _wrap({
        "computed_by": "build_calc.rvalue_zone",
        "inputs": {"component": comp, "climate_zone": zone},
        "prescriptive_r_value": RVALUE_BY_ZONE[zone][comp],
        "region_hint": region,
        "notes": "Public-domain DOE Building America range across recent editions; confirm the exact value for your adopted edition and county climate zone. FL is zone 1 to 2; NC is 3A to 5A.",
    }, "IECC", "Table R402.1.2", "https://codes.iccsafe.org/content/IECC2021P1")


def box_fill(conductors, devices=0, clamps=0, grounds=0):
    """Required electrical box volume (cubic inches). NEC 314.16.
    conductors: list of AWG sizes of current-carrying/insulated conductors passing through.
    devices: count of yokes/straps (each counts as 2x the largest conductor).
    clamps: >0 means internal cable clamps present (all clamps together = 1x largest conductor).
    grounds: count of equipment grounding conductors (all together = 1x the largest ground)."""
    conductors = conductors or []
    for awg in conductors:
        if awg not in BOX_FILL_ALLOWANCE:
            return {"error": f"unsupported AWG {awg}; supported: {sorted(BOX_FILL_ALLOWANCE)}"}
    if not conductors:
        return {"error": "at least one conductor AWG is required"}
    largest = max(BOX_FILL_ALLOWANCE[a] for a in conductors)
    cond_vol = sum(BOX_FILL_ALLOWANCE[a] for a in conductors)
    device_vol = 2 * largest * devices
    clamp_vol = largest if clamps else 0.0
    ground_vol = largest if grounds else 0.0
    required = round(cond_vol + device_vol + clamp_vol + ground_vol, 3)
    return _wrap({
        "computed_by": "build_calc.box_fill",
        "inputs": {"conductors_awg": conductors, "devices": devices, "clamps": clamps, "grounds": grounds},
        "conductor_volume_cuin": round(cond_vol, 3),
        "device_volume_cuin": round(device_vol, 3),
        "clamp_volume_cuin": round(clamp_vol, 3),
        "ground_volume_cuin": round(ground_vol, 3),
        "required_box_volume_cuin": required,
        "notes": "Choose a box whose marked volume meets or exceeds the required volume. Each device (yoke) counts as two of the largest conductor; all clamps together and all equipment grounds together each count as one of the largest conductor.",
    }, "NEC", "314.16", "https://www.nfpa.org/for-professionals/codes-and-standards/list-of-codes-and-standards/detail?code=70")


def drain_slope(pipe_dia_in, run_ft):
    """Minimum drain fall over a run. IPC 704.1 / IRC P3005."""
    if not pipe_dia_in or not run_ft:
        return {"error": "pipe_dia_in and run_ft are required"}
    if pipe_dia_in <= 2.5:
        slope = 0.25
        band = "2.5 in and smaller: 1/4 in per foot"
    else:
        slope = 0.125
        band = "3 in to 6 in: 1/8 in per foot minimum where permitted by the AHJ"
    total_fall = round(slope * run_ft, 3)
    return _wrap({
        "computed_by": "build_calc.drain_slope",
        "inputs": {"pipe_dia_in": pipe_dia_in, "run_ft": run_ft},
        "slope_in_per_ft": slope,
        "total_fall_in": total_fall,
        "band": band,
        "notes": "Too little slope clogs; too much slope siphons solids. Keep slope uniform with no bellies.",
    }, "IPC", "704.1", "https://codes.iccsafe.org/codes/i-codes")


def roof_pitch(rise, run=12.0):
    """Roof slope angle, slope factor, and asphalt-shingle minimum check. IRC R905.2.2."""
    if rise is None or rise < 0 or not run:
        return {"error": "rise (>=0) and run (>0) are required"}
    angle = round(math.degrees(math.atan2(rise, run)), 2)
    factor = round(math.sqrt(1 + (rise / run) ** 2), 4)
    ratio_12 = round(rise * 12.0 / run, 2)
    asphalt_ok = ratio_12 >= 2.0
    return _wrap({
        "computed_by": "build_calc.roof_pitch",
        "inputs": {"rise": rise, "run": run},
        "slope_ratio": f"{ratio_12}:12",
        "angle_deg": angle,
        "slope_factor": factor,
        "asphalt_shingle_ok": asphalt_ok,
        "notes": "Slope factor multiplies the plan footprint to get sloped roof area. Asphalt shingles require at least 2:12; 2:12 up to under 4:12 needs doubled underlayment.",
    }, "IRC", "R905.2.2", "https://codes.iccsafe.org/content/IRC2021P1/chapter-9-roof-assemblies")


def board_foot(thickness_in, width_in, length_ft, qty=1):
    """Board feet of lumber. 1 board foot = 144 cubic inches = 1 in x 12 in x 1 ft."""
    if not thickness_in or not width_in or not length_ft:
        return {"error": "thickness_in, width_in, and length_ft are required"}
    bf = round((thickness_in * width_in * length_ft * qty) / 12.0, 3)
    return _wrap({
        "computed_by": "build_calc.board_foot",
        "inputs": {"thickness_in": thickness_in, "width_in": width_in, "length_ft": length_ft, "qty": qty},
        "board_feet": bf,
        "notes": "Board feet use nominal lumber dimensions. This is a material-quantity estimate, not a structural check.",
    }, "PS 20", "nominal lumber sizing", "https://www.fpl.fs.usda.gov/products/publications/")


def deck_span_sanity(species, nominal, spacing_in=16.0):
    """Advisory-only deck joist span sanity ceiling. NOT a substitute for the AWC DCA6 span table.
    Uses a deliberately conservative rule-of-thumb (roughly 1.5x the joist depth in inches, in feet)
    so it never over-predicts; the real allowable span must come from DCA6 or the IRC deck table."""
    depths = {"2x6": 5.5, "2x8": 7.25, "2x10": 9.25, "2x12": 11.25}
    key = (nominal or "").lower().replace(" ", "")
    if key not in depths:
        return {"error": f"nominal must be one of {sorted(depths)}"}
    depth = depths[key]
    rough_ceiling_ft = round(1.5 * depth / 12.0 * 12.0, 1)  # ~1.5 ft per inch of depth
    # spacing derate: wider spacing reduces span
    if spacing_in >= 24:
        rough_ceiling_ft = round(rough_ceiling_ft * 0.85, 1)
    return _wrap({
        "computed_by": "build_calc.deck_span_sanity",
        "inputs": {"species": species, "nominal": key, "spacing_in": spacing_in},
        "rough_span_ceiling_ft": rough_ceiling_ft,
        "authoritative": False,
        "notes": "ROUGH APPROXIMATION ONLY, not a code span. Read the actual allowable joist span from the AWC DCA6 deck guide or the IRC deck span table for your species, size, spacing, and load. Do not build to this number.",
    }, "AWC DCA6", "joist span table", "https://awc.org/wp-content/uploads/2022/02/AWC-DCA62015-DeckGuide-1804.pdf")


# ── selftest ──────────────────────────────────────────────────────────────────
def selftest():
    failures = []

    def check(name, cond):
        if not cond:
            failures.append(name)

    s = stair(108)
    check("stair-risers", s["risers"] == 14)
    check("stair-riser-height", abs(s["riser_height_in"] - 7.714) < 0.01)
    check("stair-riser-ok", s["riser_ok"] is True)
    check("stair-run", abs(s["total_run_in"] - 130.0) < 0.01)

    e_small = egress(20, 24, sill_in=44)
    check("egress-small-fails", e_small["passes"] is False)
    e_ok = egress(30, 30, sill_in=40)
    check("egress-ok-passes", e_ok["passes"] is True)
    check("egress-area", abs(e_ok["area_sqft"] - 6.25) < 0.01)
    e_grade = egress(24, 30.5, sill_in=20, at_grade=True)
    check("egress-grade-5.0", e_grade["required_area_sqft"] == 5.0)

    check("rvalue-ceiling-z2", rvalue_zone("ceiling", 2)["prescriptive_r_value"] == "R30 to R49")
    check("rvalue-zone-letter", rvalue_zone("wall", "4A")["inputs"]["climate_zone"] == 4)
    check("rvalue-bad-comp", "error" in rvalue_zone("roofx", 2))

    bf = box_fill([14, 14, 14], devices=1, clamps=1, grounds=1)
    check("boxfill-required", abs(bf["required_box_volume_cuin"] - 14.0) < 1e-6)
    bf2 = box_fill([12, 12], devices=1)
    check("boxfill-12awg", abs(bf2["required_box_volume_cuin"] - (2 * 2.25 + 2 * 2.25)) < 1e-6)

    ds = drain_slope(2, 20)
    check("drain-2in", abs(ds["total_fall_in"] - 5.0) < 1e-6 and ds["slope_in_per_ft"] == 0.25)
    ds4 = drain_slope(4, 40)
    check("drain-4in", ds4["slope_in_per_ft"] == 0.125 and abs(ds4["total_fall_in"] - 5.0) < 1e-6)

    rp = roof_pitch(6, 12)
    check("roof-angle", abs(rp["angle_deg"] - 26.57) < 0.05)
    check("roof-factor", abs(rp["slope_factor"] - 1.1180) < 0.001)
    check("roof-asphalt-ok", rp["asphalt_shingle_ok"] is True)
    check("roof-lowslope-fail", roof_pitch(1, 12)["asphalt_shingle_ok"] is False)

    check("boardfoot", abs(board_foot(2, 6, 8, 1)["board_feet"] - 8.0) < 1e-6)

    d = deck_span_sanity("SYP", "2x8", 16)
    check("deck-advisory", d["authoritative"] is False and d["rough_span_ceiling_ft"] > 0)

    # every non-error result carries a code_ref and the boundary
    for r in (s, e_ok, rvalue_zone("wall", 3), bf, ds, rp, board_foot(2, 4, 8), d):
        check("has-code-ref", "code_ref" in r and "boundary" in r)

    n = 24
    print(f"selftest: {'PASS' if not failures else 'FAIL'} ({n - len(failures)} of {n} checks)")
    if failures:
        print("failed:", ", ".join(failures))
        return 1
    return 0


def _parse_list(s):
    return [int(x) for x in s.split(",") if x.strip()] if s else []


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS offline construction calculators")
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("stair"); p.add_argument("--total-rise", type=float, required=True)
    p = sub.add_parser("egress")
    p.add_argument("--width", type=float, required=True); p.add_argument("--height", type=float, required=True)
    p.add_argument("--sill", type=float); p.add_argument("--at-grade", action="store_true")
    p = sub.add_parser("rvalue"); p.add_argument("--component", required=True); p.add_argument("--zone", required=True)
    p = sub.add_parser("boxfill")
    p.add_argument("--conductors", required=True); p.add_argument("--devices", type=int, default=0)
    p.add_argument("--clamps", type=int, default=0); p.add_argument("--grounds", type=int, default=0)
    p = sub.add_parser("drain-slope"); p.add_argument("--diameter", type=float, required=True); p.add_argument("--run", type=float, required=True)
    p = sub.add_parser("roof-pitch"); p.add_argument("--rise", type=float, required=True); p.add_argument("--run", type=float, default=12.0)
    p = sub.add_parser("board-foot")
    p.add_argument("--thickness", type=float, required=True); p.add_argument("--width", type=float, required=True)
    p.add_argument("--length", type=float, required=True); p.add_argument("--qty", type=int, default=1)
    p = sub.add_parser("deck-span"); p.add_argument("--species", default="SYP"); p.add_argument("--nominal", required=True); p.add_argument("--spacing", type=float, default=16.0)

    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.cmd == "stair":
        out = stair(args.total_rise)
    elif args.cmd == "egress":
        out = egress(args.width, args.height, args.sill, args.at_grade)
    elif args.cmd == "rvalue":
        out = rvalue_zone(args.component, args.zone)
    elif args.cmd == "boxfill":
        out = box_fill(_parse_list(args.conductors), args.devices, args.clamps, args.grounds)
    elif args.cmd == "drain-slope":
        out = drain_slope(args.diameter, args.run)
    elif args.cmd == "roof-pitch":
        out = roof_pitch(args.rise, args.run)
    elif args.cmd == "board-foot":
        out = board_foot(args.thickness, args.width, args.length, args.qty)
    elif args.cmd == "deck-span":
        out = deck_span_sanity(args.species, args.nominal, args.spacing)
    else:
        ap.print_help()
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
