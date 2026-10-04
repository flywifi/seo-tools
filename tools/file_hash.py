#!/usr/bin/env python3
"""file_hash.py -- the hash of a tracked file, the same on a CRLF checkout as on an LF one (P101).

Why this exists: battery gates store a sha256 of tracked files and recompute it from the bytes on
disk (doc freshness, the Mac-surface manifest, the knowledge-projection manifest, the skill-package
manifest), and `tools/hash_audit.py` re-verifies those stores and the GIS boundary manifest. Git
for Windows and the Scoop build default to `core.autocrlf=true`, which checks text files out with
CRLF line endings. On the first Windows run of the battery the checkout had converted the tracked
text files, and the hashes those stores record mismatched. `.gitattributes` now asks for LF
checkouts of text files (`* text=auto eol=lf`, batch files CRLF for cmd.exe), and this module makes
the hashes indifferent to the conversion for clones checked out before that rule existed.

What it computes: for a TEXT file, the sha256 of its bytes with CRLF and lone CR folded to LF; a
BINARY file is hashed raw. For valid UTF-8 text the folded bytes equal
`Path.read_text(encoding="utf-8").encode("utf-8")` (universal newlines fold only CR and CRLF), and
on an LF checkout they equal the raw bytes, so no committed hash moved. A file is binary when a NUL
byte sits in its first 8000 bytes, the sniff git's diff uses (xdiff-interface.c, buffer_is_binary).
Git's end-of-line conversion is stricter: convert.c's convert_is_binary leaves a file alone when it
has a NUL anywhere, a lone CR, or mostly non-printable bytes, and git 2.43 converted none of those
in a probe. So every file git converts is folded here, and a file git leaves alone has the same bytes
on every checkout; either way its hash does not depend on the checkout.

Use it wherever a stored hash of a tracked file is written or verified. A store whose writer hashes
raw bytes on the same machine that verifies them (a fetched document, a locally built baseline)
keeps its raw hasher: writer and verifier must agree.

`windows_paths()` is a test helper: inside it, `PosixPath.relative_to` returns a `PureWindowsPath`,
so a selftest on Linux builds the backslash key a Windows checkout would build and can prove that a
lookup keys by `relative_to(...).as_posix()`. It patches nothing else: a key built with `os.sep`,
`os.path.relpath`, `str()` of a path, or a case-folded comparison is not simulated, so a module
that builds a key another way needs its own case (`tools/migrate_local.py` resolves both paths
and has a relative-path case). On Windows the patched class is never used and `relative_to`
already yields backslashes, so the same selftests run there unchanged.

  python3 tools/file_hash.py <path>...     # print the hash of each path
  python3 tools/file_hash.py --selftest    # the properties above, plus the committed mutations
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import pathlib
import sys
from pathlib import Path

# git's diff binary sniff reads this many bytes for a NUL (xdiff-interface.c FIRST_FEW_BYTES).
TEXT_SNIFF_BYTES = 8000


def is_text(raw: bytes) -> bool:
    """True when no NUL byte sits in the first TEXT_SNIFF_BYTES bytes."""
    return b"\x00" not in raw[:TEXT_SNIFF_BYTES]


def normalise(raw: bytes) -> bytes:
    """Text bytes with CRLF and lone CR folded to LF; binary bytes unchanged."""
    if not is_text(raw):
        return raw
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_bytes(raw: bytes) -> str:
    """sha256 of normalise(raw), as a hex string."""
    return hashlib.sha256(normalise(raw)).hexdigest()


def sha256_file(path) -> str:
    """sha256_bytes of the file's contents."""
    return sha256_bytes(Path(path).read_bytes())


@contextlib.contextmanager
def windows_paths():
    """Test helper: PosixPath.relative_to returns a PureWindowsPath while the block runs, so str()
    of a relative path has backslashes (as on a Windows checkout) and as_posix() has slashes."""
    cls = pathlib.PosixPath
    own = "relative_to" in vars(cls)
    real = cls.relative_to

    def relative_to(self, *args, **kwargs):
        return pathlib.PureWindowsPath(real(self, *args, **kwargs).as_posix())

    cls.relative_to = relative_to
    try:
        yield
    finally:
        if own:
            cls.relative_to = real
        else:
            del cls.relative_to


# --- selftest: everything below is test code; the committed mutations apply above this line ---
_SELFTEST_MARK = "# --- selftest: everything below is test code; the committed mutations apply above this line ---\n"
_IN_MUTANT = False
MIN_MUTANTS_PER_MODULE = 3

