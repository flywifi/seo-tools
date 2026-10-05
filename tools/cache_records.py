#!/usr/bin/env python3
"""Connector-contract search and fetch over the scoop cache index (shared/cache/index.local.db).

Stdlib only, so tools/mcp_server.py's search and fetch tools and their selftests run without the
mcp package (the P61 package-independent pattern). A record's `source` is its file's path relative
to the repository root with forward slashes. An index built on Windows before the cache wrote its
keys with as_posix() holds backslashes, so every source read here passes through posix_source;
search and fetch answer with the same ids and urls on any system, and a rebuild is not needed.

Usage:
  python3 tools/cache_records.py --selftest
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

REPO_BLOB = "https://github.com/flywifi/seo-tools/blob/main/"


def posix_source(source) -> str:
    """The record source with forward slashes."""
    return str(source).replace("\\", "/")


def record_url(source: str) -> str:
    """Provenance URL for a knowledge record (connector citations require a non-empty url;
    developers.openai.com/api/docs/mcp). The cache stores `source` REPO-RELATIVE (it already
    starts with canonical-sources/; shared/cache/cache.py::iter_records), so no prefix is added
    here -- a doubled segment returned 404, which this comment now guards against."""
    return REPO_BLOB + posix_source(source)


def search(query: str, db) -> dict:
    """Connector-contract search: {"results": [{"id", "title", "url"}]}, at most 8, never a .local.
    source. An FTS5 syntax error on hostile input falls back to LIKE."""
    db = Path(db)
    if not db.exists():
        return {"results": [], "note": "cache not built; run: python3 shared/cache/cache.py --build"}
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        fts = conn.execute("SELECT v FROM meta WHERE k='fts5'").fetchone()[0] == "1"
        rows = []
        if fts:
            try:
                rows = conn.execute(
                    "SELECT source, id, title FROM records WHERE records MATCH ? "
                    "AND source NOT LIKE '%.local.%' ORDER BY bm25(records) LIMIT 8",
                    (query,)).fetchall()
            except Exception:  # noqa: BLE001 -- FTS5 syntax errors on hostile input -> LIKE
                rows = []
        if not rows:
            like = f"%{query}%"
            rows = conn.execute(
                "SELECT source, id, title FROM records WHERE (text LIKE ? OR title LIKE ?) "
                "AND source NOT LIKE '%.local.%' LIMIT 8", (like, like)).fetchall()
    finally:
        conn.close()
    return {"results": [{"id": f"{posix_source(s)}::{i}", "title": ti or i, "url": record_url(s)}
                        for s, i, ti in rows if ".local." not in s]}


def fetch(record_id: str, db) -> dict:
    """Connector-contract fetch by "source::record" id. A source is matched with its separators
    made forward slashes on both sides. Refuses .local. sources so a hosted endpoint can never
    serve records that are not committed content."""
    source, _, rec = record_id.partition("::")
    source = posix_source(source)
    db = Path(db)
    if ".local." in source or not db.exists():
        return {"error": "unknown id"}
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT source, id, title, text FROM records "
            "WHERE replace(source, char(92), '/') = ? AND id = ?", (source, rec)).fetchone()
    finally:
        conn.close()
    if not row:
        return {"error": "unknown id"}
    s, i, ttl, text = row
    s = posix_source(s)
    return {"id": f"{s}::{i}", "title": ttl or i, "text": text,
            "url": record_url(s), "metadata": {"source_file": s}}


def selftest() -> int:
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    with tempfile.TemporaryDirectory() as td:
        for fts in (False, True):
            db = Path(td) / f"idx{int(fts)}.db"
            conn = sqlite3.connect(db)
            if fts:
                conn.execute("CREATE VIRTUAL TABLE records USING fts5(source, id, title, text)")
            else:
                conn.execute("CREATE TABLE records(source TEXT, id TEXT, title TEXT, text TEXT)")
            conn.execute("CREATE TABLE meta(k TEXT, v TEXT)")
            conn.execute("INSERT INTO meta VALUES('fts5', ?)", ("1" if fts else "0",))
            conn.executemany("INSERT INTO records VALUES(?,?,?,?)", [
                ("canonical-sources\\construction\\stairs.json", "st1", "Stair rise",
                 "stair riser height limit"),
                ("canonical-sources/keyword-library.json", "kw1", "", "fall decor keyword list"),
                ("canonical-sources\\seed.local.json", "sec", "Never served", "stair secret"),
            ])
            conn.commit()
            conn.close()
            mode = "fts5" if fts else "LIKE"
            st = search("stair", db)["results"]
            ok(f"{mode}: a backslash source is answered with slashes in the id and the url",
               [r["id"] for r in st] == ["canonical-sources/construction/stairs.json::st1"]
               and st[0]["url"] == REPO_BLOB + "canonical-sources/construction/stairs.json")
            ok(f"{mode}: a .local. source is never served", all(".local." not in r["id"] for r in st))
            kw = search("keyword", db)["results"]
            ok(f"{mode}: a record without a title is titled by its id",
               [(r["id"], r["title"]) for r in kw] == [("canonical-sources/keyword-library.json::kw1", "kw1")])
            fr = fetch("canonical-sources/construction/stairs.json::st1", db)
            ok(f"{mode}: fetch by the slash id finds a record stored with backslashes",
               fr.get("text") == "stair riser height limit"
               and fr["id"] == "canonical-sources/construction/stairs.json::st1"
               and fr["metadata"] == {"source_file": "canonical-sources/construction/stairs.json"}
               and fr["url"] == st[0]["url"] and set(fr) == {"id", "title", "text", "url", "metadata"})
            ok(f"{mode}: fetch by a backslash id finds the same record",
               fetch("canonical-sources\\construction\\stairs.json::st1", db) == fr)
            ok(f"{mode}: fetch refuses a .local. source in either separator form",
               fetch("canonical-sources/seed.local.json::sec", db) == {"error": "unknown id"}
               and fetch("canonical-sources\\seed.local.json::sec", db) == {"error": "unknown id"})
            ok(f"{mode}: fetch of an unknown record is an error",
               fetch("canonical-sources/construction/stairs.json::nope", db) == {"error": "unknown id"})
        ok("hostile FTS input falls back to LIKE without raising",
           isinstance(search('a AND ("', Path(td) / "idx1.db").get("results"), list))
        absent = Path(td) / "absent.db"
        ok("a missing index answers no results with a note, and fetch an error",
           search("x", absent)["results"] == [] and "note" in search("x", absent)
           and fetch("canonical-sources/a.json::x", absent) == {"error": "unknown id"})
        ok("record_url adds no second canonical-sources segment",
           record_url("canonical-sources/keyword-library.json")
           == REPO_BLOB + "canonical-sources/keyword-library.json")
    failed = [n for n, c in checks if not c]
    for n, c in checks:
        print(("ok   " if c else "FAIL ") + n)
    print(f"cache_records selftest: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print(__doc__)
    sys.exit(2)
