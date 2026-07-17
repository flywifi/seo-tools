#!/usr/bin/env python3
"""Offline keyword report over the committed keyword library + the scoop cache (P61, KW-FULL).

The keyword_offline compute job type was allowlisted in P60 but refused, because no offline
keyword capability existed: 7 of the 8 canonical-sources/keyword-library files are dict-shaped
and invisible to the scoop cache indexer (which only accepts list-of-dicts-with-text JSON). This
tool is the real implementation the user chose over a thin cache wrapper: ONE structured,
deterministic, zero-network report built from

  - a recursive flattener over every keyword-library file (list-of-strings leaves become keyword
    groups; dicts inside lists, and all-string dicts, become matchable records), and
  - the scoop cache index, reused by shelling shared/cache/cache.py --query --json (the guarded
    subprocess idiom of the MCP cache_query tool; the index auto-builds on first use).

HONESTY (protocols/no-fabrication.md): everything here is library-derived. The report carries a
structural envelope -- data_basis names the local sources, search_volumes is ALWAYS null (live
volumes are network-only by the seo-keywords spoke's own design and are never estimated), and
sources lists each file's source_ids + last_updated so provenance is inspectable.

Usage:
  python3 tools/keyword_offline.py report --query "dresser makeover" [--limit N] [--json]
  python3 tools/keyword_offline.py --selftest
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY_DIR = ROOT / "canonical-sources" / "keyword-library"

DATA_BASIS = "local keyword library + cached index; no live search data"
MAX_QUERY_CHARS = 500

# Every library file maps to exactly one report section. All 8 files flatten; a file whose
# shapes yield nothing for a query simply contributes an empty section share.
SECTION_BY_FILE = {
    "entity-keywords.json": "entities",
    "long-tail-seeds.json": "long_tail_seeds",
    "youtube-algorithm-signals.json": "algorithm_notes",
    "instagram-reels-signals.json": "algorithm_notes",
    "tiktok-api-registry.json": "algorithm_notes",
    "github-seo-methodology.json": "methodology",
    "moody-vintage.json": "aesthetic",
    "competitor-channels.json": "competitors",
}
SECTIONS = ("entities", "long_tail_seeds", "algorithm_notes", "methodology",
            "aesthetic", "competitors")


# ---------------------------------------------------------------------------
# Flattening (shape-tolerant: non-conforming leaves are skipped, never guessed at)
# ---------------------------------------------------------------------------

def iter_leaves(obj, path=""):
    """Yield ("strings", dotted_path, [str]) for list-of-strings leaves and
    ("record", dotted_path, dict) for dicts inside lists or all-string dicts.

    Keys starting with "_" (comments, notes, currency markers) are skipped. Anything that does
    not match a known shape is recursed into or ignored -- the flattener never raises on a
    library file's shape changing.
    """
    if isinstance(obj, dict):
        visible = {k: v for k, v in obj.items() if not str(k).startswith("_")}
        str_vals = [v for v in visible.values() if isinstance(v, str)]
        if len(visible) >= 2 and len(str_vals) == len(visible):
            yield ("record", path, visible)
            return
        for k, v in visible.items():
            sub = f"{path}.{k}" if path else str(k)
            yield from iter_leaves(v, sub)
    elif isinstance(obj, list):
        if obj and all(isinstance(x, str) for x in obj):
            yield ("strings", path, obj)
        else:
            for i, item in enumerate(obj):
                if isinstance(item, dict):
                    yield ("record", f"{path}[{i}]", item)
                elif isinstance(item, (dict, list)):
                    yield from iter_leaves(item, f"{path}[{i}]")


def _tokens(query):
    return [t.lower() for t in re.findall(r"[A-Za-z0-9]+", query or "")]


def _record_text(rec):
    parts = []
    for k, v in rec.items():
        if str(k).startswith("_"):
            continue
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list) and all(isinstance(x, str) for x in v):
            parts.extend(v)
    return " ".join(parts)


def _compact_record(rec, max_val=200):
    out = {}
    for k, v in rec.items():
        if str(k).startswith("_") or len(out) >= 6:
            continue
        if isinstance(v, str):
            out[k] = v[:max_val]
        elif isinstance(v, list) and all(isinstance(x, str) for x in v):
            out[k] = [x[:max_val] for x in v[:8]]
    return out


def _match_count(tokens, text):
    low = text.lower()
    return sum(1 for t in tokens if t in low)


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

def _load_library():
    """Return {filename: parsed_json} for every committed library file; unreadable files are
    reported as an error entry, never silently dropped."""
    out = {}
    for name in sorted(SECTION_BY_FILE):
        p = LIBRARY_DIR / name
        try:
            out[name] = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            out[name] = {"_load_error": str(e)}
    return out


def _sources_envelope(library):
    src = []
    for name, data in library.items():
        entry = {"file": f"canonical-sources/keyword-library/{name}",
                 "last_updated": None, "source_ids": []}
        if isinstance(data, dict):
            entry["last_updated"] = data.get("last_updated")
            ids = data.get("source_ids")
            if isinstance(ids, list):
                entry["source_ids"] = [i for i in ids if isinstance(i, str)]
            if "_load_error" in data:
                entry["load_error"] = data["_load_error"]
        src.append(entry)
    return src


def _run_cache(query, limit):
    """Shell the scoop cache (the MCP cache_query idiom); the index auto-builds on first use.
    Any failure degrades to an honest error note, never a crash and never fabricated hits."""
    argv = [sys.executable, str(ROOT / "shared" / "cache" / "cache.py"),
            "--query", query, "--limit", str(limit), "--json"]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": f"cache query unavailable: {e}"}
    if proc.returncode != 0:
        return {"error": (proc.stderr.strip() or "cache query failed")[:300]}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "cache query returned unparseable output"}
    return {"results": data.get("results", []), "fts5": data.get("fts5")}


def report(query, limit=25, cache_runner=None):
    """The one deterministic offline keyword report. Returns an error dict on bad input
    (P46 contract: clean error payloads, never a traceback)."""
    if not isinstance(query, str) or not query.strip():
        return {"error": "query must be a non-empty string"}
    if len(query) > MAX_QUERY_CHARS:
        return {"error": f"query too long (max {MAX_QUERY_CHARS} chars)"}
    limit = max(1, min(int(limit), 100))
    tokens = _tokens(query)
    library = _load_library()

    sections = {s: [] for s in SECTIONS}
    for name, data in library.items():
        section = SECTION_BY_FILE[name]
        for kind, path, leaf in iter_leaves(data):
            if kind == "strings":
                matched = [s for s in leaf if _match_count(tokens, s)]
                if matched:
                    count = sum(_match_count(tokens, s) for s in matched)
                    sections[section].append({
                        "file": name, "path": path,
                        "matches": matched[:limit], "match_count": count,
                    })
            else:
                count = _match_count(tokens, _record_text(leaf))
                if count:
                    sections[section].append({
                        "file": name, "path": path,
                        "record": _compact_record(leaf), "match_count": count,
                    })
    for s in sections:
        sections[s] = sorted(sections[s],
                             key=lambda e: (-e["match_count"], e["file"], e["path"]))[:limit]

    runner = cache_runner or _run_cache
    try:
        cache_hits = runner(query, limit)
    except Exception as e:  # an injected/broken runner must not take down the library report
        cache_hits = {"error": f"cache query unavailable: {e}"}

    return {
        "query": query,
        "sections": sections,
        "cache_hits": cache_hits,
        "data_basis": DATA_BASIS,
        "search_volumes": None,
        "sources": _sources_envelope(library),
    }


# ---------------------------------------------------------------------------
# CLI + selftest
# ---------------------------------------------------------------------------

def _print_human(rep):
    print(f"Offline keyword report for: {rep['query']}")
    print(f"({rep['data_basis']}; search volumes: not available offline)")
    for s in SECTIONS:
        entries = rep["sections"][s]
        if not entries:
            continue
        print(f"\n## {s} ({len(entries)})")
        for e in entries[:10]:
            if "matches" in e:
                print(f"  {e['path']}: {', '.join(e['matches'][:6])}")
            else:
                rec = e["record"]
                label = rec.get("title") or rec.get("signal") or rec.get("finding") or next(iter(rec.values()), "")
                print(f"  {e['path']}: {str(label)[:120]}")
    hits = rep["cache_hits"]
    if isinstance(hits, dict) and hits.get("results"):
        print(f"\n## cache_hits ({len(hits['results'])})")
        for r in hits["results"][:5]:
            print(f"  [{r.get('source')}] {r.get('title')}")
    elif isinstance(hits, dict) and hits.get("error"):
        print(f"\ncache: {hits['error']}")


def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))
        print(("ok  " if cond else "FAIL") + " " + name)

    canned = lambda q, n: {"results": [{"source": "fixture", "id": 1, "title": "canned",
                                        "snippet": "canned", "rank": 0.0}], "fts5": True}

    # 1. every committed library file flattens without raising; the two keyword-list files
    #    yield string leaves.
    library = _load_library()
    ok("all 8 files load", len(library) == 8 and
       not any(isinstance(d, dict) and "_load_error" in d for d in library.values()))
    leaf_counts = {n: sum(1 for _ in iter_leaves(d)) for n, d in library.items()}
    ok("all 8 files flatten (no raise)", len(leaf_counts) == 8)
    ok("entity + seed files yield string leaves",
       leaf_counts["entity-keywords.json"] > 3 and leaf_counts["long-tail-seeds.json"] > 3)

    # 2. a decor query hits known entities + seeds deterministically.
    rep = report("dresser makeover", cache_runner=canned)
    ents = json.dumps(rep["sections"]["entities"])
    seeds = json.dumps(rep["sections"]["long_tail_seeds"])
    ok("decor query hits entities (Welsh dresser)", "dresser" in ents.lower())
    ok("decor query hits long-tail seeds", "makeover" in seeds.lower())
    ok("ranked by match count", all(
        rep["sections"][s] == sorted(rep["sections"][s], key=lambda e: -e["match_count"])
        for s in SECTIONS))

    # 3. an off-domain query returns empty sections WITH the honesty envelope intact.
    rep2 = report("zzzz quantum chromodynamics flux", cache_runner=lambda q, n: {"results": [], "fts5": True})
    ok("off-domain query -> all sections empty", all(not rep2["sections"][s] for s in SECTIONS))
    ok("envelope: data_basis exact", rep2["data_basis"] == DATA_BASIS)
    ok("envelope: search_volumes is null", rep2["search_volumes"] is None)
    ok("envelope: 8 sources with provenance", len(rep2["sources"]) == 8 and
       all("file" in s and "source_ids" in s for s in rep2["sources"]))

    # 4. bad input -> clean error payloads (P46 contract), never a raise.
    ok("empty query refused", "error" in report(""))
    ok("non-string query refused", "error" in report(None))
    ok("oversize query refused", "error" in report("x" * 501))

    # 5. a broken cache runner degrades to an honest note; the library report survives.
    def boom(q, n):
        raise RuntimeError("no cache here")
    rep3 = report("dresser", cache_runner=boom)
    ok("cache failure -> honest error note, report intact",
       "error" in rep3["cache_hits"] and rep3["sections"]["entities"])

    # 6. canned cache hits pass through untouched.
    ok("cache hits pass through", rep["cache_hits"]["results"][0]["source"] == "fixture")

    # 7. limit caps every section.
    rep4 = report("furniture", limit=1, cache_runner=canned)
    ok("limit caps sections", all(len(rep4["sections"][s]) <= 1 for s in SECTIONS))

    failed = [n for n, c in checks if not c]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    return 0 if not failed else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline keyword report (library-derived, no live data)")
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="command")
    rep_p = sub.add_parser("report", help="run the offline keyword report")
    rep_p.add_argument("--query", required=True)
    rep_p.add_argument("--limit", type=int, default=25)
    rep_p.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.command != "report":
        parser.print_help()
        return 1
    rep = report(args.query, limit=args.limit)
    if "error" in rep:
        print(json.dumps(rep))
        return 1
    if args.json:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    else:
        _print_human(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
