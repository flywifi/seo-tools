#!/usr/bin/env python3
"""build_freshness_bundle.py -- stamp the knowledge-only surfaces with a visible freshness date (P36).

The claude.ai Projects, Custom GPT, and Gemini surfaces carry hand-authored knowledge digests under
implementation/**. They cannot execute the currency tools, so without help they silently lag
canonical-sources with no visible date. This tool gives each managed knowledge file a VISIBLE
freshness line and records a projection manifest so a published baseline can never quietly drift from
canonical.

It is an OWNER dev-time convenience: it writes the local working tree only, never auto-publishes, and
never touches GitHub. Users get ongoing freshness through their own store overlay (the live path);
this tool just dates the downloadable baseline (the static path).

  python3 tools/build_freshness_bundle.py --apply     # stamp files + write the manifest
  python3 tools/build_freshness_bundle.py --check      # verify stamps + manifest match canonical (exit 1 on drift)
  python3 tools/build_freshness_bundle.py --list       # show the managed files
  python3 tools/build_freshness_bundle.py --selftest   # offline test on temp fixtures
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "implementation" / "freshness-bundle.json"

# The knowledge that the model actually reads on each surface (README files are for the human).
MANAGED_GLOBS = [
    "implementation/claude/project/knowledge/*.md",
    "implementation/claude/project/system-prompt.md",
    "implementation/gpt/web/custom-instructions.md",
    "implementation/gemini/system-instruction.md",
]

MARKER_RE = re.compile(r"^_Data freshness: as of .*_$", re.M)


def managed_files(root=ROOT):
    out = []
    for g in MANAGED_GLOBS:
        out.extend(sorted(root.glob(g)))
    return out


def canonical_digest(root=ROOT):
    """Deterministic digest of the tracked canonical state: sorted registry source ids + the
    currency-map's as_of. Changes exactly when sources are added/removed or the map is re-dated, i.e.
    when the downloadable baseline's data actually moves."""
    reg_path = root / "canonical-sources" / "source-registry.json"
    cmap_path = root / "canonical-sources" / "data-currency-map.json"
    parts = []
    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        parts.append(",".join(sorted(s.get("id", "") for s in reg.get("sources", []))))
    except (OSError, json.JSONDecodeError):
        parts.append("")
    try:
        cmap = json.loads(cmap_path.read_text(encoding="utf-8"))
        parts.append(str(cmap.get("as_of", "")))
    except (OSError, json.JSONDecodeError):
        parts.append("")
    return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()


def freshness_line(as_of, digest):
    return f"_Data freshness: as of {as_of} (Creator OS baseline {digest[:8]}). Live updates come from your own store; see docs/FRESHNESS.md._"


def stamp_text(text, line):
    """Insert or replace the freshness marker line idempotently. If the file opens with YAML
    frontmatter, the marker goes just after the closing '---'; otherwise at the very top."""
    if MARKER_RE.search(text):
        return MARKER_RE.sub(line, text, count=1)
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            nl = text.find("\n", end + 1)
            if nl != -1:
                return text[:nl + 1] + "\n" + line + "\n" + text[nl + 1:]
    return line + "\n\n" + text


