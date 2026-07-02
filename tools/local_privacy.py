#!/usr/bin/env python3
"""Local-context privacy report (P23 Phase 3).

Read-only. Answers one question in plain English: which of the creator's files live only on this
machine, and is git accidentally tracking any of them? The creator's real context (contract records,
the obligation register, the deal-playbook, channel and voice profiles, credentials, config
overrides) belongs in gitignored *.local.* files that `git pull` never touches and that are never
pushed. Only null templates and blank schemas are committed.

This tool lists the local-only files it finds, confirms none are tracked by git, and points at the
committed templates that are safe to share. It never writes anything. The hard guarantee is enforced
by drift-guard invariant 19 (tools/sync_check.py); this report is the friendly view of the same fact.

CLI:
  python3 tools/local_privacy.py            # human-readable report
  python3 tools/local_privacy.py --json     # machine-readable
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL_FILE_RE = re.compile(r"\.local(\.|$)")


def _tracked_files() -> set[str] | None:
    """Paths git is tracking, or None if git is unavailable / not a repo."""
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=str(ROOT), capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


def _find_local_files() -> list[Path]:
    """Every *.local.* file on disk (the creator's real, machine-only context)."""
    found: list[Path] = []
    for base in (ROOT / "pipeline", ROOT):
        if not base.exists():
            continue
        it = base.rglob("*") if base == ROOT / "pipeline" else base.glob("*")
        for p in it:
            if p.is_file() and LOCAL_FILE_RE.search(p.name):
                found.append(p)
    return sorted(set(found))


def report() -> dict:
    tracked = _tracked_files()
    local_files = _find_local_files()
    rel = [p.relative_to(ROOT).as_posix() for p in local_files]
    leaked = [] if tracked is None else [r for r in rel if r in tracked]
    templates = sorted(
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "pipeline" / "user-context").glob("*.template.json")
    ) if (ROOT / "pipeline" / "user-context").exists() else []
    return {
        "git_checked": tracked is not None,
        "local_only_files": rel,
        "local_only_count": len(rel),
        "leaked_tracked_files": leaked,
        "ok": tracked is not None and not leaked,
        "committed_templates_safe_to_share": templates,
    }


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Local-context privacy report (read-only).")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args(argv)
    r = report()
    if a.json:
        print(json.dumps(r, indent=2))
        return 0 if r["ok"] or not r["git_checked"] else 1

    print("Creator OS — local-context privacy report")
    print("=" * 44)
    if not r["git_checked"]:
        print("git is unavailable here, so the tracked-file check was skipped.")
    print(f"\nFiles that live ONLY on this machine ({r['local_only_count']}):")
    if r["local_only_files"]:
        for f in r["local_only_files"]:
            print(f"  - {f}")
    else:
        print("  (none yet — you have not created any real context files)")
    print("\nThese never enter git and are never pushed. `git pull` and repo updates leave them")
    print("untouched. Only the blank templates below are committed:")
    for t in r["committed_templates_safe_to_share"]:
        print(f"  - {t}")
    if r["leaked_tracked_files"]:
        print("\nWARNING: these personal files are tracked by git and should be removed from")
        print("version control (they must stay local):")
        for f in r["leaked_tracked_files"]:
            print(f"  - {f}")
        print("\nRun: git rm --cached <path>  (then commit) to stop tracking them.")
        return 1
    if r["git_checked"]:
        print("\nGood: no personal file is tracked by git. Your context stays on your computer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
