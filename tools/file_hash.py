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

The selftest runs the committed mutation rows in child processes (`--run-rows`, rows as JSON on
stdin), at most 12 rows of one module per child and up to 8 children at a time, to keep the run
under the selftest sweep's per-tool limit.
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
     '    return f"http://127.0.0.1:{port}/"\n',
     '    return f"http://127.0.0.1:{port}"\n'),
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
     '    return f"http://127.0.0.1:{port}/", False\n',
     '    return f"http://127.0.0.1:{port}/", True\n'),
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
     '        port = ports("CREATOR_OS_WIZARD_PORT", WIZARD_BLOCK, note=lambda _msg: None)[0]\n    return f"http://127.0.0.1:{port}/", False\n',
     '        port = 8765 or ports("CREATOR_OS_WIZARD_PORT", WIZARD_BLOCK, note=lambda _msg: None)[0]\n    return f"http://127.0.0.1:{port}/", False\n'),
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
     '              if f"127.0.0.1:{p}/" not in url]',
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
     '        while not _shutdown.wait(0.5):\n            pass\n',
     '        _shutdown.wait(0)\n'),
    ('WC5 main skips wait_and_close', 'wizard.py',
     '    _wait_and_close(server)\n',
     '    server.shutdown()\n'),
    ('WC6 the wait is untimed again', 'wizard.py',
     '        while not _shutdown.wait(0.5):\n            pass\n',
     '        _shutdown.wait()\n'),
    ('WC7 one timed wait, not a loop', 'wizard.py',
     '        while not _shutdown.wait(0.5):\n            pass\n',
     '        if not _shutdown.wait(0.5):\n            pass\n'),
    ('WC8 Ctrl+C escapes the close', 'wizard.py',
     '            pass\n    except KeyboardInterrupt:\n        pass\n    finally:\n        server.shutdown()\n',
     '            pass\n    except RuntimeError:\n        pass\n    finally:\n        server.shutdown()\n'),
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
     'if name in env and (not env[name] or Path(env[name]).is_absolute())]'),
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
    ('ST03 setup example ignores home', 'setup.py',
     'example = (Path(home) if home is not None else Path.home()) / "CreatorOS"',
     'example = Path.home() / "CreatorOS"'),
    ('ST04 setup command word dropped', 'setup.py',
     '        _say("         python3 tools/profile_mirror.py sync',
     '        _say("         tools/profile_mirror.py sync'),
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
    # handoff/inbox.py (the sweep verb and the containment helpers) and handoff/runner.py (the
    # Outbox tag), chosen by the reviewer; the IB rows marked in _POSIX_ONLY need os.symlink.
    ('IB01 sweep is read from any word, not the first', 'handoff/inbox.py',
     'if argv[:1] == ["sweep"]:',
     'if "sweep" in argv:'),
    ('IB02 the sweep verb seals into the default ledger', 'handoff/inbox.py',
     'sweep_quarantine(hub, res, ledger_path=LEDGER_PATH)',
     'sweep_quarantine(hub, res)'),
    ('IB03 the sweep verb scans against the default ledger', 'handoff/inbox.py',
     'ledger=load_ledger(LEDGER_PATH)',
     'ledger=load_ledger()'),
    ('IB04 the sweep verb seals with nothing flagged', 'handoff/inbox.py',
     'if res["quarantined"]:',
     'if True:'),
    ('IB05 a failed move no longer sets exit 1', 'handoff/inbox.py',
     's.get("why") != "already swept or missing" for s in',
     's.get("why", "").startswith(("path escapes", "sealed in")) for s in'),
    ('IB06 an unwritable ledger exits 0', 'handoff/inbox.py',
     '"Inbox/Quarantine, so scan again before acting on it")\n            rc = 1',
     '"Inbox/Quarantine, so scan again before acting on it")\n            rc = 0'),
    ('IB07 a hub without an Inbox exits 0', 'handoff/inbox.py',
     'rc = 1 if "error" in res else 0',
     'rc = 0'),
    ('IB08 the sweep output is not ASCII-escaped', 'handoff/inbox.py',
     '    print(json.dumps(res, indent=2))\n    return rc',
     '    print(json.dumps(res, indent=2, ensure_ascii=False))\n    return rc'),
    ('IB09 a sweep usage error exits 1', 'handoff/inbox.py',
     '        print(__doc__)\n        return 2',
     '        print(__doc__)\n        return 1'),
    ('IB10 only a PermissionError on the ledger is caught', 'handoff/inbox.py',
     'except OSError as exc:\n            res["swept"]["error"]',
     'except PermissionError as exc:\n            res["swept"]["error"]'),
    ('IB11 a trailing --hub reads past the end', 'handoff/inbox.py',
     'if 0 <= i < len(argv) - 1 else ""',
     'if 0 <= i else ""'),
    ('IB12 the sweep verb scans against an empty ledger', 'handoff/inbox.py',
     'res = scan(hub, ledger=load_ledger(LEDGER_PATH))',
     'res = scan(hub, ledger={})'),
    ('IB13 the sweep verb reads a ledger beside the one named', 'handoff/inbox.py',
     'ledger=load_ledger(LEDGER_PATH)',
     'ledger=load_ledger(LEDGER_PATH.with_suffix(".bak"))'),
    ('IB14 the sweep output escapes only when nothing is flagged', 'handoff/inbox.py',
     '    print(json.dumps(res, indent=2))\n    return rc',
     '    print(json.dumps(res, indent=2, ensure_ascii=not res["quarantined"]))\n    return rc'),
    ('IB15 the sweep output decodes its escapes', 'handoff/inbox.py',
     '    print(json.dumps(res, indent=2))\n    return rc',
     '    print(json.dumps(res, indent=2).encode("ascii").decode("unicode_escape"))\n    return rc'),
    ('IB16 a scan OSError is not caught', 'handoff/inbox.py',
     'except OSError as exc:  # for example',
     'except ValueError as exc:  # for example'),
    ('IB17 a failed scan is reported without an error key', 'handoff/inbox.py',
     'res = {"error": f"scan failed: {exc}", "quarantined": []}',
     'res = {"note": f"scan failed: {exc}", "quarantined": []}'),
    ('IB18 a failed scan exits 0', 'handoff/inbox.py',
     'rc = 1 if "error" in res else 0',
     'rc = 1 if "error" in res and "proposals" in res else 0'),
    ('IB19 a failed scan error drops its prefix', 'handoff/inbox.py',
     'f"scan failed: {exc}"',
     'f"could not scan: {exc}"'),
    ('IB20 any skipped flagged file sets exit 1', 'handoff/inbox.py',
     's.get("why") != "already swept or missing" for s in',
     's.get("why") is not None for s in'),
    ('IB21 sweep_quarantine reports the raw refusal for a vanished file', 'handoff/inbox.py',
     'why = "already swept or missing" if refusal == "file no longer present" else refusal',
     'why = refusal'),
    ('IB22 the missing-entry refusal is reworded', 'handoff/inbox.py',
     '        return None, "file no longer present"\n    return entry, None',
     '        return None, "file no longer on disk"\n    return entry, None'),
    ('IB23 sweep_quarantine skips containment', 'handoff/inbox.py',
     'src, refusal = _confined_inbox_entry(hub, item.get("file", ""))',
     'src, refusal = hub / item.get("file", ""), None'),
    ('IB24 sweep_quarantine reports every refusal as missing', 'handoff/inbox.py',
     'why = "already swept or missing" if refusal == "file no longer present" else refusal',
     'why = "already swept or missing"'),
    ('IB25 the Inbox escape test is dropped', 'handoff/inbox.py',
     'if not _under(cand, inbox_real):',
     'if False:'),
    ('IB26 the sealed test compares exact case', 'handoff/inbox.py',
     'if _under(cand, quar_real, fold=True):',
     'if _under(cand, quar_real):'),
    ('IB27 the sealed test folds only the candidate', 'handoff/inbox.py',
     'child, parent = os.path.normcase(child).casefold(), os.path.normcase(parent).casefold()',
     'child, parent = os.path.normcase(child).casefold(), parent'),
    ('IB28 the sealed test folds only the sealed folder', 'handoff/inbox.py',
     'child, parent = os.path.normcase(child).casefold(), os.path.normcase(parent).casefold()',
     'child, parent = child, os.path.normcase(parent).casefold()'),
    ('IB29 a containment refusal exits 0', 'handoff/inbox.py',
     's.get("why") != "already swept or missing" for s in',
     's.get("why", "").startswith("move failed") for s in'),
    ('IB30 containment resolves no symlink', 'handoff/inbox.py',
     'cand = os.path.realpath(hub / rel)',
     'cand = os.path.abspath(hub / rel)'),
    ('IB31 the Inbox test folds case', 'handoff/inbox.py',
     'if not _under(cand, inbox_real):',
     'if not _under(cand, inbox_real, fold=True):'),
    ('IB32 the sweep judges an entry by its target', 'handoff/inbox.py',
     'src, refusal = _confined_inbox_entry(hub, item.get("file", ""))',
     'src, refusal = _confined_inbox_file(hub, item.get("file", ""))'),
    ('IB33 the entry check resolves the entry, not its folder', 'handoff/inbox.py',
     'folder = os.path.realpath(entry.parent)',
     'folder = os.path.realpath(entry)'),
    ('IB34 the entry sealed test compares exact case', 'handoff/inbox.py',
     'if _under(folder, os.path.realpath(hub / "Inbox" / "Quarantine"), fold=True):',
     'if _under(folder, os.path.realpath(hub / "Inbox" / "Quarantine")):'),
    ('IB35 the entry Inbox test is dropped', 'handoff/inbox.py',
     'if not _under(folder, os.path.realpath(hub / "Inbox")):',
     'if False:'),
    ('IB36 the entry Inbox test folds case', 'handoff/inbox.py',
     'if not _under(folder, os.path.realpath(hub / "Inbox")):',
     'if not _under(folder, os.path.realpath(hub / "Inbox"), fold=True):'),
    ('IB37 the entry check drops links', 'handoff/inbox.py',
     'if not (os.path.isfile(entry) or os.path.islink(entry)):',
     'if not os.path.isfile(entry):'),
    ('IB38 the entry check accepts a folder', 'handoff/inbox.py',
     'if not (os.path.isfile(entry) or os.path.islink(entry)):',
     'if not os.path.lexists(entry):'),
    ('IB39 the entry check returns the link target', 'handoff/inbox.py',
     'return entry, None',
     'return Path(os.path.realpath(entry)), None'),
    ('IB40 the entry folder resolves no symlink', 'handoff/inbox.py',
     'folder = os.path.realpath(entry.parent)',
     'folder = os.path.abspath(entry.parent)'),
    ('IB41 the entry name guard keeps only the empty name', 'handoff/inbox.py',
     'if entry.name in ("", ".", ".."):',
     'if entry.name in ("",):'),
    ('RN01 Cygwin and MSYS names tag linux', 'handoff/runner.py',
     'if s == "Windows" or "_NT" in s:',
     'if s == "Windows":'),
    ('RN02 the mac tag is renamed', 'handoff/runner.py',
     'return "mac"',
     'return "osx"'),
    ('RN03 the tag ignores the name it is given', 'handoff/runner.py',
     's = platform.system() if system is None else system',
     's = platform.system()'),
    ('RN04 the tag reads os.name, not the system name', 'handoff/runner.py',
     's = platform.system() if system is None else system',
     's = os.name if system is None else system'),
    ('RN05 delivery hard-codes the mac tag', 'handoff/runner.py',
     'tag = _platform_tag()',
     'tag = "mac"'),
    ('RN06 a numbered collision drops the tag', 'handoff/runner.py',
     'name = f"{job_type}.{stamp}.{n}.{tag}.json"',
     'name = f"{job_type}.{stamp}.{n}.mac.json"'),
    ('RN07 an unknown system tags windows', 'handoff/runner.py',
     '    return "linux"\n\n\ndef _deliver_outbox',
     '    return "windows"\n\n\ndef _deliver_outbox'),
    # P102: the cache path keys (cache.py, sync_cache.py, cache_records.py).
    ('C1 build keys str()', '../shared/cache/cache.py',
     'jf.relative_to(ROOT).as_posix(),',
     'str(jf.relative_to(ROOT)),'),
    ('C2 baseline keys str()', '../shared/cache/cache.py',
     'p.relative_to(ROOT).as_posix(): {',
     'str(p.relative_to(ROOT)): {'),
    ('C3 fts query raw source', '../shared/cache/cache.py',
     '{"source": _posix_key(s), "id": i, "title": t, "snippet": sn, "rank": round(r, 3)}',
     '{"source": s, "id": i, "title": t, "snippet": sn, "rank": round(r, 3)}'),
    ('C4 LIKE query raw source', '../shared/cache/cache.py',
     '{"source": _posix_key(s), "id": i, "title": t, "snippet": sn, "rank": None}',
     '{"source": s, "id": i, "title": t, "snippet": sn, "rank": None}'),
    ('C5 verify raw baseline keys', '../shared/cache/cache.py',
     'base = {_posix_key(k): v for k, v in',
     'base = {k: v for k, v in'),
    ('C6 _posix_key identity', '../shared/cache/cache.py',
     'return str(key).replace("\\\\", "/")',
     'return str(key)'),
    ('S1 manifest str()', 'sync_cache.py',
     '"path": p.relative_to(ROOT).as_posix(),',
     '"path": str(p.relative_to(ROOT)),'),
    ('S2 status raw keys', 'sync_cache.py',
     'base = {str(k).replace("\\\\", "/"): v',
     'base = {str(k): v'),
    ('S3 status drops removed sources', 'sync_cache.py',
     'drift += [k for k in base if k not in cur]',
     'drift += []'),
    ('R1 posix_source identity', 'cache_records.py',
     'return str(source).replace("\\\\", "/")',
     'return str(source)'),
    ('R2 search id raw', 'cache_records.py',
     '{"id": f"{posix_source(s)}::{i}"',
     '{"id": f"{s}::{i}"'),
    ('R3 record_url raw', 'cache_records.py',
     'return REPO_BLOB + posix_source(source)',
     'return REPO_BLOB + source'),
    ('R4 fetch matches raw column', 'cache_records.py',
     '"WHERE replace(source, char(92), \'/\') = ? AND id = ?"',
     '"WHERE source = ? AND id = ?"'),
    ('R5 fetch returns raw source', 'cache_records.py',
     '    s = posix_source(s)\n',
     '    pass\n'),
    ('R6 fetch id not normalised', 'cache_records.py',
     '    source = posix_source(source)\n',
     '    pass\n'),
    ('R7 fetch serves .local.', 'cache_records.py',
     'if ".local." in source.lower() or not db.exists():',
     'if not db.exists():'),
    # P102: the inbox writers (handoff/inbox.py approve re-screen, ledger lock and corrupt copy, sealed copies).
    ('X1 approve trusts the proposal record', 'handoff/inbox.py',
     'offline_prior, unscreened = _approve_screen(src, item.get("offline_pattern_scan"))',
     'offline_prior, unscreened = item.get("offline_pattern_scan"), None'),
    ('X2 the re-run always wins', 'handoff/inbox.py',
     'return (given if _RISK_RANK.get(level, 0) > _RISK_RANK.get(fresh["risk_level"], 0) else fresh), None',
     'return fresh, None'),
    ('X3 no fail-closed for text', 'handoff/inbox.py',
     'if Path(path).suffix.lower().lstrip(".") in _SCREEN_REQUIRED_EXTS:',
     'if False:'),
    ('X4 unscreened refusal ignored', 'handoff/inbox.py',
     '        if unscreened:\n',
     '        if False:\n'),
    ('X5 srt not screen-required', 'handoff/inbox.py',
     '- {"docx", "xlsx", "pptx", "pdf"}',
     '- {"docx", "xlsx", "pptx", "pdf", "srt"}'),
    ('X7 binary drops the given record', 'handoff/inbox.py',
     '        return given, None\n    fresh = ',
     '        return None, None\n    fresh = '),
    ('X8 sweep takes no lock', 'handoff/inbox.py',
     '    with _locked(ledger_path):  # one writer at a time: the wizard, the sweep verb and approve\n        data, note = _ledger_for_write(ledger_path, now)\n        if note:\n            results["ledger_note"] = note\n        entries = data["entries"]\n',
     '    with open(os.devnull):\n        data, note = _ledger_for_write(ledger_path, now)\n        if note:\n            results["ledger_note"] = note\n        entries = data["entries"]\n'),
    ('X9 approve takes no lock', 'handoff/inbox.py',
     '    with _locked(ledger_path):  # one writer at a time: the wizard, the sweep verb and approve\n        data, note = _ledger_for_write(ledger_path, now)\n        if note:\n            results["ledger_note"] = note\n        entries = list(',
     '    with open(os.devnull):\n        data, note = _ledger_for_write(ledger_path, now)\n        if note:\n            results["ledger_note"] = note\n        entries = list('),
    ('X10 sealed copies counted as handled', 'handoff/inbox.py',
     'if digest in ledger and ledger[digest].get("status") == "quarantined":',
     'if False:'),
    ('X11 re-flag drops the sealed record', 'handoff/inbox.py',
     '"offline_pattern_scan": ledger[digest].get("offline_pattern_scan"),',
     '"offline_pattern_scan": None,'),
    ('X12 load_ledger reads non-object entries', 'handoff/inbox.py',
     'if isinstance(e, dict) and e.get("sha256")}',
     'if e.get("sha256")}'),
    ('X13 no corrupt copy written', 'handoff/inbox.py',
     '    kept.write_bytes(raw)\n',
     '    pass\n'),
    ('X14 non-object entries pass as a ledger', 'handoff/inbox.py',
     'if isinstance(entries, list) and all(isinstance(e, dict) for e in entries):',
     'if isinstance(entries, list):'),
    ('X15 unreadable ledger read as empty', 'handoff/inbox.py',
     '    raw = path.read_bytes()\n',
     '    raw = path.read_bytes() if path.is_file() else b""\n'),
    ('X16 load_ledger non-object top level', 'handoff/inbox.py',
     'entries = data.get("entries") if isinstance(data, dict) else None',
     'entries = data.get("entries")'),
    # P102: job origins by system (handoff/queue.py, wizard._queue_followup).
    ('Q1 the windows origin dropped', 'handoff/queue.py',
     'ALLOWED_ORIGINS = ("web", "desktop", "mac", "windows", "linux", "other")',
     'ALLOWED_ORIGINS = ("web", "desktop", "mac", "linux", "other")'),
    ('Q2 the linux origin dropped', 'handoff/queue.py',
     'ALLOWED_ORIGINS = ("web", "desktop", "mac", "windows", "linux", "other")',
     'ALLOWED_ORIGINS = ("web", "desktop", "mac", "windows", "other")'),
    ('Q3 the ticket name fixes the origin', 'handoff/queue.py',
     'name = f"job.{stamp}.{origin}.{ticket[\'job_id\'][:8]}.json"',
     'name = f"job.{stamp}.mac.{ticket[\'job_id\'][:8]}.json"'),
    ('WZ1 follow-ups queued as mac', 'wizard.py',
     'origin=_runner._platform_tag(), consent_note=note)',
     'origin="mac", consent_note=note)'),
    # P102: cache keys and their selftests, the inbox writers and ledger readers, job origins, the loopback addresses and the follow-up queue (second set).
    ('A-R1 posix_source replaces first backslash only', 'cache_records.py',
     'return str(source).replace("\\\\", "/")',
     'return str(source).replace("\\\\", "/", 1)'),
    ('A-R2 fetch title has no id fallback', 'cache_records.py',
     'return {"id": f"{s}::{i}", "title": ttl or i, "text": text,',
     'return {"id": f"{s}::{i}", "title": ttl, "text": text,'),
    ('A-R3 LIKE search returns one row', 'cache_records.py',
     '"AND source NOT LIKE \'%.local.%\' LIMIT 8", (like, like)).fetchall()',
     '"AND source NOT LIKE \'%.local.%\' LIMIT 1", (like, like)).fetchall()'),
    ('A-R4 FTS error not caught', 'cache_records.py',
     '            except Exception:  # noqa: BLE001 -- FTS5 syntax errors on hostile input -> LIKE',
     '            except sqlite3.IntegrityError:  # narrowed'),
    ('A-C1 _posix_key replaces first backslash only', '../shared/cache/cache.py',
     'return str(key).replace("\\\\", "/")',
     'return str(key).replace("\\\\", "/", 1)'),
    ('A-C2 build source relative to SOURCES', '../shared/cache/cache.py',
     'jf.relative_to(ROOT).as_posix(),',
     'jf.relative_to(SOURCES).as_posix(),'),
    ('A-C3 verify ignores removed sources', '../shared/cache/cache.py',
     '            drift.append(f"removed {key}")',
     '            pass'),
    ('A-S1 status normalises first backslash only', 'sync_cache.py',
     'base = {str(k).replace("\\\\", "/"): v',
     'base = {str(k).replace("\\\\", "/", 1): v'),
    ('A-S2 status compares bytes not sha256', 'sync_cache.py',
     'base[k]["sha256"] != cur[k]["sha256"]]',
     'base[k]["bytes"] != cur[k]["bytes"]]'),
    ('A-S3 status skips new sources', 'sync_cache.py',
     'drift = [k for k in cur if k not in base or base[k]',
     'drift = [k for k in cur if k in base and base[k]'),
    ('B-I1 equal rank keeps the proposal record', 'handoff/inbox.py',
     'return (given if _RISK_RANK.get(level, 0) > _RISK_RANK.get(fresh["risk_level"], 0) else fresh), None',
     'return (given if _RISK_RANK.get(level, 0) >= _RISK_RANK.get(fresh["risk_level"], 0) else fresh), None'),
    ('B-I2 txt leaves the screen-required set', 'handoff/inbox.py',
     '_SCREEN_REQUIRED_EXTS = frozenset(_classify.OFFLINE_PARSEABLE) - {"docx", "xlsx", "pptx", "pdf"}',
     '_SCREEN_REQUIRED_EXTS = frozenset(_classify.OFFLINE_PARSEABLE) - {"docx", "xlsx", "pptx", "pdf", "txt"}'),
    ('B-I3 extension test is case-sensitive', 'handoff/inbox.py',
     'if Path(path).suffix.lower().lstrip(".") in _SCREEN_REQUIRED_EXTS:',
     'if Path(path).suffix.lstrip(".") in _SCREEN_REQUIRED_EXTS:'),
    ('B-I5 corrupt copy named .bak only', 'handoff/inbox.py',
     'kept = _unique_dest(path.parent, f"{path.name}.corrupt.{stamp}.bak")',
     'kept = _unique_dest(path.parent, f"{path.name}.bak")'),
    ('B-I7 non-UTF-8 ledger raises', 'handoff/inbox.py',
     "    except (ValueError, RecursionError):  # not UTF-8, not JSON, or nested past the parser's depth\n",
     "    except (json.JSONDecodeError, RecursionError):  # not UTF-8, not JSON, or nested past the parser's depth\n"),
    ('B-I8 directory ledger read as missing', 'handoff/inbox.py',
     '    if not path.exists():\n        return {"schema_version": "0.1.0", "entries": []}, None\n',
     '    if not path.is_file():\n        return {"schema_version": "0.1.0", "entries": []}, None\n'),
    ('B-I9 re-flagged copy marked pass2 pending', 'handoff/inbox.py',
     '"ext": info.get("ext"), "pass2_pending": False,',
     '"ext": info.get("ext"), "pass2_pending": True,'),
    ('B-I10 approved copies re-flagged too', 'handoff/inbox.py',
     'ledger[digest].get("status") == "quarantined":',
     'ledger[digest].get("status") in ("quarantined", "approved"):'),
    ('B-I11 load_ledger list check dropped', 'handoff/inbox.py',
     '    if not isinstance(entries, list):\n        return {}\n',
     '    if False:\n        return {}\n'),
    ('B-I12 sweep writes the ledger after the lock', 'handoff/inbox.py',
     '            results["sealed"].append(item.get("file"))\n        _write_ledger(ledger_path, data)\n    return results',
     '            results["sealed"].append(item.get("file"))\n    _write_ledger(ledger_path, data)\n    return results'),
    ('B-I13 approve writes the ledger after the lock', 'handoff/inbox.py',
     '        data["entries"] = entries\n        _write_ledger(ledger_path, data)\n    return results',
     '        data["entries"] = entries\n    _write_ledger(ledger_path, data)\n    return results'),
    ('B-I14 approve reads the ledger before the lock', 'handoff/inbox.py',
     '    with _locked(ledger_path):  # one writer at a time: the wizard, the sweep verb and approve\n        data, note = _ledger_for_write(ledger_path, now)\n        if note:\n            results["ledger_note"] = note\n        entries = list(',
     '    data, note = _ledger_for_write(ledger_path, now)\n    with _locked(ledger_path):  # one writer at a time: the wizard, the sweep verb and approve\n        if note:\n            results["ledger_note"] = note\n        entries = list('),
    ('B-I15 re-flagged copy lands in needs_review', 'handoff/inbox.py',
     '            out["quarantined"].append({\n                "file": f"Inbox/{p.name}", "sha256": digest, "format_family": info.get("family"),',
     '            out["needs_review"].append({\n                "file": f"Inbox/{p.name}", "sha256": digest, "format_family": info.get("family"),'),
    ('N-L1 load_ledger lets RecursionError out', 'handoff/inbox.py',
     "    except (OSError, ValueError, RecursionError):  # RecursionError: JSON nested past the parser's depth\n",
     '    except (OSError, ValueError):\n'),
    ('N-L2 load_ledger lets a parse error out', 'handoff/inbox.py',
     "    except (OSError, ValueError, RecursionError):  # RecursionError: JSON nested past the parser's depth\n",
     '    except (OSError, RecursionError):\n'),
    ('N-L3 load_ledger lets a missing ledger out', 'handoff/inbox.py',
     "    except (OSError, ValueError, RecursionError):  # RecursionError: JSON nested past the parser's depth\n",
     '    except (ValueError, RecursionError):\n'),
    ('N-L4 _ledger_for_write lets RecursionError out', 'handoff/inbox.py',
     "    except (ValueError, RecursionError):  # not UTF-8, not JSON, or nested past the parser's depth\n",
     '    except ValueError:\n'),
    ('N-L5 _ledger_for_write lets a parse error out', 'handoff/inbox.py',
     "    except (ValueError, RecursionError):  # not UTF-8, not JSON, or nested past the parser's depth\n",
     '    except (UnicodeDecodeError, RecursionError):\n'),
    ('N-L6 deep ledger kept aside without a copy', 'handoff/inbox.py',
     '    kept.write_bytes(raw)\n',
     '    kept.write_bytes(raw) if len(raw) < 100000 else None\n'),
    ('N-A1 approve drops entries without a sha256', 'handoff/inbox.py',
     '        entries = list(data["entries"])  # an entry without a sha256 is kept, as sweep_quarantine keeps it\n',
     '        entries = [e for e in data["entries"] if e.get("sha256")]\n'),
    ('N-A2 known set reads a missing sha256', 'handoff/inbox.py',
     '        known = {e["sha256"] for e in entries if e.get("sha256")}\n',
     '        known = {e["sha256"] for e in entries}\n'),
    ('N-A3 approve starts from an empty entry list', 'handoff/inbox.py',
     '        entries = list(data["entries"])  # an entry without a sha256 is kept, as sweep_quarantine keeps it\n',
     '        entries = []\n'),
    ('F-Q1 retired branch disabled', 'handoff/queue.py',
     '    elif data["origin"] in RETIRED_ORIGINS:\n',
     '    elif False:\n'),
    ('F-Q2 retired and generic errors both raised', 'handoff/queue.py',
     '    elif data["origin"] not in ALLOWED_ORIGINS:',
     '    if data["origin"] not in ALLOWED_ORIGINS:'),
    ('F-Q3 cowork accepted again', 'handoff/queue.py',
     'ALLOWED_ORIGINS = ("web", "desktop", "mac", "windows", "linux", "other")',
     'ALLOWED_ORIGINS = ("web", "desktop", "mac", "windows", "linux", "other", "cowork")'),
    ('F-Q4 retired table keyed on another name', 'handoff/queue.py',
     'RETIRED_ORIGINS = {"cowork": ',
     'RETIRED_ORIGINS = {"co-work": '),
    ('N-Q1 non-string origin branch disabled', 'handoff/queue.py',
     '    if not isinstance(data["origin"], str):\n        errors.append("origin is not a string")\n',
     '    if False:\n        errors.append("origin is not a string")\n'),
    ('N-Q2 an integer origin passes the type test', 'handoff/queue.py',
     '    if not isinstance(data["origin"], str):\n',
     '    if not isinstance(data["origin"], (str, int)):\n'),
    ('N-Q3 list and dict origins pass the type test', 'handoff/queue.py',
     '    if not isinstance(data["origin"], str):\n',
     '    if not isinstance(data["origin"], (str, list, dict)):\n'),
    ('N-Q4 non-string origin reported with another reason', 'handoff/queue.py',
     '        errors.append("origin is not a string")\n',
     '        errors.append(f"origin {data[\'origin\']!r} not in {ALLOWED_ORIGINS}")\n'),
    ('N-C1 fetch .local. test case-sensitive', 'cache_records.py',
     'if ".local." in source.lower() or not db.exists():',
     'if ".local." in source or not db.exists():'),
    ('N-C2 fetch .local. test on upper-cased source', 'cache_records.py',
     'if ".local." in source.lower() or not db.exists():',
     'if ".local." in source.upper() or not db.exists():'),
    ('N-C3 fetch refusal skipped for a backslash id', 'cache_records.py',
     'if ".local." in source.lower() or not db.exists():',
     'if (".local." in source.lower() and "\\\\" not in record_id) or not db.exists():'),
    ('N-C7 search filters .local. case-sensitively in SQL and Python', 'cache_records.py',
     '"AND source NOT LIKE \'%.local.%\' ORDER BY bm25(records) LIMIT 8",\n                    (query,)).fetchall()\n            except Exception:  # noqa: BLE001 -- FTS5 syntax errors on hostile input -> LIKE\n                rows = []\n        if not rows:\n            like = f"%{query}%"\n            rows = conn.execute(\n                "SELECT source, id, title FROM records WHERE (text LIKE ? OR title LIKE ?) "\n                "AND source NOT LIKE \'%.local.%\' LIMIT 8", (like, like)).fetchall()\n    finally:\n        conn.close()\n    return {"results": [{"id": f"{posix_source(s)}::{i}", "title": ti or i, "url": record_url(s)}\n                        for s, i, ti in rows if ".local." not in s.lower()]}',
     '"AND instr(source, \'.local.\') = 0 ORDER BY bm25(records) LIMIT 8",\n                    (query,)).fetchall()\n            except Exception:  # noqa: BLE001 -- FTS5 syntax errors on hostile input -> LIKE\n                rows = []\n        if not rows:\n            like = f"%{query}%"\n            rows = conn.execute(\n                "SELECT source, id, title FROM records WHERE (text LIKE ? OR title LIKE ?) "\n                "AND instr(source, \'.local.\') = 0 LIMIT 8", (like, like)).fetchall()\n    finally:\n        conn.close()\n    return {"results": [{"id": f"{posix_source(s)}::{i}", "title": ti or i, "url": record_url(s)}\n                        for s, i, ti in rows if ".local." not in s]}'),
    ('H-L1 recorded refusal prints localhost', 'loopback_server.py',
     'return [f"{name} is already running at http://127.0.0.1:{exc.port}/ (the port it last "',
     'return [f"{name} is already running at http://localhost:{exc.port}/ (the port it last "'),
    ('H-L2 in-use refusal prints localhost', 'loopback_server.py',
     'f"Open http://127.0.0.1:{exc.port}/ in your browser, or close the other window "',
     'f"Open http://localhost:{exc.port}/ in your browser, or close the other window "'),
    ('H-D1 dashboard prints localhost', 'dashboard/server.py',
     '    print(f"  URL: http://127.0.0.1:{PORT}")',
     '    print(f"  URL: http://localhost:{PORT}")'),
    ('H-D2 dashboard opens localhost', 'dashboard/server.py',
     '        webbrowser.open(f"http://127.0.0.1:{PORT}")',
     '        webbrowser.open(f"http://localhost:{PORT}")'),
    ('N-D1 dashboard opens the first port of its block', 'dashboard/server.py',
     '        webbrowser.open(f"http://127.0.0.1:{PORT}")',
     '        webbrowser.open(f"http://127.0.0.1:{_PORTS[0]}")'),
    ('N-D2 dashboard opens no browser', 'dashboard/server.py',
     '        webbrowser.open(f"http://127.0.0.1:{PORT}")',
     '        pass'),
    ('N-D3 dashboard opens the wizard address', 'dashboard/server.py',
     '        webbrowser.open(f"http://127.0.0.1:{PORT}")',
     '        webbrowser.open(_wizard_url())'),
    ('G-W2 wait step 3 s', 'wizard.py',
     '        while not _shutdown.wait(0.5):\n            pass\n',
     '        while not _shutdown.wait(3.0):\n            pass\n'),
    ('G-W3 follow-up input_ref dropped', 'wizard.py',
     'input_refs=[followup["input_ref"]] if followup.get("input_ref") else None,',
     'input_refs=None,'),
    ('G-W4 follow-up consent note dropped', 'wizard.py',
     'origin=_runner._platform_tag(), consent_note=note)',
     'origin=_runner._platform_tag(), consent_note=None)'),
    ('G-W5 wizard prints localhost', 'wizard.py',
     '    url = _wizard_url(port)\n',
     '    url = f"http://localhost:{port}/"\n'),
    ('G-W6 close keeps the port record', 'wizard.py',
     '        server.shutdown()\n        _forget_port()\n        print("\\nWizard closed.")',
     '        server.shutdown()\n        print("\\nWizard closed.")'),
    ('G-W7 follow-up origin fixed to linux', 'wizard.py',
     'origin=_runner._platform_tag(), consent_note=note)',
     'origin=_runner._platform_tag("Linux"), consent_note=note)'),
    ('N-W1 _wizard_url uses localhost', 'wizard.py',
     '    return f"http://127.0.0.1:{port}/"\n',
     '    return f"http://localhost:{port}/"\n'),
    ('N-W2 _wizard_url drops the trailing slash', 'wizard.py',
     '    return f"http://127.0.0.1:{port}/"\n',
     '    return f"http://127.0.0.1:{port}"\n'),
    ('N-W3 main rewrites the _wizard_url address', 'wizard.py',
     '    url = _wizard_url(port)\n',
     '    url = _wizard_url(port).replace("127.0.0.1", "localhost")\n'),
    ('N-W4 main opens a localhost address', 'wizard.py',
     '    _open_url(url)\n    return url',
     '    _open_url(f"http://localhost:{port}/")\n    return url'),
    # P102: the auditor's guard on Bash and PowerShell (sync_check invariant 14, readonly_bash_guard) and the git hooks' interpreter (install_hooks).
    ('GW1 the hook need not match PowerShell', 'sync_check.py',
     'GUARD_HOOK_TOOLS = ("Bash", "PowerShell")\n',
     'GUARD_HOOK_TOOLS = ("Bash",)\n'),
    ('GW2 one matched tool is enough', 'sync_check.py',
     '        if tool not in wired:\n',
     '        if not wired:\n'),
    ('GW3 an unnamed guarded agent passes', 'sync_check.py',
     '        if f\'"{agent}"\' not in GUARD_HOOK_COMMAND:\n',
     '        if False:\n'),
    ('GW4 the auditor may keep PowerShell', 'sync_check.py',
     '        if "PowerShell" not in deny:\n',
     '        if False:\n'),
    ('GW5 any guard command counts as wired', 'sync_check.py',
     '        if isinstance(entry, dict) and any(isinstance(h, dict) and h.get("command") == GUARD_HOOK_COMMAND\n',
     '        if isinstance(entry, dict) and any(isinstance(h, dict) and "readonly_bash_guard" in str(h.get("command"))\n'),
    ('GW6 the no-Python fallback lets the auditor through', 'sync_check.py',
     '\'to check this command; refused for the auditor agent" >&2; exit 2; fi; exit 0\')\n',
     '\'to check this command; refused for the auditor agent" >&2; exit 0; fi; exit 0\')\n'),
    ('GW7 the wiring reads the live tree, not the root given', 'sync_check.py',
     '    root = ROOT if root is None else Path(root)\n    out = []\n',
     '    root = ROOT\n    out = []\n'),
    ('RB1 the guard ignores PowerShell', 'readonly_bash_guard.py',
     '    if not isinstance(payload, dict) or payload.get("tool_name") not in ("Bash", "PowerShell"):\n',
     '    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":\n'),
    ('RB2 a PowerShell call is checked as Bash', 'readonly_bash_guard.py',
     '    if payload.get("tool_name") == "PowerShell":\n',
     '    if False:\n'),
    ('RB3 the PowerShell refusal exits 0', 'readonly_bash_guard.py',
     '        return 2, (f"readonly_bash_guard: refused for the {payload.get(\'agent_type\')} agent: the guard "\n',
     '        return 0, (f"readonly_bash_guard: refused for the {payload.get(\'agent_type\')} agent: the guard "\n'),
    ('RB4 PowerShell refused for every agent', 'readonly_bash_guard.py',
     '    if payload.get("agent_type") not in GUARDED_AGENT_TYPES:\n        return 0, ""\n    if payload.get("tool_name") == "PowerShell":\n',
     '    if payload.get("tool_name") == "PowerShell":\n        return 2, "x"\n    if payload.get("agent_type") not in GUARDED_AGENT_TYPES:\n        return 0, ""\n    if False:\n'),
    ('IH1 the hook tries python3 alone', 'install_hooks.py',
     '  for p in python3 python "py -3"; do $p -c "import sys" </dev/null >/dev/null 2>&1 && break; p=; done\n',
     '  p=python3\n'),
    ('IH2 the interpreter path is not quoted', 'install_hooks.py',
     '    return body.replace("@PYTHON@", _sh_quote(Path(python or sys.executable).absolute().as_posix()))\n',
     '    return body.replace("@PYTHON@", Path(python or sys.executable).absolute().as_posix())\n'),
    ('IH3 the hooks are written with CRLF', 'install_hooks.py',
     '        target.write_text(body, encoding="utf-8", newline="\\n")\n',
     '        target.write_text(body, encoding="utf-8", newline="\\r\\n")\n'),
    ('IH4 the pinned interpreter is skipped', 'install_hooks.py',
     'if "$CREATOR_OS_PY" -c "import sys" </dev/null >/dev/null 2>&1; then\n',
     'if false; then\n'),
    ('IH5 no working Python lets the commit through', 'install_hooks.py',
     'Run tools/install_hooks.py again with a working Python." >&2\n    exit 1\n',
     'Run tools/install_hooks.py again with a working Python." >&2\n    exit 0\n'),
    # P102: the sweep's per-tool time cap (selftest_sweep.TOOL_TIMEOUTS).
    ('SW1 the sweep keeps the default cap', 'selftest_sweep.py',
     '                                 capture_output=True, text=True, timeout=limit)\n',
     '                                 capture_output=True, text=True, timeout=PER_TOOL_TIMEOUT)\n'),
    ('SW2 the suite cap equals the default', 'selftest_sweep.py',
     'TOOL_TIMEOUTS = {"tools/surface_workflow_check.py": 900,\n',
     'TOOL_TIMEOUTS = {"tools/surface_workflow_check.py": 300,\n'),
    ('SW3 the per-tool lookup returns the default', 'selftest_sweep.py',
     '    return TOOL_TIMEOUTS.get(rel, PER_TOOL_TIMEOUT)\n',
     '    return PER_TOOL_TIMEOUT\n'),
    ('SW4 the cap names a renamed tool', 'selftest_sweep.py',
     'TOOL_TIMEOUTS = {"tools/surface_workflow_check.py": 900,\n',
     'TOOL_TIMEOUTS = {"tools/surface_workflow.py": 900,\n'),
    # P102: a scan cut at max_bytes reads as a partial screen (injection_scan, inbox._fully_screened).
    ('TR1 a cut record counts as a whole-file scan', 'handoff/inbox.py',
     '    return "risk_level" in rec and not rec.get("truncated")\n',
     '    return "risk_level" in rec\n'),
    ('TR3 approve moves a file it read only in part', 'handoff/inbox.py',
     '    if not _fully_screened(rec) and rec.get("risk_level") not in ("QUARANTINE", "BLOCK"):\n',
     '    if "risk_level" not in rec:\n'),
    ('TR4 approve drops a flag found in the part it read', 'handoff/inbox.py',
     '    if not _fully_screened(rec) and rec.get("risk_level") not in ("QUARANTINE", "BLOCK"):\n',
     '    if not _fully_screened(rec):\n'),
    ('TR5 scan_file does not mark a cut record', 'injection_scan.py',
     '        rec["truncated"] = True\n',
     '        pass\n'),
    # P102: the notes for a repo outside the user folder (env_paths, setup, wizard) and for older hub computers (wizard work order).
    ('OH1 a folder beside the home folder counts as inside', 'env_paths.py',
     '    return not (target == base or target.startswith(base + "\\\\"))\n',
     '    return not (target == base or target.startswith(base))\n'),
    ('OH2 the Windows gate is dropped', 'env_paths.py',
     '    if osname != "nt":\n        return False\n    home = Path(home) if home is not None else Path.home()\n    try:\n        target = ntpath.normcase(',
     '    if osname != "nt":\n        pass\n    home = Path(home) if home is not None else Path.home()\n    try:\n        target = ntpath.normcase('),
    ('OH3 the system is not read when none is given', 'env_paths.py',
     '    if osname is None:\n        osname = _os_name()\n    if osname != "nt":\n        return False\n',
     '    if osname is None:\n        osname = "posix"\n    if osname != "nt":\n        return False\n'),
    ('OH4 setup asks about the real home folder', 'setup.py',
     '    if env_paths.windows_outside_home(root, home=home):\n',
     '    if env_paths.windows_outside_home(root):\n'),
    ('OH5 setup prints no note', 'setup.py',
     '    if env_paths.windows_outside_home(root, home=home):\n',
     '    if False:\n'),
    ('OH6 setup notes the repo under the user folder', 'setup.py',
     '    if env_paths.windows_outside_home(root, home=home):\n',
     '    if not env_paths.windows_outside_home(root, home=home):\n'),
    ('OH7 the publishing screen prints no note', 'wizard.py',
     "    if env_paths.windows_outside_home(ROOT):  # P102: the drive's permissions reach the saved tokens\n",
     '    if False:\n'),
    ('OH8 the publishing screen asks about the home folder', 'wizard.py',
     "    if env_paths.windows_outside_home(ROOT):  # P102: the drive's permissions reach the saved tokens\n",
     '    if env_paths.windows_outside_home(pathlib.Path.home()):\n'),
    ('OH9 the publishing note example is not escaped', 'wizard.py',
     '        home_example = html.escape(str(pathlib.Path.home().joinpath("CreatorOS")))\n',
     '        home_example = str(pathlib.Path.home().joinpath("CreatorOS"))\n'),
    ('MV1 the work-order screen never warns', 'wizard.py',
     '    mixed = ("" if tag == "mac" else\n',
     '    mixed = ("" if True else\n'),
    ('MV2 the work-order screen warns on a Mac too', 'wizard.py',
     '    mixed = ("" if tag == "mac" else\n',
     '    mixed = ("" if False else\n'),
    ('MV3 the warning names windows whatever the system', 'wizard.py',
     '             f\'<div class="note">This computer queues work as <code>{tag}</code>. A computer that \'\n',
     '             f\'<div class="note">This computer queues work as <code>windows</code>. A computer that \'\n'),
    # P102 push 2: printed commands on Windows.
    ('LC1 the rewrite drops its lookbehind', 'env_paths.py',
     'r"(?<![\\w./\\\\-])python3 (?=(?:tools|shared)/)"',
     'r"python3 (?=(?:tools|shared)/)"'),
    ('LC2 a path before python3 is rewritten', 'env_paths.py',
     'r"(?<![\\w./\\\\-])python3 (?=(?:tools|shared)/)"',
     'r"(?<![\\w.-])python3 (?=(?:tools|shared)/)"'),
    ('LC3 any python3 command is rewritten', 'env_paths.py',
     'r"(?<![\\w./\\\\-])python3 (?=(?:tools|shared)/)"',
     'r"(?<![\\w./\\\\-])python3 (?=\\S)"'),
    ('LC4 the wizard rewrites JSON too', 'wizard.py',
     '        if content_type == "text/html":  # commands as this computer types them (py -3 on Windows)\n',
     '        if True:  # commands as this computer types them (py -3 on Windows)\n'),
    ('LC5 the wizard pages keep python3', 'wizard.py',
     '            body = env_paths.local_commands(body)\n',
     '            body = body\n'),
    ('LC6 setup prints python3', 'setup.py',
     '    print(env_paths.local_commands(msg), flush=True)',
     '    print(msg, flush=True)'),
    ('LC7 the rewrite pins the command to POSIX', 'env_paths.py',
     'command = python_command() if osname is None and which is None else python_command(osname, which)',
     'command = python_command("posix") if osname is None and which is None else python_command(osname, which)'),
    # P102 push 2: the sweep cap for file_hash.
    ('SW5 file_hash keeps the default cap', 'selftest_sweep.py',
     '                 "tools/file_hash.py": 900}\n',
     '                 "tools/file_hash.py": 300}\n'),
    ('SW6 the file_hash cap names another tool', 'selftest_sweep.py',
     '                 "tools/file_hash.py": 900}\n',
     '                 "tools/file_hashes.py": 900}\n'),
    # P102 push 2: UTF-8 output from the repo's tools.
    ('U1 tool_env drops PYTHONIOENCODING', 'env_paths.py',
     'env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")',
     'env.update(PYTHONUTF8="1")'),
    ('U2 tool_io decodes with the locale', 'env_paths.py',
     'return {"env": tool_env(base), "encoding": "utf-8", "errors": "replace"}',
     'return {"env": tool_env(base), "text": True}'),
    ('U3 utf8_stdio reconfigures a terminal', 'env_paths.py',
     'hasattr(stream, "reconfigure") and not stream.isatty():',
     'hasattr(stream, "reconfigure"):'),
    ('U4 utf8_stdio changes nothing', 'env_paths.py',
     'stream.reconfigure(encoding="utf-8", errors="replace")',
     'stream.isatty()'),
    ('U5 the job spawn decodes with the locale again', 'handoff/runner.py',
     'timeout=timeout, cwd=str(ROOT), **env_paths.tool_io())',
     'text=True, timeout=timeout, cwd=str(ROOT))'),
    ('U6 the import screen decodes with the locale again', 'wizard.py',
     'capture_output=True, timeout=900, **env_paths.tool_io())',
     'capture_output=True, text=True, timeout=900)'),
    ('U7 a tool crash reads as a wrong format', 'wizard.py',
     'if crashes is not None and "Traceback (most recent call last)" in err:',
     'if False:'),
    ('U8 the crash note is dropped', 'wizard.py',
     '        elif crashes:\n',
     '        elif False:\n'),
    ('U9 chapters keeps the code-page stdout', 'videoedit/chapters.py',
     '    env_paths.utf8_stdio()\n    try:\n        return _main(argv)',
     '    try:\n        return _main(argv)'),
    ('U10 mltxml keeps the code-page stdout', 'videoedit/mltxml.py',
     '    env_paths.utf8_stdio()\n    try:\n        return _main(argv)',
     '    try:\n        return _main(argv)'),
    ('U11 fcpxml keeps the code-page stdout', 'videoedit/fcpxml.py',
     '    env_paths.utf8_stdio()\n    try:\n        return _main(argv)',
     '    try:\n        return _main(argv)'),
    ('U12 import_parse keeps the code-page stdout', 'import_parse.py',
     '    env_paths.utf8_stdio()\n    try:\n        return _main(argv)',
     '    try:\n        return _main(argv)'),
    ('U13 library_complete keeps the code-page stdout', 'library_complete.py',
     '    env_paths.utf8_stdio()\n    try:\n        return _main(argv)',
     '    try:\n        return _main(argv)'),
    # P102 push 2: approve past a locked file; the bounded scan read.
    ('IA1 a failed approve move raises again', 'handoff/inbox.py',
     '            except OSError as exc:  # e.g. WinError 32 on Windows: the file is open in another program\n',
     '            except RuntimeError as exc:  # e.g. WinError 32 on Windows: the file is open in another program\n'),
    ('IA2 a refused move is still recorded', 'handoff/inbox.py',
     'then approve again): {exc}"})\n                continue\n            entries.append({',
     'then approve again): {exc}"})\n            entries.append({'),
    ('BR1 scan_file reads the whole file', 'injection_scan.py',
     '            raw = fh.read(max_bytes + 1)\n',
     '            raw = fh.read()\n'),
    ('BR2 scan_file reads exactly max_bytes', 'injection_scan.py',
     '            raw = fh.read(max_bytes + 1)\n',
     '            raw = fh.read(max_bytes)\n'),
    # P102 push 2: a locked ticket; files that cannot be read are not overwritten.
    ('WT1 a failed pass ends the watcher again', 'handoff/watcher.py',
     '            except Exception as exc:  # noqa: BLE001 - one failed pass must not end the watcher (P102)\n',
     '            except RuntimeError as exc:  # noqa: BLE001 - one failed pass must not end the watcher (P102)\n'),
    ('RA1 a locked ticket stops the pass again', 'handoff/runner.py',
     '    except OSError:\n        return False\n\n\ndef run_job',
     '    except ZeroDivisionError:\n        return False\n\n\ndef run_job'),
    ('RA2 a handled ticket is never archived', 'handoff/runner.py',
     '        q.archive_ticket(hub_root, ticket_path)\n        return True\n',
     '        return True\n'),
    ('DQ1 an unreadable schedule is not copied', 'dashboard/server.py',
     '    kept = _keep_corrupt_copy(QUEUE_PATH, raw)\n',
     '    kept = QUEUE_PATH\n'),
    ('DQ2 a schedule of the wrong shape is used as is', 'dashboard/server.py',
     '    if isinstance(data, dict) and isinstance(data.get("queue"), list):\n',
     '    if isinstance(data, dict):\n'),
    ('DQ3 the load note is saved into the schedule', 'dashboard/server.py',
     '    data = {k: v for k, v in data.items() if k != "load_note"}\n',
     '    data = dict(data)\n'),
    ('DQ4 each read makes another copy', 'dashboard/server.py',
     '            if old.read_bytes() == raw:\n                return old\n',
     '            if False:\n                return old\n'),
    ('WK1 the credential merge starts empty after a bad read', 'wizard.py',
     '        if not isinstance(creds, dict):\n            bak = _keep_credentials_copy(creds_path, raw)',
     '        if not isinstance(creds, dict) and False:\n            bak = _keep_credentials_copy(creds_path, raw)'),
    ('WK2 the credential merge takes no lock', 'wizard.py',
     '    with atomic_io.locked(creds_path):\n        return _merged_api_credentials(',
     '    with open(os.devnull):\n        return _merged_api_credentials('),
    ('WK3 the unreadable credentials are not copied', 'wizard.py',
     '    with os.fdopen(fd, "wb") as fh:\n        fh.write(raw)\n',
     '    with os.fdopen(fd, "wb") as fh:\n        pass\n'),
    ('WK4 the credential merge reads leniently', 'wizard.py',
     '_merged_api_credentials(_load_api_credentials(strict=True), plat, patch)',
     '_merged_api_credentials(_load_api_credentials(), plat, patch)'),
    # P102 push 2: files that cannot be read or archived, cut records, UTF-8 readers and logs, the hook probes.
    ('RF01 scan stops at a file it cannot read', 'handoff/inbox.py',
     'f"scan again): {exc}; left in place"})\n            continue\n',
     'f"scan again): {exc}; left in place"})\n            raise\n'),
    ('RF02 the scan note drops the error', 'handoff/inbox.py',
     'f"scan again): {exc}; left in place"',
     'f"scan again); left in place"'),
    ('RF03 approve stops at a file it cannot read', 'handoff/inbox.py',
     'f"another program, then approve again): {exc}"})\n                continue\n            if digest',
     'f"another program, then approve again): {exc}"})\n                raise\n            if digest'),
    ('RF04 the read guard catches only PermissionError', 'handoff/inbox.py',
     '            except OSError as exc:  # on Windows, a file another program holds open without read sharing\n                results',
     '            except PermissionError as exc:  # on Windows, a file another program holds open without read sharing\n                results'),
    ('RF05 the sweep command exits 0 for an unreadable file', 'handoff/inbox.py',
     '        rc = 1  # the scan held a file it could not read',
     '        rc = 0  # the scan held a file it could not read'),
    ('RF07 a cut record on another format keeps the proposal record', 'handoff/inbox.py',
     '        if "risk_level" not in rec:\n            return given, None\n',
     '        if True:\n            return given, None\n'),
    ("RF08 the cut mark leaves approve's record", 'handoff/inbox.py',
     '        fresh["truncated"] = True  # the tier read only the first max_bytes\n',
     '        pass\n'),
    ('RF09 run_pass archives an unparseable ticket directly', 'handoff/runner.py',
     '            _archive(hub_root, e["path"])\n            results.append({"job_id": key, "status": "refused"})',
     '            q.archive_ticket(hub_root, e["path"])\n            results.append({"job_id": key, "status": "refused"})'),
    ('RF10 run_pass archives a repeated job_id directly', 'handoff/runner.py',
     '        if jid in seen_ids:\n            _archive(hub_root, e["path"])',
     '        if jid in seen_ids:\n            q.archive_ticket(hub_root, e["path"])'),
    ('RF11 _archive lets the error out', 'handoff/runner.py',
     '    except OSError:\n        return False\n\n\ndef run_job',
     '    except OSError:\n        raise\n\n\ndef run_job'),
    ('RF12 the watcher command keeps the code page', 'handoff/watcher.py',
     '        return selftest()\n    env_paths.utf8_stdio()\n',
     '        return selftest()\n'),
    ('RF13 the failed-pass line drops the file name', 'handoff/watcher.py',
     'retrying next interval: {type(exc).__name__}: {exc}")',
     'retrying next interval: {type(exc).__name__}: {exc!r}")'),
    ('RF14 Ctrl+C escapes the watcher', 'handoff/watcher.py',
     '    except KeyboardInterrupt:\n        print("\\nhandoff watcher: stopped")',
     '    except RuntimeError:\n        print("\\nhandoff watcher: stopped")'),
    ('RF15 the schedule reader stops at a byte-order mark', 'dashboard/server.py',
     'data = json.loads(raw.decode("utf-8-sig"))',
     'data = json.loads(raw.decode("utf-8"))'),
    ('RF16 the strict credentials reader stops at a byte-order mark', 'wizard.py',
     'creds = json.loads(raw.decode("utf-8-sig"))',
     'creds = json.loads(raw.decode("utf-8"))'),
    ('RF17 the lenient credentials reader stops at a byte-order mark', 'wizard.py',
     'return json.loads(creds_path.read_text(encoding="utf-8-sig"))',
     'return json.loads(creds_path.read_text(encoding="utf-8"))'),
    ('RF18 the lenient credentials reader raises on bytes that are not UTF-8', 'wizard.py',
     '        except (OSError, ValueError):  # ValueError: not UTF-8, or not JSON\n',
     '        except (OSError, json.JSONDecodeError):  # ValueError: not UTF-8, or not JSON\n'),
    ('RF19 a repeated refusal makes another copy', 'wizard.py',
     '            if old.read_bytes() == raw:\n                return old\n        except OSError:\n            continue\n    stamp, n',
     '            if False:\n                return old\n        except OSError:\n            continue\n    stamp, n'),
    ('RF25 the pinned Python is used when its path exists', 'install_hooks.py',
     'if "$CREATOR_OS_PY" -c "import sys" </dev/null >/dev/null 2>&1; then\n',
     'if [ -e "$CREATOR_OS_PY" ]; then\n'),
    ('RF26 the PATH probe reads the hook stdin', 'install_hooks.py',
     'do $p -c "import sys" </dev/null >/dev/null 2>&1 && break',
     'do $p -c "import sys" >/dev/null 2>&1 && break'),
    ('RF27 the pin resolves links', 'install_hooks.py',
     '_sh_quote(Path(python or sys.executable).absolute().as_posix())',
     '_sh_quote(Path(python or sys.executable).resolve().as_posix())'),
    # P102 push 2: the reviewer's rows.
    ('A-IA1 approve catches only PermissionError', 'handoff/inbox.py',
     '            except OSError as exc:  # e.g. WinError 32 on Windows: the file is open in another program\n',
     '            except PermissionError as exc:  # e.g. WinError 32 on Windows: the file is open in another program\n'),
    ('A-IA2 a failed move stops the batch', 'handoff/inbox.py',
     'then approve again): {exc}"})\n                continue\n            entries.append({',
     'then approve again): {exc}"})\n                break\n            entries.append({'),
    ('A-IA3 a failed move is recorded in the ledger', 'handoff/inbox.py',
     'then approve again): {exc}"})\n                continue\n            entries.append({',
     'then approve again): {exc}"})\n                target = src\n            entries.append({'),
    ('A-IA4 mkdir left outside the guard', 'handoff/inbox.py',
     '            try:\n                processed.mkdir(parents=True, exist_ok=True)\n                target = _unique_dest(processed, src.name)',
     '            processed.mkdir(parents=True, exist_ok=True)\n            try:\n                target = _unique_dest(processed, src.name)'),
    ('A-TR1 scan drops the truncated mark', 'handoff/inbox.py',
     '                if rec.get("truncated"):\n                    entry["offline_pattern_scan"]["truncated"] = True\n',
     ''),
    ('A-TR2 a cut QUARANTINE is refused as unreadable, not sealed', 'handoff/inbox.py',
     'rec.get("risk_level") not in ("QUARANTINE", "BLOCK"):\n        if Path(path)',
     'rec.get("risk_level") not in ("BLOCK",):\n        if Path(path)'),
    ('A-TR3 scan seals only a whole-file flag', 'handoff/inbox.py',
     '                if rec["risk_level"] in ("QUARANTINE", "BLOCK"):\n                    entry["note"] = ("offline injection',
     '                if rec["risk_level"] in ("QUARANTINE", "BLOCK") and not rec.get("truncated"):\n                    entry["note"] = ("offline injection'),
    ('A-SF1 a file of exactly max_bytes is marked cut', 'injection_scan.py',
     '    truncated = len(raw) > max_bytes\n',
     '    truncated = len(raw) >= max_bytes\n'),
    ('A-SF2 scan_file reads ten times max_bytes', 'injection_scan.py',
     '            raw = fh.read(max_bytes + 1)\n',
     '            raw = fh.read(max_bytes * 10)\n'),
    ('A-SF3 every file is marked cut', 'injection_scan.py',
     '    truncated = len(raw) > max_bytes\n',
     '    truncated = bool(len(raw) - max_bytes)\n'),
    ('A-RA1 _archive catches only PermissionError', 'handoff/runner.py',
     '    except OSError:\n        return False\n\n\ndef run_job',
     '    except PermissionError:\n        return False\n\n\ndef run_job'),
    ('A-RA2 the done path archives directly', 'handoff/runner.py',
     '        status = "failed"\n    _archive(hub_root, ticket_path)\n',
     '        status = "failed"\n    q.archive_ticket(hub_root, ticket_path)\n'),
    ('A-RA3 the duplicate path archives directly', 'handoff/runner.py',
     ' Archive the extra ticket, run nothing.\n        _archive(hub_root, ticket_path)\n',
     ' Archive the extra ticket, run nothing.\n        q.archive_ticket(hub_root, ticket_path)\n'),
    ('A-RA4 the validation refusal archives directly', 'handoff/runner.py',
     '        q.write_result(hub_root, key, "refused", error="; ".join(errs), tool_version=_version())\n        _archive(hub_root, ticket_path)\n',
     '        q.write_result(hub_root, key, "refused", error="; ".join(errs), tool_version=_version())\n        q.archive_ticket(hub_root, ticket_path)\n'),
    ('A-WT1 the watcher catches only OSError', 'handoff/watcher.py',
     '            except Exception as exc:  # noqa: BLE001 - one failed pass must not end the watcher (P102)\n',
     '            except OSError as exc:  # noqa: BLE001 - one failed pass must not end the watcher (P102)\n'),
    ('A-WT2 the watcher swallows Ctrl+C during a pass', 'handoff/watcher.py',
     '            except Exception as exc:  # noqa: BLE001 - one failed pass must not end the watcher (P102)\n',
     '            except BaseException as exc:  # noqa: BLE001 - one failed pass must not end the watcher (P102)\n'),
    ('A-WT3 a failed pass yields no list', 'handoff/watcher.py',
     '                results = []\n',
     '                results = None\n'),
    ('A-DQ1 an invalid UTF-8 schedule raises', 'dashboard/server.py',
     '    except (UnicodeDecodeError, json.JSONDecodeError):\n        data = None\n',
     '    except json.JSONDecodeError:\n        data = None\n'),
    ('A-DQ2 the corrupt copy is not written', 'dashboard/server.py',
     '    kept.write_bytes(raw)\n    return kept\n',
     '    return kept\n'),
    ('A-DQ3 a stamp collision overwrites the earlier copy', 'dashboard/server.py',
     '    while kept.exists():\n',
     '    if False:\n'),
    ('A-WK1 invalid UTF-8 credentials raise UnicodeDecodeError', 'wizard.py',
     '        except (UnicodeDecodeError, json.JSONDecodeError):\n            creds = None\n',
     '        except json.JSONDecodeError:\n            creds = None\n'),
    ('A-WK2 the corrupt credentials copy is world-readable', 'wizard.py',
     'getattr(os, "O_BINARY", 0), 0o600)',
     'getattr(os, "O_BINARY", 0), 0o644)'),
    ('A-WK3 OAuth completion lets the refusal escape', 'wizard.py',
     '    try:\n        _merge_api_credentials(plat, patch)\n    except ValueError as exc:  # the credentials file did not parse; nothing was saved\n        return False, str(exc)\n',
     '    _merge_api_credentials(plat, patch)\n'),
    ('A-WK4 the writer reads leniently', 'wizard.py',
     '    if creds_path.exists() and strict:\n',
     '    if creds_path.exists() and not strict:\n'),
    ('A-LC1 shared/ commands are kept', 'env_paths.py',
     'r"(?<![\\w./\\\\-])python3 (?=(?:tools|shared)/)"',
     'r"(?<![\\w./\\\\-])python3 (?=tools/)"'),
    ('A-LC2 the space after the command is dropped', 'env_paths.py',
     'command + " ", text)',
     'command, text)'),
    ('A-LC3 a backslash path before python3 is rewritten', 'env_paths.py',
     'r"(?<![\\w./\\\\-])python3 (?=(?:tools|shared)/)"',
     'r"(?<![\\w./-])python3 (?=(?:tools|shared)/)"'),
    ('A-OH1 the comparison is case-sensitive', 'env_paths.py',
     '        target = ntpath.normcase(str(Path(path).expanduser().resolve()))\n',
     '        target = str(Path(path).expanduser().resolve())\n'),
    ('A-OH2 an unresolvable path is reported outside', 'env_paths.py',
     '    except (OSError, RuntimeError):\n        return False\n    return not (target == base',
     '    except (OSError, RuntimeError):\n        return True\n    return not (target == base'),
    ('A-U1 tool_env drops PYTHONUTF8', 'env_paths.py',
     'env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")',
     'env.update(PYTHONIOENCODING="utf-8")'),
    ('A-U2 utf8_stdio leaves stderr in the code page', 'env_paths.py',
     '    for stream in (sys.stdout, sys.stderr) if streams is None else streams:\n',
     '    for stream in (sys.stdout,) if streams is None else streams:\n'),
    ('A-U3 utf8_stdio uses strict errors', 'env_paths.py',
     'stream.reconfigure(encoding="utf-8", errors="replace")',
     'stream.reconfigure(encoding="utf-8")'),
    ('A-SU1 setup pins the rewrite to POSIX', 'setup.py',
     '    print(env_paths.local_commands(msg), flush=True)',
     '    print(env_paths.local_commands(msg, "posix"), flush=True)'),
    ('A-GW1 the matcher is read as one name', 'sync_check.py',
     '            wired |= set(str(entry.get("matcher", "")).split("|"))\n',
     '            wired |= {str(entry.get("matcher", ""))}\n'),
    ('A-GW2 a guarded agent named as a substring passes', 'sync_check.py',
     '        if f\'"{agent}"\' not in GUARD_HOOK_COMMAND:\n',
     '        if agent not in GUARD_HOOK_COMMAND:\n'),
    ('A-IH1 a failed probe keeps the last name', 'install_hooks.py',
     ' && break; p=; done\n',
     ' && break; done\n'),
    ('A-IH3 the probe accepts any exit', 'install_hooks.py',
     '$p -c "import sys" </dev/null >/dev/null 2>&1 && break; p=; done',
     '$p -c "import sys" </dev/null >/dev/null 2>&1; break; p=; done'),
    ('A-SW1 every tool gets 900 s', 'selftest_sweep.py',
     '    return TOOL_TIMEOUTS.get(rel, PER_TOOL_TIMEOUT)\n',
     '    return TOOL_TIMEOUTS.get(rel, 900)\n'),
    # P102 push 2: the reviewer's second-pass rows, and the size hold for cut text files.
    ('B-IN1 the unreadable file is listed as unknown', 'handoff/inbox.py',
     '            out["needs_review"].append({\n                "file": f"Inbox/{p.name}", "sha256": None,',
     '            out["unknown"].append({\n                "file": f"Inbox/{p.name}", "sha256": None,'),
    ('B-IN2 the unreadable entry is tagged content_pending', 'handoff/inbox.py',
     '"category_source": "unreadable", "pass2_pending": True,',
     '"category_source": "content_pending", "pass2_pending": True,'),
    ('B-IN3 the size hold takes every cut file', 'handoff/inbox.py',
     '        if ((entry.get("offline_pattern_scan") or {}).get("truncated")\n                and p.suffix.lower().lstrip(".") in _SCREEN_REQUIRED_EXTS):\n',
     '        if ((entry.get("offline_pattern_scan") or {}).get("truncated")\n                or p.suffix.lower().lstrip(".") in _SCREEN_REQUIRED_EXTS):\n'),
    ('B-IN4 approve read refusal goes on to the move', 'handoff/inbox.py',
     'then approve again): {exc}"})\n                continue\n            if digest != item.get("sha256"):',
     'then approve again): {exc}"})\n                digest = item.get("sha256")\n            if digest != item.get("sha256"):'),
    ('B-IN5 the cut mark is dropped from the fresh record', 'handoff/inbox.py',
     '    if rec.get("truncated"):\n        fresh["truncated"] = True  # the tier read only the first max_bytes\n',
     ''),
    ('B-IN6 an equal proposal level beats the cut record', 'handoff/inbox.py',
     '    return (given if _RISK_RANK.get(level, 0) > _RISK_RANK.get(fresh["risk_level"], 0) else fresh), None',
     '    return (given if _RISK_RANK.get(level, 0) >= _RISK_RANK.get(fresh["risk_level"], 0) else fresh), None'),
    ('B-IN7 the sweep looks for unreadable files in the wrong list', 'handoff/inbox.py',
     'for e in res.get("needs_review", [])):\n        rc = 1',
     'for e in res.get("unknown", [])):\n        rc = 1'),
    ('B-RN1 an unparseable ticket falls through to the job path', 'handoff/runner.py',
     '            results.append({"job_id": key, "status": "refused"})\n            continue\n        jid = e["data"].get("job_id")',
     '            results.append({"job_id": key, "status": "refused"})\n        jid = e["data"].get("job_id")'),
    ('B-RN2 _archive deletes a ticket it cannot move', 'handoff/runner.py',
     '    except OSError:\n        return False\n\n\ndef run_job',
     '    except OSError:\n        Path(ticket_path).unlink(missing_ok=True)\n        return False\n\n\ndef run_job'),
    ('B-WT1 the watcher command switches only stderr', 'handoff/watcher.py',
     '    env_paths.utf8_stdio()\n    if "--transport" in argv',
     '    env_paths.utf8_stdio([sys.stderr])\n    if "--transport" in argv'),
    ('B-WT2 the watcher catches only OSError and ValueError', 'handoff/watcher.py',
     '            except Exception as exc:  # noqa: BLE001 - one failed pass must not end the watcher (P102)\n',
     '            except (OSError, ValueError) as exc:  # noqa: BLE001 - one failed pass must not end the watcher (P102)\n'),
    ('B-WT3 Ctrl+C is raised out of watch', 'handoff/watcher.py',
     '    except KeyboardInterrupt:\n        print("\\nhandoff watcher: stopped")',
     '    except KeyboardInterrupt:\n        raise'),
    ('B-DQ1 the schedule copy is reused on a matching first byte', 'dashboard/server.py',
     '            if old.read_bytes() == raw:\n                return old\n',
     '            if old.read_bytes()[:1] == raw[:1]:\n                return old\n'),
    ('B-DQ2 the schedule is decoded as latin-1', 'dashboard/server.py',
     'data = json.loads(raw.decode("utf-8-sig"))',
     'data = json.loads(raw.decode("latin-1"))'),
    ('B-WK1 the credentials copy is opened without O_EXCL', 'wizard.py',
     'os.O_CREAT | os.O_EXCL | os.O_WRONLY',
     'os.O_CREAT | os.O_WRONLY | os.O_TRUNC'),
    ('B-WK2 the credentials copy drops its last byte', 'wizard.py',
     '        fh.write(raw)\n    return bak\n',
     '        fh.write(raw[:-1])\n    return bak\n'),
    ('B-WK3 the credentials copy is reused on equal length', 'wizard.py',
     '            if old.read_bytes() == raw:\n                return old\n        except OSError:\n            continue\n    stamp, n',
     '            if len(old.read_bytes()) == len(raw):\n                return old\n        except OSError:\n            continue\n    stamp, n'),
    ('B-WK4 the OAuth refusal loses its reason', 'wizard.py',
     '        return False, str(exc)\n    if plat == "google_drive":',
     '        return False, "nothing was saved"\n    if plat == "google_drive":'),
    ('B-WK5 the publishing flag flips before the merge', 'wizard.py',
     '    try:\n        _merge_api_credentials(plat, patch)\n    except ValueError as exc:  # the credentials file did not parse; nothing was saved\n',
     '    _update_capability_flag(f"{plat}_publishing", True)\n    try:\n        _merge_api_credentials(plat, patch)\n    except ValueError as exc:  # the credentials file did not parse; nothing was saved\n'),
    ('B-WS1 the isolated selftest keeps the real state path', 'wizard.py',
     '        _STATE_PATH, _SELFTEST_STATE_ISOLATED = pathlib.Path(td) / real_path.name, True\n',
     '        _STATE_PATH, _SELFTEST_STATE_ISOLATED = real_path, True\n'),
    ('B-WS2 the in-memory state is not put back', 'wizard.py',
     '                _state.clear()\n                _state.update(saved_state)\n',
     '                pass\n'),
    ('B-WS3 a changed real state file is not reported', 'wizard.py',
     '    if _file_state(real_path) != before:\n',
     '    if False:\n'),
    ('B-EP1 utf8_stdio switches the original streams', 'env_paths.py',
     '    for stream in (sys.stdout, sys.stderr) if streams is None else streams:\n',
     '    for stream in (sys.__stdout__, sys.__stderr__) if streams is None else streams:\n'),
    ('B-EP2 the target is folded by the host rules', 'env_paths.py',
     '        target = ntpath.normcase(str(Path(path).expanduser().resolve()))\n',
     '        target = os.path.normcase(str(Path(path).expanduser().resolve()))\n'),
    ('B-EP3 the prefix test drops the separator', 'env_paths.py',
     'target.startswith(base + "\\\\"))',
     'target.startswith(base))'),
    ('B-IH1 an executable pin counts as running', 'install_hooks.py',
     'if "$CREATOR_OS_PY" -c "import sys" </dev/null >/dev/null 2>&1; then',
     'if "$CREATOR_OS_PY" -c "import sys" </dev/null >/dev/null 2>&1 || [ -x "$CREATOR_OS_PY" ]; then'),
    ('B-IH3 the pin is written relative', 'install_hooks.py',
     'Path(python or sys.executable).absolute().as_posix()',
     'Path(os.path.relpath(python or sys.executable)).as_posix()'),
    ('RF29 a cut text file is proposed again', 'handoff/inbox.py',
     '            entry.update({"classified_as": None, "category_source": "oversize", "note": _OVERSIZE_NOTE})\n            out["needs_review"].append(entry)\n            continue\n',
     '            pass\n'),
    ('RF30 approve gives the could-not-read reason for a cut file', 'handoff/inbox.py',
     '            if rec.get("truncated"):\n                return None, f"not routed: {_OVERSIZE_NOTE}"\n',
     ''),
    ('RF31 the size hold skips JSON and CSV', 'handoff/inbox.py',
     '                and p.suffix.lower().lstrip(".") in _SCREEN_REQUIRED_EXTS):\n',
     '                and p.suffix.lower().lstrip(".") in ("srt", "vtt", "txt")):\n'),
    ('RF32 the selftest state path is not put back', 'wizard.py',
     '            _STATE_PATH, _SELFTEST_STATE_ISOLATED = real_path, False\n',
     '            _SELFTEST_STATE_ISOLATED = False\n'),
    # P102 push 2: a failing gate's report names its [FAIL] lines (battery.failure_lines).
    ('BT1 the report keeps only the last 8 lines', 'battery.py',
     '    shown = flagged[:most]\n',
     '    shown = []\n'),
    ('BT2 the flagged lines are not capped', 'battery.py',
     '    shown = flagged[:most]\n',
     '    shown = flagged[:]\n'),
    ('BT3 the long lines are not cut', 'battery.py',
     '    return [lines[i][:400] for i in sorted(set(shown))]\n',
     '    return [lines[i] for i in sorted(set(shown))]\n'),
    ('BT4 the run prints the old tail', 'battery.py',
     '            for line in failure_lines(r.stdout + r.stderr):\n',
     '            for line in (r.stdout + r.stderr).strip().splitlines()[-8:]:\n'),
    # P102: the wizard selftest refuses a lock on a file in the checkout.
    ('CL1 a lock in the checkout does not fail the run', 'wizard.py',
     '    if refused:\n        print(f"wizard selftest FAILED: it took a lock',
     '    if False:\n        print(f"wizard selftest FAILED: it took a lock'),
    ('CL2 a refused lock is taken anyway', 'wizard.py',
     '            return contextlib.nullcontext()\n        return real_locked(path)\n',
     '            return real_locked(path)\n        return real_locked(path)\n'),
    ('CL3 the credentials lock is not compared', 'wizard.py',
     '    if _file_state(creds_lock) != lock_before:\n',
     '    if False:\n'),
    ('CL4 the lock guard is not installed', 'wizard.py',
     '        atomic_io.locked = _checkout_lock_refused\n',
     '        pass\n'),
    ('CL5 the real lock is not put back', 'wizard.py',
     '            atomic_io.locked = real_locked\n',
     '            pass\n'),
    ('CL6 a folder beside the checkout counts as inside', 'wizard.py',
     'where.startswith(checkout.rstrip(os.sep) + os.sep)',
     'where.startswith(checkout)'),
    # P102: the Claude Desktop settings file on Windows (wizard._claude_config_targets and its helpers).
    ('CD1 the log is not read', 'wizard.py',
     '        if logged is not None and logged.parent.is_dir():\n',
     '        if False:\n'),
    ('CD2 a log path whose folder is missing is used', 'wizard.py',
     '        if logged is not None and logged.parent.is_dir():\n',
     '        if logged is not None:\n'),
    ('CD3 the oldest log line wins', 'wizard.py',
     '                if m and (best is None or m.group(1) > best[0]):\n',
     '                if m and (best is None or m.group(1) < best[0]):\n'),
    ("CD4 the packaged app's folder is ignored", 'wizard.py',
     '    if packaged:\n        out = [(p, "the packaged app\'s folder") for p in packaged]\n',
     '    if False:\n        out = [(p, "the packaged app\'s folder") for p in packaged]\n'),
    ('CD5 the usual file is skipped beside a package', 'wizard.py',
     '        if real.exists():\n            out.append((real, "the usual folder, which an older install reads"))\n',
     '        if False:\n            out.append((real, "the usual folder, which an older install reads"))\n'),
    ('CD6 the usual folder is written beside a package even without its file', 'wizard.py',
     '        if real.exists():\n            out.append((real, "the usual folder, which an older install reads"))\n',
     '        if True:\n            out.append((real, "the usual folder, which an older install reads"))\n'),
    ('CD7 a new file is not seeded', 'wizard.py',
     '    seed = next((c for _p, _w, c in loaded if c), {})\n',
     '    seed = {}\n'),
    ('CD8 one merged config goes into every file', 'wizard.py',
     '        cfg = cfg if cfg is not None else json.loads(json.dumps(seed))\n',
     '        cfg = seed\n'),
    ('CD9 a package folder without Roaming\\\\Claude counts', 'wizard.py',
     '        packaged = [d / _CONFIG_NAME for d in packaged if d.is_dir()]\n',
     '        packaged = [d / _CONFIG_NAME for d in packaged]\n'),
    # P102: the retired custom GPT and Gems surfaces (wizard aliases and the ChatGPT picker).
    ('RT1 an old custom GPT link finds no page', 'wizard.py',
     '_SURFACE_ALIASES = {"custom_gpt": "chatgpt_projects", "chatgpt_custom_gpt": "chatgpt_projects",\n',
     '_SURFACE_ALIASES = {"custom_gpt": "chatgpt_custom_gpt", "chatgpt_custom_gpt": "chatgpt_custom_gpt",\n'),
    ('RT2 an old Gems link finds no page', 'wizard.py',
     '                    "gemini_gems": "gemini_web"}\n',
     '                    "gemini_gems": "gemini_gems"}\n'),
    ('RT3 the ChatGPT picker offers the custom GPT again', 'wizard.py',
     '_CHATGPT_SURFACES = ("chatgpt_web_plain", "chatgpt_projects", "chatgpt_desktop")\n',
     '_CHATGPT_SURFACES = ("chatgpt_web_plain", "chatgpt_custom_gpt", "chatgpt_projects", "chatgpt_desktop")\n'),
)

