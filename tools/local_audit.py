#!/usr/bin/env python3
"""local_audit.py -- read-only schema audit of YOUR local data files (P44).

After you download a newer Creator OS baseline, a committed data shape may have a higher
`schema_version` than the copy in one of your own `.local.json` files. This tool is the READ-ONLY
detector: for each pipeline data template that carries a schema_version, it finds your matching
`.local.json` file and compares versions. It writes NOTHING and changes NOTHING; it only reports.

Consent-first (P44 decision 3): by default it prints ONE quiet line (or nothing when everything is
current). Full per-file findings appear only when you ask for them (`--details` / `report`). The
plain-language "why this matters to your data" for each stale file comes from the human-authored
CHANGELOG.migrations.json (no-fabrication: the tool never invents impact text). Repairing a stale
file is a separate, explicitly consented step (tools/migrate_local.py, P44-4); this tool never does it.

Sandbox: honors CREATOR_OS_ROOT so tests and dry runs point at a throwaway tree. Stdlib only.

Usage:
  python3 tools/local_audit.py                 # one quiet line (or 'all current'); never writes
  python3 tools/local_audit.py --details        # full per-file JSON findings
  python3 tools/local_audit.py report           # alias for --details
  python3 tools/local_audit.py --selftest        # sandboxed synthetic tree, no real files touched
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_NAME = "CHANGELOG.migrations.json"


def _root():
    return Path(os.environ.get("CREATOR_OS_ROOT", str(REPO_ROOT)))


# ── pure version compare (schema_version strings like "1.0", "0.1.0") ─────────

def _parse(v):
    if v is None:
        return ()
    m = re.search(r"(\d+(?:\.\d+)*)", str(v))
    return tuple(int(p) for p in m.group(1).split(".")) if m else ()


def _cmp(a, b):
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return (a > b) - (a < b)


def compare(installed, expected):
    """installed = the schema_version in the user's .local file; expected = the committed template's.
    behind (file is stale), current, ahead (file newer than template), or unknown."""
    iv, ev = _parse(installed), _parse(expected)
    if not iv or not ev:
        return "unknown"
    c = _cmp(ev, iv)  # expected vs installed
    if c > 0:
        return "behind"
    if c < 0:
        return "ahead"
    return "current"


# ── discovery (read-only) ─────────────────────────────────────────────────────

def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_manifest(root):
    data = _load_json(root / MANIFEST_NAME) or {}
    by_key = {}
    for m in data.get("migrations", []):
        if isinstance(m, dict) and m.get("template"):
            by_key[(m["template"], str(m.get("to")))] = m
    return by_key


def template_for(local_path, root):
    """The committed template a .local.json file corresponds to: same dir, .local.json -> .template.json."""
    name = local_path.name
    if not name.endswith(".local.json"):
        return None
    tmpl = local_path.with_name(name[: -len(".local.json")] + ".template.json")
    return tmpl if tmpl.exists() else None


def audit(root=None):
    """Compare every pipeline/**/*.local.json (that carries schema_version) against its template.
    Read-only. Returns a structured report; never writes."""
    root = Path(root) if root else _root()
    manifest = load_manifest(root)
    pipeline = root / "pipeline"
    findings = []
    if pipeline.exists():
        for local in sorted(pipeline.rglob("*.local.json")):
            doc = _load_json(local)
            rel = str(local.relative_to(root))
            if not isinstance(doc, dict) or "schema_version" not in doc:
                findings.append({"file": rel, "status": "unversioned",
                                 "note": "no schema_version; not schema-tracked, nothing to compare"})
                continue
            tmpl = template_for(local, root)
            if tmpl is None:
                findings.append({"file": rel, "status": "no_template", "installed": doc.get("schema_version"),
                                 "note": "no matching committed template; cannot determine the current shape"})
                continue
            tdoc = _load_json(tmpl) or {}
            installed = doc.get("schema_version")
            expected = tdoc.get("schema_version")
            status = compare(installed, expected)
            rel_tmpl = str(tmpl.relative_to(root))
            entry = {"file": rel, "template": rel_tmpl, "installed": installed,
                     "expected": expected, "status": status}
            if status == "behind":
                m = manifest.get((rel_tmpl, str(expected)))
                if m:
                    entry["why_it_matters"] = m.get("why_it_matters")
                    entry["concrete_impact"] = m.get("concrete_impact")
                    entry["reversible"] = m.get("reversible")
                else:
                    entry["why_it_matters"] = None
                    entry["concrete_impact"] = ("No migration note is recorded for this version; "
                                                "your values are unchanged and missing newer fields read as null.")
            findings.append(entry)

    behind = [f for f in findings if f["status"] == "behind"]
    return {
        "computed_by": "tools/local_audit.py.audit",
        "root": str(root),
        "scanned": len(findings),
        "summary": {
            "behind": len(behind),
            "current": sum(1 for f in findings if f["status"] == "current"),
            "ahead": sum(1 for f in findings if f["status"] == "ahead"),
            "unversioned": sum(1 for f in findings if f["status"] == "unversioned"),
            "no_template": sum(1 for f in findings if f["status"] == "no_template"),
        },
        "findings": findings,
        "boundary": ("Read-only. This tool writes nothing and changes nothing. Repairing a stale file "
                     "is a separate step you explicitly consent to (tools/migrate_local.py); by default "
                     "old files keep working, with missing newer fields read as null and flagged."),
    }


def quiet_line(report):
    """One passive line, or None when nothing is stale (R4: never a nag)."""
    n = report["summary"]["behind"]
    if n == 0:
        return None
    files = "file" if n == 1 else "files"
    return (f"{n} of your saved data {files} use an older format. Nothing is broken; run "
            "`python3 tools/local_audit.py --details` to see which and why (nothing is changed).")


# ── selftest (synthetic sandbox; no real files touched) ──────────────────────

def selftest():
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    ok("compare behind", compare("1.0", "2.0") == "behind")
    ok("compare current", compare("1.0", "1.0") == "current")
    ok("compare ahead", compare("2.0", "1.0") == "ahead")
    ok("compare unknown", compare(None, "1.0") == "unknown")

    tmp = Path(tempfile.mkdtemp(prefix="local_audit_selftest_"))
    try:
        (tmp / "pipeline" / "finance").mkdir(parents=True)
        (tmp / "pipeline" / "user-context").mkdir(parents=True)
        # a stale rate card: template at 2.0, user file at 1.0
        (tmp / "pipeline" / "finance" / "rate-card.template.json").write_text(
            json.dumps({"schema_version": "2.0", "rows": []}))
        (tmp / "pipeline" / "finance" / "rate-card.local.json").write_text(
            json.dumps({"schema_version": "1.0", "rows": [{"format": "reel", "rate": 500}]}))
        # a current task register
        (tmp / "pipeline" / "user-context" / "task-register.template.json").write_text(
            json.dumps({"schema_version": "0.1.0"}))
        (tmp / "pipeline" / "user-context" / "task-register.local.json").write_text(
            json.dumps({"schema_version": "0.1.0", "tasks": []}))
        # an unversioned local file (no schema_version)
        (tmp / "pipeline" / "user-context" / "voice-profile.local.json").write_text(
            json.dumps({"phrases": ["hey friends"]}))
        # a manifest that explains the rate-card bump
        (tmp / MANIFEST_NAME).write_text(json.dumps({"migrations": [
            {"template": "pipeline/finance/rate-card.template.json", "to": "2.0",
             "why_it_matters": "new tier rows", "concrete_impact": "your rates are unchanged",
             "reversible": True}]}))

        rep = audit(tmp)
        ok("scans all local files", rep["scanned"] == 3)
        ok("one behind detected", rep["summary"]["behind"] == 1)
        ok("one current detected", rep["summary"]["current"] == 1)
        ok("one unversioned detected", rep["summary"]["unversioned"] == 1)
        behind = [f for f in rep["findings"] if f["status"] == "behind"][0]
        ok("behind names the file", behind["file"] == "pipeline/finance/rate-card.local.json")
        ok("behind carries manifest why (no fabrication)", behind["why_it_matters"] == "new tier rows")
        ok("behind carries concrete impact", "unchanged" in behind["concrete_impact"])
        ok("quiet line present when behind", quiet_line(rep) is not None and "older format" in quiet_line(rep))
        ok("quiet line has no em dash", "—" not in quiet_line(rep))

        # nothing was written by the audit
        rate_local = json.loads((tmp / "pipeline" / "finance" / "rate-card.local.json").read_text())
        ok("audit wrote nothing (file unchanged)", rate_local["schema_version"] == "1.0" and rate_local["rows"][0]["rate"] == 500)

        # all-current tree -> no quiet line (never a nag)
        (tmp / "pipeline" / "finance" / "rate-card.local.json").write_text(
            json.dumps({"schema_version": "2.0", "rows": []}))
        rep2 = audit(tmp)
        ok("all current -> no behind", rep2["summary"]["behind"] == 0)
        ok("all current -> quiet line None (never a nag)", quiet_line(rep2) is None)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


def main(argv):
    ap = argparse.ArgumentParser(description="Read-only schema audit of your local data files.")
    ap.add_argument("command", nargs="?", choices=["report"], help="report = full JSON findings")
    ap.add_argument("--details", action="store_true", help="print full per-file JSON findings")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    report = audit()
    if args.details or args.command == "report":
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    line = quiet_line(report)
    print(line if line else "All your saved data files are on the current format.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
