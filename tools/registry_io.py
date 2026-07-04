#!/usr/bin/env python3
"""registry_io.py -- the single load/save implementation for the source registry.

`canonical-sources/source-registry.json` has two sanctioned writers: `source_currency.py`
(report/check/mark-checked/seed-sources/seed-partners/update-source/remove-source) and
`traversal_engine.py` (accept, which appends a graph-discovered source). Both import this module
so there is exactly one write implementation (stable JSON: indent 2, ensure_ascii false, trailing
newline). No other tool writes the registry; canonical data files stay read-only from tooling.

Stdlib only, no side effects on import.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "canonical-sources" / "source-registry.json"


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    """Return the registry dict ({_comment, version, last_registry_update, sources[]}), or a
    minimal empty shell when the file is absent."""
    if not path.exists():
        return {"sources": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_registry(data: dict, path: Path = REGISTRY_PATH) -> None:
    """Write the registry with the canonical formatting both writers must produce byte-identically."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
