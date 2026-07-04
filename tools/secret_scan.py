#!/usr/bin/env python3
"""Creator OS content secret scanner (P31).

The filename invariants (19, 20) keep real-data FILES out of git; this scanner keeps secret
CONTENT out: API keys, private-key blocks, credential values pasted into committed JSON,
personal email addresses, claude.ai session links, and dollar-amount figures inside committed
pipeline/ files (which must be blank templates). Pure stdlib, no network, read-only.

Modes:
  python3 tools/secret_scan.py --tracked                  # scan all git-tracked file content (CI, invariant 21)
  python3 tools/secret_scan.py --staged                   # scan staged additions (pre-commit hook)
  python3 tools/secret_scan.py --commit-messages RANGE    # scan commit messages + author emails (CI backstop)
  python3 tools/secret_scan.py --selftest

Exit 1 on any finding. False positives are exempted in tools/secret-scan-allowlist.json
(path + pattern_id + reason, every entry justified). The commit-message backstop only checks
commits after the policy boundary SHA recorded in the allowlist file (history predating the
hygiene policy carries session trailers by design and is not rewritten).

Fails closed under CI when git is unavailable. Fixture strings in the selftest are concatenated
so this file never trips itself or an external scanner.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST_PATH = ROOT / "tools" / "secret-scan-allowlist.json"

# Value shapes that are placeholders, not secrets (committed config snippets use these).
PLACEHOLDER_RE = re.compile(r"REPLACE|YOUR_|<[^>]+>|^null$|EXAMPLE|CHANGEME|TBD_", re.I)

# Emails that are always fine: bot/noreply identities and documentation domains, including the
# RFC 2606 reserved names (.example TLD, example.com/org) used by the fictional fixtures.
EMAIL_ALLOW_RE = re.compile(
    r"(noreply@anthropic\.com|@users\.noreply\.github\.com|@example\.(com|org)|@test\.com"
    r"|\.example)$", re.I
)

PATTERNS = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("slack_token", re.compile(r"xox[abpr]-[A-Za-z0-9-]{10,}")),
    ("stripe_key", re.compile(r"[sp]k_live_[A-Za-z0-9]{16,}")),
    ("generic_sk_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer_header", re.compile(r"(?i)authorization:\s*bearer\s+[A-Za-z0-9._\-]{16,}")),
    ("credential_value", re.compile(
        r"\"(api_key|apikey|access_token|refresh_token|client_secret|client_id|password|token)\""
        r"\s*:\s*\"([^\"]{8,})\"")),
    ("session_link", re.compile(r"claude\.ai/code/session_[A-Za-z0-9]+")),
    ("email_address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
]

# Dollar figures are suspect ONLY inside committed pipeline/ files (blank templates by contract).
AMOUNT_RE = re.compile(r"\$\s?[0-9][0-9,]{2,}(\.[0-9]{2})?")

TEXT_SUFFIXES = (".md", ".json", ".py", ".js", ".txt", ".yml", ".yaml", ".html", ".css",
                 ".svg", ".toml", ".cfg", ".ini", ".sh", ".srt", ".vtt", ".mlt", ".xml")


def _load_allowlist():
    if not ALLOWLIST_PATH.exists():
        return {"entries": [], "commit_policy_boundary": None}
    return json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))


def _allowed(allowlist, path, pattern_id):
    for e in allowlist.get("entries", []):
        if e.get("path") == path and e.get("pattern_id") == pattern_id:
            return True
    return False


def scan_text(text, path, allowlist=None):
    """Findings in one text blob. path is used for allowlist lookups and pipeline scoping."""
    allowlist = allowlist or {"entries": []}
    findings = []
    for pid, rx in PATTERNS:
        for m in rx.finditer(text):
            if pid == "credential_value" and PLACEHOLDER_RE.search(m.group(2)):
                continue
            if pid == "email_address" and EMAIL_ALLOW_RE.search(m.group(0)):
                continue
            if _allowed(allowlist, path, pid):
                continue
            snippet = m.group(0)
            if len(snippet) > 60:
                snippet = snippet[:57] + "..."
            findings.append({"path": path, "pattern_id": pid, "match": snippet})
    if path.startswith("pipeline/") and not _allowed(allowlist, path, "pipeline_amount"):
        for m in AMOUNT_RE.finditer(text):
            findings.append({"path": path, "pattern_id": "pipeline_amount", "match": m.group(0)})
    return findings


def _git(args, check=True):
    out = subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    if check and out.returncode != 0:
        return None
    return out.stdout


def scan_tracked(allowlist):
    listing = _git(["ls-files"])
    if listing is None:
        return None
    findings = []
    for path in listing.splitlines():
        path = path.strip()
        if not path or not path.lower().endswith(TEXT_SUFFIXES):
            continue
        if path == "tools/secret_scan.py":
            continue  # this file defines the patterns; its selftest fixtures are concatenated
        try:
            text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings.extend(scan_text(text, path, allowlist))
    return findings


def scan_staged(allowlist):
    """Scan only staged ADDED lines plus staged filenames (the pre-commit surface)."""
    names = _git(["diff", "--cached", "--name-only"])
    if names is None:
        return None
    findings = []
    for path in names.splitlines():
        path = path.strip()
        if not path:
            continue
        base = path.rsplit("/", 1)[-1].lower()
        if re.search(r"\.local(\.|$)", base) or base.endswith((".csv", ".xlsx", ".xls",
                                                               ".ofx", ".qfx", ".pem", ".key")) \
                or re.match(r"^\.env(\.|$)", base):
            findings.append({"path": path, "pattern_id": "forbidden_staged_file",
                             "match": base})
    diff = _git(["diff", "--cached", "--unified=0"])
    if diff is None:
        return findings
    current = "(staged)"
    added = {}
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            added.setdefault(current, []).append(line[1:])
    for path, lines in added.items():
        if path == "tools/secret_scan.py":
            continue
        findings.extend(scan_text("\n".join(lines), path, allowlist))
    return findings


def scan_commit_messages(rng, allowlist):
    """Scan commit messages and author emails in a range (the CI backstop). Bounded by the
    policy SHA in the allowlist file: commits at or before the boundary predate the hygiene
    policy and are skipped."""
    boundary = allowlist.get("commit_policy_boundary")
    log = _git(["log", rng, "--format=%H%x00%ae%x00%B%x01"], check=True)
    if log is None:
        return None
    boundary_and_before = set()
    if boundary:
        prior = _git(["rev-list", boundary], check=False)
        if prior:
            boundary_and_before = {line.strip() for line in prior.splitlines() if line.strip()}
    findings = []
    for record in log.split("\x01"):
        record = record.strip()
        if not record:
            continue
        sha, _, rest = record.partition("\x00")
        email, _, body = rest.partition("\x00")
        if sha in boundary_and_before:
            continue
        where = f"commit:{sha[:12]}"
        for f in scan_text(body, where, allowlist):
            findings.append(f)
        if email and not EMAIL_ALLOW_RE.search(email) and not _allowed(allowlist, where, "author_email"):
            findings.append({"path": where, "pattern_id": "author_email", "match": email})
    return findings


def _check(label, cond, failures):
    print(f"  [{'ok' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)


def selftest():
    f = []
    al = {"entries": [{"path": "x.md", "pattern_id": "session_link", "reason": "test"}]}
    # Fixtures concatenated so this file never contains a real-looking token at rest.
    aws = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
    gh = "gh" + "p_" + "a" * 36
    slack = "xo" + "xb-" + "1234567890-abc"
    pem = "-----BEGIN " + "RSA PRIVATE KEY-----"
    bearer = "Authorization: " + "Bearer " + "t" * 24
    sess = "https://claude." + "ai/code/session_" + "abc123XYZ"
    cred = '"client_' + 'secret": "' + "s" * 12 + '"'
    placeholder = '"client_' + 'secret": "REPLACE_' + 'WITH_CLIENT_SECRET"'
    email = "someone" + "@gmail.com"

    _check("aws key detected", any(x["pattern_id"] == "aws_access_key"
                                   for x in scan_text(aws, "a.md", al)), f)
    _check("github token detected", any(x["pattern_id"] == "github_token"
                                        for x in scan_text(gh, "a.md", al)), f)
    _check("slack token detected", any(x["pattern_id"] == "slack_token"
                                       for x in scan_text(slack, "a.md", al)), f)
    _check("private key block detected", any(x["pattern_id"] == "private_key_block"
                                             for x in scan_text(pem, "a.md", al)), f)
    _check("bearer header detected", any(x["pattern_id"] == "bearer_header"
                                         for x in scan_text(bearer, "a.md", al)), f)
    _check("session link detected", any(x["pattern_id"] == "session_link"
                                        for x in scan_text(sess, "a.md", al)), f)
    _check("credential value detected", any(x["pattern_id"] == "credential_value"
                                            for x in scan_text(cred, "a.json", al)), f)
    _check("placeholder credential value is NOT a finding",
           not any(x["pattern_id"] == "credential_value"
                   for x in scan_text(placeholder, "a.json", al)), f)
    _check("personal email detected", any(x["pattern_id"] == "email_address"
                                          for x in scan_text(email, "a.md", al)), f)
    _check("noreply email is NOT a finding",
           not scan_text("noreply@anthropic.com", "a.md", al), f)
    _check("github noreply email is NOT a finding",
           not scan_text("12345+user@users.noreply.github.com", "a.md", al), f)
    _check("allowlisted path+pattern is exempt",
           not any(x["pattern_id"] == "session_link"
                   for x in scan_text(sess, "x.md", al)), f)
    _check("dollar amount in pipeline/ file detected",
           any(x["pattern_id"] == "pipeline_amount"
               for x in scan_text("fee is $2,500.00", "pipeline/deals/x.json", al)), f)
    _check("dollar amount OUTSIDE pipeline/ is NOT a finding",
           not any(x["pattern_id"] == "pipeline_amount"
                   for x in scan_text("fee is $2,500.00", "docs/x.md", al)), f)
    _check("clean text yields no findings",
           not scan_text("a perfectly ordinary sentence", "a.md", al), f)

    n = 15
    print(f"selftest: {'PASS' if not f else 'FAIL'} ({n - len(f)} of {n} checks)")
    return 0 if not f else 1


def _report(findings, mode):
    if findings is None:
        if os.environ.get("CI"):
            print(f"secret-scan [{mode}]: git unavailable in CI; failing closed")
            return 1
        print(f"secret-scan [{mode}]: git unavailable; skipped (local run)")
        return 0
    if findings:
        print(f"secret-scan [{mode}]: {len(findings)} finding(s)")
        for x in findings:
            print(f"  - {x['path']}: {x['pattern_id']}: {x['match']}")
        print("If a finding is a verified false positive, exempt it in "
              "tools/secret-scan-allowlist.json with a reason.")
        return 1
    print(f"secret-scan [{mode}]: clean")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS content secret scanner")
    ap.add_argument("--tracked", action="store_true")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--commit-messages", metavar="RANGE")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    allowlist = _load_allowlist()
    if a.selftest:
        return selftest()
    if a.tracked:
        return _report(scan_tracked(allowlist), "tracked")
    if a.staged:
        return _report(scan_staged(allowlist), "staged")
    if a.commit_messages:
        return _report(scan_commit_messages(a.commit_messages, allowlist), "commit-messages")
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
