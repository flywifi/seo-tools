#!/usr/bin/env python3
"""video_library.py -- the creator's OWN past-video library (P45), a local gitignored store.

The read side of the content-import lane (shared/content-import-engine.md). Where competitor_snapshot.py
indexes COMPETITOR pages, this indexes the CREATOR's own videos across YouTube/Instagram/TikTok/Pinterest:
per-video metadata, stats (each wrapped in a freshness provenance envelope), YouTube audience retention,
Studio-CSV revenue, transcript text, chapters, and derived most-watched segments. FTS over title,
description, tags, and transcript.

Storage: pipeline/video-library/index.local.db (SQLite + FTS5), gitignored. There is NO committed
summary export (unlike competitor_snapshot) -- the creator's own performance/revenue/transcript data is
private and stays entirely local. Upsert is by video_key so a re-import refreshes stats in place.

Honesty: never fabricates. A platform that does not provide a field (retention off YouTube, revenue
without a Studio CSV) is stored as null and flagged; the model reasons over the stored record, never over
a guess. CREATOR_OS_ROOT-sandboxed; stdlib only (freshness_overlay is stdlib).

Usage:
  python3 tools/video_library.py init
  python3 tools/video_library.py upsert --record '<json>'          # one normalized record (or - for stdin)
  python3 tools/video_library.py upsert-batch <file.json>          # a JSON array of records
  python3 tools/video_library.py get <video_key>
  python3 tools/video_library.py list [--platform youtube] [--limit 50]
  python3 tools/video_library.py query "<fts query>" [--limit 20]
  python3 tools/video_library.py derive-most-watched <video_key>   # recompute + store from retention
  python3 tools/video_library.py --selftest
"""
import argparse
import hashlib
import json
import os
import sqlite3
import statistics
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "shared"))
import freshness_overlay as FO  # noqa: E402  (envelope() for per-stat provenance)

ROOT = Path(os.environ.get("CREATOR_OS_ROOT", str(HERE.parent)))
STORE_DIR = ROOT / "pipeline" / "video-library"
DB_PATH = STORE_DIR / "index.local.db"
PLATFORMS = ("youtube", "instagram", "tiktok", "pinterest")
# JSON-encoded columns (list/dict fields serialized for SQLite).
_JSON_COLS = ("tags", "stats", "retention", "revenue", "chapters", "most_watched_segments", "provenance")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS video_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_key TEXT UNIQUE,
    platform TEXT, platform_video_id TEXT, url TEXT,
    title TEXT, description TEXT, tags_json TEXT, category TEXT,
    published_at TEXT, duration_s INTEGER,
    stats_json TEXT, retention_json TEXT, revenue_json TEXT,
    transcript_ref TEXT, transcript_text TEXT,
    chapters_json TEXT, most_watched_json TEXT,
    provenance_json TEXT, source_mode TEXT,
    content_hash TEXT, imported_at TEXT, updated_at TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS video_records_fts
