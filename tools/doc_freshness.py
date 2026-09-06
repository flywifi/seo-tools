#!/usr/bin/env python3
"""doc_freshness.py -- content-hash staleness signal for hand-authored maintainer/docs (P52).

Mirrors tools/projection_manifest.py, but binds prose DOCS to the CODE they describe (not shared engines
to their projections). Each high-value doc is mapped to the source files it documents; `reconcile` stamps
the sha256 of each source into a manifest, and `check` re-flags a doc as "may be stale" when a bound
source changes. Drift invariant 51 surfaces the signal inside the guard, and `--check` exits 1 on a
stale doc (P79), so the CI step is a real gate.

This is a STALENESS SIGNAL, not a prose diff: a moved source means the doc *might* now lag, so a human
should re-read it and re-bless it with `reconcile`. Emerging practice (content-hash binding), adopted
here as sound engineering and modeled on the repo's own invariant-47 precedent -- not an external
standard. Stdlib only; never raises on check (it exit-codes instead).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "docs" / "doc-freshness-manifest.json"

# doc (repo-relative) -> the code files it documents. Keep bindings TIGHT (a change to a bound file
# should plausibly require re-reading the doc); coarse bindings cause churn. Advisory only.
DOC_SOURCES = {
    "docs/AUDIT-PROTOCOL.md": [
        "tools/handoff/queue.py",
        "shared/cross-modality/transitions.json",
    ],
    "docs/CURRENCY.md": [   # P80 A4: the dependency-checker contract drifted from this doc for a full year unnoticed
        "tools/dependency_currency.py",
        "tools/source_currency.py",
        "tools/sync_check.py",   # P81 A-9: the doc describes invariant 25's pin-chain rule
    ],
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
    # P61: the injection-guard engine doc's "Offline pattern tier" section describes the tool that
    # implements its categories/scores verbatim; a tool change plausibly stales that section.
    "shared/injection-guard-engine.md": ["tools/injection_scan.py"],
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

# P81 G-5: dated records (a remediation record, an audit report) are frozen above their first
# `## Addendum` heading. P80 edited four rows of the P79 record in place and left five others stale,
# so the record contradicted itself; an addendum is the only sanctioned way to add later facts.
FROZEN_GLOBS = ("docs/remediation-*.md", "docs/*-audit-*.md", "docs/production-readiness-*.md")
_ADDENDUM_RE = re.compile(r"^## Addendum\b.*$", re.M)


def frozen_docs(root: Path = ROOT) -> list:
    out = []
    for g in FROZEN_GLOBS:
        out += sorted(str(p.relative_to(root)) for p in root.glob(g))
    return out


def frozen_body_sha(text: str) -> str:
    """sha256 of the body ABOVE the first '## Addendum' heading, trailing whitespace stripped, so appending
    an addendum never moves it and any other edit does."""
    body = _ADDENDUM_RE.split(text, maxsplit=1)[0].rstrip()
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


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
                    "doc was last reconciled. If a bound source sha moves, drift invariant 51 (blocking "
                    "since P79) flags the doc as possibly stale. Re-read the doc, fix any drift, then run "
                    "`python3 tools/doc_freshness.py reconcile` to re-bless it. `frozen` (P81) pins each "
                    "dated record's body above its first '## Addendum' heading: records are append-only.",
        "generated_by": "tools/doc_freshness.py",
        "docs": out,
        "frozen": {d: frozen_body_sha((root / d).read_text(encoding="utf-8")) for d in frozen_docs(root)},
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
    blessed = manifest.get("frozen", {})
    for d in frozen_docs(root):
        fp = root / d
        if not fp.exists():
            continue
        if d not in blessed:
            stale.append({"doc": d, "changed_sources": [], "missing_sources": [],
                          "note": "dated record not yet blessed; run 'python3 tools/doc_freshness.py reconcile'"})
        elif blessed[d] != frozen_body_sha(fp.read_text(encoding="utf-8")):
            stale.append({"doc": d, "changed_sources": [], "missing_sources": [],
                          "note": "dated record edited above its Addendum section; records are append-only "
                                  "(add an '## Addendum <date>' section, or run reconcile to re-bless deliberately)"})
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

    # P81 G-5: frozen dated records. (Restore the source file the previous case deleted.)
    (d / "tools" / "a.py").write_text("def f(): pass\n", encoding="utf-8")
    (d / "docs" / "remediation-2026-01-01.md").write_text("# record\n\nbody\n", encoding="utf-8")
    reconcile(root=d, sources=srcs, manifest_path=mp)
    ok("frozen: clean after reconcile", check(root=d, sources=srcs, manifest_path=mp) == [])
    with open(d / "docs" / "remediation-2026-01-01.md", "a", encoding="utf-8") as fh:
        fh.write("\n## Addendum 2026-02-01\n\nlater facts\n")
    ok("frozen: an addendum is allowed", check(root=d, sources=srcs, manifest_path=mp) == [])
    txt = (d / "docs" / "remediation-2026-01-01.md").read_text(encoding="utf-8")
    (d / "docs" / "remediation-2026-01-01.md").write_text(txt.replace("body", "edited body"), encoding="utf-8")
    st = check(root=d, sources=srcs, manifest_path=mp)
    ok("frozen: a body edit is flagged", len(st) == 1 and "append-only" in st[0].get("note", ""))
    (d / "docs" / "prod-audit-2026-03-03.md").write_text("# new record\n", encoding="utf-8")
    st = check(root=d, sources=srcs, manifest_path=mp)
    ok("frozen: a new dated record must be blessed", any("not yet blessed" in x.get("note", "") for x in st))

    if failures:
        print("doc_freshness selftest FAILED:", ", ".join(failures))
        return 1
    print("doc_freshness selftest OK (reconcile/flag-on-change/rebless/missing-manifest/missing-source/frozen)")
    return 0


def main(argv) -> int:
    if "--selftest" in argv:
        return selftest()
    if "reconcile" in argv:
        m = reconcile()
        print(f"doc_freshness: reconciled {len(m['docs'])} doc(s) -> {MANIFEST_PATH.relative_to(ROOT)}")
        return 0
    # P79 A3: --check is the only remaining verb, and a stale result is a FAILURE (exit 1). The
    # previous form fell through on ANY argv and returned 0 even after printing ok:false, so the CI
    # step could never fail and a mistyped flag silently reported success (P78 audit F6).
    extra = [a for a in argv[1:] if a != "--check"] if argv and argv[0] == "--check" else [a for a in argv if a != "--check"]
    if extra:
        print(f"doc_freshness: unrecognized argument(s) {extra}; use --check, reconcile, or --selftest")
        return 2
    stale = check()
    if not stale:
        print("doc_freshness: all bound docs current")
        return 0
    print(json.dumps({"ok": False, "stale": stale}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