# Rows whose mutant behaves exactly like the original on Windows, so only a POSIX run can catch
# them; on Windows the runner skips them and the selftest says how many it skipped.
_POSIX_ONLY = {"aio-dir-precheck-nt-only",
               "IB30 containment resolves no symlink",
               "IB32 the sweep judges an entry by its target",
               "IB33 the entry check resolves the entry, not its folder",
               "IB37 the entry check drops links",
               "IB39 the entry check returns the link target",
               "IB40 the entry folder resolves no symlink",
               "RF27 the pin resolves links",
               # os.path is ntpath on Windows, so this swap changes nothing there
               "B-EP2 the target is folded by the host rules",
               # the copy's mode check is skipped on Windows, where chmod sets only the read-only flag
               "A-WK2 the corrupt credentials copy is world-readable"}

# The function the runner scores for a module with no selftest(): it returns 0 when clean.
# sync_check.py is exempt from the selftest sweep (running it is its test).
_ENTRIES = {"sync_check.py": "_selfproof", "wizard.py": "_selftest_p101",
            "dashboard/server.py": "_selftest", "pick_folder.py": "_selftest",
            "env_paths.py": "_selftest", "setup.py": "_selftest_location"}


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


def _run_mutants(table=None, base=None, entries=None, posix_only=None, jobs=1) -> list:
    """The labels of rows no selftest caught, each with the reason when the row is invalid: an anchor
    not found exactly once, an anchor inside the entry function itself (the test that scores the
    row; other test helpers are not detected), a mutant that does not compile or load, a module with
    no entry function, or a module whose unmutated entry does not pass (then no row against it can
    be scored). Path class attributes, the working folder and the environment are restored after
    each row, so a row that leaks state cannot decide the rows after it. With jobs above 1 the rows
    of each module run in a process of their own, up to jobs at a time (_run_mutants_parallel)."""
    if jobs > 1:
        return _run_mutants_parallel(list(_MUTANTS if table is None else table), base, entries,
                                     posix_only, jobs)
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


