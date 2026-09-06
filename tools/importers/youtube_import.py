#!/usr/bin/env python3
"""youtube_import.py -- live YouTube importer for the creator's OWN channel (P45, flag-gated, OFF by default).

Pulls the creator's uploads + metadata (Data API) and audience retention (Analytics API) with their own
OAuth token, and normalizes into tools/video_library.py records. REVENUE IS NEVER FETCHED VIA API: for a
solo creator, monetary metrics exist only in content-owner reports, so revenue comes only from the
YouTube Studio CSV export. This module builds no monetary endpoint. ASR (auto-generated) caption tracks
are skipped (they 403 on download). Every fetch takes an injectable getter so the selftest runs offline.

Usage:
  python3 tools/importers/youtube_import.py import [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--max N]
  python3 tools/importers/youtube_import.py --selftest
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _common as C  # noqa: E402

DATA = "https://www.googleapis.com/youtube/v3"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
RETENTION_DIM = "elapsedVideoTimeRatio"
RETENTION_METRICS = ["audienceWatchRatio", "relativeRetentionPerformance"]
CORE_METRICS = ["views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage"]
# Deliberately excludes every monetary metric (estimatedRevenue, estimatedAdRevenue, cpm, ...):
# revenue is Studio-CSV-only for a solo creator (see revenue_note()).


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Category decode (raw numeric categoryId -> human label) ──────────────────
_CATEGORIES_PATH = HERE.parent.parent / "canonical-sources" / "youtube-video-categories.json"
_CATEGORY_MAP = None


def _category_map():
    """Load the US categoryId->title map once; empty dict if the file is missing/unreadable."""
    global _CATEGORY_MAP
    if _CATEGORY_MAP is None:
        try:
            _CATEGORY_MAP = json.loads(_CATEGORIES_PATH.read_text(encoding="utf-8")).get("categories", {})
        except (OSError, ValueError):
            _CATEGORY_MAP = {}
    return _CATEGORY_MAP


def decode_category(category_id):
    """Numeric categoryId (e.g. '26') -> human title ('Howto & Style'); unmapped/absent -> 'Unknown (<id>)'.
    Never fabricates: an id with no entry is labeled explicitly so the user sees the raw code, not a guess."""
    if category_id in (None, ""):
        return None
    key = str(category_id)
    return _category_map().get(key, f"Unknown ({key})")


def revenue_note():
    return ("Revenue is not available via the YouTube Analytics API for a solo creator (monetary "
            "metrics are content-owner reports only). Export it from YouTube Studio to Analytics to "
            "Advanced Mode to Export (CSV), then import that file with the export-bundle tier.")


# ── Data API: uploads + videos ───────────────────────────────────────────────

def list_uploads(token, getter=C.http_get_json, max_videos=None, max_pages=1000):
    """channels.list -> uploads playlist -> playlistItems.list (paginated) -> (ids, error, truncated).

    maxResults is 50 (the documented maximum) at 1 quota unit/call. playlistItems.list documents no
    total-results cap (the ~500 cap is search.list only), so max_pages=1000 (~50,000 videos) is a
    defensive backstop against a malformed/repeating nextPageToken; truncated=True means the cap was
    hit with a next page still pending. Terminates on a missing or non-advancing nextPageToken."""
    ch, err = getter(f"{DATA}/channels?part=contentDetails&mine=true", _auth(token))
    if err:
        return [], err, False
    try:
        uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    except (KeyError, IndexError):
        return [], "no uploads playlist (is this the owner's token?)", False
    ids, page, seen = [], None, set()
    for _ in range(max_pages):
        url = f"{DATA}/playlistItems?part=contentDetails&playlistId={uploads}&maxResults=50"
        if page:
            url += f"&pageToken={page}"
        data, err = getter(url, _auth(token))
        if err:
            return ids, err, False
        for it in data.get("items", []):
            vid = (it.get("contentDetails") or {}).get("videoId")
            if vid:
                ids.append(vid)
        if max_videos and len(ids) >= max_videos:
            return ids[:max_videos], None, False
        page = data.get("nextPageToken")
        if not page or page in seen:  # end of data, or a malformed/repeating token: stop
            return ids, None, False
        seen.add(page)
    return ids, None, True  # hit the page cap with a next page still pending -> truncated


def _iso8601_to_seconds(dur):
    import re
    if not dur:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur)
    if not m:
        return None
    h, mn, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mn * 60 + s


def fetch_videos(video_ids, token, getter=C.http_get_json):
    """videos.list for up to 50 ids/call -> normalized parsed records (stats populated; revenue null)."""
    out = []
    for i in range(0, len(video_ids), 50):
        chunk = ",".join(video_ids[i:i + 50])
        url = f"{DATA}/videos?part=snippet,statistics,contentDetails,status,topicDetails&id={chunk}"
        data, err = getter(url, _auth(token))
        if err:
            continue
        for v in data.get("items", []):
            sn, st, cd = v.get("snippet", {}), v.get("statistics", {}), v.get("contentDetails", {})
            stats = {}
            for k, dst in (("viewCount", "views"), ("likeCount", "likes"), ("commentCount", "comments")):
                if st.get(k) is not None:
                    stats[dst] = int(st[k])
            out.append({
                "platform": "youtube", "source_mode": "direct_connector",
                "platform_video_id": v.get("id"),
                "url": f"https://youtu.be/{v.get('id')}",
                "title": sn.get("title"), "description": sn.get("description"),
                "tags": sn.get("tags") or [],
                "category": decode_category(sn.get("categoryId")),
                "category_code": sn.get("categoryId"),
                "published_at": sn.get("publishedAt"),
                "duration_s": _iso8601_to_seconds(cd.get("duration")),
                "stats": stats, "retention": None, "revenue": None,
                "caption_available": cd.get("caption") == "true",
            })
    return out


# ── Analytics API: audience retention (the "most-watched parts" source) ──────

def build_retention_url(video_id, start, end):
    return (f"{ANALYTICS}?ids=channel==MINE&startDate={start}&endDate={end}"
            f"&dimensions={RETENTION_DIM}&metrics={','.join(RETENTION_METRICS)}"
            f"&filters=video=={video_id}")


def parse_result_table(table):
    """Map a {columnHeaders,[rows]} resultTable into a list of dicts keyed by column name."""
    headers = [h.get("name") for h in (table or {}).get("columnHeaders", [])]
    return [dict(zip(headers, row)) for row in (table or {}).get("rows", []) or []]


def fetch_retention(video_id, token, start, end, getter=C.http_get_json):
    """Returns ([{elapsed_ratio, watch_ratio, relative_perf}], error). Empty when the report has no rows."""
    data, err = getter(build_retention_url(video_id, start, end), _auth(token))
    if err:
        return [], err
    pts = []
    for row in parse_result_table(data):
        pts.append({
            "elapsed_ratio": row.get(RETENTION_DIM),
            "watch_ratio": row.get("audienceWatchRatio"),
            "relative_perf": row.get("relativeRetentionPerformance"),
        })
    return pts, None


# ── captions: skip ASR (they 403 on download) ────────────────────────────────

def list_captions(video_id, token, getter=C.http_get_json):
    data, err = getter(f"{DATA}/captions?part=snippet&videoId={video_id}", _auth(token))
    if err:
        return [], err
    return data.get("items", []), None


def downloadable_caption(tracks):
    """Return the id of a creator-uploaded (non-ASR) track, or None. ASR tracks are skipped (403)."""
    for t in tracks or []:
        kind = str((t.get("snippet") or {}).get("trackKind") or "").lower()
        if kind != "asr":
            return t.get("id")
    return None


# ── orchestrator ──────────────────────────────────────────────────────────────

def import_channel(config, token=None, start="2020-01-01", end=None, max_videos=None, getter=C.http_get_json):
    g = C.gate(config, "youtube")
    if not g["proceed"]:
        return {"gate": g, "records": [], "revenue_note": revenue_note()}
    token = token or (C.load_credentials().get("youtube", {}) or {}).get("access_token")
    if not token:
        return {"gate": g, "error": "no youtube access_token in api-credentials.local.json", "records": []}
    from datetime import date
    end = end or date.today().isoformat()
    ids, err, truncated = list_uploads(token, getter=getter, max_videos=max_videos)
    records = fetch_videos(ids, token, getter=getter)
    ana_flag = C.gate(config, "youtube_analytics")["proceed"]
    for rec in records:
        if ana_flag:
            pts, rerr = fetch_retention(rec["platform_video_id"], token, start, end, getter=getter)
            rec["retention"] = pts or None
    res = {"gate": g, "records": records, "retention_pulled": ana_flag,
           "revenue_note": revenue_note(), "error": err}
    if truncated:
        res["truncated"] = True
        res["truncation_note"] = ("Stopped at the page safety cap; your YouTube library may be "
                                  "incomplete. Re-run to continue.")
    return res


# ── selftest (injected getter; no network; revenue-never assertion) ──────────

def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # gate blocks with flags off (no network possible)
    off = {"capabilities": {}}
    ok("gate blocks when master off", C.gate(off, "youtube")["proceed"] is False)
    on = {"capabilities": {"content_import_live": {"enabled": True}, "youtube_api": {"enabled": True},
                           "youtube_analytics": {"enabled": True}}}
    ok("gate proceeds when both on", C.gate(on, "youtube")["proceed"] is True)

    # revenue-never: no monetary term anywhere in the metric sets or the retention URL
    metric_blob = " ".join(RETENTION_METRICS + CORE_METRICS).lower()
    ok("no monetary metric in metric sets", "revenue" not in metric_blob and "cpm" not in metric_blob and "ad" not in metric_blob.replace("ratio", ""))
    ok("retention url builds no monetary metric", "revenue" not in build_retention_url("V", "2026-01-01", "2026-07-01").lower())
    ok("revenue_note points at Studio CSV", "Studio" in revenue_note())

    def fake_getter(url, headers=None):
        if "/channels" in url:
            return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUxx"}}}]}, None
        if "/playlistItems" in url:
            return {"items": [{"contentDetails": {"videoId": "vid1"}},
                              {"contentDetails": {"videoId": "vid2"}}]}, None
        if "/videos" in url:
            return {"items": [{"id": "vid1", "snippet": {"title": "Armoire makeover", "description": "diy",
                    "tags": ["armoire"], "publishedAt": "2026-03-01T00:00:00Z", "categoryId": "26"},
                    "statistics": {"viewCount": "12000", "likeCount": "800", "commentCount": "60"},
                    "contentDetails": {"duration": "PT10M0S", "caption": "true"}}]}, None
        if "youtubeanalytics" in url:
            return {"kind": "youtubeAnalytics#resultTable",
                    "columnHeaders": [{"name": "elapsedVideoTimeRatio"}, {"name": "audienceWatchRatio"},
                                      {"name": "relativeRetentionPerformance"}],
                    "rows": [[0.0, 1.4, 0.9], [0.5, 0.8, 0.5], [1.0, 0.3, 0.2]]}, None
        if "/captions" in url:
            return {"items": [{"id": "capASR", "snippet": {"trackKind": "ASR"}},
                              {"id": "capReal", "snippet": {"trackKind": "standard"}}]}, None
        return None, "unmocked"

    ids, err, truncated = list_uploads("tok", getter=fake_getter)
    ok("list_uploads paginates to ids", ids == ["vid1", "vid2"] and err is None)
    ok("clean completion is not truncated", truncated is False)

    # P46 fix 2: a runaway nextPageToken that never clears is bounded and flagged (no infinite loop).
    rn = {"n": 0}

    def fake_runaway(url, headers=None):
        if "/channels" in url:
            return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUxx"}}}]}, None
        rn["n"] += 1
        return {"items": [{"contentDetails": {"videoId": f"v{rn['n']}"}}], "nextPageToken": f"tok{rn['n']}"}, None
    rids, rerr, rtrunc = list_uploads("tok", getter=fake_runaway, max_pages=7)
    ok("runaway paging bounded + truncated", rn["n"] == 7 and rtrunc is True and rerr is None)

    recs = fetch_videos(ids, "tok", getter=fake_getter)
    ok("fetch_videos normalizes stats", recs[0]["stats"]["views"] == 12000 and recs[0]["duration_s"] == 600)
    ok("fetch_videos tags public", recs[0]["tags"] == ["armoire"])
    ok("fetch_videos revenue null (never via API)", recs[0]["revenue"] is None)
    ok("category decoded to label", recs[0]["category"] == "Howto & Style" and recs[0]["category_code"] == "26")
    ok("unknown category id labeled, not fabricated", decode_category("9999") == "Unknown (9999)")
    ok("absent category id -> None", decode_category(None) is None)
    pts, rerr = fetch_retention("vid1", "tok", "2026-01-01", "2026-07-01", getter=fake_getter)
    ok("retention parsed from resultTable", len(pts) == 3 and pts[0]["watch_ratio"] == 1.4)
    tracks, _ = list_captions("vid1", "tok", getter=fake_getter)
    ok("ASR caption skipped, real one chosen", downloadable_caption(tracks) == "capReal")

    res = import_channel(on, token="tok", start="2026-01-01", end="2026-07-01", getter=fake_getter)
    ok("orchestrator returns records + retention", len(res["records"]) == 1 and res["records"][0]["retention"])
    ok("orchestrator always carries the revenue note", "Studio" in res["revenue_note"])
    res_off = import_channel(off, getter=fake_getter)
    ok("orchestrator makes no call when gated off", res_off["records"] == [] and res_off["gate"]["proceed"] is False)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


def main(argv):
    ap = argparse.ArgumentParser(description="Live YouTube importer (flag-gated, off by default).")
    ap.add_argument("command", nargs="?", choices=["import"])
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--max", type=int, default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.command:
        ap.print_help()
        return 2
    res = import_channel(C.load_config(), start=args.start, end=args.end, max_videos=args.max)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
