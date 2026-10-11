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
import errno
import argparse
import csv
import io
import json
import re
import sys
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared" / "docintel"))
import textdecode as _td  # noqa: E402  (a byte-order mark, then strict UTF-8, then cp1252)
import classify as _classify  # noqa: E402  (a zip's end record, read before zipfile lists it)

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
        return _td.decode_text(path_or_text)[0]
    s = str(path_or_text)
    # Raw CSV/JSON text contains newlines or is long; never stat() it as a path.
    if "\n" not in s and len(s) < 4096:
        try:
            p = Path(s)
            if p.exists() and p.is_file():
                return _td.read_text_file(p)[0]
        except OSError:
            pass
    return s


def _note(message):
    """Tell the person something on stderr, as one line starting 'note: '; stdout stays the JSON
    record list. The wizard's import screen and a runner job's log show these lines (P102)."""
    print(f"note: {message}", file=sys.stderr)


_ZIP_UNREAD_NOTE = ("this file's zip directory could not be read here (it may be an incomplete "
                    "download); unzip it and import the folder")


# The largest zip member the importer reads (P102): the CSV and JSON files it reads are far smaller
# in a normal export, so this stops only a pathological member, which is skipped with a note.
MAX_MEMBER_BYTES = 256 * 1024 * 1024
try:  # zipfile reads an LZMA member only when this module is present, and so is its error
    import lzma as _lzma
    _LZMA_ERRORS = (_lzma.LZMAError,)
except ImportError:
    _LZMA_ERRORS = ()
# What reading a member that does not decompress raises: a CRC mismatch or a bad header
# (BadZipFile), a corrupt deflate stream (zlib.error), a corrupt bzip2 stream or a failed read of the
# zip file (OSError), a corrupt LZMA stream (lzma.LZMAError), a stream that ends early (EOFError), a
# compression method this Python lacks (NotImplementedError), an encrypted member (RuntimeError).
MEMBER_READ_ERRORS = (zipfile.BadZipFile, zlib.error, OSError, EOFError, NotImplementedError,
                      RuntimeError) + _LZMA_ERRORS


def _read_member(z, name):
    """The bytes of one member of an open zip, or None with one note on stderr: a member whose
    directory entry says it is over MAX_MEMBER_BYTES is not read (zipfile reads no more than that
    entry's size, so the read is bounded), and one that does not decompress (MEMBER_READ_ERRORS,
    an interrupted download) is skipped instead of stopping the import (P102)."""
    shown = " ".join(str(name).split())[:200]  # one line, so a member name cannot add a note line
    info = z.getinfo(name)
    if info.file_size > MAX_MEMBER_BYTES:
        _note(f"{shown} inside this zip is larger than {MAX_MEMBER_BYTES // (1024 * 1024)} MiB, so it "
              f"was not read; unzip the export and import the folder")
        return None
    try:
        return z.read(info)
    except MEMBER_READ_ERRORS as exc:
        kind = "zlib.error" if isinstance(exc, zlib.error) else type(exc).__name__
        _note(f"{shown} inside this zip could not be read ({kind}; it may be damaged or an incomplete "
              f"download), so it was skipped; download the export again")
        return None


def _member_text(z, name):
    """The decoded text of one zip member (textdecode's reading), or None when _read_member skips it."""
    raw = _read_member(z, name)
    return None if raw is None else _td.decode_text(raw)[0]


