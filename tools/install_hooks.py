#!/usr/bin/env python3
"""Install the Creator OS privacy git hooks (P31). Stdlib, idempotent, per-clone.

Git hooks do not travel with the repository, so every clone runs this once (documented in
CLAUDE.md). Two hooks are installed:

- pre-commit: runs `tools/secret_scan.py --staged` — blocks staged secrets (API keys, key
  blocks, credential values, session links, personal emails) AND any staged file whose name
  matches the forbidden classes (.local., .csv/.xlsx/.xls, .ofx/.qfx, .pem/.key, .env*).
- commit-msg: scans the commit message itself — blocks claude.ai session links, non-allowlisted
  email addresses, and other secret patterns from ever entering commit metadata (the
  over-sharing vector the hygiene policy exists to stop).

The CI guard job is the backstop for clones that skipped this (tracked-content scan plus the
commit-message scan bounded by the policy SHA in tools/secret-scan-allowlist.json).

CLI:
  python3 tools/install_hooks.py             # install/refresh both hooks
  python3 tools/install_hooks.py --selftest  # dry-run: report what would be written
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PRE_COMMIT = """#!/bin/sh
# Creator OS privacy hook (installed by tools/install_hooks.py). Blocks staged secrets,
# forbidden file types, and .local. files before they can enter a commit.
python3 "$(git rev-parse --show-toplevel)/tools/secret_scan.py" --staged
"""

COMMIT_MSG = """#!/bin/sh
# Creator OS commit-hygiene hook (installed by tools/install_hooks.py). Rejects commit
# messages carrying session links, personal emails, or secret patterns.
python3 - "$1" <<'PY'
import sys
import subprocess
from pathlib import Path
# P74: the previous version also inserted str(Path(__file__).resolve()) here. Inside this heredoc
# __file__ is "<stdin>", so that resolved to <cwd>/<stdin> -- a path that does not exist. Harmless
# but wrong, and import-order sensitive if anything ever shadowed a stdlib name from cwd.
top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                     text=True).stdout.strip()
sys.path.insert(0, top + "/tools")
import secret_scan
allowlist = secret_scan._load_allowlist()
problems = []

msg = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
problems += secret_scan.scan_text(msg, "commit-message", allowlist)

# P74 D1-5: the author-email rule. ADR 0015 says it is enforced by this hook AND the CI backstop;
# this half simply did not exist, so a personal address could enter git metadata locally and only
# be caught after the fact (and the CI half scans an empty range on a direct main push). The rule
# is IMPORTED from secret_scan rather than restated, so the hook and the backstop cannot drift.
author = subprocess.run(["git", "var", "GIT_AUTHOR_IDENT"], capture_output=True,
                        text=True).stdout.strip()
email = author.partition("<")[2].partition(">")[0].strip() if "<" in author else ""
if not email:
    email = subprocess.run(["git", "config", "user.email"], capture_output=True,
                           text=True).stdout.strip()
if email and not secret_scan.EMAIL_ALLOW_RE.search(email) \\
        and not secret_scan._allowed(allowlist, "commit-message", "author_email"):
    problems.append({"pattern_id": "author_email", "match": email})

if problems:
    print("commit-msg hook: commit rejected (commit and PR hygiene, CLAUDE.md):")
    for f in problems:
        print(f"  - {f['pattern_id']}: {f['match']}")
    if any(f["pattern_id"] == "author_email" for f in problems):
        print("  Set the repo-local noreply address:")
        print("    git config user.email '<your-github-noreply-address>'")
    sys.exit(1)
PY
"""


def install(dry_run=False):
    hooks_dir = ROOT / ".git" / "hooks"
    if not hooks_dir.exists():
        print("no .git/hooks directory here (not a git checkout?); nothing installed")
        return 1
    results = []
    for name, body in (("pre-commit", PRE_COMMIT), ("commit-msg", COMMIT_MSG)):
        target = hooks_dir / name
        exists = target.exists()
        current = target.read_text(encoding="utf-8") if exists else None
        if dry_run:
            state = "up to date" if current == body else ("would update" if exists else "would install")
            results.append((name, state))
            continue
        target.write_text(body, encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        results.append((name, "updated" if exists else "installed"))
    for name, state in results:
        print(f"  {name}: {state}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Install the Creator OS privacy git hooks")
    ap.add_argument("--selftest", action="store_true", help="dry run; report without writing")
    a = ap.parse_args(argv)
    return install(dry_run=a.selftest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
