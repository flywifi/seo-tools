#!/usr/bin/env python3
"""tiktok_import.py -- live TikTok importer for the creator's OWN videos (P45, flag-gated, OFF by default).

Display API (host open.tiktokapis.com, scope video.list). POST /v2/video/list/ returns data.videos[]
(15 fields) with data.cursor / data.has_more paging. NO retention/hashtag/file-url in the Display API,
so retention stays null. Injectable getter; no network in selftest.

Usage:
  python3 tools/importers/tiktok_import.py import
  python3 tools/importers/tiktok_import.py --selftest
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _common as C  # noqa: E402

VIDEO_LIST = "https://open.tiktokapis.com/v2/video/list/"
FIELDS = ("id,create_time,cover_image_url,share_url,video_description,duration,height,width,title,"
          "embed_html,embed_link,like_count,comment_count,share_count,view_count")


def list_videos(token, poster=C.http_post_json, max_pages=20):
    """POST /v2/video/list/ with cursor paging -> [video object]."""
    out, cursor = [], None
    for _ in range(max_pages):
        url = f"{VIDEO_LIST}?fields={FIELDS}"
        body = {"max_count": 20}
        if cursor is not None:
            body["cursor"] = cursor
        data, err = poster(url, body, {"Authorization": f"Bearer {token}"})
        if err:
            return out, err
        d = data.get("data", {})
        out.extend(d.get("videos", []))
        if not d.get("has_more"):
            return out, None
        cursor = d.get("cursor")
    return out, None


def _normalize(v):
    stats = {}
    for src, dst in (("view_count", "views"), ("like_count", "likes"),
                     ("comment_count", "comments"), ("share_count", "shares")):
        if v.get(src) is not None:
            stats[dst] = v[src]
    ct = v.get("create_time")
    from datetime import datetime, timezone
    published = datetime.fromtimestamp(int(ct), tz=timezone.utc).date().isoformat() if ct else None
    return {"platform": "tiktok", "source_mode": "direct_connector",
            "platform_video_id": str(v.get("id")), "url": v.get("share_url"),
            "title": v.get("title") or None, "description": v.get("video_description"),
            "tags": [], "published_at": published, "duration_s": v.get("duration"),
            "stats": stats, "retention": None, "revenue": None}


def import_account(config, token=None, poster=C.http_post_json):
    g = C.gate(config, "tiktok")
    if not g["proceed"]:
        return {"gate": g, "records": []}
    token = token or (C.load_credentials().get("tiktok", {}) or {}).get("access_token")
    if not token:
        return {"gate": g, "error": "missing tiktok access_token", "records": []}
    vids, err = list_videos(token, poster=poster)
    return {"gate": g, "records": [_normalize(v) for v in vids], "error": err,
            "note": "TikTok Display API has no retention/hashtag; retention is null (curve is UI-only)."}


def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    off = {"capabilities": {}}
    on = {"capabilities": {"content_import_live": {"enabled": True}, "tiktok_api": {"enabled": True}}}
    ok("gate blocks off", C.gate(off, "tiktok")["proceed"] is False)

    calls = {"n": 0}

    def fake_post(url, body, headers=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"data": {"videos": [{"id": "7300000000000000000", "title": "diy hack",
                    "video_description": "makeover", "create_time": 1777000000, "duration": 42,
                    "view_count": 90000, "like_count": 1234, "comment_count": 50, "share_count": 20,
                    "share_url": "https://tiktok/@x/video/7300000000000000000"}],
                    "cursor": 111, "has_more": True}}, None
        return {"data": {"videos": [{"id": "7300000000000000001", "create_time": 1777100000,
                "view_count": 100, "share_url": "u"}], "has_more": False}}, None

    vids, err = list_videos("tok", poster=fake_post)
    ok("paginates cursor/has_more", len(vids) == 2 and err is None)
    recs = [_normalize(v) for v in vids]
    ok("stats mapped", recs[0]["stats"]["views"] == 90000 and recs[0]["stats"]["likes"] == 1234)
    ok("retention null (UI-only)", recs[0]["retention"] is None)
    ok("no revenue", recs[0]["revenue"] is None)
    ok("off -> no records + no call", import_account(off, poster=fake_post)["records"] == [])

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    print(f"selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


def main(argv):
    ap = argparse.ArgumentParser(description="Live TikTok importer (flag-gated, off by default).")
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