def _safe_zip(path):
    """Open a zip, or return None if it is missing/unreadable/corrupt. Note: zipfile.BadZipFile is
    NOT an OSError subclass (it derives directly from Exception), so both must be caught. This lets a
    creator point the importer at a corrupt/partial .zip download and get a clean empty result plus a
    gap, never a traceback. The end record is read first (classify.zip_directory), and a zip whose
    end records are not read here, or whose directory is over classify's limits, is not opened: a
    note says so and how to import it instead (P102; the inbox proposes a zip it could not list when
    its name says it is an export). A zip file it does not open gets one note, so a caller that gets
    None for a zip file prints none of its own."""
    if Path(str(path)).is_file():
        directory = _classify.zip_directory(path)
        refused = _classify.zip_refusal(directory)
        if refused:
            _note(f"this zip is too large to read here ({refused}); unzip it and import the folder")
            return None
        if directory is None:
            _note(_ZIP_UNREAD_NOTE)
            return None
    try:
        return zipfile.ZipFile(path)
    except _classify.ZIP_OPEN_ERRORS:  # a damaged directory, or a member name zipfile cannot decode
        if Path(path).is_file():  # its end record reads, its directory does not: a damaged download
            _note(_ZIP_UNREAD_NOTE)
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
    if not any(mapping.values()) and any(r and any(c.strip() for c in r) for r in rows[1:]):
        _note("none of this CSV's column names were recognised (is YouTube Studio set to another "
              "language? set it to English, export again, and import that file)")
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
    """The Studio table CSV in an export zip ("Table data", else any CSV whose first line names a
    Content column), opened once, so a zip _safe_zip does not open gives one note."""
    z = _safe_zip(zip_path)
    if z is None:
        return []
    text = None
    with z:
        csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
        table = next((n for n in csvs if "table data" in n.lower()), None)
        if table is not None:
            text = _member_text(z, table)
        else:  # fall back to any csv that has a "Content" header
            for n in csvs:
                t = _member_text(z, n)
                if t and t.splitlines() and "content" in t.splitlines()[0].lower():
                    text = t
                    break
    return parse_youtube_studio_csv(text) if text else []


# ── Google Takeout (metadata only; NO analytics) ─────────────────────────────

def _probe_exists(p):
    """Path.exists() with the pre-3.14 boundary semantics (P91): absent reads False, but an
    UNPROBEABLE path (e.g. a >NAME_MAX component raising ENAMETOOLONG) raises OSError so the
    CLI envelope fires -- CPython 3.14 changed Path.exists()/is_file()/is_dir() to swallow
    those errors, which made an unreadable path parse to an empty [] instead."""
    if any(len(part) > 255 for part in Path(p).parts):
        # A name part over 255 characters cannot exist; Windows with long paths off reports it as
        # missing, so refuse it here as unprobeable, as ENAMETOOLONG does elsewhere (P102).
        raise OSError(errno.ENAMETOOLONG, "file name too long", str(p))
    try:
        p.stat()
        return True
    except (FileNotFoundError, NotADirectoryError, ValueError):
        return False


def parse_youtube_takeout(path):
    """Parse a Takeout 'YouTube and YouTube Music' folder or zip. Metadata only: id/title/published/
    description; stats stay null (Takeout carries no analytics). Defensive CSV column matching."""
    p = Path(str(path))
    _probe_exists(p)  # unprobeable (e.g. ENAMETOOLONG) raises to the CLI envelope; absent falls through
    if p.is_file() and p.name.lower().endswith((".tgz", ".tar.gz")):
        _note("this Takeout is a .tgz archive, which this tool does not read; in Google Takeout "
              "choose .zip, or extract the archive and import the folder")
        return []

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
                        t = _member_text(z, n)
                        if t is not None:
                            texts.append(t)
    elif p.is_dir():
        for f in p.rglob("*.csv"):
            if "video metadata" in str(f).lower() or "video" in f.name.lower():
                texts.append(_td.read_text_file(f)[0])
        if not texts and (any(p.glob("*.tgz")) or any(p.glob("*.tar.gz"))):
            _note("this folder holds a .tgz Takeout archive, which this tool does not read; extract it "
                  "here and import again, or choose .zip in Google Takeout")
    elif p.is_file() and p.suffix.lower() == ".csv":
        texts.append(_td.read_text_file(p)[0])
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
                        t = _member_text(z, n)
                        if t is not None:
                            texts.append(t)
    elif p.is_dir():
        for f in list(p.rglob("posts_*.json")) + list(p.rglob("reels.json")) + list(p.rglob("posts.json")):
            texts.append(_td.read_text_file(f)[0])
    elif p.is_file() and p.suffix.lower() == ".json":
        texts.append(_td.read_text_file(p)[0])
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

# The JSON file a TikTok "Download your data" zip holds, by the names public tools report.
_TIKTOK_MEMBERS = ("user_data_tiktok.json", "user_data.json")


