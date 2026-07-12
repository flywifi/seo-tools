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
    sd = statistics.pstdev(ratios) or 0.0
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
            "platform_video_id": "reel_9", "title": "quick tour", "tags": [],
            "stats": {"reach": 5000, "saved": 120}, "retention": None,
        }, platform="instagram", source_mode="direct_connector")
        _upsert(con, ig)
        igr = get_record(con, "instagram:reel_9")
        ok("instagram retention is null (not available)", igr["retention"] is None)
        ok("instagram most_watched empty", igr["most_watched_segments"] == [])
        ok("revenue null unless supplied", igr["revenue"] is None)
        con.close()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

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


def main(argv):
    ap = argparse.ArgumentParser(description="The creator's own past-video library (local, gitignored).")
    sub = ap.add_argument_group("command")
    ap.add_argument("command", nargs="?",
                    choices=["init", "upsert", "upsert-batch", "get", "list", "query", "derive-most-watched"])
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
        parsed = _load_arg_json(args.record if args.record is not None else (args.arg or "-"))
        rec = normalize_record(parsed, platform=args.platform, source_mode=args.source_mode)
        print(json.dumps({"video_key": rec["video_key"], "status": _upsert(con, rec)}))
    elif args.command == "upsert-batch":
        arr = json.loads(Path(args.arg).read_text(encoding="utf-8"))
        res = []
        for parsed in arr:
            rec = normalize_record(parsed, platform=args.platform or parsed.get("platform"),
                                   source_mode=args.source_mode or parsed.get("source_mode"))
            res.append({"video_key": rec["video_key"], "status": _upsert(con, rec)})
        print(json.dumps({"upserted": len(res), "results": res}, ensure_ascii=False))
    elif args.command == "get":
        print(json.dumps(get_record(con, args.arg), indent=2, ensure_ascii=False))
    elif args.command == "list":
        where = "WHERE platform=?" if args.platform else ""
        params = ([args.platform] if args.platform else []) + [args.limit]
        rows = con.execute(f"SELECT video_key, platform, title, published_at FROM video_records {where} "
                           f"ORDER BY published_at DESC LIMIT ?", params).fetchall()
        print(json.dumps([dict(r) for r in rows], indent=2, ensure_ascii=False))
    elif args.command == "query":
        print(json.dumps(query_fts(con, args.arg or "", limit=args.limit), indent=2, ensure_ascii=False))
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
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
