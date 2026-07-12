#!/usr/bin/env python3
"""pinterest_import.py -- live Pinterest importer for the creator's OWN video Pins (P45, flag-gated, OFF by default).

API v5 (scopes pins:read, user_accounts:read). GET /user_account/analytics/top_video_pins returns
{pins:[{pin_id, metrics}]}; per-pin analytics come keyed by app_type with summary_metrics. NO retention
and NO transcript on Pinterest -> retention stays null. Injectable getter; no network in selftest.

Usage:
  python3 tools/importers/pinterest_import.py import
  python3 tools/importers/pinterest_import.py --selftest
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _common as C  # noqa: E402

API = "https://api.pinterest.com/v5"
SORT_BY = "IMPRESSION"


def top_video_pins(token, start, end, getter=C.http_get_json):
    url = (f"{API}/user_account/analytics/top_video_pins?start_date={start}&end_date={end}"
           f"&sort_by={SORT_BY}")
    data, err = getter(url, {"Authorization": f"Bearer {token}"})
    if err:
        return [], err
    return data.get("pins", []), None


def _normalize(pin):
    stats = {}
    for k, v in (pin.get("metrics") or {}).items():
        if isinstance(v, (int, float)):
            stats[str(k).lower()] = v
    pid = pin.get("pin_id")
    return {"platform": "pinterest", "source_mode": "direct_connector",
            "platform_video_id": str(pid), "url": f"https://www.pinterest.com/pin/{pid}/",
            "tags": [], "stats": stats, "retention": None, "revenue": None}


def import_account(config, token=None, start="2026-01-01", end=None, getter=C.http_get_json):
    g = C.gate(config, "pinterest")
    if not g["proceed"]:
        return {"gate": g, "records": []}
    token = token or (C.load_credentials().get("pinterest", {}) or {}).get("access_token")
    if not token:
        return {"gate": g, "error": "missing pinterest access_token", "records": []}
    from datetime import date
    end = end or date.today().isoformat()
    pins, err = top_video_pins(token, start, end, getter=getter)
    return {"gate": g, "records": [_normalize(p) for p in pins], "error": err,
            "note": "Pinterest has no per-second retention or transcript; retention is null."}


def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    off = {"capabilities": {}}
    on = {"capabilities": {"content_import_live": {"enabled": True}, "pinterest_api": {"enabled": True}}}
    ok("gate blocks off", C.gate(off, "pinterest")["proceed"] is False)

    def fake(url, headers=None):
        if "top_video_pins" in url:
            return {"pins": [{"pin_id": "998877", "metrics": {"IMPRESSION": 2400, "SAVE": 30,
                    "VIDEO_MRC_VIEW": 400, "VIDEO_AVG_WATCH_TIME": 2507.75}}],
                    "sort_by": "IMPRESSION"}, None
        return None, "unmocked"

    pins, err = top_video_pins("tok", "2026-01-01", "2026-07-01", getter=fake)
    ok("top_video_pins returns pins", len(pins) == 1 and err is None)
    recs = [_normalize(p) for p in pins]
    ok("metrics lowercased into stats", recs[0]["stats"]["impression"] == 2400 and recs[0]["stats"]["video_mrc_view"] == 400)
    ok("retention null", recs[0]["retention"] is None)
    ok("no revenue", recs[0]["revenue"] is None)
    ok("off -> no records", import_account(off, getter=fake)["records"] == [])

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    print(f"selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


def main(argv):
    ap = argparse.ArgumentParser(description="Live Pinterest importer (flag-gated, off by default).")
    ap.add_argument("command", nargs="?", choices=["import"])
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.command:
        ap.print_help()
        return 2
    print(json.dumps(import_account(C.load_config()), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