# (label, module file under tools/, anchor, replacement). Each anchor occurs exactly once in the
# module (in file_hash.py, once above the selftest marker); the mutated module's selftest() must
# fail. Chosen by reviewers who did not write the change (docs/AUDIT-PROTOCOL.md section 7.2).
# Every module that hashes through this one or simulates Windows paths with windows_paths()
# carries at least MIN_MUTANTS_PER_MODULE rows.
_MUTANTS = (
    ('lone-cr-not-folded', 'file_hash.py',
     'return raw.replace(b"\\r\\n", b"\\n").replace(b"\\r", b"\\n")',
     'return raw.replace(b"\\r\\n", b"\\n")'),
    ('crlf-not-folded', 'file_hash.py',
     'return raw.replace(b"\\r\\n", b"\\n").replace(b"\\r", b"\\n")',
     'return raw.replace(b"\\r", b"\\n")'),
    ('sniff-whole-file', 'file_hash.py',
     'return b"\\x00" not in raw[:TEXT_SNIFF_BYTES]',
     'return b"\\x00" not in raw'),
    ('sniff-window-empty', 'file_hash.py',
     'return b"\\x00" not in raw[:TEXT_SNIFF_BYTES]',
     'return b"\\x00" not in raw[:0]'),
    ('sniff-window-short-by-one', 'file_hash.py',
     'return b"\\x00" not in raw[:TEXT_SNIFF_BYTES]',
     'return b"\\x00" not in raw[:TEXT_SNIFF_BYTES - 1]'),
    ('sniff-window-long-by-one', 'file_hash.py',
     'return b"\\x00" not in raw[:TEXT_SNIFF_BYTES]',
     'return b"\\x00" not in raw[:TEXT_SNIFF_BYTES + 1]'),
    ('sniff-window-8192', 'file_hash.py',
     'TEXT_SNIFF_BYTES = 8000',
     'TEXT_SNIFF_BYTES = 8192'),
    ('binary-folded', 'file_hash.py',
     '    if not is_text(raw):\n        return raw\n',
     ''),
    ('fold-stops-at-window', 'file_hash.py',
     'return raw.replace(b"\\r\\n", b"\\n").replace(b"\\r", b"\\n")',
     'return raw[:TEXT_SNIFF_BYTES].replace(b"\\r\\n", b"\\n").replace(b"\\r", b"\\n") + raw[TEXT_SNIFF_BYTES:]'),
    ('lone-cr-means-binary', 'file_hash.py',
     'return b"\\x00" not in raw[:TEXT_SNIFF_BYTES]',
     'import re; return b"\\x00" not in raw[:TEXT_SNIFF_BYTES] and not re.search(rb"\\r(?!\\n)", raw)'),
    ('bom-stripped', 'file_hash.py',
     'return raw.replace(b"\\r\\n", b"\\n").replace(b"\\r", b"\\n")',
     'return raw.replace(b"\\r\\n", b"\\n").replace(b"\\r", b"\\n").removeprefix(b"\\xef\\xbb\\xbf")'),
    ('bytes-hash-raw', 'file_hash.py',
     'return hashlib.sha256(normalise(raw)).hexdigest()',
     'return hashlib.sha256(raw).hexdigest()'),
    ('file-hash-raw', 'file_hash.py',
     'return sha256_bytes(Path(path).read_bytes())',
     'return hashlib.sha256(Path(path).read_bytes()).hexdigest()'),
    ('file-hash-truncated', 'file_hash.py',
     'return sha256_bytes(Path(path).read_bytes())',
     'return sha256_bytes(Path(path).read_bytes()[:TEXT_SNIFF_BYTES])'),
    ('file-hash-text-mode', 'file_hash.py',
     'return sha256_bytes(Path(path).read_bytes())',
     'return sha256_bytes(Path(path).read_text(encoding="utf-8", errors="surrogateescape").encode("utf-8", "surrogateescape"))'),
    ('fold-lossy-decode', 'file_hash.py',
     'return raw.replace(b"\\r\\n", b"\\n").replace(b"\\r", b"\\n")',
     'return raw.decode("utf-8", "replace").replace("\\r\\n", "\\n").replace("\\r", "\\n").encode("utf-8")'),
    ('winpaths-identity', 'file_hash.py',
     '        return pathlib.PureWindowsPath(real(self, *args, **kwargs).as_posix())',
     '        return real(self, *args, **kwargs)'),
    ('docfresh-sha-raw', 'doc_freshness.py',
     '    return file_hash.sha256_file(path)',
     '    import hashlib; return hashlib.sha256(path.read_bytes()).hexdigest()'),
    ('docfresh-check-raw', 'doc_freshness.py',
     '            if rec.get(s) != _sha(p):',
     '            if rec.get(s) != __import__("hashlib").sha256(p.read_bytes()).hexdigest():'),
    ('docfresh-reconcile-raw', 'doc_freshness.py',
     '            rec[s] = _sha(p) if p.exists() else None',
     '            rec[s] = __import__("hashlib").sha256(p.read_bytes()).hexdigest() if p.exists() else None'),
    ('docfresh-lone-cr-kept', 'doc_freshness.py',
     '    return file_hash.sha256_file(path)',
     '    return file_hash.hashlib.sha256(path.read_bytes().replace(b"\\r\\n", b"\\n")).hexdigest()'),
    ('docfresh-binary-folded', 'doc_freshness.py',
     '    return file_hash.sha256_file(path)',
     '    return file_hash.hashlib.sha256(path.read_bytes().replace(b"\\r\\n", b"\\n").replace(b"\\r", b"\\n")).hexdigest()'),
    ('docfresh-sha-constant', 'doc_freshness.py',
     '    return file_hash.sha256_file(path)',
     '    return file_hash.sha256_bytes(b"")'),
    ('docfresh-lf-hash-moves', 'doc_freshness.py',
     '    return file_hash.sha256_file(path)',
     '    return file_hash.hashlib.sha256(b"\\n".join(file_hash.Path(path).read_bytes().splitlines())).hexdigest()'),
    ('projection-sha-raw', 'projection_manifest.py',
     '    return file_hash.sha256_file(path)',
     '    import hashlib; return hashlib.sha256(path.read_bytes()).hexdigest()'),
    ('projection-check-source-raw', 'projection_manifest.py',
     '            if rec.get(s) != _sha(p):',
     '            if rec.get(s) != __import__("hashlib").sha256(p.read_bytes()).hexdigest():'),
    ('projection-check-self-raw', 'projection_manifest.py',
     '            edited = pinned is not None and pinned != _sha(pp)',
     '            edited = pinned is not None and pinned != __import__("hashlib").sha256(pp.read_bytes()).hexdigest()'),
    ('projection-reconcile-source-raw', 'projection_manifest.py',
     '            rec[s] = _sha(p) if p.exists() else None',
     '            rec[s] = __import__("hashlib").sha256(p.read_bytes()).hexdigest() if p.exists() else None'),
    ('projection-reconcile-self-raw', 'projection_manifest.py',
     '"projection": _sha(pp) if pp.exists() else None',
     '"projection": __import__("hashlib").sha256(pp.read_bytes()).hexdigest() if pp.exists() else None'),
    ('projection-sha-constant', 'projection_manifest.py',
     '    return file_hash.sha256_file(path)',
     '    return file_hash.sha256_bytes(b"")'),
    ('mac-sha-raw', 'mac_surface_manifest.py',
     '    return file_hash.sha256_file(path)',
     '    import hashlib; return hashlib.sha256(path.read_bytes()).hexdigest()'),
    ('mac-check-raw', 'mac_surface_manifest.py',
     '        elif _sha(p) != sha:',
     '        elif hashlib.sha256(p.read_bytes()).hexdigest() != sha:'),
    ('mac-check-never-changed', 'mac_surface_manifest.py',
     '        elif _sha(p) != sha:',
     '        elif False:'),
    ('mac-reconcile-raw', 'mac_surface_manifest.py',
     '        files[rel] = _sha(root / rel)',
     '        files[rel] = hashlib.sha256((root / rel).read_bytes()).hexdigest()'),
    ('mac-deriver-pin-raw', 'mac_surface_manifest.py',
     '"module_sha256": _sha(Path(__file__).resolve()),',
     '"module_sha256": hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest(),'),
    ('mac-deriver-check-raw', 'mac_surface_manifest.py',
     'pin["module_sha256"] != _sha(mod)',
     'pin["module_sha256"] != hashlib.sha256(mod.read_bytes()).hexdigest()'),
    ('mac-sha-constant', 'mac_surface_manifest.py',
     '    return file_hash.sha256_file(path)',
     '    return file_hash.sha256_bytes(b"")'),
    ('mac-lf-hash-moves', 'mac_surface_manifest.py',
     '    return file_hash.sha256_file(path)',
     '    return file_hash.hashlib.sha256(b"\\n".join(file_hash.Path(path).read_bytes().splitlines())).hexdigest()'),
    ('tree-key-native-hash-only', 'package_skill.py',
     'names = sorted((rel.as_posix() for rel in _source_files(d)), key=lambda n: tuple(n.split("/")))\n    for name in names:\n        h.update(name.encode("utf-8")); h.update(b"\\0")\n        h.update(file_hash.normalise((d / name).read_bytes())); h.update(b"\\0")',
     'rels = sorted(_source_files(d), key=lambda r: tuple(r.as_posix().split("/")))\n    for rel in rels:\n        h.update(str(rel).encode("utf-8")); h.update(b"\\0")\n        h.update(file_hash.normalise((d / rel.as_posix()).read_bytes())); h.update(b"\\0")'),
    ('tree-string-sort', 'package_skill.py',
     'names = sorted((rel.as_posix() for rel in _source_files(d)), key=lambda n: tuple(n.split("/")))',
     'names = sorted(rel.as_posix() for rel in _source_files(d))'),
    ('tree-unsorted', 'package_skill.py',
     'names = sorted((rel.as_posix() for rel in _source_files(d)), key=lambda n: tuple(n.split("/")))',
     'names = [rel.as_posix() for rel in _source_files(d)]'),
    ('tree-path-object-sort', 'package_skill.py',
     'names = sorted((rel.as_posix() for rel in _source_files(d)), key=lambda n: tuple(n.split("/")))',
     'names = [rel.as_posix() for rel in sorted(_source_files(d))]'),
    ('tree-case-folded-sort', 'package_skill.py',
     'names = sorted((rel.as_posix() for rel in _source_files(d)), key=lambda n: tuple(n.split("/")))',
     'names = sorted((rel.as_posix() for rel in _source_files(d)), key=lambda n: tuple(n.lower().split("/")))'),
    ('tree-bytes-raw', 'package_skill.py',
     'h.update(file_hash.normalise((d / name).read_bytes()))',
     'h.update((d / name).read_bytes())'),
    ('tree-binary-folded', 'package_skill.py',
     'h.update(file_hash.normalise((d / name).read_bytes()))',
     'h.update((d / name).read_bytes().replace(b"\\r\\n", b"\\n").replace(b"\\r", b"\\n"))'),
    ('audit-mac-raw', 'hash_audit.py',
     'bad = [f for f, h in files.items() if not (root / f).exists() or _sha_tracked(root / f) != h]',
     'bad = [f for f, h in files.items() if not (root / f).exists() or _sha(root / f) != h]'),
    ('audit-projection-source-raw', 'hash_audit.py',
     'bad += (not (root / s).exists()) or _sha_tracked(root / s) != h\n        if rec.get("projection"):',
     'bad += (not (root / s).exists()) or _sha(root / s) != h\n        if rec.get("projection"):'),
    ('audit-projection-self-raw', 'hash_audit.py',
     'bad += (not (root / proj).exists()) or _sha_tracked(root / proj) != rec["projection"]',
     'bad += (not (root / proj).exists()) or _sha(root / proj) != rec["projection"]'),
    ('audit-docfresh-raw', 'hash_audit.py',
     'bad += (not (root / s).exists()) or _sha_tracked(root / s) != h\n    return (OK if not bad else MISMATCH)',
     'bad += (not (root / s).exists()) or _sha(root / s) != h\n    return (OK if not bad else MISMATCH)'),
    ('audit-gis-manifest-raw', 'hash_audit.py',
     'or _sha_tracked(base / (r["name"] + ".geojson")) != r.get("sha256"))',
     'or _sha(base / (r["name"] + ".geojson")) != r.get("sha256"))'),
    ('audit-gis-provenance-raw', 'hash_audit.py',
     'pb += (not tgt.exists()) or _sha_tracked(tgt) != d.get("sha256")',
     'pb += (not tgt.exists()) or _sha(tgt) != d.get("sha256")'),
    ('audit-tracked-hasher-raw', 'hash_audit.py',
     'return file_hash.sha256_file(p)',
     'return hashlib.sha256(p.read_bytes()).hexdigest()'),
    ('audit-construction-folded', 'hash_audit.py',
     'or _sha(lib / r["filename"]) != r.get("sha256")]',
     'or _sha_tracked(lib / r["filename"]) != r.get("sha256")]'),
    ('audit-cache-baseline-folded', 'hash_audit.py',
     'and ((not (root / k).exists()) or _sha(root / k) != v["sha256"])]',
     'and ((not (root / k).exists()) or _sha_tracked(root / k) != v["sha256"])]'),
    ('audit-raw-hasher-folds', 'hash_audit.py',
     '    return hashlib.sha256(p.read_bytes()).hexdigest()\n\n\ndef _sha_tracked',
     '    return file_hash.sha256_file(p)\n\n\ndef _sha_tracked'),
    ('geo-rehash-raw', 'geo_source_fetch.py',
     'rec["sha256"] = file_hash.sha256_bytes(raw)',
     'rec["sha256"] = __import__("hashlib").sha256(raw).hexdigest()'),
    ('geo-rehash-crlf-expanded', 'geo_source_fetch.py',
     'rec["sha256"] = file_hash.sha256_bytes(raw)',
     'rec["sha256"] = __import__("hashlib").sha256(raw.replace(b"\\n", b"\\r\\n")).hexdigest()'),
    ('geo-writer-crlf-raw', 'geo_source_fetch.py',
     'sha = file_hash.sha256_bytes(body.encode("utf-8"))',
     'sha = __import__("hashlib").sha256(body.encode("utf-8").replace(b"\\n", b"\\r\\n")).hexdigest()'),
    ('geo-writer-other-dump', 'geo_source_fetch.py',
     'sha = file_hash.sha256_bytes(body.encode("utf-8"))',
     'sha = file_hash.sha256_bytes(json.dumps(feature_collection, sort_keys=True).encode("utf-8"))'),
    ('bundle-check-key-native', 'build_freshness_bundle.py',
     'rel = f.relative_to(root).as_posix()  # P101: the manifest keys are POSIX paths on every platform',
     'rel = str(f.relative_to(root))'),
    ('bundle-apply-key-native', 'build_freshness_bundle.py',
     'stamped.append({"file": f.relative_to(root).as_posix(),  # P101: POSIX keys on every platform',
     'stamped.append({"file": str(f.relative_to(root)),'),
    ('bundle-membership-native', 'build_freshness_bundle.py',
     'if rel not in listed:',
     'if str(f.relative_to(root)) not in listed:'),
    ('bundle-sha-lookup-native', 'build_freshness_bundle.py',
     'rec = recorded.get(rel)',
     'rec = recorded.get(str(f.relative_to(root)))'),
    ('bundle-writer-and-reader-native', 'build_freshness_bundle.py',
     'stamped.append({"file": f.relative_to(root).as_posix(),  # P101: POSIX keys on every platform\n                        "sha256": hashlib.sha256(new.encode("utf-8")).hexdigest()})\n    manifest = {"_boundary": "Owner dev-time projection. Local working tree only; never auto-published, never GitHub.",\n                "as_of": as_of, "canonical_digest": digest, "managed_files": stamped,\n                "generated_by": "tools/build_freshness_bundle.py"}\n    (root / "implementation").mkdir(parents=True, exist_ok=True)\n    MANIFEST_PATH_ = root / "implementation" / "freshness-bundle.json"\n    MANIFEST_PATH_.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")\n    return manifest\n\n\ndef check(root=ROOT):\n    """Return (ok, problems). Fails when: the manifest is missing; a managed file lacks a freshness\n    marker; a managed file is missing; a managed file\'s bytes no longer match the sha256 recorded for\n    it (P79); or the manifest\'s canonical_digest no longer matches canonical (the baseline drifted\n    from the data and needs a re-stamp)."""\n    problems = []\n    mpath = root / "implementation" / "freshness-bundle.json"\n    if not mpath.exists():\n        return False, ["freshness-bundle.json manifest missing; run --apply"]\n    try:\n        manifest = json.loads(mpath.read_text(encoding="utf-8"))\n    except (OSError, json.JSONDecodeError) as exc:\n        return False, [f"manifest unreadable: {exc}"]\n    files = managed_files(root)\n    recorded = {m["file"]: m for m in manifest.get("managed_files", [])}\n    listed = set(recorded)\n    for f in files:\n        rel = f.relative_to(root).as_posix()  # P101: the manifest keys are POSIX paths on every platform',
     'stamped.append({"file": str(f.relative_to(root)),\n                        "sha256": hashlib.sha256(new.encode("utf-8")).hexdigest()})\n    manifest = {"_boundary": "Owner dev-time projection. Local working tree only; never auto-published, never GitHub.",\n                "as_of": as_of, "canonical_digest": digest, "managed_files": stamped,\n                "generated_by": "tools/build_freshness_bundle.py"}\n    (root / "implementation").mkdir(parents=True, exist_ok=True)\n    MANIFEST_PATH_ = root / "implementation" / "freshness-bundle.json"\n    MANIFEST_PATH_.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")\n    return manifest\n\n\ndef check(root=ROOT):\n    """Return (ok, problems). Fails when: the manifest is missing; a managed file lacks a freshness\n    marker; a managed file is missing; a managed file\'s bytes no longer match the sha256 recorded for\n    it (P79); or the manifest\'s canonical_digest no longer matches canonical (the baseline drifted\n    from the data and needs a re-stamp)."""\n    problems = []\n    mpath = root / "implementation" / "freshness-bundle.json"\n    if not mpath.exists():\n        return False, ["freshness-bundle.json manifest missing; run --apply"]\n    try:\n        manifest = json.loads(mpath.read_text(encoding="utf-8"))\n    except (OSError, json.JSONDecodeError) as exc:\n        return False, [f"manifest unreadable: {exc}"]\n    files = managed_files(root)\n    recorded = {m["file"]: m for m in manifest.get("managed_files", [])}\n    listed = set(recorded)\n    for f in files:\n        rel = str(f.relative_to(root))'),
    ('audit-template-key-native', 'local_audit.py',
     'rel_tmpl = tmpl.relative_to(root).as_posix()  # P101: the manifest keys are POSIX paths',
     'rel_tmpl = str(tmpl.relative_to(root))'),
    ('audit-file-key-native', 'local_audit.py',
     'rel = local.relative_to(root).as_posix()',
     'rel = str(local.relative_to(root))'),
    ('audit-note-lookup-native', 'local_audit.py',
     'm = manifest.get((rel_tmpl, str(expected)))',
     'm = manifest.get((str(tmpl.relative_to(root)), str(expected)))'),
    ('audit-report-template-native', 'local_audit.py',
     'entry = {"file": rel, "template": rel_tmpl,',
     'entry = {"file": rel, "template": str(tmpl.relative_to(root)),'),
    ('audit-unversioned-file-native', 'local_audit.py',
     'findings.append({"file": rel, "status": "unversioned",',
     'findings.append({"file": str(local.relative_to(root)), "status": "unversioned",'),
    ('audit-no-template-file-native', 'local_audit.py',
     'findings.append({"file": rel, "status": "no_template",',
     'findings.append({"file": str(local.relative_to(root)), "status": "no_template",'),
    ('audit-current-entry-file-native', 'local_audit.py',
     'entry = {"file": rel, "template": rel_tmpl,',
     'entry = {"file": rel if status == "behind" else str(local.relative_to(root)), "template": rel_tmpl,'),
    ('migrate-template-key-native', 'migrate_local.py',
     'rel_tmpl = tmpl_path.resolve().relative_to(root.resolve()).as_posix()',
     'rel_tmpl = str(tmpl_path.resolve().relative_to(root.resolve()))'),
    ('migrate-note-lookup-native', 'migrate_local.py',
     'm = manifest.get((rel_tmpl, str(expected))) or {}',
     'm = manifest.get((str(tmpl_path.relative_to(root)), str(expected))) or {}'),
    ('migrate-report-template-native', 'migrate_local.py',
     '"template": rel_tmpl,',
     '"template": str(tmpl_path.relative_to(root)),'),
    ('migrate-fallback-key-windows-str', 'migrate_local.py',
     '        rel_tmpl = tmpl_path.as_posix()',
     '        rel_tmpl = str(__import__("pathlib").PureWindowsPath(tmpl_path))'),
    ('migrate-root-branch-never', 'migrate_local.py',
     '        rel_tmpl = tmpl_path.resolve().relative_to(root.resolve()).as_posix()\n',
     '        raise ValueError\n'),
    ('sweep-enrolment-key-native', 'selftest_sweep.py',
     'discovered = {p.relative_to(ROOT).as_posix() for p, _ in discover()}',
     'discovered = {str(p.relative_to(ROOT)) for p, _ in discover()}'),
    ('sweep-self-key-native', 'selftest_sweep.py',
     'Path(__file__).resolve().relative_to(ROOT).as_posix())',
     'str(Path(__file__).resolve().relative_to(ROOT)))'),
    ('sweep-discovered-first-separator-only', 'selftest_sweep.py',
     'discovered = {p.relative_to(ROOT).as_posix() for p, _ in discover()}',
     'discovered = {str(p.relative_to(ROOT)).replace("\\\\", "/", 1) for p, _ in discover()}'),
    ('sweep-did-not-run-under-windows-form', 'selftest_sweep.py',
     '    tracked = _tracked_python()\n    if tracked is None:',
     '    tracked = _tracked_python()\n    if tracked is None or "\\\\" in str(EXEMPTION_PATH.relative_to(ROOT)):'),
    ('sweep-enrolment-key-absolute', 'selftest_sweep.py',
     'discovered = {p.relative_to(ROOT).as_posix() for p, _ in discover()}',
     'discovered = {p.as_posix() for p, _ in discover()}'),
    ('migration-key-native-separator', 'sync_check.py',
     'rel = f.relative_to(root).as_posix()  # P101: the manifest keys are POSIX paths on every platform',
     'rel = str(f.relative_to(root))'),
    ('migration-lookup-native', 'sync_check.py',
     'if (rel, sv) not in by_key:',
     'if (str(f.relative_to(root)), sv) not in by_key:'),
    ('migration-gap-name-native', 'sync_check.py',
     'out.append((rel, sv))',
     'out.append((str(f.relative_to(root)), sv))'),
    ('migration-key-first-separator-only', 'sync_check.py',
     'rel = f.relative_to(root).as_posix()  # P101: the manifest keys are POSIX paths on every platform',
     'rel = str(f.relative_to(root)).replace("\\\\", "/", 1)'),
    ('migration-version-key-wrong-field', 'sync_check.py',
     '        by_key[(m.get("template"), str(m.get("to")))] = m',
     '        by_key[(m.get("template"), str(m.get("from")))] = m'),
    ('pd-local-missing-str', 'project_docs.py',
     '            out["missing"].append(src.relative_to(ROOT).as_posix())',
     '            out["missing"].append(str(src.relative_to(ROOT)))'),
    ('pd-local-key-str', 'project_docs.py',
     '        rel = src.relative_to(ROOT).as_posix()\n        digest = _sha(src)',
     '        rel = str(src.relative_to(ROOT))\n        digest = _sha(src)'),
    ('pd-local-key-backslash', 'project_docs.py',
     '        rel = src.relative_to(ROOT).as_posix()\n        digest = _sha(src)',
     '        rel = src.relative_to(ROOT).as_posix().replace("/", "\\\\")\n        digest = _sha(src)'),
    ('pd-check-key-str', 'project_docs.py',
     '        rel = src.relative_to(ROOT).as_posix()\n        if not src.exists():',
     '        rel = str(src.relative_to(ROOT))\n        if not src.exists():'),
    ('pd-check-key-name', 'project_docs.py',
     '        rel = src.relative_to(ROOT).as_posix()\n        if not src.exists():',
     '        rel = src.name\n        if not src.exists():'),
    ('pd-api-key-str', 'project_docs.py',
     '        rel = src.relative_to(ROOT).as_posix()\n        content = src.read_bytes()',
     '        rel = str(src.relative_to(ROOT))\n        content = src.read_bytes()'),
    ('aio-msvcrt-nolock', 'atomic_io.py',
     '                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)\n                return',
     '                return'),
    ('aio-msvcrt-giveup', 'atomic_io.py',
     '                    raise   # a bad handle or argument is an error, not a lock to wait for\n                time.sleep(0.01)',
     '                    raise   # a bad handle or argument is an error, not a lock to wait for\n                return'),
    ('aio-msvcrt-norelease', 'atomic_io.py',
     '        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)',
     '        pass'),
    ('aio-dir-precheck-gone', 'atomic_io.py',
     '    if path.is_dir():\n        raise IsADirectoryError(errno.EISDIR, "is a directory", str(path))\n',
     ''),
    ('aio-dir-precheck-nt-only', 'atomic_io.py',
     '    if path.is_dir():',
     '    if path.is_dir() and os.name == "nt":'),
    ('aio-replace-posix-retries', 'atomic_io.py',
     '            if os_name != "nt" or attempt == 19:',
     '            if attempt == 19:'),
    ('aio-replace-no-retry', 'atomic_io.py',
     '            sleep(0.05)',
     '            raise'),
    ('bat-wsl-case', 'battery.py',
     '    norm = (found or "").lower().replace("/", "\\\\")',
     '    norm = (found or "").replace("/", "\\\\")'),
    ('bat-wsl-slash', 'battery.py',
     '    norm = (found or "").lower().replace("/", "\\\\")',
     '    norm = (found or "").lower()'),
    ('bat-gitroot-depth', 'battery.py',
     '    root = Path(out.stdout.strip()).parent.parent.parent',
     '    root = Path(out.stdout.strip()).parent.parent'),
    ('bat-cand-usr', 'battery.py',
     '    for cand in (root / "usr" / "bin" / "bash.exe", root / "bin" / "bash.exe"):',
     '    for cand in (root / "bin" / "bash.exe",):'),
    ('bat-rc-ignored', 'battery.py',
     '    if out.returncode != 0 or not out.stdout.strip():',
     '    if not out.stdout.strip():'),
    ('bat-didnotrun-zero', 'battery.py',
     '        return 2\n    return (run or subprocess.run)(',
     '        return 0\n    return (run or subprocess.run)('),
    ('fcp-closed-tmp-noclose', 'videoedit/fcpxml.py',
     '    fd, name = tempfile.mkstemp(suffix=suffix)\n    os.close(fd)\n    return Path(name)',
     '    fd, name = tempfile.mkstemp(suffix=suffix)\n    return Path(name)'),
    ('fcp-validate-site', 'videoedit/fcpxml.py',
     '        tmp = _closed_tmp(".fcpxml")',
     '        tmp = Path(tempfile.mkstemp(suffix=".fcpxml")[1])'),
    ('mlt-closed-tmp-noclose', 'videoedit/mltxml.py',
     '    fd, name = tempfile.mkstemp(suffix=suffix)\n    os.close(fd)\n    return Path(name)',
     '    fd, name = tempfile.mkstemp(suffix=suffix)\n    return Path(name)'),
    ('mlt-validate-site', 'videoedit/mltxml.py',
     '        tmp = _closed_tmp(".mlt")\n        tmp.write_text(src, encoding="utf-8")',
     '        tmp = Path(tempfile.mkstemp(suffix=".mlt")[1])\n        tmp.write_text(src, encoding="utf-8")'),
    ('mlt-cutlist-site', 'videoedit/mltxml.py',
     '    listfile = _closed_tmp(".txt")',
     '    listfile = Path(tempfile.mkstemp(suffix=".txt")[1])'),
    ('mlt-melt-pkg-site', 'videoedit/mltxml.py',
     '                    tmp = _closed_tmp(".mlt")\n                    tmp.write_text(build(src), encoding="utf-8")',
     '                    tmp = Path(tempfile.mkstemp(suffix=".mlt")[1])\n                    tmp.write_text(build(src), encoding="utf-8")'),
    ('bat-windowsapps-alias', 'battery.py',
     ' and "\\\\microsoft\\\\windowsapps\\\\" not in norm:',
     ':'),
    ('mlt-melt-tmp-kept', 'videoedit/mltxml.py',
     "                    if tmp is not None:   # P101: the package's temp .mlt is not left behind\n                        tmp.unlink()\n",
     '                    pass\n'),
    ('pd-local-missing-name', 'project_docs.py',
     '            out["missing"].append(src.relative_to(ROOT).as_posix())',
     '            out["missing"].append(src.name)'),
    ('aio-msvcrt-lk-lock', 'atomic_io.py',
     '                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)\n                return',
     '                msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)\n                return'),
    ('aio-msvcrt-unlock-zero-bytes', 'atomic_io.py',
     '        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)',
     '        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 0)'),
    ('aio-msvcrt-retries-any-error', 'atomic_io.py',
     '            except OSError as exc:\n                if exc.errno not in _LOCK_HELD:\n'
     '                    raise   # a bad handle or argument is an error, not a lock to wait for\n'
     '                time.sleep(0.01)',
     '            except OSError as exc:\n                time.sleep(0.01)'),
    ('aio-msvcrt-held-lock-raised', 'atomic_io.py',
     '_LOCK_HELD = (errno.EACCES,)',
     '_LOCK_HELD = ()'),
    ('aio-msvcrt-filter-inverted', 'atomic_io.py',
     '                if exc.errno not in _LOCK_HELD:',
     '                if exc.errno in _LOCK_HELD:'),
    ('aio-msvcrt-lock-two-bytes', 'atomic_io.py',
     '                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)\n                return',
     '                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 2)\n                return'),
    ('aio-msvcrt-lock-offset-1', 'atomic_io.py',
     '        fh.seek(0)\n        while True:',
     '        fh.seek(1)\n        while True:'),
    ('aio-msvcrt-unlock-offset-1', 'atomic_io.py',
     '        fh.seek(0)\n        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)',
     '        fh.seek(1)\n        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)'),
    # P101 ports: the port block, bind policy, port records, start-up probe and MCP address helpers
    # (loopback_server), the wizard's _bind, shutdown and same-origin port, the dashboard's walk,
    # origins, links and record, and pick_folder's fallback order.
    ('L01 EACCES no longer walks', 'loopback_server.py',
     '            if exc.errno == errno.EACCES:\n',
     '            if exc.errno == errno.EPERM:\n'),
    ('L02 EACCES skipped unrecorded', 'loopback_server.py',
     '                reserved.append(port)\n                continue\n',
     '                continue\n'),
    ('L03 EACCES ends walk', 'loopback_server.py',
     '                reserved.append(port)\n                continue\n',
     '                reserved.append(port)\n                break\n'),
    ('L04 EADDRINUSE walks on', 'loopback_server.py',
     '            if exc.errno == errno.EADDRINUSE:\n                raise BindRefused("in_use", port, reserved, exc) from exc\n',
     '            if exc.errno == errno.EADDRINUSE:\n                reserved.append(port)\n                continue\n'),
    ('L05 in_use reported as error', 'loopback_server.py',
     'raise BindRefused("in_use", port, reserved, exc) from exc',
     'raise BindRefused("error", port, reserved, exc) from exc'),
    ('L06 EADDRNOTAVAIL read as in_use', 'loopback_server.py',
     '            if exc.errno == errno.EADDRINUSE:\n',
     '            if exc.errno in (errno.EADDRINUSE, errno.EADDRNOTAVAIL):\n'),
    ('L07 all reserved reported in_use', 'loopback_server.py',
     '    raise BindRefused("reserved", reserved[-1] if reserved else None, reserved)\n',
     '    raise BindRefused("in_use", reserved[-1] if reserved else None, reserved)\n'),
    ('L08 all reserved returns nothing', 'loopback_server.py',
     '    raise BindRefused("reserved", reserved[-1] if reserved else None, reserved)\n',
     '    return None, None, reserved\n'),
    ('L09 all reserved tried truncated', 'loopback_server.py',
     '    raise BindRefused("reserved", reserved[-1] if reserved else None, reserved)\n',
     '    raise BindRefused("reserved", reserved[-1] if reserved else None, reserved[-1:])\n'),
    ('L10 other error walks on', 'loopback_server.py',
     '            raise BindRefused("error", port, reserved, exc) from exc\n',
     '            reserved.append(port)\n            continue\n'),
    ('L11 other error drops OSError', 'loopback_server.py',
     '            raise BindRefused("error", port, reserved, exc) from exc\n',
     '            raise BindRefused("error", port, reserved) from exc\n'),
    ('L12 other error reported in_use', 'loopback_server.py',
     '            raise BindRefused("error", port, reserved, exc) from exc\n',
     '            raise BindRefused("in_use", port, reserved, exc) from exc\n'),
    ('L13 nt branch never taken', 'loopback_server.py',
     '        if os.name == "nt":\n',
     '        if os.name == "windows":\n'),
    ('L14 nt keeps SO_REUSEADDR', 'loopback_server.py',
     '            self.allow_reuse_address = False\n',
     '            pass\n'),
    ('L17 override ignored', 'loopback_server.py',
     '    if not raw:\n        return tuple(block)\n',
     '    if True:\n        return tuple(block)\n'),
    ('L18 lower bound 1', 'loopback_server.py',
     '    if not 1024 <= val <= 65535:\n',
     '    if not 1 <= val <= 65535:\n'),
    ('L19 upper bound dropped', 'loopback_server.py',
     '    if not 1024 <= val <= 65535:\n',
     '    if not 1024 <= val:\n'),
    ('L20 1024 excluded', 'loopback_server.py',
     '    if not 1024 <= val <= 65535:\n',
     '    if not 1024 < val <= 65535:\n'),
    ('L21 override plus block', 'loopback_server.py',
     '    return (val,)\n',
     '    return (val,) + tuple(block)\n'),
    ('L22 read_port accepts bool', 'loopback_server.py',
     'isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535',
     'isinstance(port, int) and 1 <= port <= 65535'),
    ('L23 read_port accepts 0', 'loopback_server.py',
     'isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535',
     'isinstance(port, int) and not isinstance(port, bool) and 0 <= port <= 65535'),
    ('L24 read_port no upper bound', 'loopback_server.py',
     'isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535',
     'isinstance(port, int) and not isinstance(port, bool) and 1 <= port'),
    ('L25 read_port raises on list', 'loopback_server.py',
     '    except (OSError, ValueError, AttributeError):\n',
     '    except (OSError, ValueError):\n'),
    ('L26 read_port drops launch id', 'loopback_server.py',
     'return port, doc.get("launch_id")',
     'return port, None'),
    ('W01 _bind without global PORT', 'wizard.py',
     '    global PORT\n    running, _ = loopback_server.read_port()\n',
     '    running, _ = loopback_server.read_port()\n'),
    ('W02 records first block port', 'wizard.py',
     'loopback_server.port_record(PORT, os.environ.get("CREATOR_OS_WIZARD_LAUNCH_ID"))',
     'loopback_server.port_record(_PORTS[0], os.environ.get("CREATOR_OS_WIZARD_LAUNCH_ID"))'),
    ('W03 launch id not recorded', 'wizard.py',
     'loopback_server.port_record(PORT, os.environ.get("CREATOR_OS_WIZARD_LAUNCH_ID")))',
     'loopback_server.port_record(PORT, None))'),
    ('W04 reserved note suppressed', 'wizard.py',
     '    if reserved:\n        print(loopback_server.reserved_note(reserved, PORT, "Creator OS Setup"))\n',
     '    if False:\n        print(loopback_server.reserved_note(reserved, PORT, "Creator OS Setup"))\n'),
    ('W05 walk binds default port each time', 'wizard.py',
     'lambda port: _Server(("127.0.0.1", port), _Handler))',
     'lambda port: _Server(("127.0.0.1", PORT), _Handler))'),
    ('W06 all-interfaces bind', 'wizard.py',
     'lambda port: _Server(("127.0.0.1", port), _Handler))',
     'lambda port: _Server(("0.0.0.0", port), _Handler))'),
    ('W07 origin default is first block port', 'wizard.py',
     '    port = PORT if port is None else port\n',
     '    port = _PORTS[0] if port is None else port\n'),
    ('W08 origin default captured at import', 'wizard.py',
     'def _origin_allowed(origin, referer, port=None):',
     'def _origin_allowed(origin, referer, port=PORT):'),
    ('W09 origin set also admits 8765', 'wizard.py',
     '    allowed = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}\n',
     '    allowed = {f"http://127.0.0.1:{port}", f"http://localhost:{port}", "http://127.0.0.1:8765"}\n'),
    ('W10 note names 8765 TikTok URI', 'wizard.py',
     'f"{oauth_flow.redirect_uri(\'tiktok\', PORT)}, "',
     'f"{oauth_flow.redirect_uri(\'tiktok\', 8765)}, "'),
    ('W11 wizard RefuseSharedPort after TCPServer in MRO', 'wizard.py',
     'class _Server(loopback_server.RefuseSharedPort, socketserver.TCPServer):',
     'class _Server(socketserver.TCPServer, loopback_server.RefuseSharedPort):'),
    ('D01 main without global PORT', 'dashboard/server.py',
     '    global PORT\n    handler = partial(DashboardHandler)\n',
     '    handler = partial(DashboardHandler)\n'),
    ('D02 main tries first port only', 'dashboard/server.py',
     '            _PORTS, lambda port: HTTPServer(("127.0.0.1", port), handler))\n',
     '            _PORTS[:1], lambda port: HTTPServer(("127.0.0.1", port), handler))\n'),
    ('D03 main all-interfaces bind', 'dashboard/server.py',
     'lambda port: HTTPServer(("127.0.0.1", port), handler))',
     'lambda port: HTTPServer(("0.0.0.0", port), handler))'),
    ('D04 main reserved note suppressed', 'dashboard/server.py',
     '    if reserved:\n        print("  " + loopback_server.reserved_note(reserved, PORT, "the dashboard"))\n',
     '    if False:\n        print("  " + loopback_server.reserved_note(reserved, PORT, "the dashboard"))\n'),
    ('D05 main refusal exits 0', 'dashboard/server.py',
     '"CREATOR_OS_DASHBOARD_PORT"):\n            print(line)\n        raise SystemExit(1)\n',
     '"CREATOR_OS_DASHBOARD_PORT"):\n            print(line)\n        raise SystemExit(0)\n'),
    ('D06 origins use first block port', 'dashboard/server.py',
     '    return {f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"}\n',
     '    return {f"http://localhost:{_PORTS[0]}", f"http://127.0.0.1:{_PORTS[0]}"}\n'),
    ('D07 origins drop localhost', 'dashboard/server.py',
     '    return {f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"}\n',
     '    return {f"http://127.0.0.1:{PORT}"}\n'),
    ('D08 origins also admit 8766', 'dashboard/server.py',
     '    return {f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"}\n',
     '    return {f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}", "http://127.0.0.1:8766"}\n'),
    ('D09 wizard_url ignores record', 'dashboard/server.py',
     '    port, _ = loopback_server.read_port()\n    if port is None:\n',
     '    port, _ = None, None\n    if port is None:\n'),
    ('D10 wizard_url fallback hard-coded 8765', 'dashboard/server.py',
     '        port = loopback_server.ports("CREATOR_OS_WIZARD_PORT", loopback_server.WIZARD_BLOCK,\n',
     '        port = 8765 or loopback_server.ports("CREATOR_OS_WIZARD_PORT", loopback_server.WIZARD_BLOCK,\n'),
    ('D11 wizard_url drops trailing slash', 'dashboard/server.py',
     '    return f"http://localhost:{port}/"\n',
     '    return f"http://localhost:{port}"\n'),
    ('D12 wizard_url reads a fixed path', 'dashboard/server.py',
     '    port, _ = loopback_server.read_port()\n',
     '    port, _ = loopback_server.read_port(ROOT / "creator-os-wizard-port.local.json")\n'),
    ('D13 dashboard RefuseSharedPort after stock server in MRO', 'dashboard/server.py',
     'class HTTPServer(loopback_server.RefuseSharedPort, _StockHTTPServer):',
     'class HTTPServer(_StockHTTPServer, loopback_server.RefuseSharedPort):'),
    ('M01 launch id ignored', 'loopback_server.py',
     '        if port is not None and recorded_id == launch_id:\n',
     '        if port is not None:\n'),
    ('M02 fallback reported confirmed', 'loopback_server.py',
     '    return f"http://localhost:{port}/", False\n',
     '    return f"http://localhost:{port}/", True\n'),
    ('M03 exit not detected', 'loopback_server.py',
     '        if proc.poll() is not None:\n            break\n',
     '        if proc.poll() is not None:\n            pass\n'),
    ('M04 fallback ignores last record', 'loopback_server.py',
     '    port, _ = read()\n    if port is None:\n',
     '    port = None\n    if port is None:\n'),
    ('M05 wait bound x10', 'loopback_server.py',
     '    for _ in range(max(1, int(wait / 0.2))):\n',
     '    for _ in range(max(1, int(wait / 0.02))):\n'),
    ('M06 fallback hard-coded 8765', 'loopback_server.py',
     '        port = ports("CREATOR_OS_WIZARD_PORT", WIZARD_BLOCK, note=lambda _msg: None)[0]\n    return f"http://localhost:{port}/", False\n',
     '        port = 8765 or ports("CREATOR_OS_WIZARD_PORT", WIZARD_BLOCK, note=lambda _msg: None)[0]\n    return f"http://localhost:{port}/", False\n'),
    ('M07 no sleep between reads', 'loopback_server.py',
     '        sleep(0.2)\n',
     '        pass\n'),
    ('P01 tkinter cancel falls through', 'pick_folder.py',
     '    if result is not None:\n        return result   # tkinter worked',
     '    if result:\n        return result   # tkinter worked'),
    ('P02 OS picker asked first', 'pick_folder.py',
     '    result = _tk_pick()\n',
     '    result = _os_pick()\n'),
    ('P03 no OS fallback', 'pick_folder.py',
     '    return _os_pick()\n',
     '    return ""\n'),
    ('P04 both dialogs opened', 'pick_folder.py',
     "    result = _tk_pick()\n    if result is not None:\n        return result   # tkinter worked ('' means the user cancelled)\n    return _os_pick()\n",
     "    result = _tk_pick()\n    fallback = _os_pick()\n    if result is not None:\n        return result   # tkinter worked ('' means the user cancelled)\n    return fallback\n"),
    ('P05 OS cancel returns None', 'pick_folder.py',
     '    return _os_pick()\n',
     '    return _os_pick() or None\n'),
    ('P06 _has_display always true', 'pick_folder.py',
     '    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))\n',
     '    return True\n'),
    ('PR1 probe ignores the mark', 'loopback_server.py',
     '            if mark in got:\n                return "wizard"\n',
     '            return "wizard"\n'),
    ('PR2 probe raises on a refused connection', 'loopback_server.py',
     '    except OSError:\n        return "closed"\n',
     '    except TimeoutError:\n        return "closed"\n'),
    ('PR3 probe without a total deadline', 'loopback_server.py',
     '            if left <= 0:\n                return "silent"\n            sock.settimeout(left)\n',
     '            sock.settimeout(timeout)\n'),
    ('PR4 probe matches any title', 'loopback_server.py',
     'def probe(port, mark=WIZARD_TITLE_MARK, timeout=1.0) -> str:',
     'def probe(port, mark=b"</title>", timeout=1.0) -> str:'),
    ('PR5 silent reported as other', 'loopback_server.py',
     '            except socket.timeout:\n                return "silent"\n',
     '            except socket.timeout:\n                return "other"\n'),
    ('PR6 a closed reply reported as silent', 'loopback_server.py',
     '            if not chunk:\n                return "other"\n',
     '            if not chunk:\n                return "silent"\n'),
    ('WL1 start-up check never fires', 'wizard.py',
     '    if running is not None and loopback_server.probe(running) in ("wizard", "silent"):\n',
     '    if False:\n'),
    ('WL2 any record blocks start', 'wizard.py',
     '    if running is not None and loopback_server.probe(running) in ("wizard", "silent"):\n',
     '    if running is not None:\n'),
    ('WL3 start-up check reports first port', 'wizard.py',
     '        raise loopback_server.BindRefused("recorded", running, [])\n',
     '        raise loopback_server.BindRefused("recorded", _PORTS[0], [])\n'),
    ('WL4 start-up check reads dashboard record', 'wizard.py',
     '    running, _ = loopback_server.read_port()\n',
     '    running, _ = loopback_server.read_port(loopback_server.DASHBOARD_PORT_FILE)\n'),
    ('WL5 a busy wizard does not stop start', 'wizard.py',
     'loopback_server.probe(running) in ("wizard", "silent"):',
     'loopback_server.probe(running) in ("wizard",):'),
    ('WF1 forget ignores launch id', 'wizard.py',
     '    if port == PORT and launch_id == os.environ.get("CREATOR_OS_WIZARD_LAUNCH_ID"):\n',
     '    if port == PORT:\n'),
    ('WF2 forget ignores port', 'wizard.py',
     '    if port == PORT and launch_id == os.environ.get("CREATOR_OS_WIZARD_LAUNCH_ID"):\n',
     '    if launch_id == os.environ.get("CREATOR_OS_WIZARD_LAUNCH_ID"):\n'),
    ('WF3 forget keeps the record', 'wizard.py',
     '            loopback_server.WIZARD_PORT_FILE.unlink()\n',
     '            pass\n'),
    ('WF4 close never forgets', 'wizard.py',
     '        server.shutdown()\n        _forget_port()\n',
     '        server.shutdown()\n'),
    ('WT1 page title drops the probe mark', 'wizard.py',
     '<title>{title} - Creator OS Setup</title>',
     '<title>{title} | Creator OS Setup</title>'),
    ('WE1 a hang-up is printed as an error', 'wizard.py',
     '        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):\n            return\n',
     ''),
    ('WE2 a reset is printed as an error', 'wizard.py',
     '(BrokenPipeError, ConnectionResetError)):\n            return\n',
     '(BrokenPipeError,)):\n            return\n'),
    ('WE3 a real error is hidden', 'wizard.py',
     '            return\n        super().handle_error(request, client_address)\n',
     '            return\n'),
    ('DR1 dashboard records first block port', 'dashboard/server.py',
     'atomic_io.atomic_write_text(loopback_server.DASHBOARD_PORT_FILE, loopback_server.port_record(PORT))',
     'atomic_io.atomic_write_text(loopback_server.DASHBOARD_PORT_FILE, loopback_server.port_record(_PORTS[0]))'),
    ('DR2 dashboard record lands elsewhere', 'dashboard/server.py',
     'atomic_io.atomic_write_text(loopback_server.DASHBOARD_PORT_FILE, loopback_server.port_record(PORT))',
     'atomic_io.atomic_write_text(loopback_server.DASHBOARD_PORT_FILE.with_name("elsewhere.local.json"), loopback_server.port_record(PORT))'),
    ('DR3 dashboard writes no record', 'dashboard/server.py',
     'atomic_io.atomic_write_text(loopback_server.DASHBOARD_PORT_FILE, loopback_server.port_record(PORT))',
     'pass'),
    ('DR4 dashboard never forgets', 'dashboard/server.py',
     '        server.shutdown()\n        _forget_port()\n',
     '        server.shutdown()\n'),
    ("DR5 dashboard forgets another port's record", 'dashboard/server.py',
     '    if loopback_server.read_port(loopback_server.DASHBOARD_PORT_FILE)[0] == PORT:\n',
     '    if True:\n'),
    ('DR6 dashboard forget keeps the record', 'dashboard/server.py',
     '            loopback_server.DASHBOARD_PORT_FILE.unlink()\n',
     '            pass\n'),
    ('MN1 note lists the shown port', 'loopback_server.py',
     '              if f"localhost:{p}/" not in url]',
     '              if True]'),
    ('MN2 note confirmed inverted', 'loopback_server.py',
     '    if confirmed:\n        return "The setup wizard is opening in your web browser.',
     '    if not confirmed:\n        return "The setup wizard is opening in your web browser.'),
    ('MN3 note ignores the override', 'loopback_server.py',
     '    others = [str(p) for p in ports("CREATOR_OS_WIZARD_PORT", WIZARD_BLOCK,',
     '    others = [str(p) for p in ports("CREATOR_OS_WIZARD_PORT_UNSET", WIZARD_BLOCK,'),
    ('MD1 dashboard url reads the wizard record', 'loopback_server.py',
     '    port, _ = read() if read is not None else read_port(DASHBOARD_PORT_FILE)\n',
     '    port, _ = read() if read is not None else read_port()\n'),
    ('MD2 dashboard url ignores the override', 'loopback_server.py',
     '        port = ports("CREATOR_OS_DASHBOARD_PORT", DASHBOARD_BLOCK, note=lambda _msg: None)[0]\n',
     '        port = ports("CREATOR_OS_DASHBOARD_PORT_UNSET", DASHBOARD_BLOCK, note=lambda _msg: None)[0]\n'),
    ('MD3 dashboard url ignores the record', 'loopback_server.py',
     '    port, _ = read() if read is not None else read_port(DASHBOARD_PORT_FILE)\n',
     '    port, _ = (None, None)\n'),
    ('PB1 connect timeout read as silent', 'loopback_server.py',
     '    except OSError:\n        return "closed"\n',
     '    except ConnectionRefusedError:\n        return "closed"\n    except OSError:\n        return "silent"\n'),
    ('PB2 incomplete request', 'loopback_server.py',
     '        sock.sendall(b"GET / HTTP/1.0\\r\\nHost: 127.0.0.1\\r\\n\\r\\n")\n',
     '        sock.sendall(b"GET / HTTP/1.0\\r\\n")\n'),
    ('PB3 reads 16 bytes', 'loopback_server.py',
     '        while len(got) < 262144:\n',
     '        while len(got) < 16:\n'),
    ('PB5 reset read as silent', 'loopback_server.py',
     '    except OSError:\n        return "other"\n',
     '    except OSError:\n        return "silent"\n'),
    ('WC2 close leaves server running', 'wizard.py',
     '        server.shutdown()\n        _forget_port()\n        print(',
     '        _forget_port()\n        print('),
    ('WC3 wizard does not wait', 'wizard.py',
     '    try:\n        _shutdown.wait()\n    except KeyboardInterrupt:\n',
     '    try:\n        _shutdown.wait(0)\n    except KeyboardInterrupt:\n'),
    ('WC5 main skips wait_and_close', 'wizard.py',
     '    _wait_and_close(server)\n',
     '    server.shutdown()\n'),
    ('HE1 every OSError silenced', 'wizard.py',
     '        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):\n',
     '        if isinstance(sys.exc_info()[1], OSError):\n'),
    ('HE2 real error loses traceback', 'wizard.py',
     '        super().handle_error(request, client_address)\n',
     '        print("error", file=sys.stderr)\n'),
    ('RC1 recorded refusal hides the record file', 'loopback_server.py',
     '                f"{WIZARD_PORT_FILE.name} and start it again."]',
     '                "the record and start it again."]'),
    ('WZ01 handler timeout None', 'wizard.py',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def log_message(self, fmt, *args):',
     '    timeout = None\n\n    def log_message(self, fmt, *args):'),
    ('WZ02 handler timeout misnamed', 'wizard.py',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def log_message(self, fmt, *args):',
     '    request_timeout = loopback_server.REQUEST_TIMEOUT\n\n    def log_message(self, fmt, *args):'),
    ('WZ03 handler timeout x10', 'wizard.py',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def log_message(self, fmt, *args):',
     '    timeout = loopback_server.REQUEST_TIMEOUT * 10\n\n    def log_message(self, fmt, *args):'),
    ('WZ04 handler timeout 5 s, not 3', 'wizard.py',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def log_message(self, fmt, *args):',
     '    timeout = loopback_server.REQUEST_TIMEOUT + 2\n\n    def log_message(self, fmt, *args):'),
    ('WZ05 hub warning example ~/CreatorOS', 'wizard.py',
     'example = html.escape(str(pathlib.Path.home() / "CreatorOS"))',
     'example = "~/CreatorOS"'),
    ('WZ06 hub warning python3 everywhere', 'wizard.py',
     'python = html.escape(env_paths.python_command())',
     'python = "python3"'),
    ('WZ07 hub warning command by os.name', 'wizard.py',
     'python = html.escape(env_paths.python_command())',
     'python = "python" if os.name == "posix" else "python3"'),
    ('WZ08 hub warning folder unescaped', 'wizard.py',
     '(<code>{html.escape(synced)}</code>)',
     '(<code>{synced}</code>)'),
    ('WZ09 hub warning without a folder', 'wizard.py',
     '    synced = env_paths.cloud_synced_root(ROOT)\n    if synced:',
     '    synced = env_paths.cloud_synced_root(ROOT)\n    if True:'),
    ('WZ10 hub warning asks about cwd', 'wizard.py',
     '    synced = env_paths.cloud_synced_root(ROOT)\n',
     '    synced = env_paths.cloud_synced_root(pathlib.Path.cwd())\n'),
    ('WZ11 hub warning example beside repo', 'wizard.py',
     'example = html.escape(str(pathlib.Path.home() / "CreatorOS"))',
     'example = html.escape(str(ROOT.parent / "CreatorOS"))'),
    ('WZ12 hub warning command unescaped', 'wizard.py',
     'python = html.escape(env_paths.python_command())',
     'python = env_paths.python_command()'),
    ('WZ13 late body read as empty form', 'wizard.py',
     '            # connection in http.server instead of reading as an empty form.\n            raise\n',
     '            # connection in http.server instead of reading as an empty form.\n            return ""\n'),
    ('WZ14 body read errors raise', 'wizard.py',
     '        except Exception:  # noqa: BLE001\n            return ""\n\n    def _read_form',
     '        except Exception:  # noqa: BLE001\n            raise\n\n    def _read_form'),
    ('WZ15 body re-raises every OSError', 'wizard.py',
     '        except TimeoutError:\n            # P101: a body that stops arriving',
     '        except OSError:\n            # P101: a body that stops arriving'),
    ('DB01 handler timeout None', 'dashboard/server.py',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def __init__(self, *args, **kwargs):\n        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)',
     '    timeout = None\n\n    def __init__(self, *args, **kwargs):\n        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)'),
    ('DB02 handler timeout misnamed', 'dashboard/server.py',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def __init__(self, *args, **kwargs):\n        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)',
     '    request_timeout = loopback_server.REQUEST_TIMEOUT\n\n    def __init__(self, *args, **kwargs):\n        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)'),
    ('DB03 timeout set after handling', 'dashboard/server.py',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def __init__(self, *args, **kwargs):\n        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)',
     '    def __init__(self, *args, **kwargs):\n        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)\n        self.timeout = loopback_server.REQUEST_TIMEOUT'),
    ('DB04 handler timeout 5 s, not 3', 'dashboard/server.py',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def __init__(self, *args, **kwargs):\n        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)',
     '    timeout = loopback_server.REQUEST_TIMEOUT + 2\n\n    def __init__(self, *args, **kwargs):\n        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)'),
    ('LS02 refused connect reads as other', 'loopback_server.py',
     'timeout=timeout)\n    except OSError:\n        return "closed"',
     'timeout=timeout)\n    except ConnectionRefusedError:\n        return "other"\n    except OSError:\n        return "closed"'),
    ('LS03 connect catches refused only', 'loopback_server.py',
     'timeout=timeout)\n    except OSError:\n        return "closed"',
     'timeout=timeout)\n    except ConnectionRefusedError:\n        return "closed"'),
    ('LS04 REQUEST_TIMEOUT 30', 'loopback_server.py',
     'REQUEST_TIMEOUT = 3\n',
     'REQUEST_TIMEOUT = 30\n'),
    ('LS05 REQUEST_TIMEOUT None', 'loopback_server.py',
     'REQUEST_TIMEOUT = 3\n',
     'REQUEST_TIMEOUT = None\n'),
    ('PF01 Linux display ignores Wayland', 'pick_folder.py',
     '    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))',
     '    return bool(os.environ.get("DISPLAY"))'),
    ('PF02 Linux display ignores X11', 'pick_folder.py',
     '    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))',
     '    return bool(os.environ.get("WAYLAND_DISPLAY"))'),
    ('PF04 Linux display needs both', 'pick_folder.py',
     '    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))',
     '    return bool(os.environ.get("DISPLAY") and os.environ.get("WAYLAND_DISPLAY"))'),
    ('PF05 empty DISPLAY counts', 'pick_folder.py',
     '    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))',
     '    return "DISPLAY" in os.environ or "WAYLAND_DISPLAY" in os.environ'),
    ('PF06 _os maps Linux to windows', 'pick_folder.py',
     '    return "linux"\n\n\ndef _has_display',
     '    return "windows"\n\n\ndef _has_display'),
    ('PF07 _os maps Windows to linux', 'pick_folder.py',
     '    if s == "Windows":\n        return "windows"',
     '    if s == "Windows":\n        return "linux"'),
    ('EP01 iCloud Drive dropped', 'env_paths.py',
     '("iCloud Drive",), ("iCloudDrive",))',
     '("iCloudDrive",))'),
    ('EP02 iCloudDrive dropped', 'env_paths.py',
     '("iCloud Drive",), ("iCloudDrive",))',
     '("iCloud Drive",))'),
    ('EP03 iCloud Drive under Library', 'env_paths.py',
     '("iCloud Drive",), ("iCloudDrive",))',
     '("Library", "iCloud Drive"), ("iCloudDrive",))'),
    ('EP04 OneDriveCommercial dropped', 'env_paths.py',
     'ONEDRIVE_ENV_VARS = ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")',
     'ONEDRIVE_ENV_VARS = ("OneDrive", "OneDriveConsumer")'),
    ('EP05 only the first OneDrive var', 'env_paths.py',
     'bases += [Path(env[name]) for name in ONEDRIVE_ENV_VARS\n',
     'bases += [Path(env[name]) for name in ONEDRIVE_ENV_VARS[:1]\n'),
    ('EP06 relative OneDrive value kept', 'env_paths.py',
     'if env.get(name) and Path(env[name]).is_absolute()]',
     'if env.get(name)]'),
    ('EP07 env argument ignored', 'env_paths.py',
     '    env = os.environ if env is None else env\n',
     '    env = os.environ\n'),
    ('EP08 default env empty', 'env_paths.py',
     '    env = os.environ if env is None else env\n',
     '    env = env if env is not None else dict()\n'),
    ('EP09 Drive marker name typo', 'env_paths.py',
     'DRIVEFS_MARKERS = (".shortcut-targets-by-id", ".file-revisions-by-id")',
     'DRIVEFS_MARKERS = (".shortcut-targets", ".file-revisions-by-id")'),
    ('EP10 marker may be a file', 'env_paths.py',
     'any(os.path.isdir(volume / name) for name in DRIVEFS_MARKERS)',
     'any(os.path.exists(volume / name) for name in DRIVEFS_MARKERS)'),
    ('EP11 farthest mount, not nearest', 'env_paths.py',
     '    for candidate in (target, *target.parents):',
     '    for candidate in (*reversed(target.parents), target):'),
    ('EP12 any mount holding a marker', 'env_paths.py',
     '            if ismount(candidate):\n                return candidate',
     '            if ismount(candidate) and any(os.path.isdir(candidate / n) for n in DRIVEFS_MARKERS):\n                return candidate'),
    ('EP13 ismount error propagates', 'env_paths.py',
     '        except (OSError, ValueError):\n            return None',
     '        except ZeroDivisionError:\n            return None'),
    ('EP14 ismount error skips to parent', 'env_paths.py',
     '        except (OSError, ValueError):\n            return None',
     '        except (OSError, ValueError):\n            continue'),
    ('EP15 default ismount bound at def', 'env_paths.py',
     'def cloud_synced_root(path, home=None, env=None, ismount=None):',
     'def cloud_synced_root(path, home=None, env=None, ismount=os.path.ismount):'),
    ('EP16 no default ismount', 'env_paths.py',
     '    ismount = os.path.ismount if ismount is None else ismount\n',
     '    ismount = ismount or (lambda p: False)\n'),
    ('EP17 volume branch names the path', 'env_paths.py',
     '        return str(volume)',
     '        return str(target)'),
    ('EP18 empty OneDrive value accepted', 'env_paths.py',
     'if env.get(name) and Path(env[name]).is_absolute()]',
     'if name in env and Path(env[name] or "/").is_absolute()]'),
    ('EP19 second Drive marker dropped', 'env_paths.py',
     'DRIVEFS_MARKERS = (".shortcut-targets-by-id", ".file-revisions-by-id")',
     'DRIVEFS_MARKERS = (".shortcut-targets-by-id",)'),
    ('EP20 both Drive markers required', 'env_paths.py',
     'any(os.path.isdir(volume / name) for name in DRIVEFS_MARKERS)',
     'all(os.path.isdir(volume / name) for name in DRIVEFS_MARKERS)'),
    ('EP21 Windows command ignores py', 'env_paths.py',
     '    return "py -3" if which("py") else "python"',
     '    return "python"'),
    ('EP22 py launcher looked up as python', 'env_paths.py',
     '"py -3" if which("py") else',
     '"py -3" if which("python") else'),
    ('EP23 py -3 off Windows', 'env_paths.py',
     '    if osname != "nt":\n        return "python3"',
     '    if osname != "nt":\n        return "py -3"'),
    ('EP24 command ignores shutil.which', 'env_paths.py',
     '    which = shutil.which if which is None else which\n',
     '    which = which or (lambda name: None)\n'),
    ('ST01 setup example ~/CreatorOS', 'setup.py',
     'example = (Path(home) if home is not None else Path.home()) / "CreatorOS"',
     'example = "~/CreatorOS"'),
    ('ST02 setup python3 everywhere', 'setup.py',
     'python = env_paths.python_command()',
     'python = "python3"'),
    ('ST03 setup example ignores home', 'setup.py',
     'example = (Path(home) if home is not None else Path.home()) / "CreatorOS"',
     'example = Path.home() / "CreatorOS"'),
    ('ST04 setup command word dropped', 'setup.py',
     '        _say(f"         {python} tools/profile_mirror.py sync',
     '        _say(f"         tools/profile_mirror.py sync'),
    ('ST05 setup warns when not synced', 'setup.py',
     '    if synced:\n        example',
     '    if not synced:\n        example'),
    ('ST06 setup warning names no folder', 'setup.py',
     '        _say(f"  [warn] This repo is inside a cloud-synced folder ({synced}).")',
     '        _say("  [warn] This repo is inside a cloud-synced folder.")'),
    ('EP25 default os.name fixed to posix', 'env_paths.py',
     '    osname = _os_name() if osname is None else osname',
     '    osname = "posix" if osname is None else osname'),
    ('EP26 injected which ignored', 'env_paths.py',
     '    which = shutil.which if which is None else which',
     '    which = shutil.which'),
    ('EP27 markers read at the path itself', 'env_paths.py',
     'any(os.path.isdir(volume / name) for name in DRIVEFS_MARKERS)',
     'any(os.path.isdir(target / name) for name in DRIVEFS_MARKERS)'),
    ('EP28 ValueError from ismount escapes', 'env_paths.py',
     '        except (OSError, ValueError):\n            return None',
     '        except OSError:\n            return None'),
    ('ST07 setup env not passed through', 'setup.py',
     '    synced = env_paths.cloud_synced_root(root, home=home, env=env, ismount=ismount)',
     '    synced = env_paths.cloud_synced_root(root, home=home, ismount=ismount)'),
    ('ST08 setup ismount not passed through', 'setup.py',
     '    synced = env_paths.cloud_synced_root(root, home=home, env=env, ismount=ismount)',
     '    synced = env_paths.cloud_synced_root(root, home=home, env=env)'),
    ('ST09 setup command pinned to POSIX', 'setup.py',
     '        python = env_paths.python_command()',
     '        python = env_paths.python_command("posix")'),
    ('WZ16 hub command pinned to POSIX', 'wizard.py',
     '        python = html.escape(env_paths.python_command())',
     '        python = html.escape(env_paths.python_command("posix"))'),
    ('WZ17 body timeout raised as reset', 'wizard.py',
     'instead of reading as an empty form.\n            raise\n',
     'instead of reading as an empty form.\n            raise ConnectionResetError("timed out")\n'),
    ('WZ18 handler setup ignores its timeout', 'wizard.py',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def log_message(self, fmt, *args):',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def setup(self):\n        super().setup()\n        self.connection.settimeout(None)\n\n    def log_message(self, fmt, *args):'),
    ('WZ19 waits forever only at 1 s or more', 'wizard.py',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def log_message(self, fmt, *args):',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def setup(self):\n        super().setup()\n        if self.timeout >= 1:\n            self.connection.settimeout(None)\n\n    def log_message(self, fmt, *args):'),
    ('DB05 waits forever only at 1 s or more', 'dashboard/server.py',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def __init__(self, *args, **kwargs):',
     '    timeout = loopback_server.REQUEST_TIMEOUT\n\n    def setup(self):\n        super().setup()\n        if self.timeout >= 1:\n            self.connection.settimeout(None)\n\n    def __init__(self, *args, **kwargs):'),
    ('ST10 setup empty env read as unset', 'setup.py',
     '    synced = env_paths.cloud_synced_root(root, home=home, env=env, ismount=ismount)',
     '    synced = env_paths.cloud_synced_root(root, home=home, env=env or None, ismount=ismount)'),
    ('ST11 setup home not passed through', 'setup.py',
     '    synced = env_paths.cloud_synced_root(root, home=home, env=env, ismount=ismount)',
     '    synced = env_paths.cloud_synced_root(root, env=env, ismount=ismount)'),
    ('EP29 _os_name changes the case', 'env_paths.py',
     '    return os.name\n',
     '    return os.name.upper()\n'),
    ('EP30 default bypasses _os_name', 'env_paths.py',
     '    osname = _os_name() if osname is None else osname',
     '    osname = os.name if osname is None else osname'),
)

