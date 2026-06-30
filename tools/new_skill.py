#!/usr/bin/env python3
"""Creator OS skill scaffolder.

Usage:
  python3 tools/new_skill.py <skill-name>          # a spoke, flat under skills/<name>/
  python3 tools/new_skill.py --atom <skill-name>   # an atom under skills/atoms/<name>/

Copies tools/skill-template/ into place and substitutes __SKILL_NAME__. Then edit SKILL.md and
MAINTAINER_README.md and run tools/sync_check.py.
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "tools" / "skill-template"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def main(argv):
    atom = False
    args = []
    for arg in argv:
        if arg == "--atom":
            atom = True
        else:
            args.append(arg)
    if len(args) != 1:
        print(__doc__)
        return 2
    name = args[0]
    if not NAME_RE.match(name) or len(name) > 64:
        print(f"invalid skill name: {name!r} (use lowercase, hyphen-case, <= 64 chars)")
        return 2
    dest = (ROOT / "skills" / "atoms" / name) if atom else (ROOT / "skills" / name)
    if dest.exists() and any(dest.iterdir()):
        print(f"already exists and is not empty: {dest.relative_to(ROOT)}")
        return 1
    if not TEMPLATE.exists():
        print("missing tools/skill-template/")
        return 1
    shutil.copytree(TEMPLATE, dest, dirs_exist_ok=True)
    for md in dest.rglob("*"):
        if md.is_file() and md.suffix in (".md", ".json"):
            text = md.read_text(encoding="utf-8").replace("__SKILL_NAME__", name)
            md.write_text(text, encoding="utf-8")
    print(f"scaffolded {dest.relative_to(ROOT)}")
    print("next: edit SKILL.md + MAINTAINER_README.md, then run python3 tools/sync_check.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
