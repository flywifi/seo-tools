#!/usr/bin/env python3
"""Creator OS skill packager.

Zips a skill directory into dist/<name>.skill (a zip archive) after a minimal validity check
(SKILL.md present with name + description frontmatter). Used in CI to confirm every skill is
installable.

Packaging integrity (P79 WP-D): the .skill zips embed file mtimes and are not reproducible, so the
integrity anchor is a sha256 over each skill's SOURCE TREE (sorted relative paths + bytes), recorded
in implementation/skill-package-manifest.json (tracked, beside the other generated manifests).
`--check-manifest` recomputes and exits 1 on drift; `--reconcile-manifest` re-blesses. Two skill
directories with the same leaf name would silently overwrite each other in dist/, so both verbs and
the packager refuse on a duplicate leaf name.

Usage:
  python3 tools/package_skill.py <skill-name>
  python3 tools/package_skill.py --all
  python3 tools/package_skill.py --reconcile-manifest   # (re)write the source-tree hash manifest
  python3 tools/package_skill.py --check-manifest       # exit 1 when a skill tree drifted from the manifest
  python3 tools/package_skill.py --selftest             # offline
"""
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
MANIFEST = ROOT / "implementation" / "skill-package-manifest.json"
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def skill_dirs(root=None):
    skills = (root or ROOT) / "skills"
    for skill_md in sorted(skills.rglob("SKILL.md")):
        yield skill_md.parent


def tree_sha(d):
    """sha256 over the skill's source tree: sorted relative paths + file bytes, NUL-delimited.
    mtime-free and deterministic, unlike the zip."""
    h = hashlib.sha256()
    for f in sorted(x for x in d.rglob("*") if x.is_file()):
        h.update(str(f.relative_to(d)).encode("utf-8")); h.update(b"\0")
        h.update(f.read_bytes()); h.update(b"\0")
    return h.hexdigest()


def duplicate_leaf_names(dirs):
    names = {}
    for d in dirs:
        names.setdefault(d.name, []).append(str(d))
    return {k: v for k, v in names.items() if len(v) > 1}


def reconcile_manifest(root=None, manifest=None):
    root = root or ROOT
    manifest = manifest or MANIFEST
    dirs = list(skill_dirs(root))
    dupes = duplicate_leaf_names(dirs)
    if dupes:
        print(f"package-manifest: duplicate skill leaf names {dupes}; rename before packaging")
        return 1
    man = {"_comment": "P79 packaging integrity: sha256 per skill SOURCE TREE (sorted relative paths + "
                       "bytes, NUL-delimited; mtime-free). Verify with `python3 tools/package_skill.py "
                       "--check-manifest`, re-bless with `--reconcile-manifest`. dist/ zips embed mtimes "
                       "and are not reproducible, so the tree hash is the integrity anchor.",
           "generated_by": "tools/package_skill.py",
           "skills": {d.name: tree_sha(d) for d in dirs}}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"package-manifest: {len(dirs)} skills recorded -> {manifest.relative_to(root)}")
    return 0


def check_manifest(root=None, manifest=None):
    """Return (drift_list, exit_code). Exit 1 on any drifted, missing, or unrecorded skill."""
    root = root or ROOT
    manifest = manifest or MANIFEST
    if not manifest.exists():
        print("package-manifest: manifest missing; run --reconcile-manifest")
        return ["<manifest missing>"], 1
    man = json.loads(manifest.read_text(encoding="utf-8")).get("skills", {})
    dirs = list(skill_dirs(root))
    dupes = duplicate_leaf_names(dirs)
    if dupes:
        print(f"package-manifest: duplicate skill leaf names {dupes}; rename before packaging")
        return [f"<duplicate:{k}>" for k in dupes], 1
    cur = {d.name: tree_sha(d) for d in dirs}
    drift = sorted(set(man) ^ set(cur)) + sorted(k for k in man.keys() & cur.keys() if man[k] != cur[k])
    for k in drift:
        why = "unrecorded" if k not in man else ("removed" if k not in cur else "source tree changed")
        print(f"package-manifest: {k}: {why}; run --reconcile-manifest after reviewing the change")
    if not drift:
        print(f"package-manifest: {len(cur)} skills match their recorded source-tree hashes")
    return drift, (0 if not drift else 1)


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
    dupes = duplicate_leaf_names(list(skill_dirs()))
    if skill_dir.name in dupes:
        print(f"  REFUSE {rel}: leaf name {skill_dir.name!r} is shared by {dupes[skill_dir.name]}; "
              f"packaging would silently overwrite dist/{skill_dir.name}.skill")
        return False
    DIST.mkdir(exist_ok=True)
    out = DIST / f"{skill_dir.name}.skill"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(skill_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(skill_dir.parent))
    print(f"  OK   {rel} -> dist/{out.name}")
    return True


def selftest():
    import tempfile
    checks = []
    ok = lambda name, cond: checks.append((name, bool(cond)))
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        fm = "---\nname: {n}\ndescription: fixture\n---\nbody\n"
        for n in ("alpha", "beta"):
            d = root / "skills" / n; d.mkdir(parents=True)
            (d / "SKILL.md").write_text(fm.format(n=n)); (d / "notes.md").write_text(n)
        man = root / "implementation" / "skill-package-manifest.json"
        ok("reconcile writes a manifest with one hash per skill",
           reconcile_manifest(root, man) == 0 and len(json.loads(man.read_text())["skills"]) == 2)
        ok("check is clean right after reconcile", check_manifest(root, man)[1] == 0)
        ok("tree hash is deterministic across passes", tree_sha(root / "skills" / "alpha") == tree_sha(root / "skills" / "alpha"))
        (root / "skills" / "alpha" / "notes.md").write_text("edited")
        drift, code = check_manifest(root, man)
        ok("an edited skill file drifts the check (exit 1, skill named)", code == 1 and drift == ["alpha"])
        (root / "skills" / "gamma").mkdir(); (root / "skills" / "gamma" / "SKILL.md").write_text(fm.format(n="gamma"))
        drift, code = check_manifest(root, man)
        ok("an unrecorded new skill drifts the check", code == 1 and "gamma" in drift)
        ok("reconcile clears both", reconcile_manifest(root, man) == 0 and check_manifest(root, man)[1] == 0)
        # duplicate leaf names: nested atom with the same leaf as a spoke
        dup = root / "skills" / "atoms" / "alpha"; dup.mkdir(parents=True); (dup / "SKILL.md").write_text(fm.format(n="alpha"))
        ok("duplicate leaf names are refused by reconcile", reconcile_manifest(root, man) == 1)
        ok("duplicate leaf names are refused by check", check_manifest(root, man)[1] == 1)
    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    print(f"package_skill selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if "--selftest" in argv:
        return selftest()
    if "--reconcile-manifest" in argv:
        return reconcile_manifest()
    if "--check-manifest" in argv:
        return check_manifest()[1]
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
