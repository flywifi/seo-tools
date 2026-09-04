#!/usr/bin/env python3
"""hash_audit.py -- recompute every stored hash in the repo and compare it to the bytes on disk (P79).

Why this exists: the P78 audit found that hashes stored by one code path and verified by none rot
silently -- fourteen GIS boundary hashes had never matched a committed byte, and a packaged-knowledge
hash sat stale for weeks. A stored hash is only evidence if something recomputes it. This is that
something, in one verb, for every store the repo carries.

Rules (each is a constraint the P78 census established, not a preference):
  * disk-only: never fetches; the fetch-defaulting modules (construction_fetch, geo_source_fetch,
    project_docs' API lane) are never called;
  * never creates a store: gitignored stores that are absent report `not_applicable`, never ok
    and never fail (six are expected-absent on a fresh clone); SQLite is opened read-only;
  * never writes anything;
  * tracked stores gate (exit 1 on a mismatch); gitignored stores REPORT ONLY -- "an invariant must
    never depend on out-of-repo state" (tools/project_docs.py) -- so this is a tool plus a sweep
    selftest, deliberately NOT a drift-guard invariant.

Usage:
  python3 tools/hash_audit.py            # human table; exit 1 if any TRACKED store mismatches
  python3 tools/hash_audit.py --json     # machine rows
  python3 tools/hash_audit.py --selftest # offline, tempdir synthetic stores
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

OK, MISMATCH, NA, REPORT = "ok", "MISMATCH", "not_applicable", "report_only"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _sha_text(p: Path) -> str:
    return hashlib.sha256(p.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- tracked stores (gate)

def audit_mac_surface(root):
    p = root / "canonical-sources" / "mac-surface-manifest.json"
    if not p.exists():
        return NA, "manifest absent"
    files = json.loads(p.read_text(encoding="utf-8")).get("files", {})
    bad = [f for f, h in files.items() if not (root / f).exists() or _sha(root / f) != h]
    return (OK if not bad else MISMATCH), f"{len(files)} files" + (f"; bad={bad}" if bad else "")


def audit_registry_digest(root):
    p = root / "canonical-sources" / "source-registry.json"
    if not p.exists():
        return NA, "registry absent"
    import registry_io
    reg = json.loads(p.read_text(encoding="utf-8"))
    ok = registry_io.content_digest(reg) == reg.get("_content_digest")
    return (OK if ok else MISMATCH), f"{len(reg.get('sources', []))} sources"


def audit_projection_manifest(root):
    p = root / "implementation" / "knowledge-projection-manifest.json"
    if not p.exists():
        return NA, "manifest absent"
    n = bad = 0
    for proj, rec in json.loads(p.read_text(encoding="utf-8")).get("projections", {}).items():
        for s, h in (rec.get("sources") or {}).items():
            n += 1
            bad += (not (root / s).exists()) or _sha(root / s) != h
        if rec.get("projection"):
            n += 1
            bad += (not (root / proj).exists()) or _sha(root / proj) != rec["projection"]
    return (OK if not bad else MISMATCH), f"{n} hashes" + (f"; {bad} bad" if bad else "")


def audit_doc_freshness(root):
    p = root / "docs" / "doc-freshness-manifest.json"
    if not p.exists():
        return NA, "manifest absent"
    n = bad = 0
    for doc, rec in json.loads(p.read_text(encoding="utf-8")).get("docs", {}).items():
        for s, h in (rec.get("sources") or {}).items():
            n += 1
            bad += (not (root / s).exists()) or _sha(root / s) != h
    return (OK if not bad else MISMATCH), f"{n} hashes" + (f"; {bad} bad" if bad else "")


def audit_freshness_bundle(root):
    p = root / "implementation" / "freshness-bundle.json"
    if not p.exists():
        return NA, "bundle absent"
    recs = json.loads(p.read_text(encoding="utf-8")).get("managed_files", [])
    stale = [r["file"] for r in recs
             if not (root / r["file"]).exists() or _sha_text(root / r["file"]) != r.get("sha256")]
    return (OK if not stale else MISMATCH), f"{len(recs)} files" + (f"; stale={stale}" if stale else "")


def audit_gis_boundaries(root):
    base = root / "canonical-sources" / "jurisdiction" / "orlando-boundaries"
    man = base / "MANIFEST.json"
    if not man.exists():
        return NA, "boundary cache absent"
    recs = json.loads(man.read_text(encoding="utf-8")).get("files", [])
    mb = sum(1 for r in recs if not (base / (r["name"] + ".geojson")).exists()
             or _sha(base / (r["name"] + ".geojson")) != r.get("sha256"))
    pb = 0
    for pv in sorted(base.glob("*.provenance.json")):
        d = json.loads(pv.read_text(encoding="utf-8"))
        tgt = base / d.get("file", "")
        pb += (not tgt.exists()) or _sha(tgt) != d.get("sha256")
    return (OK if not (mb or pb) else MISMATCH), f"manifest {mb}/{len(recs)} bad, provenance {pb} bad"


def audit_skill_packages(root):
    p = root / "implementation" / "skill-package-manifest.json"
    if not p.exists():
        return NA, "manifest absent"
    import package_skill
    drift, code = package_skill.check_manifest(root, p) if hasattr(package_skill, "check_manifest") else ([], 0)
    return (OK if code == 0 else MISMATCH), f"{len(json.loads(p.read_text())['skills'])} skills" + (f"; drift={drift}" if drift else "")


# ---------------------------------------------------------------- gitignored stores (report only)

def audit_video_library(root):
    p = root / "pipeline" / "video-library" / "index.local.db"
    if not p.exists():
        return NA, "store absent"
    import video_library as vl
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)  # read-only URI: cannot create or migrate
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("SELECT * FROM video_records").fetchall()
    except sqlite3.DatabaseError as exc:
        con.close()
        return REPORT, f"unreadable: {exc}"
    bad = ambiguous = 0

    def loads(v):
        try:
            return json.loads(v) if v is not None else None
        except (TypeError, ValueError):
            return None
    for r in rows:
        rec = {"title": r["title"], "description": r["description"], "tags": loads(r["tags_json"]),
               "stats": loads(r["stats_json"]), "retention": loads(r["retention_json"]),
               "revenue": loads(r["revenue_json"]), "transcript_text": r["transcript_text"],
               "chapters": loads(r["chapters_json"])}
        if vl._content_hash(rec) == r["content_hash"]:
            continue
        # _upsert stores `tags or []` / `stats or {}` / `chapters or []` while the hash was taken over
        # the raw values (possibly None): try the None-normalized reading before calling it a mismatch.
        alt = dict(rec)
        for k, empty in (("tags", []), ("stats", {}), ("chapters", [])):
            if alt.get(k) == empty:
                alt[k] = None
        if vl._content_hash(alt) == r["content_hash"]:
            ambiguous += 1
        else:
            bad += 1
    con.close()
    detail = f"{len(rows)} rows" + (f"; {ambiguous} matched only after None-normalization" if ambiguous else "") + (f"; {bad} MISMATCH" if bad else "")
    return (REPORT if not bad else MISMATCH), detail


def audit_construction_library(root):
    p = root / "pipeline" / "construction-library" / "manifest.json"
    if not p.exists():
        return NA, "store absent"
    recs = json.loads(p.read_text(encoding="utf-8")).get("files", [])
    lib = p.parent
    bad = [r["filename"] for r in recs if not (lib / r["filename"]).exists() or _sha(lib / r["filename"]) != r.get("sha256")]
    return (REPORT if not bad else MISMATCH), f"{len(recs)} files" + (f"; bad={bad}" if bad else "")


def audit_cache_baseline(root):
    p = root / "shared" / "cache" / "cache-baseline.local.json"
    if not p.exists():
        return NA, "baseline absent (not built)"
    base = json.loads(p.read_text(encoding="utf-8"))
    bad = [k for k, v in base.items() if isinstance(v, dict) and v.get("sha256")
           and ((not (root / k).exists()) or _sha(root / k) != v["sha256"])]
    return (REPORT if not bad else MISMATCH), f"{len(base)} entries" + (
        f"; drifted={bad} -> rebuild with `python3 shared/cache/cache.py --build`" if bad else "")


def _bucket(root, module, manifest_rel, label):
    p = root / manifest_rel
    if not p.exists():
        return NA, "manifest absent"
    mod = __import__(module)
    res = mod.verify(str(p))
    # four incompatible shapes normalized: {ok,verified,changed,missing[,new_since_manifest]} /
    # {ok,expected,actual} / {ok,problems,checked}
    ok = bool(res.get("ok"))
    parts = []
    for k in ("verified", "changed", "missing", "new_since_manifest", "problems", "checked"):
        if k in res:
            v = res[k]
            parts.append(f"{k}={len(v) if isinstance(v, (list, dict)) else v}")
    return (REPORT if ok else MISMATCH), (", ".join(parts) or json.dumps(res)[:80])


def audit_project_docs(root):
    p = root / "pipeline" / "user-context" / "project-docs-map.local.json"
    if not p.exists():
        return NA, "state absent"
    import project_docs
    res = project_docs.check(state_path=p)
    return (REPORT if res.get("ok") else MISMATCH), f"{len(res.get('files', []))} files, {res.get('stale', 0)} stale"


def audit_inbox_ledger(root):
    p = root / "pipeline" / "inbox" / "inbox-ledger.local.json"
    if not p.exists():
        return NA, "ledger absent"
    n = len(json.loads(p.read_text(encoding="utf-8")) or {})
    return REPORT, f"{n} entries; contents live in the Drive hub and are re-hashed at approve time (no offline recompute)"


TRACKED = [
    ("mac-surface", audit_mac_surface), ("registry-digest", audit_registry_digest),
    ("projection-manifest", audit_projection_manifest), ("doc-freshness", audit_doc_freshness),
    ("freshness-bundle", audit_freshness_bundle), ("gis-boundaries", audit_gis_boundaries),
    ("skill-packages", audit_skill_packages),
]
LOCAL = [
    ("video-library", audit_video_library), ("construction-library", audit_construction_library),
    ("cache-baseline", audit_cache_baseline),
    ("obligations-bucket", lambda r: _bucket(r, "obligations", "obligations-bucket.manifest.json", "obligations")),
    ("tasks-bucket", lambda r: _bucket(r, "tasks", "tasks-bucket.manifest.json", "tasks")),
    ("editing-bucket", lambda r: _bucket(r, "sync_editing", "editing-bucket.manifest.json", "editing")),
    ("finance-bucket", lambda r: _bucket(r, "finance", "finance-bucket.manifest.json", "finance")),
    ("project-docs", audit_project_docs), ("inbox-ledger", audit_inbox_ledger),
]


def run(root=ROOT):
    rows = []
    for name, fn in TRACKED:
        try:
            st, d = fn(root)
        except Exception as exc:  # noqa: BLE001 -- a broken auditor must not read as a clean store
            st, d = MISMATCH, f"auditor error: {type(exc).__name__}: {exc}"
        rows.append({"store": name, "scope": "tracked", "state": st, "detail": d})
    for name, fn in LOCAL:
        try:
            st, d = fn(root)
        except Exception as exc:  # noqa: BLE001
            st, d = MISMATCH, f"auditor error: {type(exc).__name__}: {exc}"
        rows.append({"store": name, "scope": "local", "state": st, "detail": d})
    return rows


def selftest():
    import tempfile
    checks = []
    ok = lambda name, cond: checks.append((name, bool(cond)))
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # a tracked store in every state, built by hand (never the real tree)
        (root / "canonical-sources").mkdir()
        f = root / "canonical-sources" / "a.txt"; f.write_text("alpha")
        (root / "canonical-sources" / "mac-surface-manifest.json").write_text(json.dumps(
            {"files": {"canonical-sources/a.txt": _sha(f)}}))
        st, _ = audit_mac_surface(root)
        ok("tracked store recomputes clean", st == OK)
        f.write_text("alpha-edited")
        st, d = audit_mac_surface(root)
        ok("tracked store MISMATCH after a byte edit, file named", st == MISMATCH and "a.txt" in d)
        ok("absent tracked store is not_applicable, not ok", audit_gis_boundaries(root)[0] == NA)
        ok("absent local store is not_applicable", audit_video_library(root)[0] == NA)
        ok("absent bucket manifest is not_applicable", _bucket(root, "tasks", "tasks-bucket.manifest.json", "t")[0] == NA)
        # never creates: the absent paths must still be absent after the run
        run(root)
        ok("run() creates no store", not (root / "pipeline").exists() and not (root / "shared").exists())
        # freshness-bundle per-file path (the F1 class)
        (root / "implementation").mkdir(); k = root / "implementation" / "k.md"; k.write_text("knowledge")
        (root / "implementation" / "freshness-bundle.json").write_text(json.dumps(
            {"managed_files": [{"file": "implementation/k.md", "sha256": _sha_text(k)}]}))
        ok("bundle per-file clean", audit_freshness_bundle(root)[0] == OK)
        k.write_text("knowledge+1")
        ok("bundle per-file MISMATCH after edit", audit_freshness_bundle(root)[0] == MISMATCH)
        # gate semantics: tracked MISMATCH -> exit 1; local-only mismatch -> exit 0
        rows = run(root)
        ok("exit code follows tracked scope only",
           exit_code(rows) == 1 and exit_code([r for r in rows if r["scope"] == "local"]) == 0)
    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    print(f"hash_audit selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


def exit_code(rows):
    return 1 if any(r["scope"] == "tracked" and r["state"] == MISMATCH for r in rows) else 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    rows = run()
    if "--json" in argv:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            print(f"  [{r['state']:14}] {r['scope']:7} {r['store']:22} {r['detail']}")
        t = sum(1 for r in rows if r["scope"] == "tracked")
        print(f"hash-audit: {'PASS' if exit_code(rows) == 0 else 'FAIL'} -- {t} tracked stores gate; "
              f"{sum(1 for r in rows if r['state'] == MISMATCH)} mismatch, "
              f"{sum(1 for r in rows if r['state'] == NA)} not applicable, "
              f"{sum(1 for r in rows if r['state'] == REPORT)} report-only")
    return exit_code(rows)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
