#!/usr/bin/env python3
"""Creator OS skill packager.

Zips a skill directory into dist/<name>.skill (a zip archive) after a minimal validity check
(SKILL.md present with name + description frontmatter). Used in CI to confirm every skill is
installable.

Packaging integrity (P79 WP-D): the .skill zips embed file mtimes and are not reproducible, so the
integrity anchor is a sha256 over each skill's SOURCE TREE (relative paths in POSIX form, sorted by
their components, each with the file's LF-normalised bytes per tools/file_hash.py; P101), recorded
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

Org-distribution facts (support.claude.com article 13837433 + Desktop changelog, fetched
2026-09-19): the manual marketplace-ZIP route caps at 50 MB per plugin and 100 plugins; a zip
whose top level is a single component folder (e.g. `skills/`) installs with nothing (Desktop fix
note 2026-08-27), so bundle from the plugin root; hosted `url` marketplaces deliver plugins as
zips and require `manifestSha256` for auto-install; admins can disable user marketplaces and
skill creation (`userPluginMarketplacesEnabled`, `skillCreationEnabled`).
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

try:
    import file_hash
except ImportError:  # loaded by file path with tools/ not on sys.path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import file_hash

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
_UNTRACKED_NAMES = (".DS_Store",)   # P81: Finder writes it into any browsed folder of a downloaded copy


class UntrackedSkill(ValueError):
    """A skill directory inside a checkout with no tracked files (P81): hashing it would record the
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
    interpreter/editor/Finder noise (a downloaded copy has no git). P81: package() and tree_sha()
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
    """sha256 over the skill's SOURCE tree: relative paths in POSIX form, sorted by their components,
    each followed by the file's LF-normalised bytes (tools/file_hash.py), NUL-delimited. mtime-free
    and deterministic, unlike the zip; untracked noise (__pycache__, *.pyc) excluded. P101: the
    POSIX form, the component sort and the normalised bytes make a Windows checkout (backslash
    paths, case-insensitive Path ordering, CRLF conversion) record the hash the Linux CI recorded."""
    d = Path(d)
    h = hashlib.sha256()
    names = sorted((rel.as_posix() for rel in _source_files(d)), key=lambda n: tuple(n.split("/")))
    for name in names:
        h.update(name.encode("utf-8")); h.update(b"\0")
        h.update(file_hash.normalise((d / name).read_bytes())); h.update(b"\0")
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
    man = {"_comment": "P79 packaging integrity: sha256 per skill SOURCE TREE (relative paths in POSIX "
                       "form sorted by component, each followed by the file's bytes with text line "
                       "endings folded to LF (P101), NUL-delimited; mtime-free). Verify with "
                       "`python3 tools/package_skill.py "
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
        for r in files:                       # P81: the SAME set tree_sha() hashes
            zf.write(skill_dir / r, str(Path(skill_dir.name) / r))
    print(f"  OK   {rel} -> dist/{out.name}")
    return True


# P90: repo-root references a skill makes to canonical engine/protocol files. In-repo these
# resolve (the drift guard enforces it); in a lone uploaded ZIP they dangle, which is why zero
# skills survive standalone upload without this exporter.
_REF_RE = re.compile(r"\b(?:shared|protocols)/[\w][\w./-]*\.md\b")
_TEXT_SUFFIXES = {".md", ".json", ".txt", ".yaml", ".yml"}
_STANDALONE_NOTE = (
    "This is a STANDALONE export of one Creator OS skill for uploading to claude.ai\n"
    "(Customize > Skills). The shared engine and protocol files it references are bundled\n"
    "under references/upstream/ and the references are rewritten to point there, so the\n"
    "skill's knowledge travels intact. What does NOT travel: multi-skill orchestration\n"
    "(workflows composing other skills) -- that needs the Creator OS plugin or the computer\n"
    "setup. Source and updates: github.com/flywifi/seo-tools\n")


def package_standalone(skill_dir, dist_root=None, repo_root=ROOT):
    """Build <dist>/standalone/<name>.zip: the skill plus embedded copies of every shared/ or
    protocols/ markdown file its text files reference, with the references rewritten to the
    embedded path IN THE PACKAGED COPY ONLY (a build transform, same class as the combined
    knowledge pack; repo files are untouched). Returns (out_path, sorted_refs) on success or
    (None, reason). A referenced file missing on disk is a refusal, not a silent drop."""
    skill_dir = Path(skill_dir)
    ok, reason = valid(skill_dir)
    if not ok:
        return None, f"{skill_dir.name}: {reason}"
    try:
        files = _source_files(skill_dir)
    except UntrackedSkill as exc:
        return None, str(exc)
    texts, refs = {}, set()
    for r in files:
        p = skill_dir / r
        if p.suffix in _TEXT_SUFFIXES:
            t = p.read_text(encoding="utf-8", errors="replace")
            texts[r] = t
            for m in _REF_RE.finditer(t):
                refs.add(m.group(0))
    missing = [x for x in sorted(refs) if not (Path(repo_root) / x).is_file()]
    if missing:
        return None, f"{skill_dir.name}: referenced file(s) missing on disk: {missing}"
    rewrite = {ref: f"references/upstream/{ref}" for ref in refs}
    dist = Path(dist_root) if dist_root else DIST
    out_dir = dist / "standalone"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{skill_dir.name}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in files:
            arc = str(Path(skill_dir.name) / r)
            if r in texts:
                body = texts[r]
                # Longest ref first, so one rewritten path can never be re-hit by a shorter
                # ref that happens to be its substring.
                for ref in sorted(rewrite, key=len, reverse=True):
                    body = body.replace(ref, rewrite[ref])
                zf.writestr(arc, body)
            else:
                zf.write(skill_dir / r, arc)
        for ref in sorted(refs):
            zf.write(Path(repo_root) / ref,
                     str(Path(skill_dir.name) / "references" / "upstream" / ref))
        zf.writestr(str(Path(skill_dir.name) / "STANDALONE-NOTE.txt"), _STANDALONE_NOTE)
    return out, sorted(refs)


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
            # Bytes, so the tree is LF on every platform (text mode writes CRLF on Windows).
            (d / "SKILL.md").write_bytes(fm.format(n=n).encode()); (d / "notes.md").write_bytes((n + "\nmore\n").encode())
        man = root / "implementation" / "skill-package-manifest.json"
        try:
            tree_sha(root / "skills" / "alpha")
            ok("an un-added skill is refused, never hashed empty (P81)", False)
        except UntrackedSkill:
            ok("an un-added skill is refused, never hashed empty (P81)", True)
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
        # P101: a checkout that converted a skill file's line endings (core.autocrlf=true) records
        # the same tree hash.
        notes = root / "skills" / "alpha" / "notes.md"
        lf_notes = notes.read_bytes()
        notes.write_bytes(b"alpha\r\nmore\r\n")
        ok("a CRLF copy of a skill file does not move the tree hash (P101)",
           lf_notes == b"alpha\nmore\n" and tree_sha(root / "skills" / "alpha") == _before)
        out = root / "alpha.skill"
        with zipfile.ZipFile(out, "w") as zf:
            for r in _source_files(root / "skills" / "alpha"):
                zf.write(root / "skills" / "alpha" / r, str(Path("alpha") / r))
        ok("the archive contains exactly the hashed set (P81)",
           sorted(zipfile.ZipFile(out).namelist()) == ["alpha/SKILL.md", "alpha/notes.md"])
        # P101: the paths a Windows checkout yields (backslash separators, and Path ordering that
        # ignores case, which puts notes.md before SKILL.md and Zeta.md) hash like POSIX ones. The
        # nested names sort differently by component than as strings ('a/z.md' before 'a-b/y.md',
        # 'notes/x.md' before 'notes.md'), and the PNG carries CR bytes that must stay raw. Only
        # these files are added, so the interpreter noise planted above stays untracked.
        from pathlib import PurePosixPath, PureWindowsPath
        alpha = root / "skills" / "alpha"
        added = {"Zeta.md": b"zeta\n", "references/guide.md": b"guide\n", "a-b/y.md": b"y\n",
                 "a/z.md": b"z\n", "notes/x.md": b"x\n",
                 "assets/logo.png": b"\x89PNG\r\n\x1a\n\x00\x00IHDR\r\n"}
        for rel, data in added.items():
            (alpha / rel).parent.mkdir(parents=True, exist_ok=True)
            (alpha / rel).write_bytes(data)
        subprocess.run(["git", "-C", td, "add", "--"] + [f"skills/alpha/{r}" for r in added], check=True)
        g = globals()
        real_sources = g["_source_files"]
        hashed = sorted(r.as_posix() for r in real_sources(alpha))
        ok("the hashed set holds the nested files and none of the noise",
           hashed == sorted(["SKILL.md", "notes.md"] + list(added)))
        ok("the fixture names order differently as strings than by component",
           sorted(hashed) != sorted(hashed, key=lambda n: tuple(n.split("/"))))
        for rel in hashed:   # an LF tree on every platform (text mode writes CRLF on Windows)
            (alpha / rel).write_bytes(file_hash.normalise((alpha / rel).read_bytes()))
        posix_form = tree_sha(alpha)
        h = hashlib.sha256()   # the pre-P101 recipe: sorted Path objects, str(rel), raw bytes
        for rel in sorted(PurePosixPath(r) for r in hashed):
            h.update(str(rel).encode("utf-8")); h.update(b"\0")
            h.update((alpha / rel).read_bytes()); h.update(b"\0")
        ok("on an LF tree the tree hash equals the pre-P101 recipe, so no recorded hash moves",
           posix_form == h.hexdigest())
        try:
            g["_source_files"] = lambda sd: sorted(PureWindowsPath(r.as_posix()) for r in real_sources(sd))
            ok("the simulated Windows listing really is in case-insensitive order",
               [str(r) for r in g["_source_files"](alpha)][-2:] == ["SKILL.md", "Zeta.md"])
            windows_form = tree_sha(alpha)
        finally:
            g["_source_files"] = real_sources
        ok("Windows-form paths hash to the POSIX tree hash (P101)", windows_form == posix_form)
        png = alpha / "assets" / "logo.png"
        png.write_bytes(png.read_bytes().replace(b"\r\n", b"\n"))
        ok("a binary file keeps its raw bytes: folding its CRs moves the tree hash", tree_sha(alpha) != posix_form)
        png.write_bytes(added["assets/logo.png"])
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
        ok("a downloaded (non-git) copy filters noise instead of refusing",   # P101: compared as
           sorted(p.as_posix() for p in _source_files(copy)) == sorted(["SKILL.md", "notes.md"] + list(added)))  # POSIX strings, so Path's case-insensitive order on Windows does not fail it
        shutil.rmtree(copy_parent)
        # P90: the standalone exporter. First the failing state the exporter exists to fix
        # (detector-can-fail proof): a PLAIN zip of a skill that references a shared engine
        # dangles -- the token is inside, the engine is not.
        eng = root / "shared" / "fixture-engine.md"
        eng.parent.mkdir(parents=True, exist_ok=True)
        eng.write_text("engine body", encoding="utf-8")
        beta = root / "skills" / "beta"
        (beta / "SKILL.md").write_text(fm.format(n="beta")
                                       + "\nLoad shared/fixture-engine.md first.\n",
                                       encoding="utf-8")
        subprocess.run(["git", "-C", td, "add", "-A"], check=True)
        plain = root / "beta-plain.zip"
        with zipfile.ZipFile(plain, "w") as zf:
            for r in _source_files(beta):
                zf.write(beta / r, str(Path("beta") / r))
        _pz = zipfile.ZipFile(plain)
        ok("PLAIN zip dangles: the reference is inside, the engine is not (the P90 defect)",
           "shared/fixture-engine.md" in _pz.read("beta/SKILL.md").decode("utf-8")
           and not any("fixture-engine" in n for n in _pz.namelist()))
        outp, refs = package_standalone(beta, dist_root=root / "dist", repo_root=root)
        _sz = zipfile.ZipFile(outp)
        _body = _sz.read("beta/SKILL.md").decode("utf-8")
        ok("standalone zip bundles the engine under references/upstream/",
           "beta/references/upstream/shared/fixture-engine.md" in _sz.namelist())
        ok("standalone SKILL.md points at the bundled copy, no repo-root token left",
           "references/upstream/shared/fixture-engine.md" in _body
           and not re.search(r"(?<!references/upstream/)\bshared/fixture-engine\.md", _body))
        ok("standalone zip carries the honesty note",
           "beta/STANDALONE-NOTE.txt" in _sz.namelist())
        (beta / "SKILL.md").write_text(fm.format(n="beta")
                                       + "\nLoad shared/missing-engine.md first.\n",
                                       encoding="utf-8")
        subprocess.run(["git", "-C", td, "add", "-A"], check=True)
        outp, reason = package_standalone(beta, dist_root=root / "dist", repo_root=root)
        ok("a dangling reference is a refusal, never a silent drop",
           outp is None and "missing" in str(reason))
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
    if "--standalone-all" in argv:
        oks = 0
        dirs = list(skill_dirs())
        for d in dirs:
            out, info = package_standalone(d)
            if out is None:
                print(f"  SKIP {d.name}: {info}")
            else:
                oks += 1
        print(f"standalone-packaged {oks}/{len(dirs)} skills -> {DIST / 'standalone'}")
        return 0 if oks else 1
    if "--standalone" in argv:
        i = argv.index("--standalone")
        name = argv[i + 1] if len(argv) > i + 1 else ""
        matches = [d for d in skill_dirs() if d.name == name]
        if not matches:
            print(f"no skill named {name!r}")
            return 1
        out, info = package_standalone(matches[0])
        if out is None:
            print(f"REFUSE {name}: {info}")
            return 1
        print(f"OK {name} -> {out} (bundled {len(info)} referenced file(s))")
        return 0
    name = argv[0]
    matches = [d for d in skill_dirs() if d.name == name]
    if not matches:
        print(f"no skill named {name!r}")
        return 1
    return 0 if package(matches[0]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