# Rows whose mutant behaves exactly like the original on Windows, so only a POSIX run can catch
# them; on Windows the runner skips them and the selftest says how many it skipped.
_POSIX_ONLY = {"aio-dir-precheck-nt-only"}

# The function the runner scores for a module with no selftest(): it returns 0 when clean.
# sync_check.py is exempt from the selftest sweep (running it is its test).
_ENTRIES = {"sync_check.py": "_migration_selfproof", "wizard.py": "_selftest_p101",
            "dashboard/server.py": "_selftest", "pick_folder.py": "_selftest",
            "env_paths.py": "_selftest", "setup.py": "_selftest"}


def _selftest_verdict(source: str, path: Path, entry: str = "selftest") -> str:
    """'pass', 'fail' or 'invalid: <reason>' for the entry function (selftest() unless named) of a
    module built from source."""
    import contextlib as _cl
    import io
    import types
    try:
        code = compile(source, f"<{path.name} mutant>", "exec")
    except SyntaxError as exc:
        return f"invalid: does not compile ({exc.msg})"
    mod = types.ModuleType(f"{path.stem}_mutant")
    mod.__file__ = str(path)
    saved_path, saved_argv = list(sys.path), list(sys.argv)
    try:
        with _cl.redirect_stdout(io.StringIO()), _cl.redirect_stderr(io.StringIO()):
            try:
                exec(code, mod.__dict__)
            except KeyboardInterrupt:
                raise
            except BaseException as exc:  # noqa: BLE001 - a module that cannot load tests nothing
                return f"invalid: does not load ({type(exc).__name__})"
            fn = mod.__dict__.get(entry)
            if not callable(fn):
                return f"invalid: no {entry}()"
            mod._IN_MUTANT = True
            try:
                rc = fn()
            except SystemExit as exc:
                return "pass" if exc.code in (0, None) else "fail"
            except KeyboardInterrupt:
                raise
            except BaseException:  # noqa: BLE001 - a selftest the mutation crashes has caught it
                return "fail"
            if isinstance(rc, tuple) and rc:   # an entry that returns (rc, ...) is scored on rc
                rc = rc[0]
            return "pass" if rc == 0 else "fail"
    finally:
        sys.path[:], sys.argv[:] = saved_path, saved_argv


