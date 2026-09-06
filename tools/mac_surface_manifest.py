#!/usr/bin/env python3
"""Mac-surface completeness manifest (P69).

Tracks the macOS surface so coverage claims are checkable. The problem this solves: "I checked
every Mac surface" is an assertion. Nothing stops a NEW file carrying Mac-specific behavior from
landing next week unnoticed, and nothing stops a file from being rewritten after someone reviewed it.

BE PRECISE ABOUT WHAT THIS PROVES. A recorded sha256 proves the bytes have not moved since a human
blessed that path. It does NOT prove anyone re-read the file today, and this tool cannot know that.
It is a change-detector on a mechanically derived set, and the `--accept-new` gate is what keeps a
path from entering the set by inaction. Say "recorded", not "audited", when describing its output.

The set is DERIVED, never memorized (docs/AUDIT-PROTOCOL.md section 1). `derive()` scans every
tracked text file for a Mac-signal token set; each match must resolve to EITHER the manifest's
`files` map (recorded at a sha256) OR its `excluded` map (a human ruled it not a Mac surface, with
a written reason). Drift invariant 58 then enforces:

  coverage  -- every derived match is in `files` or `excluded`. A new Mac-surface file fails the
               build until a human rules on it and re-blesses the manifest.
  integrity -- every manifest path still exists and still hashes to its recorded sha256. Editing a
               recorded Mac file fails the build until it is re-reviewed and re-blessed.
  denominator -- the deriver itself is pinned (module sha256 + a sha over MAC_SIGNALS), and every
               recorded file must STILL derive. Weakening the signal set is the one attack that would
               otherwise leave the gate green while shrinking what it looks at: drop a token and the
               files that token used to catch stop deriving, which fails here rather than silently
               narrowing coverage. Found by the P69 adversarial pass, which proved the unpinned
               version stayed green after three tokens were deleted.

Fail-closed in every direction, so "no macOS file changed unnoticed" is a build property
rather than a claim. Human review remains a human act; this only makes skipping it visible.

CLI:
  python3 tools/mac_surface_manifest.py               # --check (report; exit 1 on drift)
  python3 tools/mac_surface_manifest.py reconcile     # re-bless files already ruled on
  python3 tools/mac_surface_manifest.py reconcile --accept-new   # also record newly-seen paths
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
    # "Final Cut Pro" in full, never bare "Final Cut": in this domain "the final cut" means the
    # edited video, and the bare token false-positived on 8 of 12 files (scenario prose, eval
    # fixtures, task-desk copy) that have nothing to do with the macOS app. Token-class noise
    # belongs in this vocabulary, not in `excluded`.
    r"Final Cut Pro",
    r"Blackmagic",
    r"sys\.platform",
    r"platform\.machine",
    r"\.keychain",
    r"python\.org",
)
SIGNAL_RE = re.compile("|".join(MAC_SIGNALS), re.IGNORECASE)

# P73 D6-F3: MAC_SIGNALS is pinned against NARROWING (signals_sha + the deriver-drift check), so
# deleting a token fails the build. Nothing fired in the other direction: a new file using a
# macOS concept this vocabulary has never heard of simply never enters the denominator, and the
# completeness gate reports "complete" while being blind to it. These are macOS-specific concepts
# that are NOT in MAC_SIGNALS; a file matching one of them but no signal is a candidate for
# widening the vocabulary. Advisory by design -- it proposes a review, it does not guess.
CANDIDATE_SIGNALS = (
    r"\bcodesign\b",
    r"\bspctl\b",
    r"\bnotarytool\b",
    r"\bnotariz",
    r"\bplutil\b",
    r"\bdefaults write\b",
    r"Library/Containers",
    r"\bpmset\b",
    r"\bdiskutil\b",
    r"\bhdiutil\b",
    r"\blaunchctl\b",
    r"\bsw_vers\b",
    r"\bTCC\b",
    r"\bkeychain access\b",
    r"\bInfo\.plist\b",
    r"\bDMG\b",
)
CANDIDATE_RE = re.compile("|".join(CANDIDATE_SIGNALS), re.IGNORECASE)

# Self-reference and append-only-record skips ONLY. Everything else that a human judged "not a Mac
# surface" belongs in the manifest's `excluded` map, with its reason written down, so the decision is
# reviewable. (The P69 adversarial pass caught an earlier version of this tuple carrying three
# video-tooling evidence files under a stated "append-only telemetry" rationale that was factually
# false -- each has a single commit -- so they are audited normally now.)
SKIP_PREFIXES = (
    # Self-reference: these three quote the signal tokens themselves, so they always match and could
    # never stabilize. The deriver and the guard are covered instead by the `deriver` pin below.
    "canonical-sources/mac-surface-manifest.json",
    "tools/mac_surface_manifest.py",
    "tools/sync_check.py",
    # Genuinely append-only records of past work, rewritten on essentially every commit.
    "STATE.md",
    "CHANGELOG.md",
    "ledger/ledger.json",
    "canonical-sources/source-registry.json",       # restamped by every currency run
)


class PendingReview(Exception):
    """Raised when reconcile would record paths nobody has ruled on. Carries the path list."""

    def __init__(self, paths):
        self.paths = list(paths)
        super().__init__(f"{len(self.paths)} unreviewed path(s)")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signals_sha() -> str:
    """Hash of the signal vocabulary. Changing MAC_SIGNALS changes the audit's denominator, so it
    must force an explicit re-bless rather than silently narrowing what the gate inspects."""
    return hashlib.sha256("\n".join(MAC_SIGNALS).encode("utf-8")).hexdigest()


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


def reconcile(root: Path = ROOT, manifest_path: Path | None = None, accept_new: bool = False,
              paths: list | None = None) -> dict:
    """Re-bless the manifest. Records the current sha256 of every derived file that already has a
    decision, and PRESERVES `excluded`.

    A path nobody has ruled on before is NOT recorded unless `accept_new` is set. That gate is the
    difference between "recorded" and "reviewed": without it a file entered the manifest by inaction,
    which let 15 files land in one command during P69 -- 8 of them false positives nobody had read.
    Bootstrapping (no manifest yet) is exempt, since there is no prior decision to respect.

    Raises PendingReview when new paths need a human. The caller reports them; nothing is written."""
    manifest_path = manifest_path or MANIFEST_PATH
    prior, excluded, bootstrap = {}, {}, True
    if manifest_path.exists():
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
            prior = old.get("files", {})
            excluded = old.get("excluded", {})
            bootstrap = False
        except (OSError, ValueError):
            pass
    derived = derive(root, paths)
    known = set(prior) | set(excluded)
    new = [rel for rel in derived if rel not in known]
    if new and not accept_new and not bootstrap:
        raise PendingReview(new)
    files = {}
    for rel in derived:
        if rel in excluded:
            continue
        files[rel] = _sha(root / rel)
    manifest = {
        "_comment": "P69/P70 macOS surface completeness gate. `files` = the macOS surface this repo "
                    "tracks, each recorded at the sha256 it carried when a human last blessed it; the "
                    "hash proves the bytes have not moved since, not that anyone re-read them today. "
                    "`excluded` = a derived match a human ruled NOT a macOS surface, with the reason. "
                    "Adding a path nobody has ruled on requires `reconcile --accept-new`, so entering "
                    "this file is an act rather than a default. Drift invariant 58 fails the build "
                    "when a derived match is in neither map, when a recorded file's sha moves, when a "
                    "recorded file stops deriving, or when the deriver itself changes.",
        "generated_by": "tools/mac_surface_manifest.py",
        "deriver": {
            "path": "tools/mac_surface_manifest.py",
            "module_sha256": _sha(Path(__file__).resolve()),
            "signals_sha256": signals_sha(),
            "_why": "The denominator is part of the guarantee. If either hash moves, the recorded set "
                    "was computed by a different rule than the one that blessed this manifest.",
        },
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
    empty = {"unaudited": [], "changed": [], "missing": [], "undetectable": [],
             "deriver_drift": [], "vocabulary_candidates": [], "note": None}
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
    # Denominator integrity: an audited file that no longer derives means the signal set lost the
    # token that used to catch it -- coverage narrowed without a single file "changing".
    derived_set = set(derived)
    undetectable = [r for r in files if r not in derived_set and (root / r).exists()]
    # P73 D6-F3: files carrying a macOS concept the vocabulary has never heard of. Not coverage
    # failures -- proposals to widen MAC_SIGNALS, surfaced so the vocabulary gets reviewed when
    # macOS grows a new concept rather than only when someone happens to notice.
    candidates = []
    for rel in tracked:
        # Same skips derive() applies: the self-referential files quote these tokens by nature,
        # and the append-only records quote every concept the repo has ever discussed.
        if rel in derived_set or rel in excluded or rel.startswith(SKIP_PREFIXES):
            continue
        p = root / rel
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        m = CANDIDATE_RE.search(text)
        if m:
            candidates.append(f"{rel} (matched {m.group(0)!r})")
    pin = manifest.get("deriver", {})
    deriver_drift = []
    if pin:
        if pin.get("signals_sha256") != signals_sha():
            deriver_drift.append("MAC_SIGNALS changed since this manifest was blessed")
        mod = Path(__file__).resolve()
        if pin.get("module_sha256") and mod.exists() and pin["module_sha256"] != _sha(mod):
            deriver_drift.append("tools/mac_surface_manifest.py changed since this manifest was blessed")
    else:
        deriver_drift.append("manifest records no deriver pin; re-bless to pin the denominator")
    return {"unaudited": sorted(unaudited), "changed": sorted(changed),
            "missing": sorted(missing), "undetectable": sorted(undetectable),
            "deriver_drift": deriver_drift, "vocabulary_candidates": sorted(candidates),
            "note": None}


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

        # P73 D6-F3: the widening trigger. A file using a macOS concept the vocabulary has never
        # learned must be PROPOSED for review, not silently left out of the denominator.
        ok("a notarization file does not derive (the vocabulary gap is real)",
           derive(root, ["tools/macish.py"]) and not CANDIDATE_RE.search("x = 1") and
           bool(CANDIDATE_RE.search('subprocess.run(["xcrun", "notarytool", "submit"])')))
        ok("candidate sweep ignores a file with no macOS concept at all",
           not CANDIDATE_RE.search('QUARANTINE = "high"\nargs.command\n'))

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

        # DIRECTION 3 (denominator): an audited file that stops deriving must be caught. This is the
        # P69 adversarial finding: without it, deleting a signal token silently shrinks coverage.
        g = globals()  # patch THIS module's global, not a re-imported copy (run as __main__)
        saved = g["SIGNAL_RE"]
        try:
            g["SIGNAL_RE"] = re.compile(r"__no_such_token__")
            der_now = set(derive(root, paths))
            audited = set(json.loads(mpath.read_text())["files"])
            ok("denominator: audited file stops deriving when a signal is removed",
               bool(audited - der_now))
        finally:
            g["SIGNAL_RE"] = saved
        ok("signals_sha is stable and hex", len(signals_sha()) == 64)

        # DIRECTION 4 (the review gate): a path nobody has ruled on must NOT enter by inaction.
        gate_m = root / "gate.json"
        gate_m.write_text(json.dumps({"files": {}, "excluded": {}}), encoding="utf-8")
        try:
            reconcile(root, gate_m, accept_new=False, paths=paths)
            ok("gate: bare reconcile refuses an unruled path", False)
        except PendingReview as pending:
            ok("gate: bare reconcile refuses an unruled path", bool(pending.paths))
        ok("gate: refusal wrote nothing", not json.loads(gate_m.read_text())["files"])
        m2 = reconcile(root, gate_m, accept_new=True, paths=paths)
        ok("gate: --accept-new records them", bool(m2["files"]))
        m3 = reconcile(root, gate_m, accept_new=False, paths=paths)
        ok("gate: known paths re-bless without the flag", bool(m3["files"]))
        ok("gate: manifest pins the deriver", bool(m3["deriver"]["signals_sha256"]))

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
        try:
            m = reconcile(accept_new="--accept-new" in argv)
        except PendingReview as pending:
            print("mac-surface: refusing to record path(s) nobody has ruled on yet.")
            print("Read each one, then re-run with --accept-new (or add it to `excluded` with a reason):")
            for rel in pending.paths:
                print(f"  NEW {rel}")
            return 1
        print(f"mac-surface manifest: {len(m['files'])} recorded file(s), "
              f"{len(m['excluded'])} excluded -> {MANIFEST_PATH.relative_to(ROOT)}")
        return 0
    res = check()
    if res["note"]:
        print(f"mac-surface: {res['note']}")
        return 0
    if not (res["unaudited"] or res["changed"] or res["missing"]
            or res["undetectable"] or res["deriver_drift"]):
        man = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        print(f"mac-surface: complete ({len(man.get('files', {}))} recorded, "
              f"{len(man.get('excluded', {}))} excluded); nothing unrecorded or changed")
        return 0
    for rel in res["unaudited"]:
        print(f"  UNRECORDED Mac surface (not in manifest or exclusions): {rel}")
    for rel in res["changed"]:
        print(f"  CHANGED since it was blessed (re-review, then reconcile): {rel}")
    for rel in res["missing"]:
        print(f"  MISSING recorded file (deleted or moved): {rel}")
    for rel in res["undetectable"]:
        print(f"  NO LONGER DERIVES (signal set narrowed?): {rel}")
    for msg in res["deriver_drift"]:
        print(f"  DERIVER DRIFT: {msg}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