def apply(root=ROOT, as_of=None):
    as_of = as_of or date.today().isoformat()
    digest = canonical_digest(root)
    line = freshness_line(as_of, digest)
    stamped = []
    for f in managed_files(root):
        txt = f.read_text(encoding="utf-8")
        new = stamp_text(txt, line)
        if new != txt:
            f.write_text(new, encoding="utf-8")
        stamped.append({"file": str(f.relative_to(root)),
                        "sha256": hashlib.sha256(new.encode("utf-8")).hexdigest()})
    manifest = {"_boundary": "Owner dev-time projection. Local working tree only; never auto-published, never GitHub.",
                "as_of": as_of, "canonical_digest": digest, "managed_files": stamped,
                "generated_by": "tools/build_freshness_bundle.py"}
    (root / "implementation").mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH_ = root / "implementation" / "freshness-bundle.json"
    MANIFEST_PATH_.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def check(root=ROOT):
    """Return (ok, problems). Fails when: the manifest is missing; a managed file lacks a freshness
    marker; a managed file is missing; or the manifest's canonical_digest no longer matches canonical
    (the baseline drifted from the data and needs a re-stamp)."""
    problems = []
    mpath = root / "implementation" / "freshness-bundle.json"
    if not mpath.exists():
        return False, ["freshness-bundle.json manifest missing; run --apply"]
    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"manifest unreadable: {exc}"]
    files = managed_files(root)
    listed = {m["file"] for m in manifest.get("managed_files", [])}
    for f in files:
        rel = str(f.relative_to(root))
        txt = f.read_text(encoding="utf-8")
        if not MARKER_RE.search(txt):
            problems.append(f"{rel}: missing freshness marker (run --apply)")
        if rel not in listed:
            problems.append(f"{rel}: not recorded in the projection manifest")
    cur = canonical_digest(root)
    if manifest.get("canonical_digest") != cur:
        problems.append("canonical data changed since the last projection; re-run --apply so the "
                        "baseline's as_of stamp matches the data")
    return (not problems), problems


def selftest():
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    d = Path(tempfile.mkdtemp())
    (d / "canonical-sources").mkdir()
    (d / "implementation" / "claude" / "project" / "knowledge").mkdir(parents=True)
    (d / "implementation" / "gpt" / "web").mkdir(parents=True)
    (d / "implementation" / "gemini").mkdir(parents=True)
    (d / "canonical-sources" / "source-registry.json").write_text(
        json.dumps({"sources": [{"id": "a"}, {"id": "b"}]}), encoding="utf-8")
    (d / "canonical-sources" / "data-currency-map.json").write_text(
        json.dumps({"as_of": "2026-07-05"}), encoding="utf-8")
    kf = d / "implementation" / "claude" / "project" / "knowledge" / "01-x.md"
    kf.write_text("---\nname: x\ndescription: y\n---\n\n# Body\ncontent\n", encoding="utf-8")
    sp = d / "implementation" / "gpt" / "web" / "custom-instructions.md"
    sp.write_text("You are a GPT.\n", encoding="utf-8")
    si = d / "implementation" / "gemini" / "system-instruction.md"
    si.write_text("You are a Gem.\n", encoding="utf-8")

    ok("check fails before apply (no manifest)", check(d)[0] is False)
    m = apply(d, as_of="2026-07-05")
    ok("apply stamps all 3 managed files", len(m["managed_files"]) == 3)
    ok("frontmatter file stamped AFTER the frontmatter",
       kf.read_text(encoding="utf-8").split("---", 2)[2].lstrip().startswith("_Data freshness:"))
    ok("no-frontmatter file stamped at top",
       si.read_text(encoding="utf-8").startswith("_Data freshness:"))
    ok("check passes after apply", check(d)[0] is True)

    # idempotent: re-apply does not duplicate the marker
    apply(d, as_of="2026-07-06")
    ok("marker is not duplicated on re-apply",
       kf.read_text(encoding="utf-8").count("_Data freshness:") == 1)
    ok("re-apply updated the date", "2026-07-06" in kf.read_text(encoding="utf-8"))

    # digest drift detected
    (d / "canonical-sources" / "source-registry.json").write_text(
        json.dumps({"sources": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}), encoding="utf-8")
    ok_, probs = check(d)
    ok("digest drift fails check", ok_ is False and any("re-run --apply" in p for p in probs))
    apply(d, as_of="2026-07-06")
    ok("re-apply clears the drift", check(d)[0] is True)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    if "--list" in argv:
        for f in managed_files():
            print(f.relative_to(ROOT))
        return 0
    if "--apply" in argv:
        m = apply()
        print(json.dumps({"as_of": m["as_of"], "canonical_digest": m["canonical_digest"][:8],
                          "stamped": len(m["managed_files"]),
                          "wrote": str(MANIFEST_PATH.relative_to(ROOT))}, indent=2))
        return 0
    if "--check" in argv:
        ok_, problems = check()
        print(json.dumps({"ok": ok_, "problems": problems}, indent=2))
        return 0 if ok_ else 1
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
