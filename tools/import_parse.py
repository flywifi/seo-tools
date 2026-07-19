#!/usr/bin/env python3
"""import_parse.py -- parse a creator's OWN platform export bundles into normalized video records (P45).

The export_bundle tier of the content-import lane (shared/content-import-engine.md). Turns the files a
creator downloads from their own account (YouTube Studio CSV + Takeout, Instagram "Download Your
Information", TikTok "Download your data" + Studio CSV, Pinterest analytics) into the dict shape
tools/video_library.py:normalize_record consumes. Stdlib only (csv, json, zipfile).

Design notes forced by the research (observed 2026-07-12):
- YouTube Studio CSV headers and the ~500-row cap were NOT confirmable first-party, so the CSV parser
  is HEADER-DRIVEN (maps by fuzzy column name, never by position) and tolerates header drift.
- Instagram/TikTok data-export filenames + key casing vary by export vintage, so those parsers glob and
  key DEFENSIVELY (accept several spellings) rather than hard-coding one layout.
- Revenue appears ONLY in the YouTube Studio CSV (never via the channel API for a solo creator).
- Retention is never produced here (it is not in any export); it stays null off the Studio retention CSV.
Nothing is fabricated: a column that is absent yields a null field, not a guess.

Usage:
  python3 tools/import_parse.py youtube-studio-csv <Table data.csv | export.zip>
  python3 tools/import_parse.py youtube-takeout <takeout-dir | takeout.zip>
  python3 tools/import_parse.py instagram-dyi <dyi-dir | dyi.zip>
  python3 tools/import_parse.py tiktok-dyi <user_data.json>
  python3 tools/import_parse.py tiktok-studio-csv <analytics.csv>
  python3 tools/import_parse.py pinterest <pin-analytics.json>
  python3 tools/import_parse.py --selftest
"""
import argparse
import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

SOURCE_MODE = "export_bundle"


# ── helpers ───────────────────────────────────────────────────────────────────

def _num(v):
    """Parse a numeric cell (strip $ , % and whitespace). Returns int/float or None (never a guess)."""
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("$", "").replace("%", "").strip()
    if s == "" or s.lower() in ("n/a", "na", "-", "—"):
        return None
    try:
        f = float(s)
        return int(f) if f.is_integer() else f
    except ValueError:
        return None


def _read_text(path_or_text):
    """Accept a path (to a .csv/.json), a path-like object, or raw text; return text."""
    if isinstance(path_or_text, (bytes, bytearray)):
        return path_or_text.decode("utf-8", "replace")
    s = str(path_or_text)
    # Raw CSV/JSON text contains newlines or is long; never stat() it as a path.
    if "\n" not in s and len(s) < 4096:
        try:
            p = Path(s)
            if p.exists() and p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    return s


def _safe_zip(path):
    """Open a zip, or return None if it is missing/unreadable/corrupt. Note: zipfile.BadZipFile is
    NOT an OSError subclass (it derives directly from Exception), so both must be caught. This lets a
    creator point the importer at a corrupt/partial .zip download and get a clean empty result plus a
    gap, never a traceback."""
    try:
        return zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile):
        return None


def _zip_member_text(zip_path, name_contains):
    z = _safe_zip(zip_path)
    if z is None:
        return None
    with z:
        for n in z.namelist():
            if name_contains.lower() in n.lower() and n.lower().endswith(".csv"):
                return z.read(n).decode("utf-8", "replace")
    return None


# ── YouTube Studio CSV (header-driven; the ONLY revenue source) ──────────────

# canonical field <- header keyword(s). Order matters: more specific first.
_YT_HEADER_RULES = [
    ("platform_video_id", lambda h: h == "content"),
    ("title", lambda h: "video title" in h or h == "title"),
    ("published_at", lambda h: "publish time" in h or "publish date" in h),
    (("stats", "watch_time_hours"), lambda h: "watch time" in h),
    (("stats", "avg_view_duration"), lambda h: "average view duration" in h),
    (("stats", "impressions_ctr_pct"), lambda h: "click-through" in h or "click through" in h),
    (("stats", "impressions"), lambda h: "impressions" in h),
    (("stats", "subscribers"), lambda h: h == "subscribers"),
    (("stats", "views"), lambda h: h == "views" or h.endswith(" views")),
    (("revenue", "estimated_revenue"), lambda h: "estimated revenue" in h),
    (("revenue", "monetized_playbacks"), lambda h: "monetized playback" in h),
]