def _test_scopes(src: str, entry: str) -> list:
    """The functions a row's anchor must stay out of: the entry that scores the row, then every
    other top-level function named selftest* or _selftest* (a helper the entry delegates to)."""
    import ast
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [entry]
    helpers = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name.lstrip("_").startswith("selftest") and n.name != entry}
    return [entry] + sorted(helpers)


def _in_function(src: str, start: int, length: int, name: str) -> bool:
    """True when source[start:start+length] overlaps the top-level function `name`."""
    import ast
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    first = src.count("\n", 0, start) + 1
    last = src.count("\n", 0, start + max(length - 1, 0)) + 1   # the line of the anchor's last character
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
               and n.lineno <= last and first <= n.end_lineno for n in tree.body)


_STATE_CLASSES = (pathlib.PurePath, pathlib.PurePosixPath, pathlib.PureWindowsPath, pathlib.Path,
                  pathlib.PosixPath, pathlib.WindowsPath)


def _global_state():
    """What a mutant can change for the rows after it: path class attributes, cwd, environment."""
    import os
    return ([(c, dict(vars(c))) for c in _STATE_CLASSES], os.getcwd(), dict(os.environ))


def _restore_global_state(saved) -> None:
    import os
    classes, cwd, env = saved
    for cls, attrs in classes:
        for k in [k for k in vars(cls) if k not in attrs]:
            delattr(cls, k)
        for k, v in attrs.items():
            if vars(cls).get(k, _MISSING) is not v and k not in ("__dict__", "__weakref__", "__doc__"):
                try:
                    setattr(cls, k, v)
                except (AttributeError, TypeError):
                    pass
    if os.getcwd() != cwd:
        os.chdir(cwd)
    if dict(os.environ) != env:
        os.environ.clear()
        os.environ.update(env)


