#!/usr/bin/env python3
"""Edit-artifact bucket manifest — scoop-style, sha256-verified (P22 L3).

Mirrors tools/sync_cache.py. Produces a portable, hash-verified manifest of the editing
artifacts in pipeline/editing/ (edit-packages, generated FCPXML/OTIO, render manifests) so an
offline machine's outputs can be verified before the online side trusts them. Human-approved:
--status/--manifest only report; there is no destructive mode.

CLI:
  python3 tools/sync_editing.py --status
  python3 tools/sync_editing.py --manifest [--write editing-bucket.manifest.json]
  python3 tools/sync_editing.py --verify editing-bucket.manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDITING = ROOT / "pipeline" / "editing"
INCLUDE_SUFFIXES = (".local.json", ".fcpxml", ".drt", ".otio")


def _iter_artifacts():
    if not EDITING.exists():
        return
    for p in sorted(EDITING.rglob("*")):
        if p.is_file() and any(p.name.endswith(s) for s in INCLUDE_SUFFIXES):
            yield p
    # .fcpxmld bundles are directories; hash their inner files collectively
    for p in sorted(EDITING.glob("*.fcpxmld")):
        if p.is_dir():
            yield p


def _sha256_file(p: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    total = 0
    data = p.read_bytes()
    h.update(data)
    total += len(data)
    return h.hexdigest(), total


def _sha256_bundle(d: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    total = 0
    for f in sorted(d.rglob("*")):
        if f.is_file():
            data = f.read_bytes()
            h.update(f.relative_to(d).as_posix().encode())
            h.update(data)
            total += len(data)
    return h.hexdigest(), total


def manifest() -> dict:
    resources = []
    for p in _iter_artifacts():
        rel = p.relative_to(ROOT).as_posix()
        if p.is_dir():
            digest, size = _sha256_bundle(p)
            kind = "fcpxmld_bundle"
        else:
            digest, size = _sha256_file(p)
            kind = "file"
        resources.append({"path": rel, "kind": kind, "sha256": digest, "bytes": size})
    return {
        "name": "creator-os-editing-bucket",
        "version": "0.1.0",
        "resource_count": len(resources),
        "resources": resources,
        "note": "Scoop-style editing-artifact manifest. Portable and hash-verified; re-verify offline before trusting a synced copy.",
    }


def verify(manifest_path: str) -> dict:
    m = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    current = {r["path"]: r["sha256"] for r in manifest()["resources"]}
    ok, changed, missing = [], [], []
    for r in m.get("resources", []):
        cur = current.get(r["path"])
        if cur is None:
            missing.append(r["path"])
        elif cur == r["sha256"]:
            ok.append(r["path"])
        else:
            changed.append(r["path"])
    extra = [p for p in current if p not in {r["path"] for r in m.get("resources", [])}]
    return {"ok": not changed and not missing, "verified": ok, "changed": changed,
            "missing": missing, "new_since_manifest": extra}


def _main(argv) -> int:
    ap = argparse.ArgumentParser(description="Edit-artifact bucket manifest (sha256).")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--write", metavar="FILE")
    ap.add_argument("--verify", metavar="MANIFEST")
    a = ap.parse_args(argv)
    if a.verify:
        print(json.dumps(verify(a.verify), indent=2))
    elif a.manifest or a.write:
        m = manifest()
        if a.write:
            Path(a.write).write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
            print(f"wrote {a.write} ({m['resource_count']} artifacts)")
        else:
            print(json.dumps(m, indent=2))
    else:  # --status default
        m = manifest()
        print(f"pipeline/editing/: {m['resource_count']} artifact(s)")
        for r in m["resources"]:
            print(f"  {r['kind']:16} {r['bytes']:>10}  {r['path']}")
    return 0


def main(argv) -> int:
    """Thin CLI boundary (P66): an unhandled filesystem error from a user-supplied path (for
    example a >255-byte component raising ENAMETOOLONG, which Path.exists() does not suppress)
    becomes the clean {"error","next_step"} envelope instead of a raw traceback."""
    try:
        return _main(argv)
    except OSError as exc:
        print(json.dumps({"error": str(exc),
                          "next_step": "pass a readable file path (this one could not be opened)"}))
        return 1

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