def _yt_map_header(header):
    h = header.strip().lower()
    for target, test in _YT_HEADER_RULES:
        if test(h):
            return target
    return None


def parse_youtube_studio_csv(path_or_text):
    """Parse a YouTube Studio 'Table data.csv' (or its text). Header-driven. Skips the Totals row.
    Populates stats + revenue; retention stays null (that is a separate Studio report)."""
    text = _read_text(path_or_text)
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    header = rows[0]
    mapping = {i: _yt_map_header(col) for i, col in enumerate(header)}
    out = []
    for row in rows[1:]:
        if not row or not any(c.strip() for c in row):
            continue
        rec = {"platform": "youtube", "source_mode": SOURCE_MODE, "stats": {}, "revenue": {},
               "retention": None}
        for i, cell in enumerate(row):
            target = mapping.get(i)
            if target is None:
                continue
            if isinstance(target, tuple):
                group, key = target
                val = _num(cell)
                if val is not None:
                    rec[group][key] = val
            elif target == "platform_video_id":
                rec[target] = cell.strip()
            else:
                rec[target] = cell.strip() or None
        pvid = (rec.get("platform_video_id") or "").strip()
        if not pvid or pvid.lower() in ("total", "totals"):
            continue  # skip the Totals row / blank id
        if not rec["revenue"]:
            rec["revenue"] = None
        if not rec["stats"]:
            rec["stats"] = {}
        rec.setdefault("url", f"https://youtu.be/{pvid}")
        out.append(rec)
    return out


def parse_youtube_studio_zip(zip_path):
    text = _zip_member_text(zip_path, "table data")
    if text is None:
        # fall back to any csv that has a "Content" header
        z = _safe_zip(zip_path)
        if z is not None:
            with z:
                for n in z.namelist():
                    if n.lower().endswith(".csv"):
                        t = z.read(n).decode("utf-8", "replace")
                        if t.splitlines() and "content" in t.splitlines()[0].lower():
                            text = t
                            break
    return parse_youtube_studio_csv(text) if text else []


# ── Google Takeout (metadata only; NO analytics) ─────────────────────────────

def parse_youtube_takeout(path):
    """Parse a Takeout 'YouTube and YouTube Music' folder or zip. Metadata only: id/title/published/
    description; stats stay null (Takeout carries no analytics). Defensive CSV column matching."""
    p = Path(str(path))

    def _from_csv_text(text):
        recs = []
        reader = csv.DictReader(io.StringIO(text))
        for r in reader:
            low = {(k or "").strip().lower(): v for k, v in r.items()}
            pvid = (low.get("video id") or low.get("id") or "").strip()
            if not pvid:
                continue
            recs.append({
                "platform": "youtube", "source_mode": SOURCE_MODE,
                "platform_video_id": pvid,
                "title": (low.get("video title") or low.get("title") or None),
                "description": (low.get("video description") or low.get("description") or None),
                "published_at": (low.get("video create timestamp") or low.get("create timestamp")
                                 or low.get("published") or None),
                "url": f"https://youtu.be/{pvid}",
                "stats": {}, "retention": None,
            })
        return recs

    texts = []
    if p.is_file() and p.suffix.lower() == ".zip":
        z = _safe_zip(p)
        if z is not None:
            with z:
                for n in z.namelist():
                    if "video metadata" in n.lower() and n.lower().endswith(".csv"):
                        texts.append(z.read(n).decode("utf-8", "replace"))
    elif p.is_dir():
        for f in p.rglob("*.csv"):
            if "video metadata" in str(f).lower() or "video" in f.name.lower():
                texts.append(f.read_text(encoding="utf-8", errors="replace"))
    elif p.is_file() and p.suffix.lower() == ".csv":
        texts.append(p.read_text(encoding="utf-8", errors="replace"))
    out = []
    for t in texts:
        out.extend(_from_csv_text(t))
    return out


# ── Instagram "Download Your Information" (JSON; NO insights) ─────────────────

def _ig_items_from_obj(obj):
    """Yield post/media items from an IG DYI JSON object of unknown vintage."""
    if isinstance(obj, list):
        for it in obj:
            yield it
    elif isinstance(obj, dict):
        for key in ("ig_reels_media", "ig_posts", "media", "posts"):
            v = obj.get(key)
            if isinstance(v, list):
                for it in v:
                    yield it


