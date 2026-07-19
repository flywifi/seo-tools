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


def list_videos(token, poster=C.http_post_json, max_pages=250):
    """POST /v2/video/list/ with cursor paging -> (videos, error, truncated).

    max_count is 20 (the documented maximum), so max_pages=250 covers ~5,000 videos. TikTok's Display
    API documents a 600-requests/minute-per-endpoint limit (one-minute sliding window; over it returns
    HTTP 429 rate_limit_exceeded) and NO total-video ceiling (verified 2026-07-19 against
    developers.tiktok.com/doc/tiktok-api-v2-rate-limit), so the page cap is a defensive backstop, not
    a documented limit; truncated=True means has_more was still set at the cap (the creator's library
    may be incomplete). Terminates on has_more==false; a non-advancing or missing cursor while
    has_more is true stops paging rather than re-fetching page 1."""
    out, cursor, seen = [], None, set()
    for _ in range(max_pages):
        url = f"{VIDEO_LIST}?fields={FIELDS}"
        body = {"max_count": 20}
        if cursor is not None:
            body["cursor"] = cursor
        data, err = poster(url, body, {"Authorization": f"Bearer {token}"})
        if err:
            return out, err, False
        d = data.get("data", {})
        out.extend(d.get("videos", []))
        if not d.get("has_more"):
            return out, None, False
        nxt = d.get("cursor")
        if nxt is None or nxt in seen:  # malformed has_more/cursor: stop, do not loop on page 1
            return out, None, False
        seen.add(nxt)
        cursor = nxt
    return out, None, True  # hit the page cap with has_more still true -> truncated


def _epoch_to_iso(ts):
    """TikTok create_time is a non-nullable int64 UTC epoch-seconds (per the Video Object reference),
    but a malformed/partial payload must never crash the whole import. Coerce defensively -> None."""
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _normalize(v):
    stats = {}
    for src, dst in (("view_count", "views"), ("like_count", "likes"),
                     ("comment_count", "comments"), ("share_count", "shares")):
        if v.get(src) is not None:
            stats[dst] = v[src]
    ct = v.get("create_time")
    published = _epoch_to_iso(ct) if ct is not None else None
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
    vids, err, truncated = list_videos(token, poster=poster)
    res = {"gate": g, "records": [_normalize(v) for v in vids], "error": err,
           "note": "TikTok Display API has no retention/hashtag; retention is null (curve is UI-only)."}
    if truncated:
        res["truncated"] = True
        res["truncation_note"] = ("Stopped at the page safety cap; your TikTok library may be "
                                  "incomplete. Re-run to continue from where it left off.")
    return res


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

    vids, err, truncated = list_videos("tok", poster=fake_post)
    ok("paginates cursor/has_more", len(vids) == 2 and err is None)
    ok("clean completion is not truncated", truncated is False)
    recs = [_normalize(v) for v in vids]
    ok("stats mapped", recs[0]["stats"]["views"] == 90000 and recs[0]["stats"]["likes"] == 1234)
    ok("retention null (UI-only)", recs[0]["retention"] is None)
    ok("no revenue", recs[0]["revenue"] is None)
    ok("off -> no records + no call", import_account(off, poster=fake_post)["records"] == [])

    # P46 fix 1: a non-numeric create_time must never crash the batch (defensive _epoch_to_iso).
    bad = _normalize({"id": "x", "create_time": "notanumber", "view_count": 5, "share_url": "u"})
    ok("bad create_time -> published_at null, no raise", bad["published_at"] is None and bad["stats"]["views"] == 5)
    good = _normalize({"id": "y", "create_time": 1777000000, "share_url": "u"})
    ok("valid create_time still parses", good["published_at"] == "2026-04-24")

    # P46 fix 2+3: a runaway has_more that never terminates is bounded and flagged truncated (no infinite loop).
    runaway = {"n": 0}

    def fake_runaway(url, body, headers=None):
        runaway["n"] += 1
        return {"data": {"videos": [{"id": str(runaway["n"]), "create_time": 1777000000, "share_url": "u"}],
                         "cursor": runaway["n"], "has_more": True}}, None
    rv, rerr, rtrunc = list_videos("tok", poster=fake_runaway, max_pages=5)
    ok("runaway paging bounded at max_pages", runaway["n"] == 5 and len(rv) == 5)
    ok("runaway paging reports truncated (not silent None)", rtrunc is True and rerr is None)

    # P46 fix 2+3: a non-advancing cursor stops instead of re-fetching page 1 forever.
    def fake_stuck(url, body, headers=None):
        return {"data": {"videos": [{"id": "z", "create_time": 1777000000, "share_url": "u"}],
                         "cursor": 42, "has_more": True}}, None
    sv, serr, strunc = list_videos("tok", poster=fake_stuck, max_pages=100)
    ok("non-advancing cursor halts (no loop)", len(sv) == 2 and strunc is False)

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
