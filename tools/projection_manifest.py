#!/usr/bin/env python3
"""projection_manifest.py -- staleness signal for the hand-authored knowledge packs (P49 WS7).

The Claude Projects / Custom GPT / Gemini knowledge files are PROSE PROJECTIONS of the canonical
shared/*.md engines and protocols/*.md. They are hand-authored, so there is no generator to diff them
against -- but we CAN record the sha256 of each SOURCE engine at the moment a projection was last
reconciled, and flag when a source has changed since. That is a staleness SIGNAL (the projection may now
lag its source), not a prose content-diff. Mirrors the freshness-bundle mechanism.

  python3 tools/projection_manifest.py reconcile   # (re)write the manifest with current source shas
  python3 tools/projection_manifest.py --check      # list projections whose sources moved since reconcile
  python3 tools/projection_manifest.py --selftest    # offline test on temp fixtures
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "implementation" / "knowledge-projection-manifest.json"

# knowledge/instruction file (repo-relative) -> the shared engines + protocols whose content it projects.
# Edit the canonical source in shared/ or protocols/, then run `reconcile` to re-bless the projection.
_K = "implementation/claude/project/knowledge/"
PROJECTIONS = {
    _K + "01-creator-core.md": ["shared/pipeline-engine.md", "shared/brand-engine.md"],
    _K + "02-brand-voice.md": ["shared/brand-engine.md", "shared/voice-engine.md",
                               "protocols/formatting-metadata.md", "protocols/safety.md"],
    _K + "03-platform-seo.md": ["shared/platform-engine.md", "shared/seo-intelligence-engine.md"],
    _K + "04-protocols.md": ["protocols/no-fabrication.md", "protocols/formatting-metadata.md",
                             "protocols/safety.md", "protocols/quality-gates.md",
                             "protocols/research-citation.md"],
    _K + "05-content-spokes.md": ["shared/platform-engine.md", "shared/seo-intelligence-engine.md",
                                  "shared/web-intel-engine.md", "shared/audience-engine.md",
                                  "shared/brand-engine.md"],
    _K + "06-document-spoke.md": ["shared/docintel-engine.md", "shared/injection-guard-engine.md",
                                  "shared/transcription-engine.md", "shared/integrations-engine.md",
                                  "protocols/formatting-metadata.md", "protocols/safety.md",
                                  "protocols/quality-gates.md"],
    _K + "07-pipeline-spokes.md": ["shared/pipeline-engine.md", "shared/tasks-engine.md",
                                   "protocols/safety.md", "protocols/no-fabrication.md",
                                   "protocols/quality-gates.md"],
    _K + "08-key-atoms.md": ["shared/seo-intelligence-engine.md", "shared/platform-engine.md",
                             "shared/brand-engine.md", "shared/voice-engine.md",
                             "shared/web-intel-engine.md", "shared/method.md",
                             "protocols/formatting-metadata.md", "protocols/no-fabrication.md",
                             "protocols/safety.md"],
    "implementation/claude/project/system-prompt.md": ["shared/pipeline-engine.md", "shared/voice-engine.md",
                                                       "protocols/no-fabrication.md",
                                                       "protocols/formatting-metadata.md"],
    "implementation/gpt/web/custom-instructions.md": ["shared/brand-engine.md", "shared/voice-engine.md",
                                                      "protocols/no-fabrication.md",
                                                      "shared/seo-intelligence-engine.md",
                                                      "shared/tasks-engine.md"],
    "implementation/gpt/web/custom-instructions-compact.md": ["shared/brand-engine.md", "shared/voice-engine.md",
                                                              "protocols/no-fabrication.md"],
    "implementation/gpt/project/project-instructions.md": ["shared/pipeline-engine.md", "shared/voice-engine.md",
                                                           "protocols/no-fabrication.md",
                                                           "protocols/formatting-metadata.md"],
    "AGENTS.md": ["CLAUDE.md"],
    "implementation/gemini/system-instruction.md": ["shared/brand-engine.md", "shared/voice-engine.md",
                                                    "protocols/no-fabrication.md",
                                                    "shared/seo-intelligence-engine.md",
                                                    "shared/tasks-engine.md"],
}
# The combined pack (P49 WS6) contains every knowledge file, so it projects the union of their sources.
_COMBINED = "implementation/claude/project/creator-os-combined.md"


def _projections(root=ROOT):
    proj = {k: list(v) for k, v in PROJECTIONS.items()}
    union = sorted({s for k, v in PROJECTIONS.items() if k.startswith(_K) for s in v})
    proj[_COMBINED] = union
    return proj


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reconcile(root=ROOT):
    """(Re)write the manifest recording each source engine's current sha256 per projection."""
    proj = _projections(root)
    out = {}
    for kf, sources in proj.items():
        rec = {}
        for s in sources:
            p = root / s
            rec[s] = _sha(p) if p.exists() else None
        # P73 D6-F6: also pin the projection's OWN bytes. Recording only the sources meant a
        # projection hand-edited into disagreement with its source was undetectable: the source
        # sha had not moved, so nothing flagged it. AGENTS.md carried a narrowed version of the
        # registry single-writer rule for a whole phase for exactly this reason.
        pp = root / kf
        out[kf] = {"sources": rec, "projection": _sha(pp) if pp.exists() else None}
    manifest = {"_comment": "P49 WS7 staleness signal: sha256 of each shared engine/protocol at the time "
                            "its prose projection was last reconciled. If a source sha moves, drift "
                            "invariant 47 (advisory) flags the projection files that may now be stale. "
                            "Run `python3 tools/projection_manifest.py reconcile` after refreshing a "
                            "projection to re-bless it.",
                "generated_by": "tools/projection_manifest.py", "projections": out}
    mpath = root / "implementation" / "knowledge-projection-manifest.json"
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def check(root=ROOT):
    """Return a list of {knowledge_file, changed_sources, missing_sources} for projections whose sources
    moved since the last reconcile. Empty list == every projection is current. Never raises."""
    mpath = root / "implementation" / "knowledge-projection-manifest.json"
    if not mpath.exists():
        return [{"knowledge_file": "*", "changed_sources": [], "missing_sources": [],
                 "note": "manifest missing; run 'projection_manifest.py reconcile'"}]
    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [{"knowledge_file": "*", "changed_sources": [], "missing_sources": [],
                 "note": f"manifest unreadable: {exc}"}]
    recorded = manifest.get("projections", {})
    stale = []
    # P72 D6: a projection file that has been DELETED must not pass silently -- the manifest
    # records it, so its absence is staleness of the strongest kind.
    for kf in _projections(root):
        if not (root / kf).exists():
            stale.append({"knowledge_file": kf, "changed_sources": [], "missing_sources": [],
                          "note": "projection file missing (deleted or moved)"})
    for kf, sources in _projections(root).items():
        entry = recorded.get(kf, {})
        rec = entry.get("sources", {})
        changed, missing = [], []
        for s in sources:
            p = root / s
            if not p.exists():
                missing.append(s)
                continue
            if rec.get(s) != _sha(p):
                changed.append(s)
        # P73 D6-F6: a projection edited by hand, away from its source, is staleness too. Only
        # report it when the sources are unchanged -- if a source moved, the projection is
        # SUPPOSED to be rewritten, and flagging both would just be noise.
        pp = root / kf
        edited = False
        if pp.exists() and not changed and not missing:
            pinned = entry.get("projection")
            edited = pinned is not None and pinned != _sha(pp)
        if changed or missing or edited:
            row = {"knowledge_file": kf, "changed_sources": changed, "missing_sources": missing}
            if edited:
                row["note"] = ("projection edited by hand since reconcile while its sources were "
                               "unchanged (re-project from the source, or reconcile to re-bless)")
            stale.append(row)
    return stale


