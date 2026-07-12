#!/usr/bin/env python3
"""migrate_local.py -- consent-first schema catch-up for YOUR local data files (P44).

Pairs with the read-only tools/local_audit.py. When a committed data shape has gained a higher
schema_version than your own .local file, there are two ways to stay compatible:

  DEFAULT (no writes, always safe): the read-time compatibility shim `compat_view(local, template)`
  returns your data with any missing newer fields filled in as null (null-and-flag, no-fabrication).
  Old files keep working untouched; nothing is rewritten. This is what "old files keep working" means
  and it is the recommended path.

  OPT-IN (explicit, per-file, reversible): a write migration that additively fills the missing newer
  fields as null and stamps the new schema_version INTO your file. It runs only with explicit consent
  (consent=True), backs the file up first, writes atomically, records a rollback entry, and can be
  undone byte-for-byte. It NEVER transforms, renames, or overwrites an existing value: it only adds
  missing keys as null (the only schema evolution shipped so far is additive). A non-additive change
  would need a bespoke, separately reviewed migration; this tool refuses to guess.

Consent-first (P44 decision 3): findings are shown only when you ask, repairs happen only with your
explicit per-file (optionally per-change) permission, and the human-authored why/impact comes from
CHANGELOG.migrations.json (never invented). Backups and the rollback log are written as *.local.json
so they are gitignored (they never enter git; invariant 19). Local Claude Desktop / Claude Code only.

Sandbox: honors CREATOR_OS_ROOT. Stdlib only.

Usage:
  python3 tools/migrate_local.py plan <your-file.local.json>            # dry run; shows what WOULD change, writes nothing
  python3 tools/migrate_local.py apply <your-file.local.json> --yes      # backup + additive fill + stamp version (reversible)
  python3 tools/migrate_local.py apply <file> --yes --only fieldA,fieldB # per-change: fill only these missing fields
  python3 tools/migrate_local.py rollback <your-file.local.json>         # restore the most recent backup
  python3 tools/migrate_local.py --selftest                             # sandboxed synthetic tree
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_audit  # noqa: E402  (template pairing + version compare, read-only)


def _root():
    return Path(os.environ.get("CREATOR_OS_ROOT", str(REPO_ROOT)))


def _now_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── read-time compatibility shim (DEFAULT; no writes) ────────────────────────

def _fill_missing(local, template):
    """Return a copy of `local` with keys present in `template` but missing in `local` added as null,
    recursing into dicts present in both. NEVER overwrites an existing value (null-and-flag)."""
    if not isinstance(local, dict) or not isinstance(template, dict):
        return local
    out = dict(local)
    for k, tv in template.items():
        if k not in out:
            out[k] = None
        elif isinstance(tv, dict) and isinstance(out.get(k), dict):
            out[k] = _fill_missing(out[k], tv)
    return out


def compat_view(local, template):
    """The safe read path: your values, plus any missing newer fields as null. Pure; no writes."""
    return _fill_missing(local, template)


def _missing_keys(local, template):
    """Top-level keys in the template that are absent from the local file (what a migration adds)."""
    if not isinstance(local, dict) or not isinstance(template, dict):
        return []
    return [k for k in template if k not in local]


# ── plan (dry run; no writes) ─────────────────────────────────────────────────

def plan(local_path, root=None):
    root = Path(root) if root else _root()
    local_path = Path(local_path)
    local = local_audit._load_json(local_path)
    if not isinstance(local, dict):
        return {"error": f"{local_path} is not a readable JSON object"}
    tmpl_path = local_audit.template_for(local_path, root)
    if tmpl_path is None:
        return {"error": f"no committed template found next to {local_path.name}; cannot plan"}
    template = local_audit._load_json(tmpl_path) or {}
    installed = local.get("schema_version")
    expected = template.get("schema_version")
    status = local_audit.compare(installed, expected)
    manifest = local_audit.load_manifest(root)
    rel_tmpl = str(tmpl_path.relative_to(root)) if str(tmpl_path).startswith(str(root)) else str(tmpl_path)
    m = manifest.get((rel_tmpl, str(expected))) or {}
    return {
        "file": str(local_path),
        "template": rel_tmpl,
        "installed": installed,
        "expected": expected,
        "status": status,
        "would_add_fields": _missing_keys(local, template) if status == "behind" else [],
        "why_it_matters": m.get("why_it_matters"),
        "concrete_impact": m.get("concrete_impact"),
        "reversible": m.get("reversible"),
        "note": ("Nothing has been changed. This is a dry run. Applying is additive only (missing "
                 "fields become null and the version is stamped); your existing values are never "
                 "altered, and it can be rolled back."),
    }


# ── apply (opt-in, consented, reversible) ─────────────────────────────────────

def _rollback_log_path(root):
    return root / "ledger" / "rollback-log.local.json"


def _append_rollback(root, record):
    p = _rollback_log_path(root)
    log = local_audit._load_json(p) or {"_comment": "P44 local migration rollback log (gitignored).", "rollbacks": []}
    log.setdefault("rollbacks", []).append(record)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def _atomic_write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def apply_migration(local_path, root=None, consent=False, only=None):
    """Additively fill missing newer fields as null and stamp the new schema_version. Reversible.
    consent MUST be True or nothing is written. `only` (a set/list of field names) restricts the fill
    to those missing fields (per-change consent)."""
    root = Path(root) if root else _root()
    local_path = Path(local_path)
    p = plan(local_path, root=root)
    if "error" in p:
        return p
    if p["status"] != "behind":
        return {**p, "applied": False, "reason": f"nothing to migrate (status: {p['status']})"}
    if not consent:
        return {**p, "applied": False, "reason": "consent required: re-run with explicit consent (--yes). Nothing was written."}

    local = local_audit._load_json(local_path)
    template = local_audit._load_json(local_audit.template_for(local_path, root)) or {}
    add = p["would_add_fields"]
    if only is not None:
        only = set(only)
        add = [k for k in add if k in only]
    original_text = local_path.read_text(encoding="utf-8")

    # backup first (gitignored *.local.json name)
    stem = local_path.name[: -len(".local.json")] if local_path.name.endswith(".local.json") else local_path.stem
    backup = local_path.with_name(f"{stem}.bak-{_now_stamp()}.local.json")
    backup.write_text(original_text, encoding="utf-8")

    # additive fill (never overwrite an existing value) + version stamp
    migrated = dict(local)
    for k in add:
        migrated[k] = None
    stamped_version = template.get("schema_version") if (only is None or not p["would_add_fields"] or set(add) == set(p["would_add_fields"])) else migrated.get("schema_version")
    migrated["schema_version"] = stamped_version
    _atomic_write_json(local_path, migrated)

    rollback_id = f"{stem}-{_now_stamp()}"
    _append_rollback(root, {
        "id": rollback_id,
        "file": str(local_path),
        "backup": str(backup),
        "from_version": p["installed"],
        "to_version": stamped_version,
        "added_fields": add,
        "original_sha256": _sha256(original_text),
        "at": _now_stamp(),
    })
    return {
        "file": str(local_path),
        "applied": True,
        "added_fields": add,
        "from_version": p["installed"],
        "to_version": stamped_version,
        "backup": str(backup),
        "rollback_id": rollback_id,
        "note": ("Additive only: existing values untouched; new fields are null. Undo with: "
                 f"python3 tools/migrate_local.py rollback {local_path}"),
    }


def rollback(local_path, root=None):
    """Restore the most recent backup for a file (byte-for-byte), verified against its recorded sha256."""
    root = Path(root) if root else _root()
    local_path = Path(local_path)
    log = local_audit._load_json(_rollback_log_path(root)) or {}
    entries = [r for r in log.get("rollbacks", []) if r.get("file") == str(local_path)]
    if not entries:
        return {"restored": False, "reason": f"no rollback record for {local_path}"}
    rec = entries[-1]
    backup = Path(rec["backup"])
    if not backup.exists():
        return {"restored": False, "reason": f"backup missing: {backup}"}
    text = backup.read_text(encoding="utf-8")
    if rec.get("original_sha256") and _sha256(text) != rec["original_sha256"]:
        return {"restored": False, "reason": "backup sha256 does not match the recorded original; refusing to restore"}
    # byte-for-byte restore: write the backup's exact bytes atomically (no re-serialization)
    tmp = local_path.with_suffix(local_path.suffix + ".restore-tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, local_path)
    return {"restored": True, "file": str(local_path), "from_backup": str(backup),
            "to_version": rec.get("from_version"), "rollback_id": rec.get("id")}


# ── selftest (sandboxed synthetic tree; no real files touched) ───────────────

def selftest():
    import tempfile
    import shutil
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # compat_view: fills missing, never overwrites, recurses one level
    local = {"schema_version": "1.0", "a": 5, "nested": {"x": 1}}
    template = {"schema_version": "2.0", "a": None, "b": None, "nested": {"x": None, "y": None}}
    cv = compat_view(local, template)
    ok("compat fills missing top-level as null", cv["b"] is None)
    ok("compat preserves existing value", cv["a"] == 5)
    ok("compat recurses into shared dicts", cv["nested"]["y"] is None and cv["nested"]["x"] == 1)
    ok("compat does not mutate input", "b" not in local)

    tmp = Path(tempfile.mkdtemp(prefix="migrate_selftest_"))
    try:
        d = tmp / "pipeline" / "finance"
        d.mkdir(parents=True)
        (d / "rate-card.template.json").write_text(json.dumps(
            {"schema_version": "2.0", "rows": [], "tiers": None, "rate_history": None}))
        lp = d / "rate-card.local.json"
        lp.write_text(json.dumps({"schema_version": "1.0", "rows": [{"format": "reel", "rate": 500}]}))
        orig_bytes = lp.read_text(encoding="utf-8")
        (tmp / "CHANGELOG.migrations.json").write_text(json.dumps({"migrations": [
            {"template": "pipeline/finance/rate-card.template.json", "to": "2.0",
             "why_it_matters": "adds tiers", "concrete_impact": "your rates unchanged", "reversible": True}]}))

        pl = plan(lp, root=tmp)
        ok("plan reports behind", pl["status"] == "behind")
        ok("plan lists fields it would add", set(pl["would_add_fields"]) == {"tiers", "rate_history"})
        ok("plan carries manifest why (no fabrication)", pl["why_it_matters"] == "adds tiers")
        ok("plan writes nothing", json.loads(lp.read_text())["schema_version"] == "1.0")

        # apply without consent -> refuses, writes nothing
        r0 = apply_migration(lp, root=tmp, consent=False)
        ok("apply without consent refuses", r0["applied"] is False and "consent required" in r0["reason"])
        ok("refusal writes nothing", json.loads(lp.read_text())["schema_version"] == "1.0")

        # apply with consent -> additive fill + version stamp + backup + rollback record
        r1 = apply_migration(lp, root=tmp, consent=True)
        after = json.loads(lp.read_text())
        ok("apply stamps new version", after["schema_version"] == "2.0")
        ok("apply adds missing fields as null", after["tiers"] is None and after["rate_history"] is None)
        ok("apply preserves existing values", after["rows"][0]["rate"] == 500)
        ok("apply made a backup", Path(r1["backup"]).exists())
        ok("backup is a gitignored .local.json name", r1["backup"].endswith(".local.json"))
        ok("rollback log recorded", (tmp / "ledger" / "rollback-log.local.json").exists())

        # rollback -> byte-for-byte restore of the original
        rb = rollback(lp, root=tmp)
        restored = json.loads(lp.read_text())
        ok("rollback restores", rb["restored"] is True)
        ok("rollback restores old version", restored["schema_version"] == "1.0")
        ok("rollback removes added fields", "tiers" not in restored)
        ok("rollback preserves values", restored["rows"][0]["rate"] == 500)
        ok("rollback is byte-for-byte", lp.read_text(encoding="utf-8") == orig_bytes)

        # per-change consent: only fill one field
        lp2 = d / "rate-card.local.json"
        lp2.write_text(json.dumps({"schema_version": "1.0", "rows": []}))
        r2 = apply_migration(lp2, root=tmp, consent=True, only=["tiers"])
        after2 = json.loads(lp2.read_text())
        ok("per-change adds only approved field", "tiers" in after2 and "rate_history" not in after2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


def main(argv):
    ap = argparse.ArgumentParser(description="Consent-first schema catch-up for your local data files.")
    ap.add_argument("command", nargs="?", choices=["plan", "apply", "rollback"])
    ap.add_argument("file", nargs="?", help="path to your .local.json file")
    ap.add_argument("--yes", action="store_true", help="(apply) explicit consent to write the migration")
    ap.add_argument("--only", help="(apply) comma-separated field names to fill (per-change consent)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.command or not args.file:
        ap.print_help()
        return 2

    if args.command == "plan":
        print(json.dumps(plan(args.file), indent=2, ensure_ascii=False))
    elif args.command == "apply":
        only = [s.strip() for s in args.only.split(",")] if args.only else None
        print(json.dumps(apply_migration(args.file, consent=args.yes, only=only), indent=2, ensure_ascii=False))
    elif args.command == "rollback":
        print(json.dumps(rollback(args.file), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
