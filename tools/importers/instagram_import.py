#!/usr/bin/env python3
"""instagram_import.py -- live Instagram importer for the creator's OWN media (P45, flag-gated, OFF by default).

Graph API (v25.0, professional accounts). Pulls the user's media list + per-media insights and
normalizes into video_library records. Media insights use the total_value shape (read total_value.value,
not a values[] time series). NO audience retention and NO hashtag analytics are available -> retention
stays null. Injectable getter; no network in selftest. See shared/content-import-engine.md.

Usage:
  python3 tools/importers/instagram_import.py import
  python3 tools/importers/instagram_import.py --selftest
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _common as C  # noqa: E402

GRAPH = "https://graph.instagram.com"
REELS_METRICS = ["reach", "views", "likes", "comments", "saved", "shares", "ig_reels_avg_watch_time"]


def _tok(url, token):
    return url + ("&" if "?" in url else "?") + f"access_token={token}"


def list_media(ig_user_id, token, getter=C.http_get_json, limit=50):
    """GET /{ig-user-id}/media (paginated via paging.cursors.after) -> [media object]."""
    out, after = [], None
    fields = "id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count"
    while True:
        url = _tok(f"{GRAPH}/{ig_user_id}/media?fields={fields}&limit={limit}", token)
        if after:
            url += f"&after={after}"
        data, err = getter(url)
        if err:
            return out, err
        out.extend(data.get("data", []))
        after = ((data.get("paging") or {}).get("cursors") or {}).get("after")
        if not after or not data.get("data"):
            return out, None


def fetch_insights(media_id, token, getter=C.http_get_json):
    """GET /{media}/insights -> {metric: value} reading total_value.value (media metrics are total_value)."""
    url = _tok(f"{GRAPH}/{media_id}/insights?metric={','.join(REELS_METRICS)}", token)
    data, err = getter(url)
    if err:
        return {}, err
    stats = {}
    for item in data.get("data", []):
        name = item.get("name")
        tv = item.get("total_value") or {}
        val = tv.get("value")
        if val is None:  # older account-style shape
            vs = item.get("values") or []
            val = vs[0].get("value") if vs and isinstance(vs[0], dict) else None
        if val is not None:
            stats[name] = val
    return stats, None


def _normalize(media, stats):
    mid = media.get("id")
    return {"platform": "instagram", "source_mode": "direct_connector",
            "platform_video_id": str(mid), "url": media.get("permalink"),
            "title": (media.get("caption") or "")[:120] or None,
            "description": media.get("caption"), "tags": [],
            "published_at": media.get("timestamp"),
            "stats": stats, "retention": None, "revenue": None}


def import_account(config, token=None, ig_user_id=None, getter=C.http_get_json):
    g = C.gate(config, "instagram")
    if not g["proceed"]:
        return {"gate": g, "records": []}
    creds = (C.load_credentials().get("instagram", {}) or {})
    token = token or creds.get("access_token")
    ig_user_id = ig_user_id or creds.get("ig_user_id")
    if not token or not ig_user_id:
        return {"gate": g, "error": "missing instagram access_token / ig_user_id", "records": []}
    media, err = list_media(ig_user_id, token, getter=getter)
    records = []
    for m in media:
        stats, _ = fetch_insights(m.get("id"), token, getter=getter)
        records.append(_normalize(m, stats))
    return {"gate": g, "records": records, "error": err,
            "note": "Instagram has no audience-retention or hashtag analytics; retention is null."}


def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    off = {"capabilities": {}}
    on = {"capabilities": {"content_import_live": {"enabled": True}, "instagram_api": {"enabled": True}}}
    ok("gate blocks off", C.gate(off, "instagram")["proceed"] is False)

    def fake(url):
        if "/media?" in url or "/media&" in url or "/media" in url and "insights" not in url:
            return {"data": [{"id": "17900", "caption": "quick tour", "permalink": "https://insta/p/17900",
                    "timestamp": "2026-05-01T00:00:00Z", "media_product_type": "REELS"}],
                    "paging": {"cursors": {}}}, None
        if "insights" in url:
            return {"data": [{"name": "reach", "total_value": {"value": 5000}},
                             {"name": "views", "total_value": {"value": 8000}},
                             {"name": "saved", "total_value": {"value": 120}}]}, None
        return None, "unmocked"

    media, err = list_media("ME", "tok", getter=fake)
    ok("list_media returns items", len(media) == 1 and err is None)
    stats, _ = fetch_insights("17900", "tok", getter=fake)
    ok("insights read total_value.value", stats["reach"] == 5000 and stats["views"] == 8000)
    res = import_account(on, token="tok", ig_user_id="ME", getter=fake)
    ok("record normalized, retention null", res["records"][0]["retention"] is None and res["records"][0]["stats"]["saved"] == 120)
    ok("no revenue via IG import", res["records"][0]["revenue"] is None)
    ok("off -> no records", import_account(off, getter=fake)["records"] == [])

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    print(f"selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


def main(argv):
    ap = argparse.ArgumentParser(description="Live Instagram importer (flag-gated, off by default).")
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
