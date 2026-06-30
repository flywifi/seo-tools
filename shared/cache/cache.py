#!/usr/bin/env python3
"""Creator OS scoop cache, L1: offline, deterministic, low-token retrieval.

A local SQLite FTS5 index over the canonical-sources/ JSON records. It returns ranked snippets plus
provenance (source file + record id) instead of loading the full reference data into context. The
index (index.local.db) is gitignored and regenerable. If the host SQLite lacks FTS5, a LIKE fallback
is built and reported honestly; it never pretends ranked full-text search ran.

Usage:
  python3 shared/cache/cache.py --build
  python3 shared/cache/cache.py --stats
  python3 shared/cache/cache.py --query "moody fall" --limit 5
  python3 shared/cache/cache.py --query "renter" --json
  python3 shared/cache/cache.py --verify
"""
import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCES = ROOT / "canonical-sources"
DB = HERE / "index.local.db"
BASELINE = HERE / "cache-baseline.local.json"


def iter_records():
    for jf in sorted(SOURCES.rglob("*.json")):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for rec in data:
                if isinstance(rec, dict) and rec.get("text"):
                    yield (
                        str(jf.relative_to(ROOT)),
                        str(rec.get("id", "")),
                        str(rec.get("title", "")),
                        str(rec["text"]),
                    )


def has_fts5(conn):
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.fts_probe USING fts5(x)")
        conn.execute("DROP TABLE temp.fts_probe")
        return True
    except sqlite3.OperationalError:
        return False


def build():
    if DB.exists():
        DB.unlink()
    conn = sqlite3.connect(DB)
    fts = has_fts5(conn)
    if fts:
        conn.execute("CREATE VIRTUAL TABLE records USING fts5(source, id, title, text)")
    else:
        conn.execute("CREATE TABLE records(source TEXT, id TEXT, title TEXT, text TEXT)")
    count = 0
    for source, rid, title, text in iter_records():
        conn.execute(
            "INSERT INTO records(source, id, title, text) VALUES(?,?,?,?)",
            (source, rid, title, text),
        )
        count += 1
    conn.execute("CREATE TABLE meta(k TEXT, v TEXT)")
    conn.execute("INSERT INTO meta VALUES('fts5', ?)", ("1" if fts else "0",))
    conn.execute("INSERT INTO meta VALUES('count', ?)", (str(count),))
    conn.commit()
    conn.close()
    write_baseline()
    mode = "fts5" if fts else "LIKE fallback (host SQLite lacks FTS5)"
    print(f"built index: {count} records, mode={mode}")
    return 0


def _match_query(q):
    tokens = re.findall(r"[A-Za-z0-9]+", q)
    return " ".join(tokens)


def query(q, limit, as_json):
    if not DB.exists():
        build()
    conn = sqlite3.connect(DB)
    fts = conn.execute("SELECT v FROM meta WHERE k='fts5'").fetchone()[0] == "1"
    results = []
    if fts:
        match = _match_query(q)
        if match:
            rows = conn.execute(
                "SELECT source, id, title, snippet(records, 3, '[', ']', '...', 10), bm25(records) "
                "FROM records WHERE records MATCH ? ORDER BY bm25(records) LIMIT ?",
                (match, limit),
            ).fetchall()
            results = [
                {"source": s, "id": i, "title": t, "snippet": sn, "rank": round(r, 3)}
                for s, i, t, sn, r in rows
            ]
    else:
        like = f"%{q}%"
        rows = conn.execute(
            "SELECT source, id, title, substr(text, 1, 160) FROM records "
            "WHERE text LIKE ? OR title LIKE ? LIMIT ?",
            (like, like, limit),
        ).fetchall()
        results = [
            {"source": s, "id": i, "title": t, "snippet": sn, "rank": None}
            for s, i, t, sn in rows
        ]
    conn.close()
    if as_json:
        print(json.dumps({"query": q, "fts5": fts, "results": results}, indent=2))
    elif not results:
        print("no matches")
    else:
        for r in results:
            print(f"[{r['source']} #{r['id']}] {r['title']}")
            print(f"    {r['snippet']}")
    return results


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_state():
    return {
        str(p.relative_to(ROOT)): {"sha256": sha256_of(p), "bytes": p.stat().st_size}
        for p in sorted(SOURCES.rglob("*.json"))
    }


def write_baseline():
    BASELINE.write_text(json.dumps(current_state(), indent=2), encoding="utf-8")


def verify():
    if not BASELINE.exists():
        print("no baseline; run --build first")
        return 1
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    cur = current_state()
    drift = []
    for key, val in cur.items():
        if key not in base:
            drift.append(f"new source {key}")
        elif base[key]["sha256"] != val["sha256"]:
            drift.append(f"changed {key}")
    for key in base:
        if key not in cur:
            drift.append(f"removed {key}")
    if drift:
        print("cache drift vs build baseline:")
        for item in drift:
            print(f"  - {item}")
        return 1
    print("cache is fresh (sources match the build baseline)")
    return 0


def stats():
    if not DB.exists():
        print("no index; run --build first")
        return 1
    conn = sqlite3.connect(DB)
    count = conn.execute("SELECT v FROM meta WHERE k='count'").fetchone()[0]
    fts = conn.execute("SELECT v FROM meta WHERE k='fts5'").fetchone()[0] == "1"
    conn.close()
    print(f"index: {count} records, fts5={'yes' if fts else 'no (LIKE fallback)'}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS scoop cache L1")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--query")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.build:
        return build()
    if args.stats:
        return stats()
    if args.verify:
        return verify()
    if args.query:
        query(args.query, args.limit, args.json)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
