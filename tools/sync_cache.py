#!/usr/bin/env python3
"""Creator OS scoop cache, L3: manifest-driven sync and a portable, hash-verified bucket manifest.

Reuses the L1 sha256 baseline for local drift. Human-approved by default: --sync is a dry-run, and
rebuilding the L1 index needs --apply.

Usage:
  python3 tools/sync_cache.py --status
  python3 tools/sync_cache.py --manifest --write bucket.manifest.json
  python3 tools/sync_cache.py --sync     # dry-run: what would rebuild
  python3 tools/sync_cache.py --apply    # rebuild L1 from canonical-sources
  python3 tools/sync_cache.py --selftest

A manifest path is relative to the repository root with forward slashes on every system; a
baseline an older Windows build wrote with backslash keys is read with forward slashes.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "canonical-sources"
CACHE = ROOT / "shared" / "cache"
BASELINE = CACHE / "cache-baseline.local.json"


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest():
    resources = [
        {
            "path": p.relative_to(ROOT).as_posix(),
            "sha256": sha256_of(p),
            "bytes": p.stat().st_size,
        }
        for p in sorted(SOURCES.rglob("*.json"))
    ]
    return {
        "name": "creator-os-canonical-sources",
        "version": "0.1.0",
        "resource_count": len(resources),
        "resources": resources,
        "rebuild": "python3 shared/cache/cache.py --build",
        "note": "Scoop-style bucket manifest. Portable and hash-verified; re-verify offline before trusting a synced copy.",
    }


def status():
    cur = {r["path"]: r for r in manifest()["resources"]}
    if not BASELINE.exists():
        print("local L1 cache: not built (no baseline). Run --apply.")
    else:
        base = {str(k).replace("\\", "/"): v
                for k, v in json.loads(BASELINE.read_text(encoding="utf-8")).items()}
        drift = [k for k in cur if k not in base or base[k]["sha256"] != cur[k]["sha256"]]
        drift += [k for k in base if k not in cur]
        if drift:
            print("local L1 cache: stale. Would rebuild for:")
            for item in drift:
                print(f"  - {item}")
        else:
            print("local L1 cache: fresh (matches the build baseline).")
    print(f"{len(cur)} canonical-source resources tracked.")
    return 0


def selftest():
    """manifest() and status() against a temp tree with ROOT, SOURCES, CACHE and BASELINE pointed at
    it, never the real baseline, with Windows relative paths stood in by file_hash.windows_paths()."""
    import contextlib
    import io
    import tempfile
    sys.path.insert(0, str(Path(__file__).resolve().parent))
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

    def run_status():
        out = io.StringIO()
        with file_hash.windows_paths(), contextlib.redirect_stdout(out):
            rc = status()
        return rc, out.getvalue()

    g = globals()
    saved = {k: g[k] for k in ("ROOT", "SOURCES", "CACHE", "BASELINE")}
    real_before = state(saved["BASELINE"])
    want = ["canonical-sources/construction/stairs.json", "canonical-sources/keywords.json"]
    try:
        td = Path(tempfile.mkdtemp(prefix="sync-cache-selftest-"))
        g.update(ROOT=td, SOURCES=td / "canonical-sources", CACHE=td / "shared" / "cache",
                 BASELINE=td / "shared" / "cache" / "baseline.json")
        (SOURCES / "construction").mkdir(parents=True)
        (SOURCES / "construction" / "stairs.json").write_text('[{"id": "st1", "text": "riser"}]',
                                                              encoding="utf-8")
        (SOURCES / "keywords.json").write_text('[{"id": "kw1", "text": "fall"}]', encoding="utf-8")
        with file_hash.windows_paths():
            m = manifest()
        ok("manifest paths use forward slashes with Windows paths",
           [r["path"] for r in m["resources"]] == want and m["resource_count"] == 2)
        rc0, text0 = run_status()
        ok("status without a baseline says the cache is not built", rc0 == 0 and "not built" in text0)
        CACHE.mkdir(parents=True)
        old = {r["path"].replace("/", "\\"): {"sha256": r["sha256"], "bytes": r["bytes"]}
               for r in m["resources"]}
        BASELINE.write_text(json.dumps(old), encoding="utf-8")
        rc1, text1 = run_status()
        ok("status reads a baseline with backslash keys as fresh", rc1 == 0 and "fresh" in text1)
        (SOURCES / "keywords.json").write_text('[{"id": "kw1", "text": "changed"}]', encoding="utf-8")
        rc2, text2 = run_status()
        ok("status names a changed source once, with forward slashes",
           "stale" in text2 and text2.count("canonical-sources/keywords.json") == 1
           and "\\" not in text2 and "stairs.json" not in text2)
        (SOURCES / "construction" / "stairs.json").unlink()
        new = {r["path"]: {"sha256": r["sha256"], "bytes": r["bytes"]} for r in m["resources"]}
        BASELINE.write_text(json.dumps(new), encoding="utf-8")
        rc3, text3 = run_status()
        ok("status names a removed source from a forward-slash baseline",
           "stale" in text3 and "canonical-sources/construction/stairs.json" in text3)
    finally:
        g.update(saved)
    ok("the selftest left the real baseline as it was", state(BASELINE) == real_before)
    failed = [n for n, c in checks if not c]
    for n, c in checks:
        print(("ok   " if c else "FAIL ") + n)
    print(f"sync_cache selftest: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS scoop cache L3")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--write")
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.manifest:
        data = manifest()
        text = json.dumps(data, indent=2)
        if args.write:
            Path(args.write).write_text(text + "\n", encoding="utf-8")
            print(f"wrote {args.write} ({data['resource_count']} resources, hash-verified)")
        else:
            print(text)
        return 0
    if args.status:
        return status()
    if args.sync:
        print("dry-run (--sync). Re-run with --apply to rebuild the L1 index.")
        return status()
    if args.apply:
        print("rebuilding L1 index from canonical-sources...")
        return subprocess.call([sys.executable, str(CACHE / "cache.py"), "--build"])
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