_MISSING = object()


def _run_mutants(table=None, base=None, entries=None, posix_only=None) -> list:
    """The labels of rows no selftest caught, each with the reason when the row is invalid: an anchor
    not found exactly once, an anchor inside the entry function itself (the test that scores the
    row; other test helpers are not detected), a mutant that does not compile or load, a module with
    no entry function, or a module whose unmutated entry does not pass (then no row against it can
    be scored). Path class attributes, the working folder and the environment are restored after
    each row, so a row that leaks state cannot decide the rows after it."""
    here = Path(base) if base is not None else Path(__file__).resolve().parent
    me = Path(__file__).resolve()
    entries = _ENTRIES if entries is None else entries
    survivors, baseline = [], {}
    for label, module, old, new in (_MUTANTS if table is None else table):
        if os.name == "nt" and label in (_POSIX_ONLY if posix_only is None else posix_only):
            continue
        path = here / module
        entry = entries.get(module, "selftest")
        src = path.read_text(encoding="utf-8")
        if path.resolve() == me:
            scope, mark, tail = src.partition(_SELFTEST_MARK)
        else:
            scope, mark, tail = src, "", ""
        if module not in baseline:
            baseline[module] = _selftest_verdict(src, path, entry)
        if baseline[module] != "pass":
            survivors.append(f"{label} (unmutated selftest: {baseline[module]})")
            continue
        if scope.count(old) != 1:
            survivors.append(f"{label} (anchor not found exactly once)")
            continue
        hit = next((n for n in _test_scopes(src, entry)
                    if _in_function(src, scope.index(old), len(old), n)), None)
        if hit == entry:
            survivors.append(f"{label} (invalid: anchor in {entry}(), the test that scores it)")
            continue
        if hit:
            survivors.append(f"{label} (invalid: anchor in {hit}(), test code)")
            continue
        saved = _global_state()
        try:
            verdict = _selftest_verdict(scope.replace(old, new) + mark + tail, path, entry)
        finally:
            _restore_global_state(saved)
        if verdict == "pass":
            survivors.append(label)
        elif verdict != "fail":
            survivors.append(f"{label} ({verdict})")
    return survivors


