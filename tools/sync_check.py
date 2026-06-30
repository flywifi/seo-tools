#!/usr/bin/env python3
"""Drift guard for the seo-tools atom library.

Same 5 invariants as dbz/tools/sync_check.py, applied to seo-tools atoms.

Run:   python3 tools/sync_check.py
Exit:  0 if every invariant holds, 1 (with a report) otherwise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ATOMS_DIR = ROOT / "skills" / "atoms"
REGISTRY = ATOMS_DIR / "atoms.json"
SKIP = {"atom-template"}


def main() -> int:
    failures: list[str] = []

    atom_dirs = sorted(
        d for d in ATOMS_DIR.iterdir()
        if d.is_dir() and d.name not in SKIP and not d.name.startswith(".")
    )

    for d in atom_dirs:
        for fname in ("SKILL.md", "MAINTAINER.md"):
            if not (d / fname).exists():
                failures.append(f"  ✗ Invariant 1 — missing {fname}: {d.name}/")

    for d in atom_dirs:
        skill_md = d / "SKILL.md"
        if skill_md.exists():
            text = skill_md.read_text(encoding="utf-8")
            if "minority-report" not in text:
                failures.append(
                    f"  ✗ Invariant 2 — SKILL.md missing 'minority-report' reference: {d.name}/"
                )

    if REGISTRY.exists():
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        registered_ids = {a["id"] for a in reg.get("atoms", [])}
        dir_names = {d.name for d in atom_dirs}
        for atom_id in registered_ids:
            if atom_id not in dir_names:
                failures.append(
                    f"  ✗ Invariant 3 — atoms.json entry '{atom_id}' has no directory"
                )
    else:
        failures.append(f"  ✗ Invariant 3 — atoms.json not found")

    for d in atom_dirs:
        if not (d / "evals" / "evals.json").exists():
            failures.append(f"  ✗ Invariant 4 — missing evals/evals.json: {d.name}/")

    for d in atom_dirs:
        evals_path = d / "evals" / "evals.json"
        if evals_path.exists():
            try:
                data = json.loads(evals_path.read_text(encoding="utf-8"))
                cases = data.get("cases", data.get("evals", []))
                if len(cases) < 3:
                    failures.append(
                        f"  ✗ Invariant 5 — needs ≥3 eval cases, has {len(cases)}: {d.name}/"
                    )
            except json.JSONDecodeError as e:
                failures.append(f"  ✗ Invariant 5 — invalid JSON: {d.name}/ ({e})")

    print(f"seo-tools atom library drift check — {len(atom_dirs)} atom(s)\n")
    if failures:
        print("DRIFT DETECTED:\n")
        print("\n".join(failures))
        print(f"\n{len(failures)} invariant(s) failed.")
        return 1

    print(f"OK — all 5 invariants pass across {len(atom_dirs)} atom(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
