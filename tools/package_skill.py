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
the packager refuse on a duplicate leaf name. The archive contains exactly the hashed set (P81).

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
import shutil
import subprocess
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


_UNTRACKED_NOISE = ("__pycache__",)
_UNTRACKED_SUFFIXES = (".pyc", ".pyo", ".tmp")
_UNTRACKED_NAMES = (".DS_Store",)   # P81 B-4: Finder writes it into any browsed folder of a downloaded copy


class UntrackedSkill(ValueError):
    """A skill directory inside a checkout with no tracked files (P81 B-2): hashing it would record the
    empty digest and 'verify' content git has never seen."""


def _git_tracked(d):
    """None when d is not inside a git checkout (or git is missing); else the tracked, present, relative
    paths -- possibly [] for an un-added directory. The two cases MUST stay distinct: P80 treated both as
    'the tracked set', so an un-added skill hashed to sha256(b'')."""
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--", "."], cwd=str(d), capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return sorted(Path(f) for f in out.stdout.decode("utf-8").split("\0") if f and (d / f).is_file())


def _source_files(d):
    """The files that ARE the skill, relative to d: the git-tracked set inside a checkout (P80: a
    __pycache__ written by a second interpreter must never move the hash), else every file that is not
    interpreter/editor/Finder noise (a downloaded copy has no git). P81 B-1: package() and tree_sha()
    both use THIS set, so the manifest anchors exactly what the .skill archive contains."""
    d = Path(d)
    tracked = _git_tracked(d)
    disk = sorted(x.relative_to(d) for x in d.rglob("*") if x.is_file()
                  and not any(part in _UNTRACKED_NOISE for part in x.relative_to(d).parts)
                  and x.suffix not in _UNTRACKED_SUFFIXES and x.name not in _UNTRACKED_NAMES
                  and ".local." not in x.name)
    if tracked is None:
        return disk
    if not tracked and disk:
        raise UntrackedSkill(f"{d.name}: no tracked files (git add the skill before packaging or reconciling it)")
    return tracked


def tree_sha(d):
    """sha256 over the skill's SOURCE tree: sorted relative paths + file bytes, NUL-delimited.
    mtime-free and deterministic, unlike the zip; untracked noise (__pycache__, *.pyc) excluded."""
    d = Path(d)
    h = hashlib.sha256()
    for rel in _source_files(d):
        h.update(str(rel).encode("utf-8")); h.update(b"\0")
        h.update((d / rel).read_bytes()); h.update(b"\0")
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
           "skills": {}}
    for d in dirs:
        try:
            man["skills"][d.name] = tree_sha(d)
        except UntrackedSkill as exc:
            print(f"package-manifest: {exc}")
            return 1
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
    cur, untracked = {}, []
    for d in dirs:
        try:
            cur[d.name] = tree_sha(d)
        except UntrackedSkill as exc:
            print(f"package-manifest: {exc}")
            untracked.append(f"<untracked:{d.name}>")
    drift = untracked + sorted(set(man) ^ set(cur)) + sorted(k for k in man.keys() & cur.keys() if man[k] != cur[k])
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
    try:
        files = _source_files(skill_dir)
    except UntrackedSkill as exc:
        print(f"  REFUSE {rel}: {exc}")
        return False
    DIST.mkdir(exist_ok=True)
    out = DIST / f"{skill_dir.name}.skill"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in files:                       # P81 B-1: the SAME set tree_sha() hashes
            zf.write(skill_dir / r, str(Path(skill_dir.name) / r))
    print(f"  OK   {rel} -> dist/{out.name}")
    return True


def selftest():
    import tempfile
    checks = []
    ok = lambda name, cond: checks.append((name, bool(cond)))
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        subprocess.run(["git", "init", "-q", td], check=True)
        subprocess.run(["git", "-C", td, "config", "user.email", "fixture@example.com"], check=True)
        subprocess.run(["git", "-C", td, "config", "user.name", "fixture"], check=True)
        fm = "---\nname: {n}\ndescription: fixture\n---\nbody\n"
        for n in ("alpha", "beta"):
            d = root / "skills" / n; d.mkdir(parents=True)
            (d / "SKILL.md").write_text(fm.format(n=n)); (d / "notes.md").write_text(n)
        man = root / "implementation" / "skill-package-manifest.json"
        try:
            tree_sha(root / "skills" / "alpha")
            ok("an un-added skill is refused, never hashed empty (P81 B-2)", False)
        except UntrackedSkill:
            ok("an un-added skill is refused, never hashed empty (P81 B-2)", True)
        subprocess.run(["git", "-C", td, "add", "-A"], check=True)
        ok("reconcile writes a manifest with one hash per skill",
           reconcile_manifest(root, man) == 0 and len(json.loads(man.read_text())["skills"]) == 2)
        ok("check is clean right after reconcile", check_manifest(root, man)[1] == 0)
        ok("tree hash is deterministic across passes", tree_sha(root / "skills" / "alpha") == tree_sha(root / "skills" / "alpha"))
        _before = tree_sha(root / "skills" / "alpha")
        (root / "skills" / "alpha" / "scripts" / "__pycache__").mkdir(parents=True)
        (root / "skills" / "alpha" / "scripts" / "__pycache__" / "score.cpython-312.pyc").write_bytes(b"\x00magic")
        (root / "skills" / "alpha" / "notes.local.json").write_text("{}")
        (root / "skills" / "alpha" / ".DS_Store").write_bytes(b"\x00")
        ok("interpreter, local, and Finder noise never move the tree hash (P80, P81)",
           tree_sha(root / "skills" / "alpha") == _before)
        out = root / "alpha.skill"
        with zipfile.ZipFile(out, "w") as zf:
            for r in _source_files(root / "skills" / "alpha"):
                zf.write(root / "skills" / "alpha" / r, str(Path("alpha") / r))
        ok("the archive contains exactly the hashed set (P81 B-1)",
           sorted(zipfile.ZipFile(out).namelist()) == ["alpha/SKILL.md", "alpha/notes.md"])
        (root / "skills" / "alpha" / "notes.md").write_text("edited")
        drift, code = check_manifest(root, man)
        ok("an edited skill file drifts the check (exit 1, skill named)", code == 1 and drift == ["alpha"])
        (root / "skills" / "gamma").mkdir(); (root / "skills" / "gamma" / "SKILL.md").write_text(fm.format(n="gamma"))
        drift, code = check_manifest(root, man)
        ok("an un-added new skill is reported, not hashed", code == 1 and "<untracked:gamma>" in drift)
        subprocess.run(["git", "-C", td, "add", "-A"], check=True)
        ok("reconcile clears both once the skill is tracked",
           reconcile_manifest(root, man) == 0 and check_manifest(root, man)[1] == 0)
        dup = root / "skills" / "atoms" / "alpha"; dup.mkdir(parents=True); (dup / "SKILL.md").write_text(fm.format(n="alpha"))
        subprocess.run(["git", "-C", td, "add", "-A"], check=True)
        ok("duplicate leaf names are refused by reconcile", reconcile_manifest(root, man) == 1)
        ok("duplicate leaf names are refused by check", check_manifest(root, man)[1] == 1)
        # the non-git branch: a copied tree has no .git, so the noise filter is what protects it
        copy_parent = Path(tempfile.mkdtemp())
        copy = copy_parent / "alpha"
        shutil.copytree(root / "skills" / "alpha", copy)
        ok("a downloaded (non-git) copy filters noise instead of refusing",
           _source_files(copy) == [Path("SKILL.md"), Path("notes.md")])
        shutil.rmtree(copy_parent)
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
