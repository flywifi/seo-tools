#!/usr/bin/env python3
"""registry_io.py -- the single load/save implementation for the source registry.

`canonical-sources/source-registry.json` has five sanctioned writers, all funneling through this
module's `save_registry` so there is exactly one write implementation (stable JSON: indent 2,
ensure_ascii false, trailing newline). Four import registry_io directly:
  1. `source_currency.py` (report/check/mark-checked/seed-sources/seed-partners/update-source/
     remove-source),
  2. `traversal_engine.py` (accept, which appends a graph-discovered source),
  3. `dependency_currency.py` (check --apply -> apply_stamps, which stamps dependency freshness),
  4. `update_check.py` (apply_stamp, which stamps the repo-self-update source).
A fifth, `competitor_snapshot.py` (register-competitor), writes through `source_currency`'s
re-exported `save_registry` (`SC.save_registry`), so it too goes through this single implementation.
No other tool writes the registry; canonical data files stay read-only from tooling.

Stdlib only, no side effects on import.
"""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "canonical-sources" / "source-registry.json"


def content_digest(data: dict) -> str:
    """sha256 over the canonical dump of sources[] (P66). The sanctioned write path stamps this
    into `_content_digest` on every save, so an out-of-band in-place edit to an EXISTING entry's
    content — which changes no source id and therefore slips past the id-level freshness digest —
    leaves the stamp stale and trips drift invariant 56 (advisory)."""
    payload = json.dumps(data.get("sources", []), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    """Return the registry dict ({_comment, version, last_registry_update, sources[]}), or a
    minimal empty shell when the file is absent."""
    if not path.exists():
        return {"sources": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_registry(data: dict, path: Path = REGISTRY_PATH) -> None:
    """Write the registry with the canonical formatting both writers must produce byte-identically.
    Stamps `_content_digest` (see content_digest) so hand edits are detectable.

    The write is ATOMIC: serialize in full, write to a temp file in the same directory, then
    os.replace onto the target. A bare write_text truncates the destination first, so an
    interrupt (Ctrl-C, a crash, a full disk) mid-write left a 5,500-line registry truncated with
    no backup and no recovery path. os.replace is atomic within a filesystem, so a reader either
    sees the whole old file or the whole new one, never a half-written one (P73 D6-F8).
    """
    data["_content_digest"] = content_digest(data)
    blob = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    try:
        tmp.write_text(blob, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
