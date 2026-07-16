#!/usr/bin/env python3
"""Doc-declared source reconciliation (P55). Read-only toward the registry.

A maintainer/doc file whose claims rest on external authoritative sources declares them in a
fenced block:

    ```sources
    [{"id": "the-id", "name": "...", "url": "https://...", "category": "...", "tier": "T1"}]
    ```

or ties a single claim to a declared id with an inline `<!-- source: the-id -->` marker.
This tool scans the same corpus the drift guard validates (sync_check._reference_scan_files)
and reconciles the declarations against canonical-sources/source-registry.json:

  check              report declared-but-unregistered ids, URL mismatches, incomplete
                     declarations, unregistered marker ids, and unparseable blocks
                     (exit 1 if any)
  reconcile [--out]  the same scan, plus write a ready seed file for the unregistered
                     complete entries; the human then runs
                     `python3 tools/source_currency.py seed-sources <out>`. This tool NEVER
                     writes the registry itself: the sanctioned writer set (CLAUDE.md) is
                     unchanged, and the default out path is a `.local.` file so the seed
                     artifact cannot be committed by accident.
  --selftest         offline fixture test (temp files; no network; no repo mutation)

Invariant 52 (sync_check.check_doc_source_registry) is the enforcing twin: the build fails
when a declared id is missing from the registry or its declared URL disagrees with the
registry's. This tool generates the seed that makes it pass. It never invents data: a block
entry missing the seed-required fields (id, name, url, category, tier) is reported as
incomplete for the doc author to finish, not guessed.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES_BLOCK_RE = re.compile(r"^```sources[ \t]*\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)
SOURCE_MARKER_RE = re.compile(r"<!--\s*source:\s*([A-Za-z0-9][A-Za-z0-9_-]*)\s*-->")
SEED_REQUIRED = ("id", "name", "url", "category", "tier")
DEFAULT_OUT = "canonical-sources/source-sync-seed.local.json"
ALLOWLIST = "tools/doc-source-allowlist.json"


def load_registry_urls(root=ROOT):
    """id -> url for every registered source (plain json read; this tool has no write path)."""
    path = root / "canonical-sources" / "source-registry.json"
    try:
        reg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {s.get("id"): s.get("url") for s in reg.get("sources", []) if s.get("id")}


def load_exempt_ids(root=ROOT):
    """Illustrative/example ids exempted from enforcement (mirror of doc-verify-allowlist)."""
    path = root / ALLOWLIST
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("exempt", []))
    except (OSError, ValueError):
        return set()


def scan_file(path, root=ROOT):
    """Parse one doc: returns (entries, marker_ids, errors). Each entry is the declared dict
    plus a `_doc` key naming the declaring file; errors are (doc, message) tuples."""
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [], [], [(rel, f"unreadable: {exc}")]
    entries, errors = [], []
    for m in SOURCES_BLOCK_RE.finditer(text):
        try:
            data = json.loads(m.group(1))
        except ValueError as exc:
            errors.append((rel, f"unparseable sources block: {exc}"))
            continue
        if not isinstance(data, list):
            errors.append((rel, "sources block must be a JSON array of source objects"))
            continue
        for item in data:
            if not isinstance(item, dict) or not item.get("id"):
                errors.append((rel, "sources block entry missing an id"))
                continue
            entries.append({**item, "_doc": rel})
    marker_ids = [(rel, mid) for mid in SOURCE_MARKER_RE.findall(text)]
    return entries, marker_ids, errors


def corpus_files(root=ROOT):
    """The exact file set the drift guard validates (invariants 5/49/52)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sync_check
    return sync_check._reference_scan_files()


def reconcile_data(root=ROOT, files=None):
    """Scan + diff. Pure; no writes. Returns the full report dict."""
    files = corpus_files(root) if files is None else files
    registry = load_registry_urls(root)
    exempt = load_exempt_ids(root)
    entries, markers, errors = [], [], []
    for f in files:
        e, m, err = scan_file(f, root)
        entries.extend(e)
        markers.extend(m)
        errors.extend(err)
    declared_ids = {e["id"] for e in entries}
    unregistered, incomplete, mismatches = [], [], []
    seen = set()
    for e in entries:
        sid = e["id"]
        if sid in exempt:
            continue
        if sid in registry:
            if e.get("url") and e["url"] != registry[sid]:
                mismatches.append({"id": sid, "doc": e["_doc"], "declared_url": e["url"],
                                   "registry_url": registry[sid]})
            continue
        if sid in seen:
            continue
        seen.add(sid)
        if all(e.get(k) for k in SEED_REQUIRED):
            unregistered.append(e)
        else:
            missing = [k for k in SEED_REQUIRED if not e.get(k)]
            incomplete.append({"id": sid, "doc": e["_doc"], "missing_fields": missing})
    unregistered_markers = [{"id": mid, "doc": doc} for doc, mid in markers
                            if mid not in registry and mid not in declared_ids
                            and mid not in exempt]
    return {
        "files_scanned": len(files),
        "declared_entries": len(entries),
        "marker_refs": len(markers),
        "registered_ok": len(entries) - len(unregistered) - len(incomplete) - len(mismatches),
        "unregistered": unregistered,
        "incomplete": incomplete,
        "url_mismatches": mismatches,
        "unregistered_marker_ids": unregistered_markers,
        "parse_errors": [{"doc": d, "error": msg} for d, msg in errors],
    }


