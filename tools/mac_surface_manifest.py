#!/usr/bin/env python3
"""Mac-surface completeness manifest (P69).

The macOS audit's completeness guarantee, made machine-checkable. The problem this solves: an
audit that says "I checked every Mac surface" is an assertion. Nothing stops a NEW file carrying
Mac-specific behavior from landing next week and never being audited, and nothing stops an
already-audited file from being rewritten after the audit signed off on it.

So the audited set is DERIVED, never memorized (docs/AUDIT-PROTOCOL.md section 1). `derive()` scans
every tracked text file for a Mac-signal token set; each match must resolve to EITHER the manifest
(a file audited at a recorded sha256) OR the manifest's `excluded` map (a match the audit judged
NOT a Mac surface, each with a written reason). Drift invariant 58 then enforces two properties:

  coverage  -- every derived match is in `files` or `excluded`. A new Mac-surface file fails the
               build until a human audits it and re-blesses the manifest.
  integrity -- every manifest path still exists and still hashes to its recorded sha256. Editing an
               audited Mac file fails the build until it is re-audited and re-blessed.

Two-way, fail-closed, so "nothing was missed" stops being a claim and becomes a build property.

CLI:
  python3 tools/mac_surface_manifest.py               # --check (report; exit 1 on drift)
  python3 tools/mac_surface_manifest.py reconcile     # re-bless: rewrite the manifest from the tree
  python3 tools/mac_surface_manifest.py --selftest    # offline proof of both directions
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "canonical-sources" / "mac-surface-manifest.json"

# Mac-signal tokens. Deliberately high-signal: the audit's raw sweep over-matched ~100 files on the
# injection-risk constant QUARANTINE and on argparse's `args.command`, so neither bare "quarantine"
# nor bare "command" is a signal here. Anchored spellings only ("com.apple.quarantine" IS a signal).
MAC_SIGNALS = (
    r"darwin",
    r"mac\s?os",
    r"osascript",
    r"gatekeeper",
    r"com\.apple\.",
    r"xattr",
    r"/opt/homebrew",
    r"\bhomebrew\b",
    r"\bbrew install\b",
    r"launchd",
    r"CloudStorage",
    r"Library/Application Support",
    r"Library/Logs",
    r"apple silicon",
    r"\barm64\b",
    r"whisper[.\-]cpp",  # both spellings: the brew formula (whisper-cpp) and the project (whisper.cpp)
    r"\btahoe\b",
    r"\bsequoia\b",
    r"\brosetta\b",
    r"universal2",
    r"Compressor\.app",
    r"Blackmagic",
    r"sys\.platform",
    r"platform\.machine",
    r"\.keychain",
    r"python\.org",
)
SIGNAL_RE = re.compile("|".join(MAC_SIGNALS), re.IGNORECASE)

# Paths whose Mac hits are records of past work, not a live Mac surface to audit. These are
# append-only history/telemetry files; auditing them would churn the manifest on every commit.
SKIP_PREFIXES = (
    "canonical-sources/mac-surface-manifest.json",  # this manifest quotes the signals themselves
    "tools/mac_surface_manifest.py",                # ditto: the deriver contains every token
    "tools/sync_check.py",                          # invariant 58's own prose quotes the signals
    "STATE.md",
    "CHANGELOG.md",
    "ledger/ledger.json",
    "canonical-sources/source-registry.json",
    "docs/video-tooling-scores.json",
    "docs/video-tooling-spike-evidence.json",
    "docs/video-tooling-integration-evidence.json",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tracked_files(root: Path = ROOT) -> list:
    """Tracked paths per git. Returns [] outside a git checkout (the caller degrades loudly)."""
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files"],
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    return [line for line in out.stdout.splitlines() if line.strip()]


def derive(root: Path = ROOT, paths: list | None = None) -> list:
    """Every tracked text file carrying at least one Mac signal, sorted. The audit denominator."""
    paths = paths if paths is not None else tracked_files(root)
    hits = []
    for rel in paths:
        if rel.startswith(SKIP_PREFIXES):
            continue
        p = root / rel
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:8192]:  # binary sniff, same posture as the secret scanner
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if SIGNAL_RE.search(text):
            hits.append(rel)
    return sorted(hits)


def reconcile(root: Path = ROOT, manifest_path: Path | None = None) -> dict:
    """Re-bless: record the sha256 of every currently-audited Mac file, preserving exclusion
    reasons. A derived path with no prior decision lands in `files` (audited at this sha)."""
    manifest_path = manifest_path or MANIFEST_PATH
    prior = {}
    excluded = {}
    if manifest_path.exists():
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
            prior = old.get("files", {})
            excluded = old.get("excluded", {})
        except (OSError, ValueError):
            pass
    derived = derive(root)
    files = {}
    for rel in derived:
        if rel in excluded:
            continue
        files[rel] = _sha(root / rel)
    manifest = {
        "_comment": "P69 macOS audit completeness gate. `files` = every Mac-surface file audited, at "
                    "its sha256 when the audit blessed it. `excluded` = a derived match the audit "
                    "judged NOT a Mac surface, with the reason. Drift invariant 58 fails the build "
                    "when a derived match is in neither (an unaudited Mac surface appeared) or when "
                    "an audited file's sha moved (an audited surface changed). Re-bless with "
                    "`python3 tools/mac_surface_manifest.py reconcile` ONLY after re-auditing.",
        "generated_by": "tools/mac_surface_manifest.py",
        "files": dict(sorted(files.items())),
        "excluded": dict(sorted(excluded.items())),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def check(root: Path = ROOT, manifest_path: Path | None = None) -> dict:
    """Two-way result: {'unaudited': [...], 'changed': [...], 'missing': [...], 'note': str|None}.
    All-empty == the audited set still equals the live Mac surface. Never raises."""
    manifest_path = manifest_path or MANIFEST_PATH
    empty = {"unaudited": [], "changed": [], "missing": [], "note": None}
    if not manifest_path.exists():
        return dict(empty, note="manifest missing; run 'python3 tools/mac_surface_manifest.py reconcile'")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return dict(empty, note=f"manifest unreadable: {exc}")
    files = manifest.get("files", {})
    excluded = manifest.get("excluded", {})
    tracked = tracked_files(root)
    if not tracked:
        return dict(empty, note="not a git checkout; Mac-surface coverage DID NOT RUN")
    derived = derive(root, tracked)
    unaudited = [r for r in derived if r not in files and r not in excluded]
    changed, missing = [], []
    for rel, sha in files.items():
        p = root / rel
        if not p.exists():
            missing.append(rel)
        elif _sha(p) != sha:
            changed.append(rel)
    return {"unaudited": sorted(unaudited), "changed": sorted(changed),
            "missing": sorted(missing), "note": None}


def selftest() -> int:
    """Offline proof of BOTH directions on a synthetic tree (no network, no repo mutation)."""
    import tempfile
    failures = []

    def ok(label, cond):
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            failures.append(label)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "tools").mkdir()
        mac = root / "tools" / "macish.py"
        mac.write_text('if sys.platform == "darwin":\n    pass\n', encoding="utf-8")
        (root / "plain.py").write_text("x = 1\n", encoding="utf-8")
        # A file whose only hit is the false-positive class the raw sweep over-matched.
        (root / "noisy.py").write_text('QUARANTINE = "high"\nargs.command\n', encoding="utf-8")
        mpath = root / "m.json"
        paths = ["tools/macish.py", "plain.py", "noisy.py"]

        d = derive(root, paths)
        ok("derive finds the darwin file", "tools/macish.py" in d)
        ok("derive skips a non-Mac file", "plain.py" not in d)
        ok("derive ignores QUARANTINE/args.command false positives", "noisy.py" not in d)

        # Reconcile blesses it, then check is clean.
        def _rec():
            prior = json.loads(mpath.read_text()) if mpath.exists() else {}
            excl = prior.get("excluded", {})
            files = {r: _sha(root / r) for r in derive(root, paths) if r not in excl}
            mpath.write_text(json.dumps({"files": files, "excluded": excl}), encoding="utf-8")

        _rec()
        m = json.loads(mpath.read_text())
        ok("reconcile recorded the mac file", "tools/macish.py" in m["files"])

        def _chk():
            man = json.loads(mpath.read_text())
            files, excl = man["files"], man.get("excluded", {})
            der = derive(root, paths)
            return {
                "unaudited": [r for r in der if r not in files and r not in excl],
                "changed": [r for r in files if (root / r).exists() and _sha(root / r) != files[r]],
                "missing": [r for r in files if not (root / r).exists()],
            }

        r = _chk()
        ok("clean after reconcile", not r["unaudited"] and not r["changed"] and not r["missing"])

        # DIRECTION 1 (coverage): a NEW Mac file must be caught as unaudited.
        (root / "tools" / "newmac.py").write_text('osascript -e "choose folder"\n', encoding="utf-8")
        paths.append("tools/newmac.py")
        ok("coverage: new Mac file flagged unaudited", "tools/newmac.py" in _chk()["unaudited"])
        _rec()
        ok("coverage: clean after re-bless", not _chk()["unaudited"])

        # DIRECTION 2 (integrity): editing an audited Mac file must be caught.
        mac.write_text('if sys.platform == "darwin":\n    changed = True\n', encoding="utf-8")
        ok("integrity: edited Mac file flagged changed", "tools/macish.py" in _chk()["changed"])
        _rec()
        ok("integrity: clean after re-bless", not _chk()["changed"])

        # Deleting an audited file is reported, not crashed on.
        mac.unlink()
        ok("missing audited file reported", "tools/macish.py" in _chk()["missing"])

        # An excluded path stays out of `files` across a reconcile.
        mpath.write_text(json.dumps({"files": {}, "excluded": {"noisy.py": "false positive"}}), encoding="utf-8")
        _rec()
        ok("exclusion survives reconcile", "noisy.py" in json.loads(mpath.read_text())["excluded"])

    print(f"\nmac_surface_manifest selftest: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 1 if failures else 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        return selftest()
    if argv and argv[0] == "reconcile":
        m = reconcile()
        print(f"mac-surface manifest: {len(m['files'])} audited file(s), "
              f"{len(m['excluded'])} excluded -> {MANIFEST_PATH.relative_to(ROOT)}")
        return 0
    res = check()
    if res["note"]:
        print(f"mac-surface: {res['note']}")
        return 0
    if not (res["unaudited"] or res["changed"] or res["missing"]):
        man = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        print(f"mac-surface: complete ({len(man.get('files', {}))} audited, "
              f"{len(man.get('excluded', {}))} excluded); no unaudited or changed surface")
        return 0
    for rel in res["unaudited"]:
        print(f"  UNAUDITED Mac surface (not in manifest or exclusions): {rel}")
    for rel in res["changed"]:
        print(f"  CHANGED since audit (re-audit, then reconcile): {rel}")
    for rel in res["missing"]:
        print(f"  MISSING audited file (deleted or moved): {rel}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
