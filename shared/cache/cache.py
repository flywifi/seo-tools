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
  python3 shared/cache/cache.py --selftest

A record's source, and a baseline key, is the file's path relative to the repository root with
forward slashes on every system. An index or baseline built on Windows before keys were written
with as_posix() holds backslashes; query() and verify() read those as forward slashes, so neither
needs a rebuild.
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


def _posix_key(key):
    """A source path or baseline key with forward slashes (an older Windows build wrote backslashes)."""
    return str(key).replace("\\", "/")


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
                        jf.relative_to(ROOT).as_posix(),
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
                {"source": _posix_key(s), "id": i, "title": t, "snippet": sn, "rank": round(r, 3)}
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
            {"source": _posix_key(s), "id": i, "title": t, "snippet": sn, "rank": None}
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
        p.relative_to(ROOT).as_posix(): {"sha256": sha256_of(p), "bytes": p.stat().st_size}
        for p in sorted(SOURCES.rglob("*.json"))
    }


def write_baseline():
    BASELINE.write_text(json.dumps(current_state(), indent=2), encoding="utf-8")


def verify():
    if not BASELINE.exists():
        print("no baseline; run --build first")
        return 1
    base = {_posix_key(k): v for k, v in json.loads(BASELINE.read_text(encoding="utf-8")).items()}
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


def selftest():
    """Build, query and verify a temp tree with ROOT, SOURCES, DB and BASELINE pointed at it, never
    the real index, with Windows relative paths stood in by file_hash.windows_paths(); then the same
    reads against an index and baseline holding backslash keys, as an older Windows build wrote."""
    import contextlib
    import io
    import shutil
    import tempfile
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
    import file_hash
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    def state(p):
        try:
            st = Path(p).stat()
            return (st.st_size, st.st_mtime_ns)
        except OSError:
            return None

    g = globals()
    saved = {k: g[k] for k in ("ROOT", "SOURCES", "DB", "BASELINE", "has_fts5")}
    real_before = (state(saved["DB"]), state(saved["BASELINE"]))
    want = ["canonical-sources/construction/stairs.json", "canonical-sources/keywords.json"]
    made = []
    try:
        for fts in (True, False):
            mode = "fts5" if fts else "LIKE"
            td = Path(tempfile.mkdtemp(prefix="cache-selftest-"))
            made.append(td)
            g.update(ROOT=td, SOURCES=td / "canonical-sources", DB=td / "idx.db",
                     BASELINE=td / "baseline.json")
            if not fts:
                g["has_fts5"] = lambda conn: False
            (SOURCES / "construction").mkdir(parents=True)
            (SOURCES / "construction" / "stairs.json").write_text(json.dumps(
                [{"id": "st1", "title": "Stair rise", "text": "stair riser height limit"}]),
                encoding="utf-8")
            (SOURCES / "keywords.json").write_text(json.dumps(
                [{"id": "kw1", "title": "Fall decor", "text": "fall entryway decor"}]), encoding="utf-8")
            out = io.StringIO()
            with file_hash.windows_paths(), contextlib.redirect_stdout(out):
                build()
                conn = sqlite3.connect(DB)
                stored = sorted(r[0] for r in conn.execute("SELECT source FROM records"))
                conn.close()
                keys = sorted(current_state())
                fresh = verify()
            ok(f"{mode}: a build with Windows paths stores sources with forward slashes", stored == want)
            ok(f"{mode}: the baseline it writes has forward-slash keys",
               keys == want and sorted(json.loads(BASELINE.read_text(encoding="utf-8"))) == want)
            ok(f"{mode}: verify passes on the baseline the build wrote", fresh == 0)
            conn = sqlite3.connect(DB)
            conn.execute("UPDATE records SET source = replace(source, '/', char(92))")
            conn.commit()
            conn.close()
            base = json.loads(BASELINE.read_text(encoding="utf-8"))
            BASELINE.write_text(json.dumps({k.replace("/", "\\"): v for k, v in base.items()}),
                                encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                got = query("stair", 5, True)
                old_fresh = verify()
            printed = json.loads(out.getvalue()[:out.getvalue().rindex("}") + 1])
            ok(f"{mode}: query answers an index built with backslash sources with forward slashes",
               [r["source"] for r in got] == [want[0]]
               and [r["source"] for r in printed["results"]] == [want[0]])
            ok(f"{mode}: verify reads a baseline with backslash keys as fresh", old_fresh == 0)
            (SOURCES / "keywords.json").write_text(json.dumps(
                [{"id": "kw1", "title": "Fall decor", "text": "changed"}]), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                drifted = verify()
            ok(f"{mode}: verify still reports a changed source under its forward-slash key",
               drifted == 1 and "changed canonical-sources/keywords.json" in out.getvalue())
            (SOURCES / "construction" / "stairs.json").unlink()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                gone = verify()
            ok(f"{mode}: verify reports a removed source under its forward-slash key",
               gone == 1 and "removed canonical-sources/construction/stairs.json" in out.getvalue())
            g["has_fts5"] = saved["has_fts5"]
    finally:
        g.update(saved)
        for d in made:
            shutil.rmtree(d, ignore_errors=True)
    ok("the selftest left the real index and baseline as they were",
       (state(DB), state(BASELINE)) == real_before)
    failed = [n for n, c in checks if not c]
    for n, c in checks:
        print(("ok   " if c else "FAIL ") + n)
    print(f"cache selftest: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS scoop cache L1")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--query")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
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