# The parallel run: at most this many rows per child (a module with more is split, each part
# scoring its own baseline), and the seconds a child may take, under the selftest sweep's
# 300-second per-tool limit.
_CHUNK_ROWS = 12
_CHILD_TIMEOUT = 240


def _parallel_spec(base, entries, posix_only) -> dict:
    """The settings a --run-rows child gets with its rows."""
    return {"base": str(Path(base)) if base is not None else None,
            "entries": dict(_ENTRIES if entries is None else entries),
            "posix_only": sorted(_POSIX_ONLY if posix_only is None else posix_only)}


def _run_mutants_parallel(rows, base, entries, posix_only, jobs) -> list:
    """_run_mutants for rows in child processes (`file_hash.py --run-rows`: rows and settings as JSON
    on stdin), at most jobs at a time. A child gets rows of one module only, at most _CHUNK_ROWS of
    them, in table order, so a module's baseline and the state restored between its rows behave as
    in a serial run; survivors come back in table order. A child's result counts only when it
    exits 0 and its last stdout line is the JSON object carrying this run's nonce and the number of
    rows it was sent; otherwise each of its rows is reported as a survivor with the reason."""
    import concurrent.futures
    import json
    import secrets
    import subprocess
    chunks, by_module = [], {}
    for row in rows:
        by_module.setdefault(row[1], []).append(list(row))
    for module_rows in by_module.values():
        chunks += [module_rows[i:i + _CHUNK_ROWS] for i in range(0, len(module_rows), _CHUNK_ROWS)]
    spec = dict(_parallel_spec(base, entries, posix_only), nonce=secrets.token_hex(8))
    env = dict(os.environ, PYTHONIOENCODING="utf-8")

    def run(chunk):
        try:
            done = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--run-rows"],
                                  input=json.dumps(dict(spec, rows=chunk)), text=True,
                                  encoding="utf-8", errors="replace", capture_output=True,
                                  timeout=_CHILD_TIMEOUT, env=env)
        except (OSError, subprocess.SubprocessError) as exc:
            return [f"{r[0]} (worker failed: {type(exc).__name__})" for r in chunk]
        try:
            result = json.loads(done.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            result = None
        if (done.returncode != 0 or not isinstance(result, dict) or result.get("nonce") != spec["nonce"]
                or result.get("rows") != len(chunk) or not isinstance(result.get("survivors"), list)):
            return [f"{r[0]} (worker failed: exit {done.returncode}, no result)" for r in chunk]
        return result["survivors"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        found = [s for got in pool.map(run, chunks) for s in got]
    order = {row[0]: i for i, row in enumerate(rows)}
    return sorted(found, key=lambda s: order.get(s.split(" (", 1)[0], len(order)))


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
    # jobs above 1: each module's rows run in a child process of their own. Interleaved modules give
    # the serial survivors in table order, named entries included; process state one module leaves
    # (a sys attribute, which the serial run does not restore) does not reach another module's
    # rows; a child that cannot start reports its rows as survivors.
    with tempfile.TemporaryDirectory() as td3:
        d3 = Path(td3)
        (d3 / "good.py").write_text("x = 1\ndef selftest():\n    return 0 if x == 1 else 1\n", encoding="utf-8")
        (d3 / "red.py").write_text("def selftest():\n    return 1\n", encoding="utf-8")
        (d3 / "alt.py").write_text("x = 1\ndef check():\n    return 0 if x == 1 else 1\n", encoding="utf-8")
        (d3 / "leaker.py").write_text("import sys\nx = 1\ndef selftest():\n    sys.zz_file_hash_leak = 1\n"
                                      "    return 0\n", encoding="utf-8")
        (d3 / "victim.py").write_text("import sys\nx = 1\ndef selftest():\n"
                                      "    return 1 if hasattr(sys, 'zz_file_hash_leak') or x != 1 else 0\n",
                                      encoding="utf-8")
        mixed = [("p-equivalent", "good.py", "x = 1\n", "x = 1  # same\n"),
                 ("p-redbase", "red.py", "return 1", "return 2"),
                 ("p-entry", "alt.py", "x = 1\n", "x = 2\n"),
                 ("p-caught", "good.py", "x = 1\n", "x = 2\n"),
                 ("p-equivalent-2", "good.py", "x = 1\n", "x = 1  # again\n")]
        serial_mixed = _run_mutants(mixed, base=d3, entries={"alt.py": "check"})
        parallel_mixed = _run_mutants(mixed, base=d3, entries={"alt.py": "check"}, jobs=2)
        iso = [("leak-first", "leaker.py", "x = 1\n", "x = 1  # same\n"),
               ("victim-caught", "victim.py", "x = 1\n", "x = 2\n")]
        try:
            serial_iso = _run_mutants(iso, base=d3)
        finally:
            sys.__dict__.pop("zz_file_hash_leak", None)
        parallel_iso = _run_mutants(iso, base=d3, jobs=2)
        leaked_here = hasattr(sys, "zz_file_hash_leak")
        real_exe = sys.executable
        sys.executable = str(d3 / "no-such-python")
        try:
            no_worker = _run_mutants(mixed[:1], base=d3, jobs=2)
        finally:
            sys.executable = real_exe
        # A child whose selftest writes to the process's own stdout and stderr (non-UTF-8 bytes
        # included) is still read; one that stops before its result is reported, not taken as clean.
        (d3 / "noisy.py").write_text("import os\nx = 1\ndef selftest():\n"
                                     "    os.write(1, b'[] noise \\xe9 before the result\\n')\n"
                                     "    os.write(2, b'\\xe9 warning\\n')\n    return 0 if x == 1 else 1\n",
                                     encoding="utf-8")
        # These exit only inside a --run-rows child, never the process running this selftest.
        child = "    if sys.argv[1:] != ['--run-rows']:\n        return 0\n"
        (d3 / "dies.py").write_text("import os, sys\nx = 1\ndef selftest():\n" + child +
                                    "    os.write(1, b'[]\\n')\n    os._exit(0)\n", encoding="utf-8")
        (d3 / "forges.py").write_text("import os, sys\nx = 1\ndef selftest():\n" + child +
                                      "    os.write(1, b'{\"nonce\": \"guess\", \"rows\": 1, \"survivors\": []}\\n')\n"
                                      "    os._exit(0)\n", encoding="utf-8")
        (d3 / "exits_late.py").write_text("import atexit, os, sys\nx = 1\ndef selftest():\n" + child +
                                          "    atexit.register(lambda: os._exit(3))\n"
                                          "    return 0 if x == 1 else 1\n", encoding="utf-8")
        noisy = _run_mutants([("noisy-equivalent", "noisy.py", "x = 1\n", "x = 1  # same\n")],
                             base=d3, jobs=2)
        died = _run_mutants([("dies-row", "dies.py", "x = 1\n", "x = 2\n"),
                             ("forges-row", "forges.py", "x = 1\n", "x = 2\n"),
                             ("exits-late-row", "exits_late.py", "x = 1\n", "x = 2\n")],
                            base=d3, jobs=2)
        # Two modules whose selftests each take 1 s, two rows apiece with their baselines: with two
        # workers the run takes about 2 s, with one about 4 s.
        for name in ("slow_a.py", "slow_b.py"):
            (d3 / name).write_text("import time\nx = 1\ndef selftest():\n    time.sleep(1.0)\n"
                                   "    return 0 if x == 1 else 1\n", encoding="utf-8")
        import time as _time
        began = _time.monotonic()
        slow = _run_mutants([("slow-a", "slow_a.py", "x = 1\n", "x = 2\n"),
                             ("slow-b", "slow_b.py", "x = 1\n", "x = 2\n")], base=d3, jobs=2)
        slow_took = _time.monotonic() - began
    out.append(("with jobs above 1 the survivors match a serial run, in table order",
                parallel_mixed == serial_mixed
                == ["p-equivalent", "p-redbase (unmutated selftest: fail)", "p-equivalent-2"]))
    out.append(("with jobs above 1 a child runs rows of one module only: state one module "
                "leaves does not reach another module's rows",
                serial_iso == ["leak-first", "victim-caught (unmutated selftest: fail)"]
                and parallel_iso == ["leak-first"] and not leaked_here))
    out.append(("with jobs above 1 a worker that cannot start reports its rows as survivors",
                len(no_worker) == 1 and no_worker[0].startswith("p-equivalent (worker failed")))
    out.append(("with jobs above 1 a child that writes to its own stdout and stderr, non-UTF-8 "
                "bytes included, is read as in a serial run", noisy == ["noisy-equivalent"]))
    out.append(("with jobs above 1 a child that stops before its result, prints a result without "
                "this run's nonce, or exits non-zero after it reports its rows as survivors",
                [d.split(" (worker failed")[0] for d in died] == ["dies-row", "forges-row", "exits-late-row"]
                and all("(worker failed" in d for d in died)))
    out.append((f"with jobs above 1 two modules run at the same time ({slow_took:.1f} s for two 2 s "
                "modules)", slow == [] and slow_took < 3.6))
    out.append(("a child is sent the POSIX-only rows it must skip on Windows",
                _parallel_spec(None, None, {"x-row"})["posix_only"] == ["x-row"]
                and _parallel_spec(None, None, None)["posix_only"] == sorted(_POSIX_ONLY)))
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
        survivors = _run_mutants(jobs=min(8, os.cpu_count() or 1))
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
    if argv == ["--run-rows"]:   # a child of _run_mutants_parallel
        import json
        spec = json.loads(sys.stdin.read())
        rows = [tuple(r) for r in spec["rows"]]
        survivors = _run_mutants(rows, base=spec["base"], entries=spec["entries"],
                                 posix_only=set(spec["posix_only"]))
        print(json.dumps({"nonce": spec["nonce"], "rows": len(rows), "survivors": survivors}))
        return 0
    if not argv:
        print(__doc__)
        return 2
    for a in argv:
        print(f"{sha256_file(a)}  {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