def selftest(root=ROOT):
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    d = Path(tempfile.mkdtemp())
    # minimal source tree covering the referenced files
    srcs = sorted({s for v in PROJECTIONS.values() for s in v})
    for s in srcs:
        p = d / s
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {s}\noriginal content\n", encoding="utf-8")
    for kf in list(PROJECTIONS) + [_COMBINED]:
        p = d / kf
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("projection\n", encoding="utf-8")

    ok("check reports missing manifest before reconcile", check(d) and check(d)[0]["knowledge_file"] == "*")
    reconcile(d)
    ok("clean immediately after reconcile", check(d) == [])
    # edit one source engine -> the projections that map it are flagged, others are not
    (d / "shared" / "brand-engine.md").write_text("# changed\nNEW\n", encoding="utf-8")
    stale = check(d)
    flagged = {e["knowledge_file"] for e in stale}
    ok("editing brand-engine flags 02-brand-voice", _K + "02-brand-voice.md" in flagged)
    ok("editing brand-engine flags the combined pack", _COMBINED in flagged)
    ok("a projection that does not map brand-engine is NOT flagged", _K + "04-protocols.md" not in flagged)
    reconcile(d)
    ok("reconcile re-blesses and clears the signal", check(d) == [])

    # P73 D6-F6: hand-editing a projection while its sources are untouched must be caught.
    target = _K + "04-protocols.md"
    (d / target).write_text("projection\nHAND EDITED, contradicts the source\n", encoding="utf-8")
    stale = check(d)
    row = next((e for e in stale if e["knowledge_file"] == target), None)
    ok("hand-editing a projection is flagged even though no source moved",
       row is not None and row.get("changed_sources") == [] and "edited by hand" in row.get("note", ""))
    ok("an untouched projection is NOT flagged by the self-hash",
       all(e["knowledge_file"] != _K + "02-brand-voice.md" for e in stale))
    reconcile(d)
    ok("reconcile re-blesses a deliberately rewritten projection", check(d) == [])
    # A moved source must not ALSO report a hand-edit: the projection is meant to be rewritten.
    (d / "shared" / "brand-engine.md").write_text("# changed again\nNEWER\n", encoding="utf-8")
    (d / (_K + "02-brand-voice.md")).write_text("rewritten for the new source\n", encoding="utf-8")
    row2 = next((e for e in check(d) if e["knowledge_file"] == _K + "02-brand-voice.md"), None)
    ok("a moved source reports the source, not a spurious hand-edit",
       row2 is not None and row2["changed_sources"] == ["shared/brand-engine.md"]
       and "note" not in row2)
    reconcile(d)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    print(f"selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    if "reconcile" in argv:
        m = reconcile()
        print(json.dumps({"reconciled": len(m["projections"]),
                          "wrote": str(MANIFEST_PATH.relative_to(ROOT))}, indent=2))
        return 0
    if "--check" in argv:
        stale = check()
        print(json.dumps({"ok": not stale, "stale": stale}, indent=2, ensure_ascii=False))
        return 0 if not stale else 1
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