def _ig_record(item):
    # media[] may hold uri/creation at the item or per-media level (both seen historically)
    media = item.get("media") if isinstance(item, dict) else None
    first = media[0] if isinstance(media, list) and media else {}
    uri = item.get("uri") or (first.get("uri") if isinstance(first, dict) else None)
    ts = item.get("creation_timestamp") or (first.get("creation_timestamp") if isinstance(first, dict) else None)
    title = item.get("title") or (first.get("title") if isinstance(first, dict) else None)
    if not uri and not title:
        return None
    stem = Path(str(uri)).stem if uri else re.sub(r"\W+", "-", (title or "media"))[:40]
    return {
        "platform": "instagram", "source_mode": SOURCE_MODE,
        "platform_video_id": stem,
        "title": title, "description": title,
        "published_at": _epoch_to_iso(ts),
        "url": None, "stats": {}, "retention": None,
        "_media_uri": uri,
    }


def _epoch_to_iso(ts):
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def parse_instagram_dyi(path):
    """Parse an Instagram DYI folder/zip. Globs posts_*.json / reels.json (filenames vary by vintage).
    Metadata only: no insights, no transcripts."""
    p = Path(str(path))
    texts = []
    if p.is_file() and p.suffix.lower() == ".zip":
        z = _safe_zip(p)
        if z is not None:
            with z:
                for n in z.namelist():
                    b = Path(n).name.lower()
                    if n.lower().endswith(".json") and (b.startswith("posts_") or b in ("reels.json", "posts.json") or "reels" in b):
                        texts.append(z.read(n).decode("utf-8", "replace"))
    elif p.is_dir():
        for f in list(p.rglob("posts_*.json")) + list(p.rglob("reels.json")) + list(p.rglob("posts.json")):
            texts.append(f.read_text(encoding="utf-8", errors="replace"))
    elif p.is_file() and p.suffix.lower() == ".json":
        texts.append(p.read_text(encoding="utf-8", errors="replace"))
    out = []
    for t in texts:
        try:
            obj = json.loads(t)
        except json.JSONDecodeError:
            continue
        for item in _ig_items_from_obj(obj):
            rec = _ig_record(item)
            if rec:
                out.append(rec)
    return out


# ── TikTok "Download your data" (JSON/TXT; retention UI-only) ─────────────────

def parse_tiktok_dyi(path_or_obj):
    """Parse a TikTok data-export JSON. Key casing varies (Video>Videos>VideoList[] PascalCase, or a
    flat list, or snake_case), so navigation is defensive."""
    if isinstance(path_or_obj, (dict, list)):
        obj = path_or_obj
    else:
        obj = json.loads(_read_text(path_or_obj))

    def _looks_like_videos(lst):
        return (isinstance(lst, list) and lst and isinstance(lst[0], dict)
                and any(k in lst[0] for k in ("Link", "link", "share_url", "id", "Date", "video_description")))

    def _find_video_list(o, depth=6):
        if depth < 0:
            return []
        if _looks_like_videos(o):
            return o
        if isinstance(o, dict):
            # prefer an explicitly named list, else recurse into any child
            for k in ("VideoList", "video_list", "ItemList", "Videos"):
                if _looks_like_videos(o.get(k)):
                    return o[k]
            for v in o.values():
                r = _find_video_list(v, depth - 1)
                if r:
                    return r
        elif isinstance(o, list):
            for it in o:
                r = _find_video_list(it, depth - 1)
                if r:
                    return r
        return []

    items = _find_video_list(obj)
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        link = it.get("Link") or it.get("link") or it.get("share_url") or ""
        m = re.search(r"/video/(\d+)", str(link))
        pvid = m.group(1) if m else (str(it.get("id") or "").strip() or Path(str(link)).name or None)
        if not pvid:
            continue
        stats = {}
        for src, dst in (("Likes", "likes"), ("like_count", "likes"), ("view_count", "views"),
                         ("comment_count", "comments"), ("share_count", "shares")):
            v = _num(it.get(src))
            if v is not None:
                stats[dst] = v
        out.append({
            "platform": "tiktok", "source_mode": SOURCE_MODE,
            "platform_video_id": str(pvid),
            "title": it.get("title") or it.get("Title") or None,
            "description": it.get("video_description") or it.get("Description") or None,
            "published_at": (str(it.get("Date") or it.get("create_time") or "") or None),
            "url": link or None, "stats": stats, "retention": None,
        })
    return out