USING fts5(video_key, title, description, tags_json, transcript_text);
"""


def _open_db(db_path=None):
    db_path = Path(db_path or DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    con.commit()
    return con


# ── most-watched derivation (pure; the selftest pins this) ───────────────────

def derive_most_watched(retention, peak_k=0.5, min_points=5):
    """From a YouTube retention array [{elapsed_ratio, watch_ratio, ...}] derive peak ranges (watch_ratio
    at or above mean + peak_k*stdev) plus the single steepest-drop cliff. Returns [] when too few points.
    Pure; never fabricates (empty in, empty out)."""
    pts = [(p.get("elapsed_ratio"), p.get("watch_ratio")) for p in (retention or [])
           if isinstance(p, dict) and p.get("elapsed_ratio") is not None and p.get("watch_ratio") is not None]
    if len(pts) < min_points:
        return []
    pts.sort(key=lambda x: x[0])
    ratios = [r for _, r in pts]
    mean = statistics.fmean(ratios)
    sd = statistics.pstdev(ratios)
    if sd == 0:
        return []  # a perfectly flat curve has no most-watched region: every point equals the mean
    thr = mean + peak_k * sd
    segs = []
    run = None
    for er, wr in pts:
        if wr >= thr:
            run = [er, er] if run is None else [run[0], er]
        elif run:
            segs.append({"start_ratio": round(run[0], 4), "end_ratio": round(run[1], 4), "label": "peak"})
            run = None
    if run:
        segs.append({"start_ratio": round(run[0], 4), "end_ratio": round(run[1], 4), "label": "peak"})
    steepest = None
    for i in range(1, len(pts)):
        drop = pts[i - 1][1] - pts[i][1]
        if steepest is None or drop > steepest[0]:
            steepest = (drop, pts[i - 1][0], pts[i][0])
    if steepest and steepest[0] > 0:
        segs.append({"start_ratio": round(steepest[1], 4), "end_ratio": round(steepest[2], 4),
                     "label": "cliff", "drop": round(steepest[0], 4)})
    return segs


# ── normalize a parsed record into the canonical store shape ─────────────────

def normalize_record(parsed, platform=None, source_mode=None, source_citation=None):
    """Turn a parser/importer dict into the canonical record. Each stat value is wrapped in a
    freshness_overlay.envelope so a stale stat ages and flags. Missing fields stay null (never invented).
    `parsed` keys: platform_video_id, url, title, description, tags[], category, published_at,
    duration_s, stats{metric:value}, retention[]|None, revenue{}|None, transcript_text, chapters[]."""
    platform = (platform or parsed.get("platform") or "").lower()
    if platform not in PLATFORMS:
        raise ValueError(f"unknown platform {platform!r} (expected one of {PLATFORMS})")
    pvid = str(parsed.get("platform_video_id") or "").strip()
    if not pvid:
        raise ValueError("platform_video_id is required")
    src = source_citation or parsed.get("source_citation") or parsed.get("url") or ""
    stats_env = {}
    for metric, value in (parsed.get("stats") or {}).items():
        if value is None:
            continue
        stats_env[metric] = FO.envelope(value, src, publish_date=parsed.get("published_at"))
    retention = parsed.get("retention")  # None off YouTube -> stays null (not available)
    rec = {
        "video_key": f"{platform}:{pvid}",
        "platform": platform,
        "platform_video_id": pvid,
        "url": parsed.get("url"),
        "title": parsed.get("title"),
        "description": parsed.get("description"),
        "tags": parsed.get("tags") or [],
        "category": parsed.get("category"),
        "published_at": parsed.get("published_at"),
        "duration_s": parsed.get("duration_s"),
        "stats": stats_env,
        "retention": retention if isinstance(retention, list) else None,
        "revenue": parsed.get("revenue"),  # null unless a Studio CSV supplied it
        "transcript_ref": parsed.get("transcript_ref"),
        "transcript_text": parsed.get("transcript_text"),
        "chapters": parsed.get("chapters") or [],
        "most_watched_segments": derive_most_watched(retention) if isinstance(retention, list) else [],
        "provenance": {"source_mode": source_mode or parsed.get("source_mode"),
                       "source_citation": src or None,
                       "imported_at": date.today().isoformat()},
        "source_mode": source_mode or parsed.get("source_mode"),
    }
    return rec


def _content_hash(rec):
    payload = {k: rec.get(k) for k in ("title", "description", "tags", "stats", "retention",
                                       "revenue", "transcript_text", "chapters")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ── upsert (by video_key; UPDATE on re-import so stats refresh) ──────────────

def _upsert(con, rec):
    today = date.today().isoformat()
    ch = _content_hash(rec)
    cur = con.execute("SELECT id, imported_at FROM video_records WHERE video_key=?", (rec["video_key"],))
    existing = cur.fetchone()
    cols = {
        "video_key": rec["video_key"], "platform": rec["platform"],
        "platform_video_id": rec["platform_video_id"], "url": rec.get("url"),
        "title": rec.get("title"), "description": rec.get("description"),
        "tags_json": json.dumps(rec.get("tags") or [], ensure_ascii=False),
        "category": rec.get("category"), "published_at": rec.get("published_at"),
        "duration_s": rec.get("duration_s"),
        "stats_json": json.dumps(rec.get("stats") or {}, ensure_ascii=False),
        "retention_json": json.dumps(rec["retention"], ensure_ascii=False) if rec.get("retention") is not None else None,
        "revenue_json": json.dumps(rec["revenue"], ensure_ascii=False) if rec.get("revenue") is not None else None,
        "transcript_ref": rec.get("transcript_ref"), "transcript_text": rec.get("transcript_text"),
        "chapters_json": json.dumps(rec.get("chapters") or [], ensure_ascii=False),
        "most_watched_json": json.dumps(rec.get("most_watched_segments") or [], ensure_ascii=False),
        "provenance_json": json.dumps(rec.get("provenance") or {}, ensure_ascii=False),
        "source_mode": rec.get("source_mode"), "content_hash": ch, "updated_at": today,
    }
    if existing:
        cols["imported_at"] = existing["imported_at"] or today
        sets = ", ".join(f"{k}=?" for k in cols)
        con.execute(f"UPDATE video_records SET {sets} WHERE video_key=?",
                    [*cols.values(), rec["video_key"]])
        status = "updated"
    else:
        cols["imported_at"] = today
        keys = ", ".join(cols)
        con.execute(f"INSERT INTO video_records ({keys}) VALUES ({', '.join('?' for _ in cols)})",
                    list(cols.values()))
        status = "inserted"
    # keep the standalone FTS row in sync (delete + reinsert by video_key)
    con.execute("DELETE FROM video_records_fts WHERE video_key=?", (rec["video_key"],))
    con.execute("INSERT INTO video_records_fts (video_key, title, description, tags_json, transcript_text) "
                "VALUES (?,?,?,?,?)",
                (rec["video_key"], rec.get("title") or "", rec.get("description") or "",
                 " ".join(rec.get("tags") or []), rec.get("transcript_text") or ""))
    con.commit()
    return status


def _row_to_record(row):
    if row is None:
        return None
    out = dict(row)
    for base in _JSON_COLS:
        col = f"{base}_json" if base != "most_watched_segments" else "most_watched_json"
        if col in out:
            raw = out.pop(col)
            out[base] = json.loads(raw) if raw else ([] if base in ("tags", "chapters", "most_watched_segments") else ({} if base in ("stats", "provenance") else None))
    return out


def get_record(con, video_key):
    return _row_to_record(con.execute("SELECT * FROM video_records WHERE video_key=?", (video_key,)).fetchone())


def query_fts(con, q, limit=20):
    try:
        rows = con.execute(
            "SELECT video_key FROM video_records_fts WHERE video_records_fts MATCH ? LIMIT ?",
            (q, limit)).fetchall()
    except sqlite3.OperationalError as exc:
        return {"error": f"fts query error: {exc}"}
    return [get_record(con, r["video_key"]) for r in rows]


# ── analytics over the store (read-only; cites video_keys; null-and-flags) ────
# Every number is traceable to the video_keys it came from, and any field a platform does not
# provide (retention off YouTube, an absent transcript) is flagged, never estimated.

import re  # noqa: E402

_STOPWORDS = {
    "the", "and", "that", "this", "with", "your", "you", "have", "just", "like", "what", "when",
    "then", "here", "there", "they", "them", "from", "into", "onto", "over", "very", "really",
    "going", "gonna", "want", "will", "would", "could", "should", "about", "some", "these", "those",
    "were", "been", "because", "which", "while", "their", "also", "gonna", "okay", "yeah", "know",
}


def _stat_value(stats, metric):
    """Unwrap a freshness-envelope stat (or a raw value) to its number, else None."""
    v = (stats or {}).get(metric)
    if isinstance(v, dict):
        return v.get("value")
    return v


def top_tags(con, platform=None, limit=20):
    """Tag frequency across the library, weighted by total views, each tag citing its video_keys."""
    where = "WHERE platform=?" if platform else ""
    params = [platform] if platform else []
    rows = con.execute(f"SELECT video_key, tags_json, stats_json FROM video_records {where}", params).fetchall()
    agg = {}
    for r in rows:
        tags = json.loads(r["tags_json"] or "[]")
        views = _stat_value(json.loads(r["stats_json"] or "{}"), "views") or 0
        for t in tags:
            key = str(t).strip().lower()
            if not key:
                continue
            a = agg.setdefault(key, {"count": 0, "total_views": 0, "video_keys": []})
            a["count"] += 1
            a["total_views"] += views
            a["video_keys"].append(r["video_key"])
    out = [{"tag": k, **v} for k, v in agg.items()]
    out.sort(key=lambda x: (-x["count"], -x["total_views"]))
    return out[:limit]


def retention_insights(con, limit=50):
    """YouTube most-watched peaks + steepest-drop cliffs, carrying the transcript words at each moment
    when the join has been run. Non-YouTube (or retention-less) records are null-flagged, not estimated."""
    rows = con.execute("SELECT video_key, platform, most_watched_json, retention_json, transcript_text "
                       "FROM video_records").fetchall()
    insights, null_flagged = [], []
    for r in rows:
        if r["platform"] != "youtube" or not r["retention_json"]:
            null_flagged.append(r["video_key"])
            continue
        mw = json.loads(r["most_watched_json"] or "[]")
        peaks = [s for s in mw if s.get("label") == "peak"]
        cliffs = [s for s in mw if s.get("label") == "cliff"]
        insights.append({"video_key": r["video_key"], "peaks": peaks, "cliffs": cliffs,
                         "words_joined": bool(r["transcript_text"])})
    return {"insights": insights[:limit], "retention_unavailable": null_flagged,
            "note": "Retention is a YouTube-only first-party signal; other platforms are null-flagged, "
                    "not estimated. Peak/cliff words appear once library-complete has joined a transcript."}


def _duration_bucket(seconds):
    if seconds is None:
        return "unknown"
    s = float(seconds)
    if s <= 60:
        return "short (<=60s)"
    if s <= 600:
        return "mid (1 to 10 min)"
    return "long (>10 min)"


def format_performance(con, platform=None):
    """Average views by duration bucket and by category, each cell citing its video_keys."""
    where = "WHERE platform=?" if platform else ""
    params = [platform] if platform else []
    rows = con.execute(f"SELECT video_key, category, duration_s, stats_json FROM video_records {where}",
                       params).fetchall()
    by_bucket, by_category = {}, {}
    for r in rows:
        views = _stat_value(json.loads(r["stats_json"] or "{}"), "views")
        bucket = _duration_bucket(r["duration_s"])
        b = by_bucket.setdefault(bucket, {"count": 0, "views_sum": 0, "views_n": 0, "video_keys": []})
        b["count"] += 1
        b["video_keys"].append(r["video_key"])
        if views is not None:
            b["views_sum"] += views
            b["views_n"] += 1
        cat = r["category"] or "uncategorized"
        c = by_category.setdefault(cat, {"count": 0, "views_sum": 0, "views_n": 0, "video_keys": []})
        c["count"] += 1
        c["video_keys"].append(r["video_key"])
        if views is not None:
            c["views_sum"] += views
            c["views_n"] += 1

    def _finish(d):
        out = []
        for k, v in d.items():
            avg = round(v["views_sum"] / v["views_n"], 1) if v["views_n"] else None
            out.append({"group": k, "video_count": v["count"], "avg_views": avg,
                        "views_known_for": v["views_n"], "video_keys": v["video_keys"]})
        out.sort(key=lambda x: (x["avg_views"] is None, -(x["avg_views"] or 0)))
        return out
    return {"by_duration": _finish(by_bucket), "by_category": _finish(by_category)}


def transcript_themes(con, top_n=25, min_len=4, platform=None):
    """Recurring spoken terms across the library's transcripts, each term citing its video_keys.
    Empty (with a flag) when no transcripts are present; never invents themes from metadata."""
    where = "WHERE transcript_text IS NOT NULL AND transcript_text<>''"
    params = []
    if platform:
        where += " AND platform=?"
        params.append(platform)
    rows = con.execute(f"SELECT video_key, transcript_text FROM video_records {where}", params).fetchall()
    if not rows:
        return {"themes": [], "flag": "no_transcripts",
                "note": "No transcripts in the library yet; run library-complete to add them on-device."}
    freq = {}
    for r in rows:
        for w in re.findall(r"[a-z][a-z']{%d,}" % (min_len - 1), (r["transcript_text"] or "").lower()):
            if w in _STOPWORDS:
                continue
            f = freq.setdefault(w, {"count": 0, "video_keys": set()})
            f["count"] += 1
            f["video_keys"].add(r["video_key"])
    out = [{"term": k, "count": v["count"], "video_keys": sorted(v["video_keys"])} for k, v in freq.items()]
    out.sort(key=lambda x: (-x["count"], x["term"]))
    return {"themes": out[:top_n], "flag": None, "transcripts_analyzed": len(rows)}


def import_status(con):
    """A read-only completeness snapshot of the library: totals by platform and how many records
    still lack a transcript, retention, or revenue. Drives the wizard/MCP import-status view."""
    rows = con.execute("SELECT platform, transcript_text, retention_json, revenue_json FROM video_records").fetchall()
    by_platform, total = {}, 0
    with_transcript = with_retention = with_revenue = 0
    for r in rows:
        total += 1
        by_platform[r["platform"]] = by_platform.get(r["platform"], 0) + 1
        if r["transcript_text"]:
            with_transcript += 1
        if r["retention_json"]:
            with_retention += 1
        if r["revenue_json"]:
            with_revenue += 1
    return {
        "total_records": total,
        "by_platform": by_platform,
        "with_transcript": with_transcript,
        "missing_transcript": total - with_transcript,
        "with_retention": with_retention,
        "with_revenue": with_revenue,
        "note": "Retention is YouTube-only; revenue is Studio-CSV-only; missing transcripts complete "
                "on-device via library-complete (never fabricated).",
    }


def analyze(con, platform=None):
    """The full read-only analysis: top tags, retention insights, format performance, transcript
    themes. Every section cites video_keys and null-flags what a platform does not provide."""
    return {
        "top_tags": top_tags(con, platform=platform),
        "retention_insights": retention_insights(con),
        "format_performance": format_performance(con, platform=platform),
        "transcript_themes": transcript_themes(con, platform=platform),
        "boundaries": "Retention is YouTube-only; revenue is Studio-CSV-only; transcripts come from "
                      "on-device STT. Unavailable data is null-flagged, never estimated.",
    }


# ── selftest (temp DB; no real store touched) ────────────────────────────────

def selftest():
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # derive_most_watched: a clear peak at the front and a cliff mid-way
    retention = [{"elapsed_ratio": round(i / 100, 2),
                  "watch_ratio": (1.4 if i < 10 else (0.4 if i >= 50 else 0.9))} for i in range(0, 100, 2)]
    seg = derive_most_watched(retention)
    ok("most_watched finds a front peak", any(s["label"] == "peak" and s["start_ratio"] <= 0.02 for s in seg))
    ok("most_watched finds a cliff", any(s["label"] == "cliff" for s in seg))
    ok("most_watched empty on too-few points", derive_most_watched([{"elapsed_ratio": 0.1, "watch_ratio": 1.0}]) == [])
    ok("most_watched empty on None", derive_most_watched(None) == [])
    # P46 fix 7: a perfectly flat retention curve has no most-watched region (not a whole-video "peak").
    flat = [{"elapsed_ratio": round(i / 10, 2), "watch_ratio": 0.8} for i in range(10)]
    ok("most_watched empty on a flat curve", derive_most_watched(flat) == [])

    tmp = Path(tempfile.mkdtemp(prefix="video_library_selftest_"))
    try:
        con = _open_db(tmp / "index.local.db")
        yt = normalize_record({
            "platform_video_id": "vid123", "url": "https://youtu.be/vid123",
            "title": "Painting an armoire", "description": "diy makeover",
            "tags": ["armoire", "patina", "diy"], "category": "Howto & Style",
            "published_at": "2026-03-01", "duration_s": 600,
            "stats": {"views": 12000, "likes": 800, "comments": 60},
            "retention": retention,
        }, platform="youtube", source_mode="export_bundle", source_citation="studio_csv")
        ok("stats wrapped in envelope", yt["stats"]["views"]["value"] == 12000 and "as_of" in yt["stats"]["views"])
        ok("most_watched derived on normalize", len(yt["most_watched_segments"]) >= 1)
        ok("insert", _upsert(con, yt) == "inserted")
        yt2 = normalize_record({"platform_video_id": "vid123", "url": "https://youtu.be/vid123",
                                "title": "Painting an armoire", "stats": {"views": 15000}},
                               platform="youtube", source_mode="export_bundle")
        ok("re-import updates in place", _upsert(con, yt2) == "updated")
        got = get_record(con, "youtube:vid123")
        ok("get returns record", got and got["video_key"] == "youtube:vid123")
        ok("no duplicate row after re-import", con.execute("SELECT COUNT(*) c FROM video_records WHERE video_key=?", ("youtube:vid123",)).fetchone()["c"] == 1)
        ok("fts finds a tag", any(r["video_key"] == "youtube:vid123" for r in query_fts(con, "armoire")))

        # an Instagram record has null retention + null revenue (not available)
        ig = normalize_record({
            "platform_video_id": "reel_9", "title": "quick tour", "tags": ["diy", "armoire"],
            "stats": {"reach": 5000, "saved": 120, "views": 5000}, "retention": None,
        }, platform="instagram", source_mode="direct_connector")
        _upsert(con, ig)
        igr = get_record(con, "instagram:reel_9")
        ok("instagram retention is null (not available)", igr["retention"] is None)
        ok("instagram most_watched empty", igr["most_watched_segments"] == [])
        ok("revenue null unless supplied", igr["revenue"] is None)

        # analytics: top tags cite video_keys; retention insights are YouTube-only with IG null-flagged.
        _upsert(con, yt)  # restore the full YouTube record (the yt2 re-import test stripped its tags/retention/duration)
        tags = top_tags(con)
        armoire = next((t for t in tags if t["tag"] == "armoire"), None)
        ok("top_tags aggregates across records", armoire and armoire["count"] == 2)
        ok("top_tags cites video_keys", armoire and "youtube:vid123" in armoire["video_keys"])
        ri = retention_insights(con)
        ok("retention insight only for youtube record", any(i["video_key"] == "youtube:vid123" for i in ri["insights"]))
        ok("instagram retention null-flagged", "instagram:reel_9" in ri["retention_unavailable"])
        fp = format_performance(con)
        ok("format_performance buckets by duration with avg views",
           any(g["group"].startswith("mid") for g in fp["by_duration"]) and
           any(g["avg_views"] is not None for g in fp["by_duration"]))
        tt = transcript_themes(con)
        ok("transcript_themes flags empty library honestly", tt["flag"] == "no_transcripts" and tt["themes"] == [])
        # add a transcript and re-check themes cite the video_key
        con.execute("UPDATE video_records SET transcript_text=? WHERE video_key=?",
                    ("today we restore an antique armoire with patina hardware and wainscoting panels", "youtube:vid123"))
        con.commit()
        tt2 = transcript_themes(con, min_len=5)
        ok("transcript_themes surfaces a spoken term with its video_key",
           any(t["term"] == "armoire" and "youtube:vid123" in t["video_keys"] for t in tt2["themes"]))
        full = analyze(con)
        ok("analyze returns all four sections", set(["top_tags", "retention_insights", "format_performance", "transcript_themes"]) <= set(full))
        con.close()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # P46 fixes 5+6: the CLI returns a clean error + nonzero exit on bad input (no raw traceback),
    # and a malformed FTS query exits nonzero rather than exit 0 with an error payload. Run main()
    # against a temp store so the real gitignored store is never touched.
    import io as _io
    import contextlib as _cl
    global DB_PATH
    _saved_db = DB_PATH
    tmp2 = Path(tempfile.mkdtemp(prefix="video_library_cli_"))
    DB_PATH = tmp2 / "index.local.db"
    try:
        def _run_main(argv):
            buf = _io.StringIO()
            with _cl.redirect_stdout(buf):
                rc = main(argv)
            return rc, buf.getvalue()
        rc, out = _run_main(["upsert", "--record", "this is not json"])
        ok("cli: malformed json -> exit 1 + error dict", rc == 1 and '"error"' in out)
        rc, out = _run_main(["upsert", "--record", '{"platform":"vimeo","platform_video_id":"1"}'])
        ok("cli: unknown platform -> exit 1 + error dict", rc == 1 and "unknown platform" in out)
        rc, out = _run_main(["query", "armoire OR (unbalanced"])
        ok("cli: malformed FTS -> exit 1 (not 0)", rc == 1 and '"error"' in out)
        rc, out = _run_main(["upsert", "--record", '{"platform":"youtube","platform_video_id":"cliok"}'])
        ok("cli: valid upsert still exits 0", rc == 0 and "youtube:cliok" in out)
    finally:
        DB_PATH = _saved_db
        import shutil as _sh
        _sh.rmtree(tmp2, ignore_errors=True)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


# ── CLI ───────────────────────────────────────────────────────────────────────

def _load_arg_json(val):
    if val == "-":
        return json.loads(sys.stdin.read())
    return json.loads(val)


def _fail(msg, next_step=None):
    """Emit a one-line JSON error (never a raw traceback) and signal a nonzero exit. Non-technical
    users and agent tool wrappers get an actionable message instead of a Python stack dump."""
    out = {"error": str(msg)}
    if next_step:
        out["next_step"] = next_step
    print(json.dumps(out, ensure_ascii=False))
    return 1


def main(argv):
    ap = argparse.ArgumentParser(description="The creator's own past-video library (local, gitignored).")
    sub = ap.add_argument_group("command")
    ap.add_argument("command", nargs="?",
                    choices=["init", "upsert", "upsert-batch", "get", "list", "query",
                             "derive-most-watched", "analyze", "status"])
    ap.add_argument("arg", nargs="?", help="video_key / fts query / batch file, per command")
    ap.add_argument("--record", help="(upsert) a normalized record as JSON, or - for stdin")
    ap.add_argument("--platform", choices=PLATFORMS)
    ap.add_argument("--source-mode", dest="source_mode")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.command:
        ap.print_help()
        return 2

    con = _open_db()
    if args.command == "init":
        print(json.dumps({"initialized": str(DB_PATH)}))
    elif args.command == "upsert":
        try:
            parsed = _load_arg_json(args.record if args.record is not None else (args.arg or "-"))
            rec = normalize_record(parsed, platform=args.platform, source_mode=args.source_mode)
        except json.JSONDecodeError as exc:
            con.close()
            return _fail(f"the record is not valid JSON: {exc}", "pass a JSON object via --record or on stdin")
        except ValueError as exc:
            con.close()
            return _fail(exc, "a record needs a known platform and a non-empty platform_video_id")
        print(json.dumps({"video_key": rec["video_key"], "status": _upsert(con, rec)}))
    elif args.command == "upsert-batch":
        try:
            arr = json.loads(Path(args.arg).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            con.close()
            return _fail(f"could not read the batch file as JSON: {exc}", "point at a JSON array of records")
        res = []
        for parsed in arr:
            try:
                rec = normalize_record(parsed, platform=args.platform or parsed.get("platform"),
                                       source_mode=args.source_mode or parsed.get("source_mode"))
            except (ValueError, AttributeError) as exc:
                res.append({"error": str(exc), "record": parsed})
                continue
            res.append({"video_key": rec["video_key"], "status": _upsert(con, rec)})
        print(json.dumps({"upserted": sum(1 for r in res if "status" in r), "results": res}, ensure_ascii=False))
    elif args.command == "get":
        print(json.dumps(get_record(con, args.arg), indent=2, ensure_ascii=False))
    elif args.command == "list":
        where = "WHERE platform=?" if args.platform else ""
        params = ([args.platform] if args.platform else []) + [args.limit]
        rows = con.execute(f"SELECT video_key, platform, title, published_at FROM video_records {where} "
                           f"ORDER BY published_at DESC LIMIT ?", params).fetchall()
        print(json.dumps([dict(r) for r in rows], indent=2, ensure_ascii=False))
    elif args.command == "query":
        result = query_fts(con, args.arg or "", limit=args.limit)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if isinstance(result, dict) and result.get("error"):
            con.close()
            return 1  # a malformed FTS query is a failure, not a success with an error payload
    elif args.command == "derive-most-watched":
        rec = get_record(con, args.arg)
        if not rec:
            print(json.dumps({"error": f"no record {args.arg}"}))
            return 1
        seg = derive_most_watched(rec.get("retention"))
        con.execute("UPDATE video_records SET most_watched_json=?, updated_at=? WHERE video_key=?",
                    (json.dumps(seg, ensure_ascii=False), date.today().isoformat(), args.arg))
        con.commit()
        print(json.dumps({"video_key": args.arg, "most_watched_segments": seg}, indent=2, ensure_ascii=False))
    elif args.command == "analyze":
        print(json.dumps(analyze(con, platform=args.platform), indent=2, ensure_ascii=False))
    elif args.command == "status":
        print(json.dumps(import_status(con), indent=2, ensure_ascii=False))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
