#!/usr/bin/env python3
"""Creator OS content secret scanner (P31).

The filename invariants (19, 20) keep real-data FILES and audit-record files out of git; this scanner keeps secret
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
    # Classic gh?_ prefixes plus fine-grained github_pat_ tokens.
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,}")),
    ("slack_token", re.compile(r"xox[abpr]-[A-Za-z0-9-]{10,}")),
    ("stripe_key", re.compile(r"[sp]k_live_[A-Za-z0-9]{16,}")),
    # The body allows - and _ so the CURRENT provider formats match: OpenAI sk-proj-/sk-svcacct-/
    # sk-admin- and Anthropic sk-ant-api03-/sk-ant-oat01- keys are base64url with hyphenated
    # prefixes; the old alnum-only class missed every one of them.
    ("generic_sk_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer_header", re.compile(r"(?i)authorization:\s*bearer\s+[A-Za-z0-9._\-]{16,}")),
    # DEV-TRAP: this flags a literal "access_token": "<8+ chars>" even in FAKE test fixtures (only
    # REPLACE_/YOUR_/<...>-style placeholders are exempt). In tests bind the key to a variable
    # (AT = "access_token"; {AT: "FAKE"}) rather than allowlisting a real-looking value. See
    # tools/publishing/MAINTAINER_README.md "Contributor gotchas".
    ("credential_value", re.compile(
        r"\"(api_key|apikey|access_token|refresh_token|client_secret|client_id|password|token)\""
        r"\s*:\s*\"([^\"]{8,})\"")),
    ("session_link", re.compile(r"claude\.ai/code/session_[A-Za-z0-9]+")),
    ("email_address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    # North American phone numbers: (NNN) NNN-NNNN and NNN-NNN-NNNN, NNN.NNN.NNNN or NNN NNN NNNN,
    # each with an optional +1 or 1 prefix (1-800-...) and with letters such as an x extension
    # allowed right after the last digit. Area and exchange codes start 2 to 9 as the numbering plan
    # requires, and a match may not sit inside a longer dotted or dashed number, so dates,
    # versions, ISBNs and ports stay clean. Bare 10-digit runs and non-NANP numbers are not matched.
    ("phone_number", re.compile(
        r"(?<![\w.+-])(?:\+1[ .-]?|1[ .-])?(?:\([2-9]\d{2}\)[ .-]?|[2-9]\d{2}[ .-])[2-9]\d{2}[ .-]\d{4}(?!\d)(?![-.]\d)")),
]

# Dollar figures are suspect ONLY inside committed pipeline/ files (blank templates by contract).
AMOUNT_RE = re.compile(r"\$\s?[0-9][0-9,]{2,}(\.[0-9]{2})?")

# Data-at-rest forbidden tracked suffixes. The SINGLE shared list consumed by three enforcement
# points so they can never drift apart: sync_check invariant 20 (tracked files), the --staged
# pre-commit gate below, and CI. Tiered rationale (what each class carries and why it can never
# be tracked) lives in docs/DOC-MAINTENANCE.md and ADR 0048. Matching is case-insensitive
# (callers lowercase the basename first); dotfile names like .netrc match whole-basename via
# endswith. The gitignore is the first line; this list is the fail-closed backstop that catches
# force-adds and path gaps.
FORBIDDEN_DATA_SUFFIXES = (
    # Spreadsheets (rows of PII/financial data; .xlsm carries VBA macros, .xlsb is binary)
    ".xls", ".xlsx", ".xlsm", ".xlsb", ".xlt", ".xltx", ".xltm", ".ods", ".fods", ".numbers",
    # Delimited / columnar data exports (bank, analytics, CRM dumps)
    ".csv", ".tsv", ".parquet", ".feather", ".arrow", ".avro", ".orc",
    # Financial application files (OFX/QFX statements, QuickBooks, Quicken, TurboTax, YNAB, Money)
    ".ofx", ".qfx", ".qbo", ".qbw", ".qba", ".qbb", ".qbm", ".qbx", ".qby", ".qif", ".iif",
    ".qdf", ".qel", ".qph", ".tax", ".tax2022", ".tax2023", ".tax2024", ".tax2025", ".tax2026",
    ".ynab4", ".mny",
    # Credential / key material and credential stores (private keys, cert bundles, password
    # manager databases, Apple Keychain/.p8/provisioning, PuTTY, PGP, tool credential dotfiles)
    ".pem", ".key", ".p12", ".pfx", ".pkcs12", ".jks", ".keystore", ".bks", ".ppk",
    ".kdbx", ".kdb", ".1pif", ".opvault", ".agilekeychain", ".keychain", ".keychain-db",
    ".p8", ".mobileprovision", ".provisionprofile", ".cer", ".crt", ".der", ".csr",
    ".gpg", ".pgp", ".asc", ".netrc", ".pgpass", ".htpasswd", ".npmrc", ".pypirc",
    # Databases (on-device stores that hold real CRM/finance rows) and backups/dumps
    ".sqlite", ".sqlite3", ".db", ".db3", ".mdb", ".accdb", ".sdf", ".realm", ".gdb", ".nsf",
    ".frm", ".myd", ".bak", ".bkp", ".backup", ".dump", ".sql", ".bson", ".ldf", ".mdf",
    # Email / PIM / contacts (mailboxes, messages, .vcf contact cards are PII)
    ".pst", ".ost", ".mbox", ".eml", ".emlx", ".msg", ".vcf", ".vcard", ".olm",
    # Disk / container images (can carry an entire home directory)
    ".dmg", ".vmdk", ".vdi", ".ova",
    # Archives: opaque to the content scanner, so a tracked one smuggles unscannable data
    ".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".zst",
    # Office / document binaries: media kits, contracts, proposals carry PII and the content
    # scanner cannot read them (.docx/.pptx are zip-XML, .pdf is binary)
    ".doc", ".docx", ".dot", ".dotx", ".ppt", ".pptx", ".rtf", ".pages", ".pdf", ".odt", ".odp",
    # Capture media (EXIF/GPS/device metadata in photos, footage, audio). Web graphics
    # (.png/.gif/.webp/.svg/.ico) stay ALLOWED as legitimate committed assets.
    ".jpg", ".jpeg", ".heic", ".heif", ".tiff", ".tif", ".raw", ".cr2", ".cr3", ".nef",
    ".arw", ".dng", ".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mp3", ".m4a", ".wav",
    ".aac", ".flac",
)

# Audit-record file names. Review output (audit reports, remediation and readiness records, triage
# tables, findings, a pass's ledger, notes, transcripts and minutes) is kept outside the
# repository; the repository carries the change and the docs that describe behavior (CLAUDE.md,
# Non-negotiables). A path names an audit record when its file name pairs a review keyword (whole
# word, plural and -ed forms included) with a calendar date (ISO 2026-10-01 or compact 20261001,
# either order) and carries a text suffix, or when it is listed in AUDIT_RECORD_PATHS (record names
# that carry no date). Method docs and tools (AUDIT-PROTOCOL.md, persona_audit.py, an ADR titled
# "...-audit-remediation") carry no date and do not match. Consumers: sync_check invariant 20
# (tracked files) and scan_staged (the pre-commit gate).
# Limit: the rule matches the dated and listed record names this repository has carried, and a
# bare dated file under a keyword directory (docs/audits/2026-10-01.md) through the directory
# name. An underscore or dotted date (audit_2026_10_01.md) is not matched; the selftest pins
# that, so widening the rule is a deliberate change.
AUDIT_RECORD_KEYWORD_RE = re.compile(
    r"(?<![a-z])(?:audit|remediation|readiness|review|triage|finding|ledger|verification|note"
    r"|addendum|addenda|session|transcript|discussion|minute)(?:s|es|ed|d)?(?![a-z])")
AUDIT_RECORD_DATE_RE = re.compile(
    r"(?<![0-9])(?:19|20)[0-9]{2}(-?)(?:0[1-9]|1[0-2])\1(?:0[1-9]|[12][0-9]|3[01])(?![0-9])")
AUDIT_RECORD_TEXT_SUFFIXES = (
    ".md", ".markdown", ".mdx", ".txt", ".text", ".rst", ".adoc", ".org", ".html", ".htm", ".xml",
    ".json", ".jsonl", ".ndjson", ".yaml", ".yml", ".toml", ".csv", ".tsv", ".log", ".ipynb",
)
AUDIT_RECORD_PATHS = (
    "docs/CROSS-MODALITY-AUDIT.md",
    "docs/FL-COUNTY-SEEDING-EFFORT.md",
)
# Filename findings do not pass through _allowed() (that map is keyed by content pattern), so the
# name rule has its own exemption map: {path: reason}. A reason shorter than
# AUDIT_RECORD_MIN_REASON does not exempt, and invariant 20 reports an entry that no longer does
# work (path untracked, or the rule no longer matches it).
AUDIT_RECORD_EXEMPT = {}
AUDIT_RECORD_MIN_REASON = 25


def audit_record_name(path):
    """Why `path` names an audit record, or None. Pure: reads nothing."""
    rel = path.replace("\\", "/")
    if rel.startswith("./"):
        rel = rel[2:]
    if rel in AUDIT_RECORD_PATHS:
        return "listed in AUDIT_RECORD_PATHS"
    base = rel.rsplit("/", 1)[-1].lower()
    if not base.endswith(AUDIT_RECORD_TEXT_SUFFIXES):
        return None
    key = AUDIT_RECORD_KEYWORD_RE.search(base)
    if key is None:
        # A bare dated file under a keyword directory (docs/audits/2026-10-01.md).
        key = next((m for m in (AUDIT_RECORD_KEYWORD_RE.search(d)
                                for d in rel.lower().split("/")[:-1]) if m), None)
    date = AUDIT_RECORD_DATE_RE.search(base)
    if key and date:
        return f"review keyword {key.group(0)!r} with date {date.group(0)!r}"
    return None


def audit_record_findings(paths, exempt=None):
    """Findings for the audit-record names among `paths`, minus reasoned exemptions."""
    exempt = AUDIT_RECORD_EXEMPT if exempt is None else exempt
    findings = []
    for path in paths:
        why = audit_record_name(path)
        if why is None:
            continue
        if len((exempt.get(path) or "").strip()) >= AUDIT_RECORD_MIN_REASON:
            continue
        findings.append({"path": path, "pattern_id": "audit_record_file", "match": why})
    return findings


def audit_exempt_problems(tracked, exempt=None):
    """Exemption entries that do no work or carry no reviewable reason."""
    exempt = AUDIT_RECORD_EXEMPT if exempt is None else exempt
    tracked = set(tracked)
    problems = []
    for path, reason in sorted(exempt.items()):
        if len((reason or "").strip()) < AUDIT_RECORD_MIN_REASON:
            problems.append(f"audit-record exemption for {path} needs a written reason of at least "
                            f"{AUDIT_RECORD_MIN_REASON} characters")
        elif path not in tracked:
            problems.append(f"audit-record exemption for {path} names an untracked file; drop it")
        elif audit_record_name(path) is None:
            problems.append(f"audit-record exemption for {path} exempts nothing (the name rule "
                            f"does not match it); drop it")
    return problems


def _is_probably_text(data):
    """Binary sniff: NUL byte in the head means binary (the injection_scan convention). The
    tracked-content scan reads EVERY tracked file and skips only true binaries, so a credential
    in secrets.conf or an extensionless 'credentials' file is no longer suffix-invisible."""
    return b"\x00" not in data[:8192]


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
        if not path:
            continue
        if path == "tools/secret_scan.py":
            continue  # this file defines the patterns; its selftest fixtures are concatenated
        try:
            data = (ROOT / path).read_bytes()
        except OSError:
            continue
        # Every tracked file is content-scanned unless it is a true binary: suffix-gating let a
        # credential file with an unlisted extension sail through invisible to this scan.
        if not _is_probably_text(data):
            continue
        text = data.decode("utf-8", errors="replace")
        findings.extend(scan_text(text, path, allowlist))
    return findings


def scan_staged(allowlist):
    """Scan only staged ADDED lines plus staged filenames (the pre-commit surface). Staged
    deletions are not names being added, so --diff-filter=d leaves them out: deleting a forbidden
    file or an audit record is the fix, not a finding."""
    names = _git(["diff", "--cached", "--name-only", "--diff-filter=d"])
    if names is None:
        return None
    findings = []
    for path in names.splitlines():
        path = path.strip()
        if not path:
            continue
        base = path.rsplit("/", 1)[-1].lower()
        if re.search(r"\.local(\.|$)", base) or base.endswith(FORBIDDEN_DATA_SUFFIXES) \
                or re.match(r"^\.env(\.|$)", base):
            findings.append({"path": path, "pattern_id": "forbidden_staged_file",
                             "match": base})
    findings.extend(audit_record_findings([p.strip() for p in names.splitlines() if p.strip()]))
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


def _check(label, cond, failures, ran):
    ran[0] += 1
    print(f"  [{'ok' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)


def selftest():
    f = []
    ran = [0]
    al = {"entries": [{"path": "x.md", "pattern_id": "session_link", "reason": "test"}]}
    # Fixtures concatenated so this file never contains a real-looking token at rest.
    aws = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
    gh = "gh" + "p_" + "a" * 36
    gh_pat = "github_" + "pat_" + "a" * 22
    slack = "xo" + "xb-" + "1234567890-abc"
    sk_classic = "sk" + "-" + "a" * 24
    sk_proj = "sk" + "-proj-" + "a" * 20
    sk_ant = "sk" + "-ant-api03-" + "a" * 20
    pem = "-----BEGIN " + "RSA PRIVATE KEY-----"
    bearer = "Authorization: " + "Bearer " + "t" * 24
    sess = "https://claude." + "ai/code/session_" + "abc123XYZ"
    cred = '"client_' + 'secret": "' + "s" * 12 + '"'
    placeholder = '"client_' + 'secret": "REPLACE_' + 'WITH_CLIENT_SECRET"'
    email = "someone" + "@gmail.com"
    # Phone fixtures are concatenated too, so no phone-shaped string sits in this file at rest.
    phones = ("(415" + ") 555-" + "0199", "+1 415" + " 555 " + "0199", "415." + "555." + "0199",
              "1-800" + "-555-" + "1234", "1.415" + ".555." + "0199", "(415)" + "-555-" + "0199x12")
    not_phones = ("2026-09-25", "v2.312.4567", "ISBN 978-0-306-40615-7", "port 8766",
                  "1234 Market St", "12.345.678.9012")
    _check("phone number detected in the paren, +1, 1-prefix, dotted and extension NANP shapes",
           all(any(x["pattern_id"] == "phone_number" for x in scan_text(p, "docs/a.md", al))
               for p in phones), f, ran)
    unmatched = ("415" + "5550199", "415/" + "555-" + "0199", "415 - " + "555 - " + "0199")
    _check("one digit run, slash and spaced-dash phone forms are NOT phone findings",
           not any(x["pattern_id"] == "phone_number"
                   for s in unmatched for x in scan_text(s, "docs/a.md", al)), f, ran)
    _check("dates, versions, ISBNs, ports and street numbers are NOT phone findings",
           not any(x["pattern_id"] == "phone_number"
                   for s in not_phones for x in scan_text(s, "docs/a.md", al)), f, ran)

    _check("aws key detected", any(x["pattern_id"] == "aws_access_key"
                                   for x in scan_text(aws, "a.md", al)), f, ran)
    _check("github token detected", any(x["pattern_id"] == "github_token"
                                        for x in scan_text(gh, "a.md", al)), f, ran)
    _check("fine-grained github_pat_ token detected",
           any(x["pattern_id"] == "github_token"
               for x in scan_text(gh_pat, "a.md", al)), f, ran)
    _check("slack token detected", any(x["pattern_id"] == "slack_token"
                                       for x in scan_text(slack, "a.md", al)), f, ran)
    _check("classic sk- key detected", any(x["pattern_id"] == "generic_sk_key"
                                           for x in scan_text(sk_classic, "a.md", al)), f, ran)
    _check("modern hyphenated sk-proj- key detected (current OpenAI format)",
           any(x["pattern_id"] == "generic_sk_key"
               for x in scan_text(sk_proj, "a.md", al)), f, ran)
    _check("hyphenated sk-ant- key detected (current Anthropic format)",
           any(x["pattern_id"] == "generic_sk_key"
               for x in scan_text(sk_ant, "a.md", al)), f, ran)
    _check("hyphen-embedded prose word (desk-...) is NOT an sk- finding",
           not scan_text("a desk-mounted-microphone-arm-for-recording setup", "a.md", al), f, ran)
    _check("private key block detected", any(x["pattern_id"] == "private_key_block"
                                             for x in scan_text(pem, "a.md", al)), f, ran)
    _check("bearer header detected", any(x["pattern_id"] == "bearer_header"
                                         for x in scan_text(bearer, "a.md", al)), f, ran)
    _check("session link detected", any(x["pattern_id"] == "session_link"
                                        for x in scan_text(sess, "a.md", al)), f, ran)
    _check("credential value detected", any(x["pattern_id"] == "credential_value"
                                            for x in scan_text(cred, "a.json", al)), f, ran)
    _check("placeholder credential value is NOT a finding",
           not any(x["pattern_id"] == "credential_value"
                   for x in scan_text(placeholder, "a.json", al)), f, ran)
    _check("personal email detected", any(x["pattern_id"] == "email_address"
                                          for x in scan_text(email, "a.md", al)), f, ran)
    _check("noreply email is NOT a finding",
           not scan_text("noreply@anthropic.com", "a.md", al), f, ran)
    _check("github noreply email is NOT a finding",
           not scan_text("12345+user@users.noreply.github.com", "a.md", al), f, ran)
    _check("allowlisted path+pattern is exempt",
           not any(x["pattern_id"] == "session_link"
                   for x in scan_text(sess, "x.md", al)), f, ran)
    _check("dollar amount in pipeline/ file detected",
           any(x["pattern_id"] == "pipeline_amount"
               for x in scan_text("fee is $2,500.00", "pipeline/deals/x.json", al)), f, ran)
    _check("dollar amount OUTSIDE pipeline/ is NOT a finding",
           not any(x["pattern_id"] == "pipeline_amount"
                   for x in scan_text("fee is $2,500.00", "docs/x.md", al)), f, ran)
    _check("clean text yields no findings",
           not scan_text("a perfectly ordinary sentence", "a.md", al), f, ran)
    _check("binary sniff: plain text is scannable",
           _is_probably_text(b"just ordinary text\nwith lines"), f, ran)
    _check("binary sniff: NUL-bearing bytes are skipped as binary",
           not _is_probably_text(b"PK\x03\x04\x00binaryblob"), f, ran)
    _check("forbidden suffixes cover the known leak classes",
           all(s in FORBIDDEN_DATA_SUFFIXES
               for s in (".xlsm", ".kdbx", ".sqlite", ".vcf", ".qbw", ".pst", ".zip", ".pdf",
                         ".heic", ".pem", ".key", ".csv")), f, ran)
    _check("dotfile credential names match via endswith (.netrc as whole basename)",
           ".netrc".endswith(FORBIDDEN_DATA_SUFFIXES), f, ran)
    _check("allowed web-graphic and text suffixes are NOT forbidden",
           not any(s in FORBIDDEN_DATA_SUFFIXES
                   for s in (".png", ".svg", ".md", ".json", ".py", ".srt", ".mlt")), f, ran)

    # Audit-record file names (invariant 20 and the --staged gate). Fixture names are synthetic.
    _check("audit-record rule: a review keyword with an ISO date is flagged",
           all(audit_record_name(p) for p in (
               "docs/phase-audit-2026-01-02.md", "docs/release-readiness-2026-01-02.md",
               "docs/remediation-2026-01-02.md", "docs/tool-audit-2026-01-02.md",
               "docs/source-audit-2026-01-02.md")), f, ran)
    _check("audit-record rule: compact dates, date-first order, word forms and text suffixes",
           all(audit_record_name(p) for p in (
               "notes/2026-01-02-review.txt", "session-transcript-20260102.json",
               "20260102_triaged.yaml", "minutes-2026-01-02.html", "findings.2026-01-02.rst",
               "ledger-2026-01-02.jsonl", "addendum-2026-01-02.md", "discussion-20260102.md",
               "audited-2026-01-02.txt", "reviews-2026-01-02.md", "verification-2026-01-02.log")),
           f, ran)
    _check("audit-record rule: every AUDIT_RECORD_PATHS entry is flagged",
           bool(AUDIT_RECORD_PATHS) and all(audit_record_name(p) for p in AUDIT_RECORD_PATHS),
           f, ran)
    _check("audit-record rule: method docs and dated non-review data are not flagged",
           not any(audit_record_name(p) for p in (
               "docs/AUDIT-PROTOCOL.md", "docs/PERSONA-AUDIT.md", "tools/persona_audit.py",
               "tools/hash_audit.py", "tools/local_audit.py",
               "docs/adr/0056-p81-audit-remediation.md",
               "canonical-sources/volatile-corrections.2026-07-14.json",
               "skills/quality-review/SKILL.md", "skills/atoms/contract-triage/SKILL.md",
               "ledger/ledger.json")), f, ran)
    _check("audit-record rule: needs a whole keyword, a real date and a text suffix",
           not any(audit_record_name(p) for p in (
               "reviewer-2026-01-02.md", "notebook-2026-01-02.md", "audit-2026-13-02.md",
               "audit-2026-01-32.md", "review-2026-01-02.py", "review-2026-0102.md",
               "audit-v2026.md", "docs/reviewer/2026-01-02.md")), f, ran)
    _check("audit-record rule: a bare dated file under a keyword directory is flagged",
           all(audit_record_name(p) for p in (
               "docs/audits/2026-01-02.md", "notes/20260102.md", "reviews/2026/2026-01-02-q1.md")),
           f, ran)
    _check("audit-record rule: the stated limit holds (an underscore or dotted date)",
           not any(audit_record_name(p) for p in (
               "docs/audit_2026_01_02.md", "docs/audit.2026.01.02.md")),
           f, ran)
    _rec = "docs/review-2026-01-02.md"
    _check("audit-record exemption needs a written reason to exempt",
           audit_record_findings([_rec], {_rec: "short"})
           and not audit_record_findings([_rec], {_rec: "a fixture the name rule is tested on"}),
           f, ran)
    _check("audit-record exemption that does no work is reported",
           audit_exempt_problems([], {_rec: "a fixture the name rule is tested on"})
           and audit_exempt_problems(["docs/plain.md"],
                                     {"docs/plain.md": "a fixture the name rule is tested on"})
           and not audit_exempt_problems([_rec], {_rec: "a fixture the name rule is tested on"}),
           f, ran)
    # The staged gate reads added, copied, modified and renamed names; a staged deletion of a
    # record is how one leaves the tree, so it must not be refused.
    _g = globals()
    _real_git = _g["_git"]

    def _fake_git(args, check=True):
        if args[:2] == ["diff", "--cached"] and "--name-only" in args:
            if "--diff-filter=d" in args:
                return "docs/review-2026-01-02.md\n"
            return "docs/review-2026-01-02.md\ndocs/remediation-2026-01-02.md\n"
        return ""
    _g["_git"] = _fake_git
    try:
        _staged = {x["path"] for x in scan_staged({"entries": []})
                   if x["pattern_id"] == "audit_record_file"}
    finally:
        _g["_git"] = _real_git
    _check("staged gate refuses an added audit record and passes a staged deletion",
           _staged == {"docs/review-2026-01-02.md"}, f, ran)
    # Drift invariant 20 consumes the rule: run its check on a stubbed tracked list.
    import sync_check as _sc
    _real_ls, _saved = _sc._git_ls_files, list(_sc.PROBLEMS)
    _sc._git_ls_files = lambda: ["docs/review-2026-01-02.md", "docs/AUDIT-PROTOCOL.md"]
    try:
        del _sc.PROBLEMS[:]
        _sc.check_pipeline_allowlist()
        _inv20 = list(_sc.PROBLEMS)
    finally:
        _sc._git_ls_files = _real_ls
        _sc.PROBLEMS[:] = _saved
    _check("drift invariant 20 refuses a tracked audit record through this rule",
           len(_inv20) == 1 and "docs/review-2026-01-02.md" in _inv20[0], f, ran)

    n = ran[0]
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
