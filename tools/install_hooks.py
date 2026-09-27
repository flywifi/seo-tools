#!/usr/bin/env python3
"""Install the Creator OS privacy git hooks (P31). Stdlib, idempotent, per-clone.

Git hooks do not travel with the repository, so every clone runs this once (documented in
CLAUDE.md). Two hooks are installed:

- pre-commit: runs `tools/secret_scan.py --staged` — blocks staged secrets (API keys, key
  blocks, credential values, session links, personal emails) AND any staged file whose name
  matches the forbidden classes (.local., .csv/.xlsx/.xls, .ofx/.qfx, .pem/.key, .env*).
  It also refuses a staged audit-record file name (tools/secret_scan.py::audit_record_name);
  a staged deletion passes, since removing the file is the fix.
- commit-msg: scans the commit message itself — blocks claude.ai session links, non-allowlisted
  email addresses, and other secret patterns from ever entering commit metadata (the
  over-sharing vector the hygiene policy exists to stop).
  It also runs tools/commit_claims.py: a subject the invariant-60 claim detector flags needs a
  resolving Claim-Proof: trailer (the check fails open locally when it cannot import).

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
# Inside this heredoc __file__ is "<stdin>", so the tools/ directory comes from git itself.
top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                     text=True).stdout.strip()
sys.path.insert(0, top + "/tools")
import secret_scan
allowlist = secret_scan._load_allowlist()
problems = []

msg = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
problems += secret_scan.scan_text(msg, "commit-message", allowlist)

# P74: the author-email rule. It is imported from secret_scan rather than restated (ADR 0015),
# so this hook and the CI backstop apply one rule.
author = subprocess.run(["git", "var", "GIT_AUTHOR_IDENT"], capture_output=True,
                        text=True).stdout.strip()
email = author.partition("<")[2].partition(">")[0].strip() if "<" in author else ""
if not email:
    email = subprocess.run(["git", "config", "user.email"], capture_output=True,
                           text=True).stdout.strip()
if email and not secret_scan.EMAIL_ALLOW_RE.search(email) \\
        and not secret_scan._allowed(allowlist, "commit-message", "author_email"):
    problems.append({"pattern_id": "author_email", "match": email})

# Commit-subject claims (tools/commit_claims.py): a subject the invariant-60 detector flags needs a
# resolving Claim-Proof: trailer. This check fails open, with a DID-NOT-RUN line, when it cannot be
# imported; the CI commit hygiene step over the pushed commits fails closed.
try:
    import commit_claims
    problems += commit_claims.message_problems(msg)
except Exception as exc:  # noqa: BLE001
    print(f"commit-msg hook: claim-subject check DID NOT RUN ({type(exc).__name__}: {exc}); "
          "the CI commit hygiene step still checks this subject")

if problems:
    print("commit-msg hook: commit rejected (commit and PR hygiene, CLAUDE.md):")
    for f in problems:
        print(f"  - {f['pattern_id']}: {f['match']}")
    if any(f["pattern_id"].startswith("claim_") for f in problems):
        print("  Name the mechanism the commit changed, or add a Claim-Proof: trailer naming the")
        print("  invariant or selftest pin that proves the claim (tools/commit_claims.py).")
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