def _is_path_text(value) -> bool:
    """True for a value that names a path rather than holding raw JSON or CSV text."""
    if isinstance(value, Path):
        return True
    return isinstance(value, str) and "\n" not in value and len(value) < 4096


def _tiktok_zip_text(zip_path):
    """(text, noted): the text of the export JSON inside a TikTok data zip (user_data_tiktok.json
    first), or None; noted is True when a note already says why there is no text (_safe_zip did not
    open the zip, or _read_member skipped the member)."""
    z = _safe_zip(zip_path)
    if z is None:
        return None, True
    with z:
        names = z.namelist()
        for want in _TIKTOK_MEMBERS:
            for n in names:
                if n.replace("\\", "/").rsplit("/", 1)[-1].lower() == want:
                    text = _member_text(z, n)
                    return text, text is None
    return None, False


def parse_tiktok_dyi(path_or_obj):
    """Parse a TikTok data-export JSON. Key casing varies (Video>Videos>VideoList[] PascalCase, or a
    flat list, or snake_case), so navigation is defensive."""
    if isinstance(path_or_obj, (dict, list)):
        obj = path_or_obj
    elif _is_path_text(path_or_obj) and str(path_or_obj).lower().endswith(".zip"):
        text, noted = _tiktok_zip_text(path_or_obj)
        if text is None:
            if not noted:  # _safe_zip, or _read_member for a damaged member, has said why
                _note("no user_data_tiktok.json or user_data.json in this zip (choose JSON as the file "
                      "format when you request your TikTok data)")
            return []
        obj = json.loads(text)
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
    # P102: a Studio CSV saved with a byte-order mark keeps its first column, "Content".
    import codecs
    ok("yt studio: a CSV with a UTF-8 BOM parses the same two rows",
       parse_youtube_studio_csv(codecs.BOM_UTF8 + yt_csv.encode("utf-8")) == yt)
    ok("yt studio: a UTF-16 CSV with a BOM parses the same two rows",
       parse_youtube_studio_csv(codecs.BOM_UTF16_LE + yt_csv.encode("utf-16-le")) == yt)
    import tempfile as _tf_bom
    with _tf_bom.TemporaryDirectory() as _td_bom:
        _zp = Path(_td_bom) / "Content 2026-09-07_2026-10-05 Fictional Channel.zip"
        try:  # invariant 35: each ZipFile call sits inside a try
            with zipfile.ZipFile(_zp, "w") as _z:
                _z.writestr("Table data.csv", codecs.BOM_UTF8 + yt_csv.encode("utf-8"))
        except (OSError, zipfile.BadZipFile):
            pass  # the check below then fails
        _csvp = Path(_td_bom) / "Table data.csv"
        _csvp.write_bytes(codecs.BOM_UTF8 + yt_csv.encode("utf-8"))
        ok("yt studio: a zip whose Table data.csv carries a BOM, and the same file on disk, parse the "
           "same two rows", parse_youtube_studio_zip(_zp) == yt and parse_youtube_studio_csv(str(_csvp)) == yt)
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
    # P102: a TikTok data zip is read through its JSON member, and .tgz Takeouts and Studio CSVs
    # in another language say why they give nothing (a note: line on stderr).
    import contextlib as _cl_n
    import io as _io_n
    import tempfile as _tf_tt
    tt_obj = {"Video": {"Videos": {"VideoList": [
        {"Date": "2026-05-01 12:00:00", "Link": "https://www.tiktokv.com/share/video/7300000000000000000/",
         "Likes": "1,234", "Title": "diy hack"}]}}}
    with _tf_tt.TemporaryDirectory() as _td_tt:
        bad_zip = Path(_td_tt) / "cut-download.zip"
        bad_zip.write_bytes(b"PK\x03\x04 the start of a zip whose download stopped")
        _ttz = Path(_td_tt) / "TikTok_Data_1759600000.zip"
        _bare = Path(_td_tt) / "TikTok_Data_empty.zip"
        _tgz = Path(_td_tt) / "takeout-20261005T120000Z-001.tgz"
        _es = Path(_td_tt) / "Datos de la tabla.csv"
        try:  # invariant 35: each ZipFile call sits inside a try
            with zipfile.ZipFile(_ttz, "w") as _z:
                _z.writestr("TikTok_Data/user_data_tiktok.json", json.dumps(tt_obj))
            with zipfile.ZipFile(_bare, "w") as _z:
                _z.writestr("readme.txt", "no export here")
        except (OSError, zipfile.BadZipFile):
            pass  # the checks below then fail
        _tgz.write_bytes(b"\x1f\x8b\x08\x00 not read")
        _es.write_text("Contenido,T\u00edtulo del v\u00eddeo,Visualizaciones\nabc123,Pintar,12\n", encoding="utf-8")
        _err = _io_n.StringIO()
        with _cl_n.redirect_stderr(_err):
            from_zip = parse_tiktok_dyi(str(_ttz))
            bare = parse_tiktok_dyi(str(_bare))
            tgz = parse_youtube_takeout(str(_tgz))
            es = parse_youtube_studio_csv(str(_es))
            quiet = parse_youtube_studio_csv(yt_csv)
        _lines = [ln for ln in _err.getvalue().splitlines() if ln.startswith("note: ")]
        ok("tiktok dyi: a data zip is read through user_data_tiktok.json, the same record as the JSON",
           from_zip == parse_tiktok_dyi(tt_obj) and len(from_zip) == 1)
        ok("tiktok dyi: a zip without the export JSON gives [] and a note, not a traceback",
           bare == [] and any("user_data_tiktok.json" in ln for ln in _lines))
        ok("takeout: a .tgz gives [] and a note naming the .zip choice",
           tgz == [] and any(".tgz" in ln and ".zip" in ln for ln in _lines))
        _err2 = _io_n.StringIO()
        with _cl_n.redirect_stderr(_err2):
            in_dir = parse_youtube_takeout(_td_tt)
        ok("takeout: a folder holding only a .tgz gives [] and a note",
           in_dir == [] and "folder holds a .tgz" in _err2.getvalue())
        ok("yt studio: a CSV whose column names are all unrecognised gives [] and a note; a known one "
           "gives none", es == [] and quiet == yt and sum("column names" in ln for ln in _lines) == 1)
        # P102: the TikTok member is matched by its exact name, user_data_tiktok.json first; a
        # header-only CSV in another language says nothing; a zip over classify's limits, or one whose
        # end records are not read, is not opened, with a note.
        _both = Path(_td_tt) / "both.zip"
        _other = Path(_td_tt) / "other.zip"
        _many = Path(_td_tt) / "takeout-many.zip"
        _hdr = Path(_td_tt) / "Encabezados.csv"
        later = {"Video": {"Videos": {"VideoList": [
            {"Date": "2026-05-02 12:00:00", "Link": "https://www.tiktokv.com/share/video/7300000000000000001/",
             "Likes": "5", "Title": "older file"}]}}}
        try:  # invariant 35: each ZipFile call sits inside a try
            with zipfile.ZipFile(_both, "w") as _z:
                _z.writestr("user_data.json", json.dumps(later))
                _z.writestr("TikTok/user_data_tiktok.json", json.dumps(tt_obj))
            with zipfile.ZipFile(_other, "w") as _z:
                _z.writestr("old_user_data.json", json.dumps(later))
        except (OSError, zipfile.BadZipFile):
            pass  # the checks below then fail
        _many.write_bytes(_classify._zip_bytes(
            ["Takeout/YouTube and YouTube Music/video metadata/videos.csv"]
            + [f"Takeout/x{i}.txt" for i in range(_classify.ZIP_MAX_ENTRIES + 1)]))
        _hdr.write_text("Contenido,Visualizaciones\n", encoding="utf-8")
        _err3 = _io_n.StringIO()
        with _cl_n.redirect_stderr(_err3):
            from_both = parse_tiktok_dyi(str(_both))
            from_other = parse_tiktok_dyi(str(_other))
            from_many = parse_youtube_takeout(str(_many))
            from_bad = parse_youtube_studio_zip(bad_zip)
            from_hdr = parse_youtube_studio_csv(str(_hdr))
        _lines3 = [ln for ln in _err3.getvalue().splitlines() if ln.startswith("note: ")]
        ok("tiktok dyi: user_data_tiktok.json is read before user_data.json, and a member that only "
           "ends in user_data.json is not taken",
           from_both == parse_tiktok_dyi(tt_obj) and from_other == []
           and any("no user_data_tiktok.json" in ln for ln in _lines3))
        ok("a zip over the entry limit is not opened, and its note says to unzip it",
           from_many == [] and any("too large to read here" in ln and "50,000" in ln for ln in _lines3))
        ok("a file whose zip directory is not read gives [] and a note naming an incomplete download",
           from_bad == [] and any("incomplete download" in ln for ln in _lines3))
        ok("a header-only CSV with unrecognised column names gives [] and no note",
           from_hdr == [] and not any("column names" in ln for ln in _lines3))
        # A zip _safe_zip does not open gives one note per parser, and no parser adds one of its own:
        # a zip over the limits, and one whose end record reads but whose directory does not.
        _bent = Path(_td_tt) / "bent.zip"
        _bent.write_bytes(_classify._zip_bytes(["user_data_tiktok.json"]).replace(b"PK\x01\x02", b"PK\x01\x03"))

        def _notes_of(fn, arg):
            buf = _io_n.StringIO()
            with _cl_n.redirect_stderr(buf):
                got = fn(arg)
            return got, [ln for ln in buf.getvalue().splitlines() if ln.startswith("note: ")]
        _shut = {(name, fn.__name__): _notes_of(fn, str(name))
                 for name in (_many, _bent) for fn in (parse_tiktok_dyi, parse_youtube_studio_zip)}
        ok("a zip that is not opened gives [] and one note, the refusal or the damaged download, from "
           "the TikTok and Studio parsers alike",
           all(got == [] and len(lines) == 1 for got, lines in _shut.values())
           and all("too large to read here" in lines[0] for (name, _f), (_g, lines) in _shut.items()
                   if name == _many)
           and all("incomplete download" in lines[0] for (name, _f), (_g, lines) in _shut.items()
                   if name == _bent))
        # A zip whose directory classify does not read is not opened, even where this Python's
        # zipfile would open it (the fake ZIP64 locator on a Python without the CVE-2025-8291 fix):
        # zip_directory is stubbed to report no directory for a readable TikTok zip.
        _real_zd = _classify.zip_directory
        _classify.zip_directory = lambda _path: None
        try:
            _unread = _notes_of(parse_tiktok_dyi, str(_both))
        finally:
            _classify.zip_directory = _real_zd
        ok("a zip whose directory classify does not read is not opened, with one note, even when "
           "zipfile could open it",
           _unread[0] == [] and len(_unread[1]) == 1 and "incomplete download" in _unread[1][0])
        # A member name zipfile cannot decode (the UTF-8 flag on bytes that are not UTF-8) gives []
        # and the one note from each zip parser; a zip path that does not exist gives no note.
        _badname = Path(_td_tt) / "badname.zip"
        _badname.write_bytes(_classify._bad_name_zip_bytes())
        _bad_runs = [_notes_of(fn, str(_badname))
                     for fn in (parse_tiktok_dyi, parse_youtube_studio_zip, parse_youtube_takeout)]
        ok("a zip whose member name zipfile cannot decode gives [] and one note from the TikTok, Studio "
           "and Takeout parsers alike",
           all(got == [] and len(lines) == 1 and "incomplete download" in lines[0] for got, lines in _bad_runs))
        ok("a zip path that does not exist gives [] and no note",
           _notes_of(parse_tiktok_dyi, str(Path(_td_tt) / "missing.zip")) == ([], []))
        # The Studio zip's table is the CSV named Table data, in any letter case, even after another
        # CSV with a Content column; without one, the first CSV with a Content column is read.
        _pick = Path(_td_tt) / "studio-pick.zip"
        _fall = Path(_td_tt) / "studio-fallback.zip"
        _other_rows = "Content,Video title,Views\nzzz999,Not the table,1\n"
        try:  # invariant 35: each ZipFile call sits inside a try
            with zipfile.ZipFile(_pick, "w") as _z:
                _z.writestr("Chart data.csv", _other_rows)
                _z.writestr("TABLE DATA.csv", yt_csv)
            with zipfile.ZipFile(_fall, "w") as _z:
                _z.writestr("Totals.csv", "Date,Views\n2026-10-01,5\n")
                _z.writestr("Export.csv", yt_csv)
        except (OSError, zipfile.BadZipFile):
            pass  # the checks below then fail
        ok("a Studio zip's table is the CSV named Table data, in any letter case, even after another "
           "CSV with a Content column", parse_youtube_studio_zip(str(_pick)) == yt)
        ok("without a Table data CSV, the first CSV whose first line names a Content column is read",
           parse_youtube_studio_zip(str(_fall)) == yt)

    # P102 push 4c: a member that does not decompress, or whose directory entry is over
    # MAX_MEMBER_BYTES, is skipped with one note naming it on one line; the zip's other members are
    # read, and nothing raises.
    def _zip_with(path, members, damaged=None, method=zipfile.ZIP_DEFLATED, block=False):
        """Write a zip of members (name -> bytes) and damage `damaged`'s data: flip one byte in its
        middle (a CRC mismatch), or with block, break the start of its compressed stream: a deflate
        stream starts with the reserved block type, which zlib refuses; a bzip2 stream loses its
        "BZh" mark, which bz2 refuses with OSError; an LZMA stream gets a properties byte over 224,
        which lzma refuses with LZMAError."""
        buf = _io_n.BytesIO()
        try:  # invariant 35: each ZipFile call sits inside a try
            with zipfile.ZipFile(buf, "w", method) as _zw:
                for _n, _data in members.items():
                    _zw.writestr(_n, _data)
            raw = bytearray(buf.getvalue())
            if damaged is not None:
                with zipfile.ZipFile(_io_n.BytesIO(bytes(raw))) as _zr:
                    _info = _zr.getinfo(damaged)
                _off = _info.header_offset
                _start = (_off + 30 + int.from_bytes(raw[_off + 26:_off + 28], "little")
                          + int.from_bytes(raw[_off + 28:_off + 30], "little"))
                if block and method == zipfile.ZIP_BZIP2:
                    raw[_start] = 0x00  # the B of the BZh stream header
                elif block and method == zipfile.ZIP_LZMA:
                    raw[_start + 4] = 0xFF  # after zipfile's 4-byte LZMA header: the lc/lp/pb byte
                elif block:
                    raw[_start] = 0x07  # BFINAL 1, BTYPE 11: a reserved deflate block type
                else:
                    raw[_start + _info.compress_size // 2] ^= 0xFF
            path.write_bytes(bytes(raw))
        except (OSError, zipfile.BadZipFile):
            pass  # the checks below then fail
    _rows_csv = ("Video ID,Video title\n" + "".join(f"vid{i},Title {i}\n" for i in range(400))).encode()
    with _tf_bom.TemporaryDirectory() as _td_dm:
        _dm = Path(_td_dm)
        _zip_with(_dm / "studio.zip", {"Table data.csv": yt_csv.encode() * 40}, "Table data.csv",
                  zipfile.ZIP_STORED)
        _studio_got = _notes_of(parse_youtube_studio_zip, str(_dm / "studio.zip"))
        _zip_with(_dm / "takeout.zip", {"Takeout/YouTube/video metadata/videos.csv": _rows_csv,
                                        "Takeout/YouTube/video metadata/videos (1).csv": _rows_csv},
                  "Takeout/YouTube/video metadata/videos.csv", block=True)
        _takeout_got = _notes_of(parse_youtube_takeout, str(_dm / "takeout.zip"))
        _zip_with(_dm / "tiktok.zip", {"user_data_tiktok.json": json.dumps(
            {"Video": {"Videos": {"VideoList": [{"Link": f"https://x/{i}", "Date": "2026-01-01"}
                                                for i in range(300)]}}}).encode()}, "user_data_tiktok.json")
        _tiktok_got = _notes_of(parse_tiktok_dyi, str(_dm / "tiktok.zip"))
        _zip_with(_dm / "named.zip", {"Table data\nnote: made-up.csv": yt_csv.encode() * 40},
                  "Table data\nnote: made-up.csv", zipfile.ZIP_STORED)
        _named_got = _notes_of(parse_youtube_studio_zip, str(_dm / "named.zip"))
        _zip_with(_dm / "ig.zip", {"posts_1.json": json.dumps([{"media": [
            {"uri": "media/posts/1.mp4", "creation_timestamp": 1772409600, "title": "x" * 5000}]}]).encode()})
        _ig_whole = _notes_of(parse_instagram_dyi, str(_dm / "ig.zip"))
        _zip_with(_dm / "fallback.zip", {"Chart.csv": yt_csv.encode() * 40, "Export.csv": yt_csv.encode()},
                  "Chart.csv", zipfile.ZIP_STORED)
        _fallback_got = _notes_of(parse_youtube_studio_zip, str(_dm / "fallback.zip"))
        _other_methods = {}
        for _label, _method, _mod in (("bzip2", zipfile.ZIP_BZIP2, "bz2"), ("lzma", zipfile.ZIP_LZMA, "lzma")):
            try:
                __import__(_mod)
            except ImportError:  # this Python cannot write the member, so the case is skipped
                print(f"  [skip] a damaged {_label} member: the {_mod} module is missing")
                continue
            _zip_with(_dm / f"takeout-{_label}.zip",
                      {"Takeout/YouTube/video metadata/videos.csv": _rows_csv,
                       "Takeout/YouTube/video metadata/videos (1).csv": _rows_csv},
                      "Takeout/YouTube/video metadata/videos.csv", _method, block=True)
            _other_methods[_label] = _notes_of(parse_youtube_takeout, str(_dm / f"takeout-{_label}.zip"))
        _cap_saved = globals()["MAX_MEMBER_BYTES"]
        globals()["MAX_MEMBER_BYTES"] = 1000  # under posts_1.json's size, over its compressed size
        try:
            _ig_capped = _notes_of(parse_instagram_dyi, str(_dm / "ig.zip"))
        finally:
            globals()["MAX_MEMBER_BYTES"] = _cap_saved
        _out_cli, _err_cli = _io_n.StringIO(), _io_n.StringIO()
        with _cl_n.redirect_stdout(_out_cli), _cl_n.redirect_stderr(_err_cli):
            _rc_cli = main(["youtube-studio-zip", str(_dm / "studio.zip")])
    ok("a damaged member gives [] and one note naming it, from the Studio and TikTok parsers",
       _studio_got[0] == [] and len(_studio_got[1]) == 1 and "Table data.csv" in _studio_got[1][0]
       and "BadZipFile" in _studio_got[1][0] and _tiktok_got[0] == [] and len(_tiktok_got[1]) == 1
       and "user_data_tiktok.json" in _tiktok_got[1][0] and "could not be read" in _tiktok_got[1][0])
    ok("a damaged member is skipped and the zip's other members are read",
       len(_takeout_got[0]) == 400 and len(_takeout_got[1]) == 1
       and "videos.csv inside this zip could not be read (zlib.error" in _takeout_got[1][0])
    ok("a damaged bzip2 member (OSError) or LZMA member (LZMAError) is skipped with its note, and the "
       "zip's other member is read",
       all(len(_got[0]) == 400 and len(_got[1]) == 1
           and f"videos.csv inside this zip could not be read ({_kind};" in _got[1][0]
           for _label, _kind in (("bzip2", "OSError"), ("lzma", "LZMAError"))
           for _got in [_other_methods.get(_label)] if _got is not None))  # a skipped case drops out
    ok("a damaged CSV is passed over when the Studio parser looks for one with a Content column",
       _fallback_got[0] == yt and len(_fallback_got[1]) == 1 and "Chart.csv" in _fallback_got[1][0])
    ok("a member name with a line break stays on the one note line",
       _named_got[0] == [] and len(_named_got[1]) == 1 and "made-up.csv" in _named_got[1][0])
    ok("a member whose directory entry is over the cap is not read, with a note to unzip the export",
       len(_ig_whole[0]) == 1 and _ig_whole[1] == [] and _ig_capped[0] == [] and len(_ig_capped[1]) == 1
       and "larger than" in _ig_capped[1][0] and "unzip the export" in _ig_capped[1][0])
    ok("the command line prints [] and exits 0 for a zip whose table is damaged, with one note",
       _rc_cli == 0 and json.loads(_out_cli.getvalue()) == []
       and [ln for ln in _err_cli.getvalue().splitlines() if ln.startswith("note: ")] == _studio_got[1]
       and "Traceback" not in _err_cli.getvalue())
    ok("the member cap is 256 MiB", MAX_MEMBER_BYTES == 256 * 1024 * 1024)

    pin = parse_pinterest_export({"pins": [{"pin_id": "998877",
                                            "metrics": {"IMPRESSION": 2400, "SAVE": 30, "VIDEO_MRC_VIEW": 400}}]})
    ok("pinterest: id + metrics", pin[0]["platform_video_id"] == "998877" and pin[0]["stats"]["impression"] == 2400)
    ok("pinterest: retention null", pin[0]["retention"] is None)

    # P46 fix 4: a corrupt / non-zip file degrades to [] (no BadZipFile traceback).
    import tempfile as _tf
    bad = Path(_tf.mkdtemp()) / "corrupt.zip"
    bad.write_bytes(b"this is not a zip file at all")
    with _cl_n.redirect_stderr(_io_n.StringIO()):  # each prints its note
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
    import file_hash as _fh_lp  # P102: Windows with long paths off reports the long name as missing
    buf = io.StringIO()
    with _fh_lp.long_paths_off(), contextlib.redirect_stdout(buf):
        rc_lp = main(["youtube-takeout", "x" * 300])
    ok(">255-character path arg -> clean envelope where the system reports it missing (P102)",
       rc_lp == 1 and "next_step" in buf.getvalue())

    # P102: a Studio export with an emoji title, piped under a cp1252 codec (what a Windows pipe
    # uses), is parsed with the title intact; main switches the redirected stdout to UTF-8.
    import os
    import subprocess
    import tempfile
    fx = json.loads((Path(__file__).resolve().parent.parent / "skills" / "creator-core" / "evals" / "fixtures"
                     / "video-library-youtube-studio.json").read_text(encoding="utf-8"))["csv_text"]
    title = "Restoring a farmhouse armoire \U0001f3a5 (before \u2192 after; caf\u00e9)"  # no comma: a CSV cell
    with tempfile.TemporaryDirectory() as td:
        csv_path = Path(td) / "Table data.csv"
        csv_path.write_text(fx.replace("Restoring a farmhouse armoire", title, 1), encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        env.pop("PYTHONUTF8", None)
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "youtube-studio-csv", str(csv_path)],
                           capture_output=True, env=env, timeout=120)
    try:
        piped = json.loads(r.stdout.decode("utf-8"))
    except ValueError:
        piped = []
    ok("a Studio export with an emoji title piped under a cp1252 codec keeps the title",
       r.returncode == 0 and any(rec.get("title") == title for rec in piped))
    ok("main switches a redirected stdout to UTF-8", "utf8_stdio" in main.__code__.co_names)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


class _TmpFile:
    """A throwaway file for the selftest (glob-based parsers expect a path)."""
    def __init__(self, text, suffix):
        import os
        import tempfile
        fd, name = tempfile.mkstemp(suffix=suffix)
        os.close(fd)   # P101: Windows cannot rewrite or remove a file a handle holds open
        self._p = Path(name)
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
    becomes the clean {"error","next_step"} envelope instead of a raw traceback. Its output is UTF-8
    when stdout is redirected or piped (env_paths.utf8_stdio, P102), so a title with an emoji
    reaches the file instead of stopping the tool on Windows."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for env_paths
    import env_paths
    env_paths.utf8_stdio()
    try:
        return _main(argv)
    except OSError as exc:
        print(json.dumps({"error": str(exc),
                          "next_step": "pass a readable file path (this one could not be opened)"}))
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
