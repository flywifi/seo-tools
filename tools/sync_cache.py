#!/usr/bin/env python3
"""Creator OS scoop cache, L3: manifest-driven sync and a portable, hash-verified bucket manifest.

Reuses the L1 sha256 baseline for local drift. Human-approved by default: --sync is a dry-run, and
rebuilding the L1 index needs --apply.

Usage:
  python3 tools/sync_cache.py --status
  python3 tools/sync_cache.py --manifest --write bucket.manifest.json
  python3 tools/sync_cache.py --sync     # dry-run: what would rebuild
  python3 tools/sync_cache.py --apply    # rebuild L1 from canonical-sources
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
            "path": str(p.relative_to(ROOT)),
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
        base = json.loads(BASELINE.read_text(encoding="utf-8"))
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


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS scoop cache L3")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--write")
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
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
