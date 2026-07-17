#!/usr/bin/env python3
"""doc_freshness.py -- content-hash staleness signal for hand-authored maintainer/docs (P52).

Mirrors tools/projection_manifest.py, but binds prose DOCS to the CODE they describe (not shared engines
to their projections). Each high-value doc is mapped to the source files it documents; `reconcile` stamps
the sha256 of each source into a manifest, and `check` re-flags a doc as "may be stale" when a bound
source changes. Drift invariant 51 (advisory, non-blocking) surfaces the signal.

This is a STALENESS SIGNAL, not a prose diff: a moved source means the doc *might* now lag, so a human
should re-read it and re-bless it with `reconcile`. Emerging practice (content-hash binding), adopted
here as sound engineering and modeled on the repo's own invariant-47 precedent -- not an external
standard. Stdlib only; never raises on check.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "docs" / "doc-freshness-manifest.json"

# doc (repo-relative) -> the code files it documents. Keep bindings TIGHT (a change to a bound file
# should plausibly require re-reading the doc); coarse bindings cause churn. Advisory only.
DOC_SOURCES = {
    "tools/publishing/MAINTAINER_README.md": [
        "tools/publishing/__init__.py",
        "tools/publishing/youtube.py",
        "tools/publishing/instagram.py",
        "tools/publishing/tiktok.py",
        "tools/publishing/pinterest.py",
        "tools/publishing/_http.py",
        "tools/oauth_flow.py",
        "tools/publishing_compliance.py",
    ],
    "docs/PUBLISHING.md": [
        "tools/publishing/youtube.py",
        "tools/publishing/instagram.py",
        "tools/publishing/tiktok.py",
        "tools/publishing/pinterest.py",
        "tools/oauth_flow.py",
    ],
    "docs/WIZARD.md": [
        "tools/wizard.py",
        "tools/pick_folder.py",
    ],
    # P59: the finance maintainer docs quote finance.py selftest pass-counts and behavior; a
    # finance.py change plausibly stales them (the P59 audit found seven stale counts this
    # binding would have flagged).
    "skills/finance-desk/MAINTAINER_README.md": ["tools/finance.py"],
    "skills/atoms/ar-review/MAINTAINER_README.md": ["tools/finance.py"],
    "skills/atoms/cashflow-view/MAINTAINER_README.md": ["tools/finance.py"],
    "skills/atoms/cost-estimate/MAINTAINER_README.md": ["tools/finance.py"],
    "skills/atoms/dunning-draft/MAINTAINER_README.md": ["tools/finance.py"],
    "skills/atoms/invoice-generate/MAINTAINER_README.md": ["tools/finance.py"],
    "skills/atoms/payment-reconcile/MAINTAINER_README.md": ["tools/finance.py"],
    "skills/atoms/proposal-price/MAINTAINER_README.md": ["tools/finance.py"],
    # P60: the Drive-hub spec is bound to the job contract and the handoff package it documents.
    "docs/DRIVE-HUB.md": [
        "shared/schemas/compute-job.json",
        "tools/handoff/queue.py",
        "tools/handoff/runner.py",
        "tools/handoff/watcher.py",
        "tools/handoff/drive_api.py",
        "tools/handoff/inbox.py",
        "shared/docintel/inbox_rules.json",
        "tools/project_docs.py",
    ],
    "tools/handoff/MAINTAINER_README.md": [
        "tools/handoff/queue.py",
        "tools/handoff/runner.py",
        "tools/handoff/watcher.py",
        "tools/handoff/drive_api.py",
        "tools/handoff/inbox.py",
        "shared/docintel/inbox_rules.json",
    ],
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reconcile(root: Path = ROOT, sources: dict | None = None, manifest_path: Path | None = None) -> dict:
    """(Re)write the manifest recording each bound source's current sha256 per doc."""
    sources = sources if sources is not None else DOC_SOURCES
    manifest_path = manifest_path or MANIFEST_PATH
    out = {}
    for doc, srcs in sources.items():
        rec = {}
        for s in srcs:
            p = root / s
            rec[s] = _sha(p) if p.exists() else None
        out[doc] = {"sources": rec}
    manifest = {
        "_comment": "P52 doc-freshness signal: sha256 of each CODE file a doc documents, at the time the "
                    "doc was last reconciled. If a bound source sha moves, drift invariant 51 (advisory) "
                    "flags the doc as possibly stale. Re-read the doc, fix any drift, then run "
                    "`python3 tools/doc_freshness.py reconcile` to re-bless it.",
        "generated_by": "tools/doc_freshness.py",
        "docs": out,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def check(root: Path = ROOT, sources: dict | None = None, manifest_path: Path | None = None) -> list:
    """Return [{doc, changed_sources, missing_sources}] for docs whose bound sources moved since the last
    reconcile. Empty == all current. Never raises."""
    sources = sources if sources is not None else DOC_SOURCES
    manifest_path = manifest_path or MANIFEST_PATH
    if not manifest_path.exists():
        return [{"doc": "*", "changed_sources": [], "missing_sources": [],
                 "note": "manifest missing; run 'python3 tools/doc_freshness.py reconcile'"}]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [{"doc": "*", "changed_sources": [], "missing_sources": [],
                 "note": f"manifest unreadable: {exc}"}]
    recorded = manifest.get("docs", {})
    stale = []
    for doc, srcs in sources.items():
        rec = recorded.get(doc, {}).get("sources", {})
        changed, missing = [], []
        for s in srcs:
            p = root / s
            if not p.exists():
                missing.append(s)
                continue
            if rec.get(s) != _sha(p):
                changed.append(s)
        if changed or missing:
            stale.append({"doc": doc, "changed_sources": changed, "missing_sources": missing})
    return stale


def selftest(root: Path = ROOT) -> int:
    import tempfile
    failures = []

    def ok(name, cond):
        if not cond:
            failures.append(name)

    d = Path(tempfile.mkdtemp())
    (d / "tools").mkdir()
    (d / "docs").mkdir()
    (d / "tools" / "a.py").write_text("def f(): pass\n", encoding="utf-8")
    (d / "docs" / "A.md").write_text("# doc A\n", encoding="utf-8")
    srcs = {"docs/A.md": ["tools/a.py"]}
    mp = d / "docs" / "m.json"

    # Fresh after reconcile.
    reconcile(root=d, sources=srcs, manifest_path=mp)
    ok("clean-after-reconcile", check(root=d, sources=srcs, manifest_path=mp) == [])

    # Source moves -> flagged.
    (d / "tools" / "a.py").write_text("def f(): return 1\n", encoding="utf-8")
    st = check(root=d, sources=srcs, manifest_path=mp)
    ok("flags-changed-source", len(st) == 1 and "tools/a.py" in st[0]["changed_sources"])

    # Re-reconcile clears it.
    reconcile(root=d, sources=srcs, manifest_path=mp)
    ok("clean-after-rebless", check(root=d, sources=srcs, manifest_path=mp) == [])

    # Missing manifest -> a note, not a crash.
    mp.unlink()
    st = check(root=d, sources=srcs, manifest_path=mp)
    ok("missing-manifest-note", len(st) == 1 and st[0].get("note"))

    # Missing source -> reported, no crash.
    reconcile(root=d, sources=srcs, manifest_path=mp)
    (d / "tools" / "a.py").unlink()
    st = check(root=d, sources=srcs, manifest_path=mp)
    ok("flags-missing-source", len(st) == 1 and "tools/a.py" in st[0]["missing_sources"])

    if failures:
        print("doc_freshness selftest FAILED:", ", ".join(failures))
        return 1
    print("doc_freshness selftest OK (reconcile/flag-on-change/rebless/missing-manifest/missing-source)")
    return 0


def main(argv) -> int:
    if "--selftest" in argv:
        return selftest()
    if "reconcile" in argv:
        m = reconcile()
        print(f"doc_freshness: reconciled {len(m['docs'])} doc(s) -> {MANIFEST_PATH.relative_to(ROOT)}")
        return 0
    # default / --check
    stale = check()
    if not stale:
        print("doc_freshness: all bound docs current")
        return 0
    print(json.dumps({"ok": False, "stale": stale}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