def parse_tiktok_studio_csv(path_or_text):
    """Header-driven parse of a TikTok Studio analytics CSV (per-video). Retention curve is UI-only and
    absent here."""
    text = _read_text(path_or_text)
    reader = csv.DictReader(io.StringIO(text))
    out = []
    for r in reader:
        low = {(k or "").strip().lower(): v for k, v in r.items()}
        pvid = (low.get("video id") or low.get("id") or low.get("video link") or "").strip()
        m = re.search(r"/video/(\d+)", pvid)
        if m:
            pvid = m.group(1)
        if not pvid:
            continue
        stats = {}
        for key, dst in (("views", "views"), ("total views", "views"), ("likes", "likes"),
                         ("comments", "comments"), ("shares", "shares"),
                         ("total time watched", "total_time_watched"),
                         ("average time watched", "avg_time_watched")):
            for hk, hv in low.items():
                if key in hk:
                    v = _num(hv)
                    if v is not None:
                        stats[dst] = v
                    break
        out.append({"platform": "tiktok", "source_mode": SOURCE_MODE, "platform_video_id": pvid,
                    "title": low.get("video title") or low.get("title") or None,
                    "stats": stats, "retention": None})
    return out


# ── Pinterest (API-style analytics json) ─────────────────────────────────────

def parse_pinterest_export(path_or_obj):
    """Parse Pinterest Pin-analytics JSON: either a top_video_pins response {pins:[{pin_id,metrics}]}
    or a single-pin {ALL:{summary_metrics}}. Retention/transcript are not available on Pinterest."""
    obj = path_or_obj if isinstance(path_or_obj, (dict, list)) else json.loads(_read_text(path_or_obj))
    out = []

    def _rec(pin_id, metrics):
        stats = {}
        for k, v in (metrics or {}).items():
            n = _num(v)
            if n is not None:
                stats[k.lower()] = n
        return {"platform": "pinterest", "source_mode": SOURCE_MODE,
                "platform_video_id": str(pin_id), "stats": stats, "retention": None,
                "url": f"https://www.pinterest.com/pin/{pin_id}/"}

    if isinstance(obj, dict) and isinstance(obj.get("pins"), list):
        for pin in obj["pins"]:
            if isinstance(pin, dict) and pin.get("pin_id"):
                out.append(_rec(pin["pin_id"], pin.get("metrics")))
    elif isinstance(obj, dict):
        # single-pin: {"ALL": {"summary_metrics": {...}}} plus an optional pin_id sidecar
        pin_id = obj.get("pin_id") or "pin"
        for app in obj.values():
            if isinstance(app, dict) and isinstance(app.get("summary_metrics"), dict):
                out.append(_rec(pin_id, app["summary_metrics"]))
                break
    return out


PARSERS = {
    "youtube-studio-csv": parse_youtube_studio_csv,
    "youtube-studio-zip": parse_youtube_studio_zip,
    "youtube-takeout": parse_youtube_takeout,
    "instagram-dyi": parse_instagram_dyi,
    "tiktok-dyi": parse_tiktok_dyi,
    "tiktok-studio-csv": parse_tiktok_studio_csv,
    "pinterest": parse_pinterest_export,
}


# ── selftest (embedded synthetic fixtures; no external files) ────────────────

