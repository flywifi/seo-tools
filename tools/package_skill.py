#!/usr/bin/env python3
"""Creator OS skill packager.

Zips a skill directory into dist/<name>.skill (a zip archive) after a minimal validity check
(SKILL.md present with name + description frontmatter). Used in CI to confirm every skill is
installable.

Usage:
  python3 tools/package_skill.py <skill-name>
  python3 tools/package_skill.py --all
"""
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def skill_dirs():
    skills = ROOT / "skills"
    for skill_md in sorted(skills.rglob("SKILL.md")):
        yield skill_md.parent


def valid(skill_dir):
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return False, "no SKILL.md"
    m = FM_RE.match(skill_md.read_text(encoding="utf-8"))
    if not m:
        return False, "no frontmatter"
    block = m.group(1)
    if "name:" not in block or "description:" not in block:
        return False, "frontmatter missing name or description"
    return True, "ok"


def package(skill_dir):
    ok, reason = valid(skill_dir)
    rel = skill_dir.relative_to(ROOT)
    if not ok:
        print(f"  SKIP {rel}: {reason}")
        return False
    DIST.mkdir(exist_ok=True)
    out = DIST / f"{skill_dir.name}.skill"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(skill_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(skill_dir.parent))
    print(f"  OK   {rel} -> dist/{out.name}")
    return True


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if "--all" in argv:
        results = [package(d) for d in skill_dirs()]
        print(f"packaged {sum(results)}/{len(results)} skills")
        return 0 if all(results) else 1
    name = argv[0]
    matches = [d for d in skill_dirs() if d.name == name]
    if not matches:
        print(f"no skill named {name!r}")
        return 1
    return 0 if package(matches[0]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