def _failing(report):
    return any(report[k] for k in ("unregistered", "incomplete", "url_mismatches",
                                   "unregistered_marker_ids", "parse_errors"))


def write_seed(unregistered, out_path):
    """Emit the ready-to-seed file (declared fields only, `_doc` stripped; nothing invented)."""
    seed = [{k: v for k, v in e.items() if k != "_doc"} for e in unregistered]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8")
    return len(seed)


def cmd_check(root=ROOT):
    report = reconcile_data(root)
    print(json.dumps(report, indent=2))
    return 1 if _failing(report) else 0


def cmd_reconcile(root=ROOT, out=None):
    report = reconcile_data(root)
    out_path = root / (out or DEFAULT_OUT)
    wrote = write_seed(report["unregistered"], out_path) if report["unregistered"] else 0
    summary = {**report, "seed_file": str(out_path.relative_to(root)) if wrote else None,
               "seed_entries_written": wrote}
    print(json.dumps(summary, indent=2))
    if wrote:
        print(f"\nNext (human step): python3 tools/source_currency.py seed-sources {summary['seed_file']}",
              file=sys.stderr)
    blocking = any(report[k] for k in ("incomplete", "url_mismatches", "parse_errors"))
    return 1 if blocking else 0


def selftest():
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "canonical-sources").mkdir()
        (root / "tools").mkdir()
        (root / "canonical-sources" / "source-registry.json").write_text(json.dumps({
            "sources": [
                {"id": "reg-match", "url": "https://example.com/match"},
                {"id": "reg-drift", "url": "https://example.com/real"},
            ]}), encoding="utf-8")
        (root / ALLOWLIST).write_text(json.dumps({"exempt": ["an-example-id"]}), encoding="utf-8")
        doc1 = root / "doc1.md"
        doc1.write_text(
            "# doc1\n\n```sources\n" + json.dumps([
                {"id": "reg-match", "url": "https://example.com/match"},
                {"id": "new-complete", "name": "New", "url": "https://example.com/new",
                 "category": "os-platform", "tier": "T1"},
                {"id": "new-incomplete", "url": "https://example.com/partial"},
                {"id": "reg-drift", "url": "https://example.com/moved"},
                {"id": "an-example-id", "url": "https://example.com/illustrative"},
            ]) + "\n```\n\nClaim. <!-- source: reg-match -->\nOther. <!-- source: ghost-id -->\n",
            encoding="utf-8")
        doc2 = root / "doc2.md"
        doc2.write_text("# doc2\n\n```sources\nnot json at all\n```\n", encoding="utf-8")
        doc3 = root / "doc3.md"
        doc3.write_text("# doc3\nno declarations here\n", encoding="utf-8")

        report = reconcile_data(root, files=[doc1, doc2, doc3])
        ok("registered id with matching url passes",
           not any(u["id"] == "reg-match" for u in report["unregistered"]))
        ok("unregistered complete entry surfaces",
           [u["id"] for u in report["unregistered"]] == ["new-complete"])
        ok("incomplete entry reported with missing fields",
           report["incomplete"] and report["incomplete"][0]["id"] == "new-incomplete"
           and set(report["incomplete"][0]["missing_fields"]) == {"name", "category", "tier"})
        ok("url mismatch detected",
           report["url_mismatches"] and report["url_mismatches"][0]["id"] == "reg-drift")
        ok("exempt id skipped entirely",
           not any("an-example-id" in json.dumps(report[k]) for k in
                   ("unregistered", "incomplete", "url_mismatches")))
        ok("marker on registered id passes; ghost marker flagged",
           [m["id"] for m in report["unregistered_marker_ids"]] == ["ghost-id"])
        ok("unparseable block is a parse error, not a skip",
           report["parse_errors"] and "doc2.md" in report["parse_errors"][0]["doc"])
        ok("report counts declared entries", report["declared_entries"] == 5)
        ok("failing report detected", _failing(report))

        out = root / "seed.local.json"
        wrote = write_seed(report["unregistered"], out)
        seeded = json.loads(out.read_text(encoding="utf-8"))
        ok("seed carries only the complete unregistered entry",
           wrote == 1 and [s["id"] for s in seeded] == ["new-complete"])
        ok("seed entries carry no _doc key", "_doc" not in seeded[0])
        ok("seed entry keeps all declared fields",
           all(k in seeded[0] for k in SEED_REQUIRED))

        doc_clean = root / "clean.md"
        doc_clean.write_text("```sources\n" + json.dumps(
            [{"id": "reg-match", "url": "https://example.com/match"}]) + "\n```\n",
            encoding="utf-8")
        clean = reconcile_data(root, files=[doc_clean])
        ok("clean corpus is non-failing", not _failing(clean))

    failed = [n for n, c in checks if not c]
    for n, c in checks:
        print(("ok   " if c else "FAIL ") + n)
    print(f"selftest: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", nargs="?", choices=["check", "reconcile"], default="check")
    ap.add_argument("--out", help=f"seed output path for reconcile (default {DEFAULT_OUT})")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.command == "reconcile":
        return cmd_reconcile(out=args.out)
    return cmd_check()


if __name__ == "__main__":
    sys.exit(main())