def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    yt_csv = ("Content,Video title,Video publish time,Views,Watch time (hours),"
              "Average view duration,Impressions,Impressions click-through rate (%),Estimated revenue (USD)\n"
              "abc123,Painting an armoire,2026-03-01,\"12,000\",340.5,0:04:12,\"90,000\",4.80,\"$52.10\"\n"
              "def456,Wainscoting 101,2026-04-02,8000,120.0,0:03:00,50000,3.90,$21.00\n"
              "Total,,,\"20,000\",460.5,,140000,,\"$73.10\"\n")
    yt = parse_youtube_studio_csv(yt_csv)
    ok("yt studio: two rows, Totals skipped", len(yt) == 2)
    ok("yt studio: id from Content", yt[0]["platform_video_id"] == "abc123")
    ok("yt studio: views parsed with comma", yt[0]["stats"]["views"] == 12000)
    ok("yt studio: revenue parsed (only source)", yt[0]["revenue"]["estimated_revenue"] == 52.10)
    ok("yt studio: ctr mapped distinctly from impressions",
       yt[0]["stats"]["impressions"] == 90000 and yt[0]["stats"]["impressions_ctr_pct"] == 4.80)
    ok("yt studio: retention stays null", yt[0]["retention"] is None)

    ig_json = json.dumps({"ig_reels_media": [
        {"media": [{"uri": "media/reels/202603_reel_ABC.mp4", "creation_timestamp": 1772409600,
                    "title": "quick armoire tour"}]}]})
    ig = parse_instagram_dyi(_TmpFile(ig_json, ".json"))
    ok("ig dyi: one record", len(ig) == 1)
    ok("ig dyi: id from uri stem", ig[0]["platform_video_id"] == "202603_reel_ABC")
    ok("ig dyi: no stats (no insights in export)", ig[0]["stats"] == {})
    ok("ig dyi: retention null", ig[0]["retention"] is None)

    tt = parse_tiktok_dyi({"Video": {"Videos": {"VideoList": [
        {"Date": "2026-05-01 12:00:00", "Link": "https://www.tiktokv.com/share/video/7300000000000000000/",
         "Likes": "1,234", "Title": "diy hack"}]}}})
    ok("tiktok dyi: id from link", tt[0]["platform_video_id"] == "7300000000000000000")
    ok("tiktok dyi: likes parsed", tt[0]["stats"]["likes"] == 1234)
    ok("tiktok dyi: retention null (UI-only)", tt[0]["retention"] is None)

    pin = parse_pinterest_export({"pins": [{"pin_id": "998877",
                                            "metrics": {"IMPRESSION": 2400, "SAVE": 30, "VIDEO_MRC_VIEW": 400}}]})
    ok("pinterest: id + metrics", pin[0]["platform_video_id"] == "998877" and pin[0]["stats"]["impression"] == 2400)
    ok("pinterest: retention null", pin[0]["retention"] is None)

    # P46 fix 4: a corrupt / non-zip file degrades to [] (no BadZipFile traceback).
    import tempfile as _tf
    bad = Path(_tf.mkdtemp()) / "corrupt.zip"
    bad.write_bytes(b"this is not a zip file at all")
    ok("corrupt studio zip -> [] (no raise)", parse_youtube_studio_zip(bad) == [])
    ok("corrupt takeout zip -> [] (no raise)", parse_youtube_takeout(bad) == [])
    ok("corrupt instagram zip -> [] (no raise)", parse_instagram_dyi(bad) == [])
    ok("missing zip path -> [] (no raise)", parse_youtube_studio_zip(Path(_tf.mkdtemp()) / "nope.zip") == [])

    # every parser output is normalize_record-ready
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import video_library as VL
    rec = VL.normalize_record(yt[0], source_mode="export_bundle")
    ok("output feeds normalize_record", rec["video_key"] == "youtube:abc123" and rec["revenue"]["estimated_revenue"] == 52.10)

    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["youtube-takeout", "x" * 300])
    ok(">255-byte path arg -> clean envelope, no traceback (P66 boundary)",
       rc == 1 and "next_step" in buf.getvalue())

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


class _TmpFile:
    """A throwaway file for the selftest (glob-based parsers expect a path)."""
    def __init__(self, text, suffix):
        import tempfile
        self._p = Path(tempfile.mkstemp(suffix=suffix)[1])
        self._p.write_text(text, encoding="utf-8")

    def __fspath__(self):
        return str(self._p)

    def __str__(self):
        return str(self._p)


def _main(argv):
    ap = argparse.ArgumentParser(description="Parse platform export bundles into normalized video records.")
    ap.add_argument("format", nargs="?", choices=list(PARSERS))
    ap.add_argument("path", nargs="?")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.format or not args.path:
        ap.print_help()
        return 2
    records = PARSERS[args.format](args.path)
    print(json.dumps(records, indent=2, ensure_ascii=False))
    return 0


def main(argv):
    """Thin CLI boundary (P66): an unhandled filesystem error from a user-supplied path (for
    example a >255-byte component raising ENAMETOOLONG, which Path.exists() does not suppress)
    becomes the clean {"error","next_step"} envelope instead of a raw traceback."""
    try:
        return _main(argv)
    except OSError as exc:
        print(json.dumps({"error": str(exc),
                          "next_step": "pass a readable file path (this one could not be opened)"}))
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
