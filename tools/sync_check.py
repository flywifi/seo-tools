#!/usr/bin/env python3
"""Creator OS drift guard.

Asserts repository invariants rather than diffing text. Exit 0 = clean, 1 = drift.
Pure stdlib. Run from anywhere: `python3 tools/sync_check.py`.

Invariants enforced:
  1. Canonical engines + protocols (tools/sync_manifest.json) all exist.
  2. Every SKILL.md has valid frontmatter with a hyphen-case `name` and a `description`.
  3. Every skill directory with a SKILL.md also carries a MAINTAINER_README.md.
  4. Formatting rule (protocols/formatting-metadata.md): no em dashes anywhere, no en dashes
     (ranges are written with "to"), and no forbidden tokens (TODO/FIXME/PLACEHOLDER/merge markers)
     in committed .md content.
  5. Referential integrity: every backticked repo path (shared/protocols/skills/pipeline/tools/docs
     ending in .md/.json/.py) named in a SKILL.md exists on disk.
  6. Hub integrity: every spoke directory is listed in the hub's downstream spokes, and the hub
     carries the routing object schema.
  7. Workflow atom resolution: every atom named in a workflow.json is an installed atom.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBLEMS = []


def problem(msg):
    PROBLEMS.append(msg)


def load_manifest():
    path = ROOT / "tools" / "sync_manifest.json"
    if not path.exists():
        problem("missing tools/sync_manifest.json")
        return {"engines": [], "protocols": []}
    return json.loads(path.read_text(encoding="utf-8"))


def check_canonical(manifest):
    for rel in manifest.get("engines", []) + manifest.get("protocols", []):
        if not (ROOT / rel).exists():
            problem(f"canonical file missing: {rel}")


FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def parse_frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        if line and not line.startswith((" ", "-", "\t")) and ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm


def iter_skill_mds():
    skills = ROOT / "skills"
    if skills.exists():
        yield from sorted(skills.rglob("SKILL.md"))


def check_skills():
    for skill_md in iter_skill_mds():
        rel = skill_md.relative_to(ROOT)
        text = skill_md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm is None:
            problem(f"{rel}: missing YAML frontmatter")
            continue
        name = fm.get("name")
        if not name:
            problem(f"{rel}: frontmatter missing 'name'")
        elif not NAME_RE.match(name):
            problem(f"{rel}: name '{name}' is not hyphen-case")
        elif len(name) > 64:
            problem(f"{rel}: name longer than 64 chars")
        if not fm.get("description"):
            problem(f"{rel}: frontmatter missing 'description'")
        if not (skill_md.parent / "MAINTAINER_README.md").exists():
            problem(f"{rel.parent}: missing MAINTAINER_README.md")


EM_DASH = "—"
EN_DASH = "–"
FORBIDDEN_TOKENS = ["TODO", "FIXME", "PLACEHOLDER", "<<<<<<<", "=======", ">>>>>>>"]
CONTENT_DIRS = ["shared", "protocols", "skills", "docs", "examples", "canonical-sources"]


def check_formatting():
    for name in CONTENT_DIRS:
        base = ROOT / name
        if not base.exists():
            continue
        for md in sorted(base.rglob("*.md")):
            rel = md.relative_to(ROOT)
            text = md.read_text(encoding="utf-8")
            if EM_DASH in text:
                problem(f"{rel}: contains an em dash (forbidden by formatting-metadata.md)")
            if EN_DASH in text:
                problem(f"{rel}: contains an en dash (write ranges with 'to')")
            for tok in FORBIDDEN_TOKENS:
                if tok in text:
                    problem(f"{rel}: contains forbidden token {tok!r}")


PATH_RE = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:md|json|py))`")
KNOWN_ROOTS = ("shared", "protocols", "skills", "pipeline", "tools", "docs")


def check_references():
    for skill_md in iter_skill_mds():
        rel = skill_md.relative_to(ROOT)
        text = skill_md.read_text(encoding="utf-8")
        for match in PATH_RE.finditer(text):
            ref = match.group(1)
            if ref.split("/")[0] in KNOWN_ROOTS and not (ROOT / ref).exists():
                problem(f"{rel}: references missing path `{ref}`")


def check_hub():
    hub = ROOT / "skills" / "creator-core" / "SKILL.md"
    if not hub.exists():
        problem("missing hub skills/creator-core/SKILL.md")
        return
    text = hub.read_text(encoding="utf-8")
    listed = set()
    if "## Downstream spokes" in text:
        listed = set(re.findall(r"[a-z][a-z-]+", text.split("## Downstream spokes")[-1]))
    actual = {
        p.name
        for p in (ROOT / "skills").iterdir()
        if p.is_dir() and p.name not in ("creator-core", "atoms")
    }
    for spoke in sorted(actual):
        if spoke not in listed:
            problem(f"orphan spoke skills/{spoke} not listed in hub downstream spokes")
    if '"request_classification"' not in text:
        problem("hub SKILL.md missing the routing object schema")


def check_workflows():
    atoms_dir = ROOT / "skills" / "atoms"
    available = (
        {p.name for p in atoms_dir.iterdir() if p.is_dir()} if atoms_dir.exists() else set()
    )
    for wf in sorted((ROOT / "skills").rglob("workflow.json")):
        rel = wf.relative_to(ROOT)
        try:
            data = json.loads(wf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problem(f"{rel}: invalid JSON ({exc})")
            continue
        named = [s.get("atom") for s in data.get("steps", []) if s.get("atom")]
        named += list(data.get("shortcut_atoms", []))
        for atom in named:
            if atom not in available:
                problem(f"{rel}: references unknown atom '{atom}'")


def main():
    manifest = load_manifest()
    check_canonical(manifest)
    check_skills()
    check_formatting()
    check_references()
    check_hub()
    check_workflows()
    if PROBLEMS:
        print(f"DRIFT GUARD: {len(PROBLEMS)} problem(s) found\n")
        for item in PROBLEMS:
            print(f"  - {item}")
        return 1
    print("DRIFT GUARD: clean (all invariants hold)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
