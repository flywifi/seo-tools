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

# Pin the API version explicitly. An unversioned graph.instagram.com call resolves to a
# Meta-chosen default; v25.0 was released 2026-02-18 (Graph API changelog).
GRAPH = "https://graph.instagram.com/v25.0"
REELS_METRICS = ["reach", "views", "likes", "comments", "saved", "shares", "ig_reels_avg_watch_time"]


def _tok(url, token):
    return url + ("&" if "?" in url else "?") + f"access_token={token}"


def list_media(ig_user_id, token, getter=C.http_get_json, limit=50, max_pages=500):
    """GET /{ig-user-id}/media (cursor paging) -> (media, error, truncated).

    Meta's documented terminator is the ABSENCE of paging.next, NOT the after cursor (a cursor edge
    can return `after` on the final page, which would loop forever). We stop when paging.next is gone,
    when the after cursor does not advance, or at max_pages (a defensive backstop; Instagram documents
    no per-edge limit maximum, so limit stays <=50). truncated=True means the cap was hit with a next
    page still present."""
    out, after, seen = [], None, set()
    fields = "id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count"
    for _ in range(max_pages):
        url = _tok(f"{GRAPH}/{ig_user_id}/media?fields={fields}&limit={limit}", token)
        if after:
            url += f"&after={after}"
        data, err = getter(url)
        if err:
            return out, err, False
        out.extend(data.get("data", []))
        paging = data.get("paging") or {}
        if not paging.get("next") or not data.get("data"):  # documented end-of-data signal
            return out, None, False
        after = (paging.get("cursors") or {}).get("after")
        if not after or after in seen:  # no/repeating cursor while next is present: stop, do not loop
            return out, None, False
        seen.add(after)
    return out, None, True  # hit the page cap with paging.next still present -> truncated


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
    media, err, truncated = list_media(ig_user_id, token, getter=getter)
    records = []
    for m in media:
        stats, _ = fetch_insights(m.get("id"), token, getter=getter)
        records.append(_normalize(m, stats))
    res = {"gate": g, "records": records, "error": err,
           "note": "Instagram has no audience-retention or hashtag analytics; retention is null."}
    if truncated:
        res["truncated"] = True
        res["truncation_note"] = ("Stopped at the page safety cap; your Instagram library may be "
                                  "incomplete. Re-run to continue.")
    return res


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

    media, err, truncated = list_media("ME", "tok", getter=fake)
    ok("list_media returns items", len(media) == 1 and err is None)
    ok("no paging.next -> not truncated", truncated is False)

    # P46 fix 2: an 'after' cursor that persists with no paging.next must still terminate (the docs'
    # rule) rather than loop forever; and a genuinely non-terminating next is bounded + flagged.
    def fake_after_no_next(url):
        # returns an after cursor but NO paging.next: documented end-of-data, must stop.
        return {"data": [{"id": "1", "timestamp": "2026-01-01T00:00:00Z"}],
                "paging": {"cursors": {"after": "CURSOR"}}}, None
    m2, e2, t2 = list_media("ME", "tok", getter=fake_after_no_next)
    ok("terminates on paging.next absence despite an after cursor", len(m2) == 1 and t2 is False)

    rn = {"n": 0}

    def fake_runaway(url):
        rn["n"] += 1
        return {"data": [{"id": str(rn["n"]), "timestamp": "2026-01-01T00:00:00Z"}],
                "paging": {"next": "http://x", "cursors": {"after": f"c{rn['n']}"}}}, None
    m3, e3, t3 = list_media("ME", "tok", getter=fake_runaway, max_pages=6)
    ok("runaway next bounded + truncated", rn["n"] == 6 and t3 is True and e3 is None)
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