def _coverage_gaps(table=None, base=None) -> list:
    """Modules in the folder that hash through this one (call sha256_bytes, sha256_file or normalise)
    or simulate Windows paths (call windows_paths), and this module itself, with fewer than
    MIN_MUTANTS_PER_MODULE committed rows."""
    import re
    here = Path(base) if base is not None else Path(__file__).resolve().parent
    rows = _MUTANTS if table is None else table
    uses = re.compile(r"file_hash\.(?:sha256_bytes|sha256_file|normalise|windows_paths)\(")
    need = {Path(__file__).name} | {p.name for p in sorted(here.glob("*.py"))
                                    if uses.search(p.read_text(encoding="utf-8"))}
    count = {m: sum(1 for r in rows if r[1] == m) for m in need}
    return sorted(f"{m}: {n} of {MIN_MUTANTS_PER_MODULE}" for m, n in count.items()
                  if n < MIN_MUTANTS_PER_MODULE)


def _runner_controls() -> list:
    """(name, ok) for rows the runner must NOT score as caught, run against throwaway modules."""
    import tempfile
    out = []
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "good.py").write_text("x = 1\ndef f():\n    return x\ndef selftest():\n"
                                   "    return 0 if f() == 1 else 1\n", encoding="utf-8")
        (d / "noself.py").write_text("x = 1\n", encoding="utf-8")
        (d / "red.py").write_text("def selftest():\n    return 1\n", encoding="utf-8")
        (d / "alt.py").write_text("x = 1\ndef check():\n    return 0 if x == 1 else 1\n", encoding="utf-8")
        (d / "tup.py").write_text("x = 1\ndef tcheck():\n    return (0 if x == 1 else 1), 5\n",
                                  encoding="utf-8")
        (d / "leak.py").write_text("x = 1\ndef selftest():\n    return 0\n", encoding="utf-8")
        (d / "guard.py").write_text("import pathlib\ny = 1\ndef selftest():\n"
                                    "    return 1 if hasattr(pathlib.PosixPath, 'zz_leak') else 0\n",
                                    encoding="utf-8")
        rows = [
            ("equivalent", "good.py", "x = 1\n", "x = 1  # same\n"),
            ("syntax", "good.py", "x = 1\n", "x = (\n"),
            ("exit0", "good.py", "    return x\n", "    raise SystemExit(0)\n"),
            ("loadfail", "good.py", "x = 1\n", "raise RuntimeError('import')\n"),
            ("noself", "noself.py", "x = 1", "x = 2"),
            ("redbase", "red.py", "return 1", "return 2"),
            ("caught", "good.py", "x = 1\n", "x = 2\n"),
            ("exit1", "good.py", "    return x\n", "    raise SystemExit(1)\n"),
            ("entry", "alt.py", "x = 1\n", "x = 2\n"),
            ("entry-equivalent", "alt.py", "x = 1\n", "x = 1  # same\n"),
            ("tuple", "tup.py", "x = 1\n", "x = 2\n"),
            ("tuple-equivalent", "tup.py", "x = 1\n", "x = 1  # same\n"),
        ]
        got = _run_mutants(rows, base=d, entries={"alt.py": "check", "tup.py": "tcheck"})
        missing_entry = _run_mutants([("noentry", "alt.py", "x = 1\n", "x = 2\n")], base=d,
                                     entries={})
        leak_rows = [("guard-a", "guard.py", "y = 1\n", "y = 1  # same\n"),
                     ("leak", "leak.py", "x = 1\n", "import pathlib\npathlib.PosixPath.zz_leak = 1\nx = 1\n"),
                     ("guard-b", "guard.py", "y = 1\n", "y = 1  # still same\n")]
        leaked = _run_mutants(leak_rows, base=d)
        restored = not hasattr(pathlib.PosixPath, "zz_leak")
        in_test = _run_mutants([("testcode", "good.py", "    return 0 if f() == 1 else 1",
                                 "    return 1")], base=d)
        (d / "deleg.py").write_text("x = 1\ndef selftest():\n    return _selftest_checks()\n"
                                    "def _selftest_checks():\n    return 0 if x == 1 else 1\n",
                                    encoding="utf-8")
        delegated = _run_mutants([("deleg-testcode", "deleg.py", "    return 0 if x == 1 else 1",
                                   "    return 1"),
                                  ("deleg-caught", "deleg.py", "x = 1\n", "x = 2\n")], base=d)
    labels = [g.split(" (")[0] for g in got]
    out.append(("an equivalent row is reported as a survivor", "equivalent" in labels))
    out.append(("a row that does not compile is reported invalid, not caught",
                any(g.startswith("syntax (invalid: does not compile") for g in got)))
    out.append(("a selftest that exits 0 under the mutant is a survivor", "exit0" in labels))
    out.append(("a mutant module that fails to load is reported invalid, not caught",
                any(g.startswith("loadfail (invalid: does not load") for g in got)))
    out.append(("a module with no selftest() is reported invalid, not caught",
                any(g.startswith("noself (unmutated selftest: invalid: no selftest()") for g in got)))
    out.append(("a module whose unmutated selftest fails scores no row",
                any(g.startswith("redbase (unmutated selftest: fail") for g in got)))
    out.append(("a real mutation and a non-zero exit are caught",
                "caught" not in labels and "exit1" not in labels))
    out.append(("a named entry function is scored: a real mutation caught, an equivalent one not",
                "entry" not in labels and "entry-equivalent" in labels))
    out.append(("an entry that returns (rc, ...) is scored on rc: a real mutation caught, an "
                "equivalent one not", "tuple" not in labels and "tuple-equivalent" in labels))
    out.append(("without its entry a module with no selftest() is invalid, not caught",
                len(missing_entry) == 1 and "invalid: no selftest()" in missing_entry[0]))
    out.append(("a row that leaks state is undone: the equivalent row after it is still a survivor",
                "guard-b" in leaked and "guard-a" in leaked and restored))
    out.append(("a row whose anchor is inside the selftest that scores it is invalid, not caught",
                len(in_test) == 1 and "invalid: anchor in selftest()" in in_test[0]))
    out.append(("a row whose anchor is inside a _selftest* helper the entry delegates to is invalid, "
                "not caught; a real row in the same module is caught",
                len(delegated) == 1 and "invalid: anchor in _selftest_checks(), test code" in delegated[0]))
    # A row listed as POSIX-only is run (here an equivalent row, so it survives) under a POSIX os
    # and skipped under Windows; the runner's os is swapped for each run.
    class _AsOs:
        def __init__(self, name):
            self.name = name

        def __getattr__(self, attr):
            return getattr(real_os, attr)
    g, real_os = globals(), globals()["os"]
    runs = {}
    with tempfile.TemporaryDirectory() as td2:
        d2 = Path(td2)
        (d2 / "good.py").write_text("x = 1\ndef selftest():\n    return 0 if x == 1 else 1\n", encoding="utf-8")
        row = [("posix-row", "good.py", "x = 1\n", "x = 1  # same\n")]
        for name in ("posix", "nt"):
            g["os"] = _AsOs(name)
            try:
                runs[name] = _run_mutants(row, base=d2, posix_only={"posix-row"})
            finally:
                g["os"] = real_os
    out.append(("a POSIX-only row runs under a POSIX os and is skipped under Windows",
                runs == {"posix": ["posix-row"], "nt": []}))
    return out


