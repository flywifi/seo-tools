#!/usr/bin/env python3
"""Scaffold a new SEO atom from the standard template.

Usage:
  python3 tools/new_atom.py <atom-name>

Creates skills/atoms/<atom-name>/ from skills/atoms/atom-template/,
substituting __ATOM_NAME__ with the given name throughout.
After scaffolding: edit SKILL.md, MAINTAINER.md, and evals/evals.json,
then run python3 tools/sync_check.py to verify.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "skills" / "atoms" / "atom-template"
ATOMS_DIR = ROOT / "skills" / "atoms"
REGISTRY = ATOMS_DIR / "atoms.json"


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0]:
        print("usage: python3 tools/new_atom.py <atom-name>")
        return 2

    name = argv[0].strip().strip("/")
    if not name or not all(c.isalnum() or c == "-" for c in name):
        print(f"[!] invalid atom name: {name!r} (use lowercase letters, digits, hyphens)")
        return 2

    dest = ATOMS_DIR / name
    if dest.exists():
        print(f"[!] already exists: {dest.relative_to(ROOT)}")
        return 1
    if not TEMPLATE.exists():
        print(f"[!] template missing: {TEMPLATE.relative_to(ROOT)}")
        return 1

    shutil.copytree(TEMPLATE, dest)
    for fn in ("SKILL.md", "MAINTAINER.md", "evals/evals.json"):
        f = dest / fn
        if f.exists():
            f.write_text(
                f.read_text(encoding="utf-8").replace("__ATOM_NAME__", name),
                encoding="utf-8",
            )

    if REGISTRY.exists():
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        reg["atoms"].append({
            "id": name,
            "label": name.replace("-", " ").title(),
            "version": "1.0",
            "path": f"skills/atoms/{name}",
            "script": "REPLACE",
            "input_schema": {},
            "output_schema": {"human_review_required": "boolean"},
            "tags": [],
        })
        REGISTRY.write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")

    print(f"created skills/atoms/{name}/")
    print("next: edit SKILL.md + MAINTAINER.md + evals/evals.json, then run: python3 tools/sync_check.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