def selftest() -> int:
    import io
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    lf = b"line one\nline two\n\xc3\xa9 caf\xc3\xa9\n"
    crlf = lf.replace(b"\n", b"\r\n")
    cr = lf.replace(b"\n", b"\r")
    ok("CRLF, CR and LF copies of a text hash equal",
       sha256_bytes(crlf) == sha256_bytes(lf) == sha256_bytes(cr))
    ok("the folded hash differs from the raw CRLF hash (the fold is doing work)",
       sha256_bytes(crlf) != hashlib.sha256(crlf).hexdigest())
    lf_varied = (b"Upper and lower\t\n  trailing blanks   \n\x0bvertical tab\x0c form feed\n"
                 b"\x1c\x1d\x1e separators \xc2\x85 next line \xe2\x80\xa8 line sep \xe2\x80\xa9 para sep\n")
    ok("an LF text, with blanks, tabs, case, VT, FF, NEL and U+2028, hashes to its raw sha256",
       sha256_bytes(lf_varied) == hashlib.sha256(lf_varied).hexdigest())
    mixed = b"\xef\xbb\xbfa\r\nb\rc\n" + lf_varied.replace(b"\n", b"\r\n")
    ok("for valid UTF-8 the folded bytes equal a universal-newline text read, re-encoded",
       normalise(mixed) == io.TextIOWrapper(io.BytesIO(mixed), encoding="utf-8", newline=None).read().encode("utf-8"))
    ok("the BOM is kept, not stripped (read_text with encoding=utf-8 keeps it too)",
       normalise(mixed).startswith(b"\xef\xbb\xbf"))
    ok("a non-UTF-8 LF text hashes raw, and its content still decides the hash",
       sha256_bytes(b"caf\xe9\n") == hashlib.sha256(b"caf\xe9\n").hexdigest()
       and sha256_bytes(b"caf\xe9\r\n") == sha256_bytes(b"caf\xe9\n")
       and sha256_bytes(b"caf\xe9\n") != sha256_bytes(b"caf\xe8\n"))
    ok("an empty file hashes as sha256 of no bytes", sha256_bytes(b"") == hashlib.sha256(b"").hexdigest())
    binary = b"\x89PNG\r\n\x1a\n\x00\x00IHDR\r\n"
    ok("a binary (NUL in the first 8000 bytes) hashes raw: its CR bytes are not folded",
       not is_text(binary) and sha256_bytes(binary) == hashlib.sha256(binary).hexdigest())
    lead_nul = b"\x00a\r\n"
    ok("a NUL at byte 0 makes the file binary",
       not is_text(lead_nul) and sha256_bytes(lead_nul) == hashlib.sha256(lead_nul).hexdigest())
    ok("the sniff window is exactly 8000 bytes: a NUL at byte 7999 is binary, at byte 8000 text",
       not is_text(b"x" * 7999 + b"\x00\r\n") and is_text(b"x" * 8000 + b"\x00\r\n")
       and TEXT_SNIFF_BYTES == 8000)
    late = b"a\r\n" * 4000 + b"\x00"
    ok("a NUL past the window leaves the file text, and the whole file is folded",
       is_text(late) and normalise(late) == b"a\n" * 4000 + b"\x00")
    control = b"\x01" * 300 + b"a\r\n"
    ok("a NUL-free control-heavy file is text and folded (git leaves it alone on every checkout)",
       is_text(control) and sha256_bytes(control) == sha256_bytes(b"\x01" * 300 + b"a\n"))
    big = (b"0123456789abcdef" * 4096 + b"\r\n") * 2       # 131076 bytes
    ok("the hash covers the whole content, past 8000 bytes and past 64 KiB",
       sha256_bytes(big) == hashlib.sha256(big.replace(b"\r\n", b"\n")).hexdigest()
       and sha256_bytes(big[:-1] + b"!") != sha256_bytes(big)
       and sha256_bytes(big[:-3] + b"!\r\n") != sha256_bytes(big))
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "sample.md"
        p.write_bytes(big)
        ok("sha256_file reads the whole file and folds it like sha256_bytes",
           sha256_file(p) == sha256_bytes(big) == sha256_bytes(big.replace(b"\r\n", b"\n")))
        p.write_bytes(big[:-3] + b"!\r\n")
        ok("an edit at the end of a large file moves sha256_file", sha256_file(p) != sha256_bytes(big))
        q = Path(td) / "sample.bin"
        q.write_bytes(binary)
        ok("sha256_file hashes a binary file raw and accepts a str path",
           sha256_file(str(q)) == hashlib.sha256(binary).hexdigest())
        root = Path(td)
        nested = root / "pipeline" / "x" / "a.template.json"
        native = nested.relative_to(root)
        state = ("relative_to" in vars(pathlib.PosixPath), vars(pathlib.PosixPath).get("relative_to"))
        # The patched method is called on a pure POSIX path, so the check runs the patch itself on
        # every platform (PosixPath cannot be instantiated on Windows).
        probe = pathlib.PurePosixPath("/r/pipeline/x/a.template.json")
        with windows_paths():
            winrel = pathlib.PosixPath.relative_to(probe, "/r")
        ok("windows_paths() makes relative_to give backslash str() and slash as_posix()",
           str(winrel) == "pipeline\\x\\a.template.json" and winrel.as_posix() == "pipeline/x/a.template.json")
        # Compared by class state and by the native result, so the check holds on Windows too, where
        # relative_to already gives backslashes and the patched PosixPath is never used.
        ok("windows_paths() restores PosixPath.relative_to when the block ends",
           ("relative_to" in vars(pathlib.PosixPath), vars(pathlib.PosixPath).get("relative_to")) == state
           and type(nested.relative_to(root)) is type(native)
           and str(nested.relative_to(root)) == str(native))
    if not _IN_MUTANT:
        for name, cond in _runner_controls():
            ok(f"runner control: {name}", cond)
        survivors = _run_mutants()
        skipped = len(_POSIX_ONLY & {r[0] for r in _MUTANTS}) if os.name == "nt" else 0
        ok(f"each of {len(_MUTANTS) - skipped} committed mutations is caught by the selftest it targets"
           + (f" ({skipped} POSIX-only not run on Windows)" if skipped else "")
           + (f" (survivors: {survivors})" if survivors else ""), not survivors)
        gaps = _coverage_gaps()
        ok("every module that hashes through file_hash or simulates Windows paths carries at least "
           f"{MIN_MUTANTS_PER_MODULE} committed rows" + (f" (short: {gaps})" if gaps else ""), not gaps)
    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    print(f"file_hash selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


def main(argv) -> int:
    if "--selftest" in argv:
        return selftest()
    if not argv:
        print(__doc__)
        return 2
    for a in argv:
        print(f"{sha256_file(a)}  {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
