#!/usr/bin/env python3
"""Creator OS content secret scanner (P31).

The filename invariants (19, 20) keep real-data FILES and audit-record files out of git; this scanner keeps secret
CONTENT out: API keys in the vendor formats PATTERNS lists, private-key blocks, credential values in committed JSON, YAML and .env text,
personal email addresses, claude.ai session links, and dollar-amount figures inside committed
pipeline/ files (which must be blank templates). Pure stdlib, no network, read-only.

Modes:
  python3 tools/secret_scan.py --tracked                  # scan all git-tracked file content (CI, invariant 21)
  python3 tools/secret_scan.py --staged                   # scan staged additions (pre-commit hook)
  python3 tools/secret_scan.py --commit-messages RANGE    # scan commit messages + author emails (CI backstop)
  python3 tools/secret_scan.py --selftest

Exit 1 on any finding. False positives are exempted in tools/secret-scan-allowlist.json
(path + pattern_id + reason; --tracked fails on an entry that no longer exempts anything). The commit-message backstop checks
the commits after the policy boundary SHA recorded in the allowlist file: the boundary commit and
its ancestors are not re-checked, because history is not rewritten (some predate the message
rules, and some carry text a later rule refuses). The selftest runs the scan over a scripted
history framed as git log frames it and checks that limit, a boundary git cannot resolve (no
commit skipped) and a range git cannot list (the scan returns None); ten committed mutations of
the scan each fail that check.

Fails closed under CI when git is unavailable. Fixture strings in the selftest are concatenated
so this file never trips itself or an external scanner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST_PATH = ROOT / "tools" / "secret-scan-allowlist.json"

# Value shapes that are placeholders, not secrets (committed config snippets use these).
PLACEHOLDER_RE = re.compile(r"REPLACE|YOUR_|<[^>]+>|^null$|EXAMPLE|CHANGEME|TBD_", re.I)

# Emails that are always fine: the Anthropic noreply identity, GitHub noreply addresses, and the
# RFC 2606 documentation names (example.com, example.org and any name under the .example
# top-level domain) used by the fictional fixtures. The pattern must match the whole address,
# anchored at both ends, so a local part that only ends in noreply (jane.noreply@...), a domain
# that only ends in an allowed name (myexample.com) or extends one (anthropic.com.evil.io), a
# misspelt domain, and an author email with a second @ are findings. The address pattern reads
# letters, digits and . _ % + - in a local part, so a local part that joins noreply with any other
# character (an apostrophe, !, /) is read from noreply on and passes.
EMAIL_ALLOW_RE = re.compile(
    r"\A(?:noreply@anthropic\.com|[A-Za-z0-9._%+-]+@(?:users\.noreply\.github\.com"
    r"|example\.(?:com|org)|(?:[A-Za-z0-9-]+\.)+example))\Z", re.I
)
# In text the address match stops before a digit, _ or - that follows the last letters of a
# domain, so an allowed address counts only when nothing that continues a domain follows the
# match: a letter, digit, _ or -, or a dot followed by one. An allowed address directly followed
# by _x.io is a finding; a closing bracket, quote or sentence-ending dot is not a continuation.
EMAIL_DOMAIN_CONT_RE = re.compile(r"[A-Za-z0-9_-]|\.[A-Za-z0-9_-]")

# credential_value keys and values (PATTERNS). A key is one of these names in any letter case, its
# words joined by _, - or nothing (api_key, apiKey, API-KEY), after any prefix of letters, digits,
# _ and - (stripe_api_key, access_token, client_secret, dbPassword, nextPageToken); a .env key is
# upper case (GITHUB_TOKEN). A YAML or .env value is read from these characters up to a space, a
# quote or #, so an expression (os.environ[...], get_password()) is not read as a value, and a
# value that starts with / or . (a file path) is not read.
_CRED_KEY = (r"[A-Za-z0-9_-]*?(?:api[_-]?key|client[_-]?id|password|passwd|secret(?:[_-]?key)?"
             r"|private[_-]?key|token)")
_CRED_ENV_KEY = r"[A-Z0-9_]*(?:API_?KEY|CLIENT_ID|PASSWORD|PASSWD|SECRET(?:_KEY)?|PRIVATE_KEY|TOKEN)"
_CRED_VAL = r"[A-Za-z0-9._~+/=:@!*-]{8,}"

PATTERNS = [
    # Long-term (AKIA) and temporary (ASIA) access key ids.
    ("aws_access_key", re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}")),
    # Classic gh?_ prefixes plus fine-grained github_pat_ tokens.
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,}")),
    # Bot, user, app, refresh and config tokens, the app-level xapp- token.
    ("slack_token", re.compile(r"xox[abprse]-[A-Za-z0-9-]{10,}|xapp-\d-[A-Za-z0-9-]{10,}")),
    ("stripe_key", re.compile(r"[spr]k_live_[A-Za-z0-9]{16,}")),
    # The body allows - and _ so the CURRENT provider formats match: OpenAI sk-proj-/sk-svcacct-/
    # sk-admin- and Anthropic sk-ant-api03-/sk-ant-oat01- keys are base64url with hyphenated
    # prefixes; the old alnum-only class missed every one of them.
    ("generic_sk_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    # PEM and OpenSSH blocks, the PGP armor header (PRIVATE KEY BLOCK), the SSH2 header written
    # with four dashes and spaces, and the first line of a PuTTY key file.
    ("private_key_block", re.compile(
        r"-{4,5} ?BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)? ?-{4,5}|(?m:^[ \t]*PuTTY-User-Key-File-\d+:)")),
    # An Authorization value in a header line, a JSON or dict pair (a quoted key) or an assignment
    # (authorization=): the Bearer scheme under bearer_header; a scheme from the IANA HTTP
    # authentication scheme registry (Basic, Digest, Negotiate, ...) or a common vendor scheme
    # (Token, ApiKey, Key, SSWS) with a 12+ character credential, and an X-Api-Key value, under
    # authorization_header. A credential is read in the token68 characters. Not read: a value
    # with no scheme word or under another scheme word, and another header name (X-Auth-Token), by
    # these two patterns; the selftest pins that.
    ("bearer_header", re.compile(
        r"(?i)authorization[\"']?\s*[:=]\s*[\"']?bearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    ("authorization_header", re.compile(
        r"(?i)\bauthorization[\"']?\s*[:=]\s*[\"']?"
        r"(?:basic|digest|dpop|gnap|hoba|mutual|negotiate|ntlm|oauth|privatetoken|scram-sha-(?:1|256)"
        r"|vapid|concealed|token|api-?key|key|ssws)\s+"
        r"[A-Za-z0-9._~+/=-]{12,}|\bx-api-key[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9._~+/=-]{16,}")),
    # DEV-TRAP: this flags a literal "access_token": "<8+ chars>" even in FAKE test fixtures (only
    # REPLACE_/YOUR_/<...>-style placeholders are exempt). In tests bind the key to a variable
    # (AT = "access_token"; {AT: "FAKE"}) rather than allowlisting a real-looking value. See
    # tools/publishing/MAINTAINER_README.md "Contributor gotchas".
    # A credential key (_CRED_KEY) with a value of 8+ characters in a JSON pair, a single-quoted
    # Python dict pair, a YAML line (key: value) or a .env line (KEY=value, optionally after
    # export). Not read: a keyword argument or an assignment in code with a lower-case name
    # (password="..."), and a key name outside _CRED_KEY.
    ("credential_value", re.compile(
        rf"\"{_CRED_KEY}\"\s*:\s*\"([^\"]{{8,}})\"|'{_CRED_KEY}'\s*:\s*'([^'\n]{{8,}})'"
        rf"|^[ \t-]*{_CRED_KEY}[ \t]*:[ \t]*[\"']?((?![./]){_CRED_VAL})(?=[\"']?[ \t]*(?:#|$))"
        rf"|(?-i:^(?:export[ \t]+)?{_CRED_ENV_KEY}[ \t]*=[ \t]*[\"']?((?![./]){_CRED_VAL})"
        rf"(?=[\"']?[ \t]*(?:#|$)))", re.I | re.M)),
    # A host is case-insensitive, so the link is read in any letter case; a percent-encoded link
    # is read through the decoded reading (_text_views); a JSON-escaped slash (\/) is read. An
    # HTML-entity slash (&#47;) is not read; the selftest pins that.
    ("session_link", re.compile(r"(?i)claude\.ai\\?/code\\?/session_[A-Za-z0-9]+")),
    # Vendor formats are read by their fixed prefix and length. A secret with no fixed prefix (an
    # AWS secret access key, a password) and a vendor format not listed in PATTERNS (Azure, Twilio,
    # a Google OAuth client secret) are not read; the selftest pins one of each.
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("gitlab_token", re.compile(r"glpat-[0-9A-Za-z_-]{20,}")),
    ("slack_webhook", re.compile(r"hooks\.slack\.com/services/T[A-Za-z0-9]+/B[A-Za-z0-9]+/[A-Za-z0-9]+")),
    ("npm_token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("huggingface_token", re.compile(r"\bhf_[A-Za-z0-9]{34,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("sendgrid_key", re.compile(r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b")),
    ("pypi_token", re.compile(r"\bpypi-AgE[A-Za-z0-9_-]{50,}")),
    ("email_address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    # North American phone numbers: (NNN) NNN-NNNN and NNN-NNN-NNNN, NNN.NNN.NNNN or NNN NNN NNNN,
    # each with an optional +1 or 1 prefix written with a dash, dot or space after it or flush
    # against the area code (1-800-..., 1(415)..., 1415-...), and with letters such as an x
    # extension allowed right after the last digit. Area and exchange codes start 2 to 9 as the
    # numbering plan requires, and a match may not follow a letter or digit or sit inside a longer
    # dotted or dashed number (an underscore before it, as in a tel_ key, does not block it), so
    # dates, versions, ISBNs and ports stay clean. Bare 10-digit runs and non-NANP numbers are not
    # matched. The selftest builds every prefix, area-code and separator combination.
    ("phone_number", re.compile(
        r"(?<![^\W_])(?<![.+-])(?:\+?1[ .-]?)?(?:\([2-9]\d{2}\)[ .-]?|[2-9]\d{2}[ .-])[2-9]\d{2}[ .-]\d{4}(?!\d)(?![-.]\d)")),
]

# Dollar figures are suspect ONLY inside committed pipeline/ files (blank templates by contract).
# Read: a currency sign (every character of Unicode category Sc: $, the pound, euro, yen and
# rupee signs; a fullwidth sign folds to these) before or after a figure of any length, with an
# optional k, M or B suffix ($12, $5k, $1.5M, 5000 followed by a euro sign); a currency code in
# _AMOUNT_CODE before or after a figure; a figure followed by dollars, euros or pounds. A figure
# written in words and a currency code outside _AMOUNT_CODE are not read.
_AMOUNT_SIGN = "[" + re.escape("".join(chr(c) for c in range(sys.maxunicode + 1)
                                        if unicodedata.category(chr(c)) == "Sc")) + "]"
_AMOUNT_FIG = r"\d[\d,]*(?:\.\d+)?"
_AMOUNT_CODE = r"(?:usd|eur|gbp|cad|aud|chf|jpy|inr)"
AMOUNT_RE = re.compile(
    rf"{_AMOUNT_SIGN}\s?{_AMOUNT_FIG}(?:\s?[kmb]\b)?|\b{_AMOUNT_FIG}(?:\s?[kmb])?\s?{_AMOUNT_SIGN}"
    rf"|\b{_AMOUNT_CODE}\s?{_AMOUNT_FIG}"
    rf"|\b{_AMOUNT_FIG}(?:\s?[kmb])?\s?(?:dollars|euros|pounds|{_AMOUNT_CODE})\b", re.I)

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
# tables, findings, verdicts, pass records, a pass's ledger, notes, transcripts and minutes) is kept
# outside the repository; the repository carries the change and the docs that describe behavior
# (CLAUDE.md, Non-negotiables). A path names an audit record when it carries a review keyword
# (AUDIT_RECORD_KEYWORD_RE: whole word, plural and -ed forms and four -ing forms included) and a
# calendar date (AUDIT_RECORD_DATE_RE: year-month-day joined by a dash, underscore, dot, slash or
# nothing; year-month with a separator; day-month-year or month-day-year; a month name with a
# year), either of them in the file name or in a directory above it, and the file name has a
# suffix on AUDIT_RECORD_TEXT_SUFFIXES or is unsuffixed; or when it is listed in
# AUDIT_RECORD_PATHS, compared in any letter case. The path is folded first (fold_text), so
# fullwidth digits and letters, digits from other scripts, and a Unicode dash or minus sign used as
# a date separator read as ASCII. Method docs and tools (AUDIT-PROTOCOL.md, persona_audit.py, an
# ADR titled "...-audit-remediation") carry no date and do not match. Consumers: sync_check
# invariant 20 (tracked files) and scan_staged (the pre-commit gate).
# The path is also read as git prints it: a C-quoted name (one holding a byte above 0x7f, as
# `git ls-files` and `git diff --name-only` print it) is unquoted before the fold. A lowercase
# letter followed by a capital splits joined words (AuditReport_2026-10-01.md), format characters
# such as a zero-width space are dropped, and a compact date may carry a time (20261001120000).
# Limit: a record named with a word outside AUDIT_RECORD_KEYWORD_RE or run into another word in
# one letter case (securityaudit), dated by a bare year, a two-digit year, a week or a quarter
# (2026-W40, 2026-Q4), an unpadded month or day (2026-1-5), a month and day with no year, or in
# words, spelled with look-alike letters from another script (a Cyrillic a), saved under a suffix
# on neither AUDIT_RECORD_TEXT_SUFFIXES nor FORBIDDEN_DATA_SUFFIXES (a .png), or undated and not
# listed, is not matched. A product path that pairs a keyword with a year-month (a JSON Schema
# 2020-12 record file, release notes versioned 2026.10) is matched and needs an AUDIT_RECORD_EXEMPT
# entry. The selftest pins each limit, so widening the rule is a deliberate change.
AUDIT_RECORD_KEYWORD_RE = re.compile(
    r"(?<![a-z])(?:(?:audit|remediation|readiness|review|triage|finding|ledger|verification|note"
    r"|addendum|addenda|session|transcript|discussion|minute|report|verdict|record|pass"
    r"|post-?mortem|retrospective|follow-?up|inspection|walkthrough|assessment|critique|debrief"
    r"|investigation)(?:s|es|ed|d)?|auditing|reviewing|triaging|inspecting)(?![a-z])")
_AR_Y = r"(?:19|20)[0-9]{2}"
_AR_M = r"(?:0[1-9]|1[0-2])"
_AR_D = r"(?:0[1-9]|[12][0-9]|3[01])"
_AR_N = r"(?:0?[1-9]|[12][0-9]|3[01])"
_AR_MON = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
           r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
AUDIT_RECORD_DATE_RE = re.compile(
    rf"(?<![0-9]){_AR_Y}([-_./]?){_AR_M}\1{_AR_D}(?![0-9])"
    rf"|(?<![0-9]){_AR_Y}{_AR_M}{_AR_D}[0-9]{{4}}(?:[0-9]{{2}})?(?![0-9])"
    rf"|(?<![0-9]){_AR_Y}[-_./]{_AR_M}(?![0-9])(?![-_./][0-9])"
    rf"|(?<![0-9]){_AR_N}([-_./]){_AR_N}\2{_AR_Y}(?![0-9])"
    rf"|(?<![a-z0-9])(?:{_AR_N}[-_. ]?)?{_AR_MON}(?![a-z])[-_. ]?(?:{_AR_N}[-_., ]*)?{_AR_Y}(?![0-9])"
    rf"|(?<![0-9]){_AR_Y}[-_. ]?{_AR_MON}(?![a-z])")
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

# Discovery narration in the decision records (docs/adr/, ledger/ledger.json): a sentence that says
# a review, pass or planning step found or flagged something, or that a defect was found. The
# records state what was decided and what the code does. scan_text runs it on those paths.
# The actors are a review, audit, auditor, reviewer, verifier or refuter after a determiner (not a
# product tool's name: hash, local, persona, deal, contract, quality, ar, human, source) and a named
# pass (adaptability, planning, research, independent, review, audit, verification, refuter); and a
# defect, finding, gap, bug, issue or problem that was found. One verb set, _AR_VERB, serves both
# forms (a review found, flagged, surfaced, caught, spotted, identified, detected or uncovered it;
# a gap was found, flagged, ...). A camera lens, a render pass, email verification, a review queue
# and "the binary was found" are product prose and are not read.
# Limit: other phrasings ("turning it on showed", "found by the review", a lens, a verb outside
# _AR_VERB such as noticed or confirmed), words between
# the actor and the verb other than a parenthesis or a listed adverb, and other files are not
# read; the selftest pins that, and review holds them.
AUDIT_RECORD_NARRATION_SCOPE = ("docs/adr/", "ledger/ledger.json")
_AR_DET = r"(?:a|an|the|this|that|one|each|every)\s+"
_AR_NOT_TOOL = r"(?!(?:hash|local|persona|deal|contract|quality|ar|human|source)\s)"
_AR_VERB = r"(?:found|flagged|surfaced|caught|spotted|identified|detected|uncovered)"
AUDIT_RECORD_NARRATION_RE = re.compile(
    rf"\b(?:{_AR_DET}{_AR_NOT_TOOL}(?:[\w-]+\s+)?(?:audit|review|auditor|reviewer|verifier|refuter)s?"
    r"|(?:independent|adaptability|planning|research|review|audit|verification|refuter)\s+pass(?:es)?)"
    r"(?:\s+(?:\([^)]*\)|also|then|later|first|further|immediately|independently|itself)){0,3}"
    rf"\s+{_AR_VERB}\b"
    r"|\b(?:defects?|findings?|gaps?|bugs?|issues?|problems?)\s+(?:were|was|had\s+been|have\s+been)"
    rf"\s+(?:\w+\s+)?{_AR_VERB}\b", re.I)

# Review tallies and report pointers in tracked text: a severity count list (two counts, each
# followed by a word from one severity set, _AR_SEV, in either order: N high, N medium; N critical,
# N major; N minor, N nits; N blockers, N warnings; N P1, N P2; N Sev1, N Sev2) and
# a pointer to a report committed to the repository. Both point at review output kept outside the
# repository. They join PATTERNS, so --tracked (invariant 21), --staged, --commit-messages and the
# commit-msg hook refuse them.
# Limit: other phrasings ("in the report", a report committed to the repository, a qualifier before
# "report" outside the listed review words, a tally in words, a count after its label ("high: 5",
# "high 5"), a count on a word outside _AR_SEV (3 errors, 5 warnings)) are not read, and a priority
# count written like a tally (3 high, 2 low tasks) is read; the selftest pins that, and review holds
# them.
_AR_SEV = r"(?:critical|high|medium|low|major|minor|blocker|warning|nit|P[0-4]|sev[0-4])"
AUDIT_RECORD_REPORT_PATTERNS = [
    ("committed_report", re.compile(
        r"\bcommitted\s+(?:(?:audit|review|readiness|production-readiness|findings?|remediation"
        r"|triage|verification|integrity|security)\s+){0,2}report\b", re.I)),
    ("severity_tally", re.compile(
        rf"\b\d+\s+{_AR_SEV}(?:-severity)?s?(?![\w-])"
        r"\s*(?:,|;|/|\+|\||and)\s*\|?\s*\d+\s+"
        rf"{_AR_SEV}(?:-severity)?s?(?![\w-])", re.I)),
]
PATTERNS.extend(AUDIT_RECORD_REPORT_PATTERNS)

# Finding-id tokens in tracked text. A comment or record that cites a review's finding id points at
# output kept outside the repository, so the id has no committed referent; a phase tag (P73)
# carries the history. The pattern reads a dimension-finding id (D6-F3), a phase-qualified id
# (P57 F3, P101-F3, P73 D6-F3) and a bare F-number of up to three digits closed by a colon, a
# parenthesis or a square bracket (F5:, (F9), [F3], F123:); an en dash between the parts is read
# through the folded reading (_text_views). It joins
# PATTERNS, so --tracked (invariant 21), --staged, --commit-messages and the commit-msg hook refuse
# it, and tools/secret-scan-allowlist.json exempts a pinned false positive.
# Limit: a letter-number id without an F (A3, G1) is not read, because ADR and scenario ids of
# that shape have committed referents. A lower-case id, an id joined by a slash, an underscore
# or a dot (p57 f3, P57/F3, P101_F3, D6.F3) and an
# F-number in running text (finding F3) or closed by a full stop (F3.) are not read either; the
# selftest pins these. A
# function-key name in parentheses or before a colon ((F12), F5:) reads as an id;
# tools/secret-scan-allowlist.json exempts one pinned match with a written reason.
AUDIT_RECORD_ID_PATTERNS = [
    ("finding_id", re.compile(
        r"\b(?:[A-Z]{1,3}\d{1,2}-F\d{1,3}|P\d{1,3}(?:\s+|-)(?:[A-Z]{1,3}\d{1,2}[-\s])?F\d{1,3})\b"
        r"|(?<![\w-])F\d{1,3}(?=[:)\]])")),
]
PATTERNS.extend(AUDIT_RECORD_ID_PATTERNS)


# Characters outside category Pd that render as a dash and that NFKC leaves alone: the minus sign,
# the modifier-letter minus, the hyphen bullet, the heavy minus sign, the Ogham space mark, the
# box-drawing horizontals and the horizontal line extension. fold_text reads each as '-'.
_DASH_LOOKALIKES = frozenset("−˗⁃➖ ─━⎯")


def fold_text(text):
    """`text` as the content patterns and the audit-record rule read it: NFKC (fullwidth letters,
    digits and signs, the small and fullwidth at signs and dollar signs read as ASCII), format
    characters (Unicode category Cf: a zero-width space, a bidi mark, a soft hyphen) dropped, every
    dash (category Pd, the non-breaking hyphen and en dash included) and every character in
    _DASH_LOOKALIKES read as '-', the ideographic full stop (NFKC folds its halfwidth form into
    it) read as '.', and every decimal digit (category Nd) read as its ASCII digit.
    An invisible default-ignorable code point outside category Cf (a variation selector, the
    combining grapheme joiner, a Hangul filler) is NOT dropped and splits a keyword; a character
    that only resembles a dash or a dot and is not listed (a middle dot, a box-drawing corner)
    and a letter from another script (a Cyrillic look-alike) are not folded; the selftest pins
    one case of each. ASCII text is returned unchanged."""
    import unicodedata
    if text.isascii():
        return text
    out = []
    for c in unicodedata.normalize("NFKC", text):
        cat = unicodedata.category(c)
        if cat == "Cf":
            continue
        if cat == "Pd" or c in _DASH_LOOKALIKES:
            out.append("-")
        elif c == "。":
            out.append(".")
        elif cat == "Nd" and ord(c) > 127:
            out.append(str(unicodedata.digit(c)))
        else:
            out.append(c)
    return "".join(out)


def audit_record_name(path):
    """Why `path` names an audit record, or None. Pure: reads nothing."""
    if len(path) > 1 and path[0] == path[-1] == '"':
        try:
            path = re.sub(r"\\([0-7]{3})|\\(.)",
                          lambda m: chr(int(m.group(1), 8)) if m.group(1) else
                          {"n": "\n", "t": "\t"}.get(m.group(2), m.group(2)),
                          path[1:-1]).encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    rel = fold_text(path)
    rel = rel.replace("\\", "/")
    if rel.startswith("./"):
        rel = rel[2:]
    if rel.lower() in {p.lower() for p in AUDIT_RECORD_PATHS}:
        return "listed in AUDIT_RECORD_PATHS"
    # A lowercase letter followed by a capital splits joined words (AuditReport reads as
    # audit-report).
    low = re.sub(r"(?<=[a-z])(?=[A-Z])", "-", rel).lower()
    base = low.rsplit("/", 1)[-1]
    ext = base.rsplit(".", 1)[1] if "." in base.lstrip(".") else ""
    # A text suffix, no suffix, or a date as the tail (audit.2026.10.01, review.2026-10-01).
    if ext and not re.fullmatch(r"[0-9_-]+", ext) and not base.endswith(AUDIT_RECORD_TEXT_SUFFIXES):
        return None
    # The keyword and the date are each read over the whole path, so a dated or keyword
    # directory counts (docs/audits/2026-10-01.md, docs/2026-10-01/notes.md).
    key = AUDIT_RECORD_KEYWORD_RE.search(low)
    date = AUDIT_RECORD_DATE_RE.search(low)
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


def _match_sha256(text):
    """The pin an allowlist entry stores for the one match it exempts (its full matched text)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _allowed(allowlist, path, pattern_id, text=None):
    """Does an entry exempt this finding? An entry pins the exact text it exempts as the sha256
    `match_sha256`, so it covers that one false positive and never a later, different match of
    the same pattern in the same file; an entry with no pin exempts nothing. With `text=None`
    (tools/install_hooks.py's author-email lookup passes no text) any pinned entry for the path
    and pattern counts, since there is nothing to compare."""
    for e in allowlist.get("entries", []):
        if e.get("path") != path or e.get("pattern_id") != pattern_id:
            continue
        pin = e.get("match_sha256")
        if pin and (text is None or pin == _match_sha256(text)):
            return True
    return False


ALLOWLIST_MIN_REASON = 25


def allowlist_problems(allowlist, tracked, read_bytes=None):
    """Allowlist entries that do no work, as messages. An entry must name a known pattern id and
    carry a written reason of ALLOWLIST_MIN_REASON+ characters. An entry for a file must name a
    tracked path and still exempt something: scanning the file with that entry alone must report
    fewer matches of its pattern than scanning it with no allowlist. Entries for commit messages
    ('commit-message', 'commit:<sha12>') are checked for id and reason only, because the text they
    exempt is not in the tree. --tracked runs this, so CI and drift invariant 21 fail on a stale
    entry."""
    read_bytes = read_bytes or (lambda rel: (ROOT / rel).read_bytes())
    known = {pid for pid, _ in PATTERNS} | {"pipeline_amount", "author_email", "review_narration"}
    out, keys = [], set()
    for e in allowlist.get("entries", []):
        path, pid = str(e.get("path", "")), str(e.get("pattern_id", ""))
        where = f"allowlist entry ({path}, {pid})"
        key = (path, pid, e.get("match_sha256"))
        if key in keys:
            out.append(f"{where}: listed more than once")
        keys.add(key)
        if pid not in known:
            out.append(f"{where}: unknown pattern_id")
            continue
        if len(str(e.get("reason", "")).strip()) < ALLOWLIST_MIN_REASON:
            out.append(f"{where}: needs a written reason of {ALLOWLIST_MIN_REASON}+ characters")
        if path == "commit-message" or path.startswith("commit:"):
            continue
        if path not in tracked:
            out.append(f"{where}: the path is not tracked; drop the entry")
            continue
        try:
            text = read_bytes(path).decode("utf-8", errors="replace")
        except OSError:
            out.append(f"{where}: the file cannot be read")
            continue
        bare = sum(f["pattern_id"] == pid for f in scan_text(text, path, None))
        kept = sum(f["pattern_id"] == pid for f in scan_text(text, path, {"entries": [e]}))
        if kept >= bare:
            out.append(f"{where}: exempts nothing (no {pid} match in the file is removed by it); "
                       f"drop it")
    return out


def _text_views(text):
    """The readings of `text` the patterns run on: the text as written, the text folded
    (fold_text), and the folded text percent-decoded (urllib.parse.unquote, then folded again)
    when it carries a %. Decoding runs once, so a doubly encoded character (%2540) is read as its
    single encoding, and an HTML entity (&#64;) is not decoded; the selftest pins that. A reading
    equal to an earlier one is dropped. The written text stays a
    reading because folding can remove a match: a phone number after an em dash is read with the
    em dash, and folded it follows a hyphen, which the phone pattern refuses."""
    import urllib.parse
    views = [text]
    folded = fold_text(text)
    if folded != text:
        views.append(folded)
    if "%" in folded:
        decoded = fold_text(urllib.parse.unquote(folded))
        if decoded not in views:
            views.append(decoded)
    return views


def scan_text(text, path, allowlist=None):
    """Findings in one text blob. path is used for allowlist lookups and pipeline scoping. The
    patterns run on every reading _text_views gives; a match (pattern id and matched text) found
    in more than one reading is reported as often as the one reading that holds it most often.
    One occurrence whose raw and folded readings match as DIFFERENT text (a digit run written
    with non-ASCII digits, say) is keyed by each text, so it can be reported once per reading."""
    allowlist = allowlist or {"entries": []}
    findings, counted = [], {}
    for view in _text_views(text):
        here = {}
        for f in _scan_view(view, path, allowlist):
            key = (f["pattern_id"], f["sha256"])
            here[key] = here.get(key, 0) + 1
            if here[key] > counted.get(key, 0):
                findings.append(f)
        for key, n in here.items():
            counted[key] = max(counted.get(key, 0), n)
    return findings


def _scan_view(text, path, allowlist):
    """Findings in one reading of a text blob (scan_text)."""
    findings = []
    for pid, rx in PATTERNS:
        for m in rx.finditer(text):
            if pid == "credential_value" and PLACEHOLDER_RE.search(m.group(m.lastindex)):
                continue
            if (pid == "email_address" and EMAIL_ALLOW_RE.search(m.group(0))
                    and not EMAIL_DOMAIN_CONT_RE.match(text, m.end())):
                continue
            if _allowed(allowlist, path, pid, m.group(0)):
                continue
            snippet = m.group(0)
            if len(snippet) > 60:
                snippet = snippet[:57] + "..."
            findings.append({"path": path, "pattern_id": pid, "match": snippet,
                             "sha256": _match_sha256(m.group(0))})
    if path.startswith("pipeline/"):
        for m in AMOUNT_RE.finditer(text):
            if _allowed(allowlist, path, "pipeline_amount", m.group(0)):
                continue
            findings.append({"path": path, "pattern_id": "pipeline_amount", "match": m.group(0),
                             "sha256": _match_sha256(m.group(0))})
    if path.startswith(AUDIT_RECORD_NARRATION_SCOPE):
        for m in AUDIT_RECORD_NARRATION_RE.finditer(text):
            if _allowed(allowlist, path, "review_narration", m.group(0)):
                continue
            findings.append({"path": path, "pattern_id": "review_narration", "match": m.group(0),
                             "sha256": _match_sha256(m.group(0))})
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
    policy SHA in the allowlist file: the boundary commit and its ancestors (`git rev-list
    <boundary>`) are skipped, because history is not rewritten; some predate the message rules
    and some carry text a later rule refuses. A boundary git cannot resolve skips nothing, so
    every commit in the range is scanned."""
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
        if email and not EMAIL_ALLOW_RE.search(email) and not _allowed(allowlist, where, "author_email", email):
            findings.append({"path": where, "pattern_id": "author_email", "match": email,
                             "sha256": _match_sha256(email)})
    return findings


def _check(label, cond, failures, ran):
    ran[0] += 1
    print(f"  [{'ok' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)


def selftest():
    f = []
    ran = [0]
    al = {"entries": [{"path": "x.md", "pattern_id": "session_link", "reason": "test",
                       "match_sha256": _match_sha256("claude." + "ai/code/session_" + "abc123XYZ")}]}
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
    # Every prefix (none, +1 or 1, each flush or followed by a space, dot or dash), every area-code
    # form (parenthesised with or without a following separator, or bare with one) and every
    # exchange separator, the bare dash and space forms included. Built from digit pieces at run
    # time so no phone-shaped string sits in this file.
    _area, _exch, _line = "4" + "15", "55" + "5", "01" + "99"
    _prefixes = [""] + [p + s for p in ("+1", "1") for s in ("", " ", ".", "-")]
    _areas = (["(" + _area + ")" + s for s in ("", " ", ".", "-")]
              + [_area + s for s in (" ", ".", "-")])
    _combos = [p + a + _exch + s + _line
               for p in _prefixes for a in _areas for s in (" ", ".", "-")]
    _missed = [c for c in _combos
               if not any(x["pattern_id"] == "phone_number"
                          for x in scan_text("call " + c + " today", "docs/a.md"))]
    if _missed:
        print(f"  [note] {len(_missed)} of {len(_combos)} phone forms missed, e.g. {_missed[:3]}")
    _check("phone number detected in every prefix, area-code and separator combination, bare dash "
           "and space forms included", not _missed, f, ran)
    # The same forms with every leading digit the numbering plan allows (2 to 9) in the area and
    # exchange codes, every digit leading the line number, and the number set inside quotes, after
    # a tel: or key= prefix, in a table cell, in a tag or in brackets. Built from digit pieces.
    _nums = ([_d + "15-" + _exch + "-" + _line for _d in "23456789"]
             + [_area + "-" + _d + "55-" + _line for _d in "23456789"]
             + [_area + "-" + _exch + "-" + _d * 4 for _d in "0123456789"])
    _wraps = (("", ""), ("tel:", ""), ('"', '"'), ("'", "'"), ("| ", " |"), ("<td>", "</td>"),
              ("phone=", "&x=1"), ("[", "]"), ("\n", "\n"))
    _shown = [_area + "-" + _exch + "-" + _line, "(" + _area + ") " + _exch + "-" + _line,
              "+1 " + _area + " " + _exch + " " + _line]
    _missed = [s for s in _nums + [a + s + b for a, b in _wraps for s in _shown]
               if not any(x["pattern_id"] == "phone_number" for x in scan_text(s, "docs/a.md"))]
    if _missed:
        print(f"  [note] phone forms missed: {_missed[:3]}")
    _check("phone number detected for every leading area and exchange digit 2 to 9, every leading "
           "line digit, and inside quotes, tel: and key= prefixes, table cells, tags and brackets",
           not _missed, f, ran)

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
    _check("an address whose local part only ends in noreply is a finding",
           all(any(x["pattern_id"] == "email_address" for x in scan_text(e, "a.md", al))
               for e in ("jane." + "noreply@anthropic.com", "jane+" + "noreply@anthropic.com")),
           f, ran)
    _check("an address at test.com, a registered domain rather than a reserved one, is a finding",
           any(x["pattern_id"] == "email_address"
               for x in scan_text("someone" + "@test.com", "a.md", al)), f, ran)
    _check("an address at a domain that only ends in an allowed name, extends one, runs on past "
           "one or misspells one is a finding",
           all(any(x["pattern_id"] == "email_address" for x in scan_text(e, "a.md", al)) for e in (
               "jane@my" + "example.com", "jane@example.com" + ".evil.io",
               "jane@my" + "example.org", "jane@corp.example" + ".evil.io",
               "jane@my" + "users.noreply.github.com", "noreply@anthropic.com" + ".evil.io",
               "noreply@my" + "anthropic.com", "noreply@anthr" + "0pic.com",
               "noreply@anthropic.com" + "_x.evil.io", "jane@example.com" + "9x",
               "jane@example.org" + "-x")), f, ran)
    _check("an author email is allowed only when the whole value is one allowed address",
           not any(EMAIL_ALLOW_RE.search(e) for e in (
               "jane@gm" + "ail.com@example.com", "jane " + "noreply@anthropic.com",
               "noreply@anthropic.com" + ".evil.io"))
           and all(EMAIL_ALLOW_RE.search(e) for e in (
               "noreply" + "@anthropic.com", "12345+user" + "@users.noreply.github.com")), f, ran)
    _check("an allowed address followed by a bracket, a quote or a sentence-ending dot is NOT a "
           "finding",
           not any(x["pattern_id"] == "email_address" for s in (
               "Co-Authored-By: Claude <noreply" + "@anthropic.com>", "(jane" + "@example.com).",
               '"owner": "jane' + '@corp.example",', "mail noreply" + "@anthropic.com.\n")
               for x in scan_text(s, "a.md", al)), f, ran)
    # Content findings do not depend on the path that carries the text (only pipeline_amount is
    # path-scoped). The path set is every tracked path when git answers, plus a floor that holds
    # without git, so a suffix or directory carve-out anywhere in the tree turns this check red.
    _samples = (email, gh, aws, slack, sk_proj, pem, bearer, sess, cred, phones[0])
    _want = [sorted(x["pattern_id"] for x in scan_text(s, "a.md")) for s in _samples]
    _paths = {"a.md", "a.json", "a.py", "a.txt", "a", "pipeline/deals/a.json", "docs/a.yaml"}
    try:
        _paths.update(p.strip() for p in (_git(["ls-files"], check=False) or "").splitlines()
                      if p.strip())
    except OSError:
        pass
    _moved = sorted(p for p in _paths
                    if [sorted(x["pattern_id"] for x in scan_text(s, p))
                        for s in _samples] != _want)
    if _moved:
        print(f"  [note] findings differ at {len(_moved)} path(s), e.g. {_moved[:3]}")
    _check("content findings are the same at every tracked path and at .md, .json, .py, .txt, "
           "extensionless and pipeline/ paths", all(_want) and not _moved, f, ran)
    _check("addresses at common personal mail providers are findings",
           all(any(x["pattern_id"] == "email_address" for x in scan_text("jane@" + d, "a.md", al))
               for d in ("gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com",
                         "proton.me", "aol.com")), f, ran)
    # The same samples inside a JSON document, a YAML value and a table row, and before or after
    # more than 64 KB of other text, so a carve-out keyed on the shape of the file or on the
    # position of the match also turns this red.
    _fill = "lorem ipsum " * 6000
    _docs = (('{\n  "owner": [\n    ', '\n  ]\n}\n'), ("owner: ", "\n"), ("| ", " |\n"),
             (_fill + "\n", "\n"), ("\n", "\n" + _fill))
    _shifted = [w[0][:12] for w in _docs
                if [sorted(x["pattern_id"] for x in scan_text(w[0] + s + w[1], "a.md"))
                    for s in _samples] != _want]
    if _shifted:
        print(f"  [note] findings differ inside: {_shifted}")
    _check("content findings are the same inside a JSON document, a YAML value and a table row, "
           "and before or after more than 64 KB of other text", not _shifted, f, ran)
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
    _check("audit-record rule: the date forms the rule states are flagged",
           all(audit_record_name(p) for p in (
               "docs/audit_2026_01_02.md", "docs/audit.2026.01.02.md", "docs/audit-2026-01.md",
               "docs/audit-02-01-2026.md", "docs/audit-01-31-2026.md", "docs/audit-2026-jan-02.md",
               "docs/audit-jan-2026.md", "docs/audit-2-january-2026.md",
               "docs/reviews/2026/01/02.md", "docs/audit.2026.01.02")), f, ran)
    _check("audit-record rule: a dated directory over an undated file, and an unsuffixed name",
           all(audit_record_name(p) for p in (
               "docs/2026-01-02/notes.md", "docs/audit-2026-01-02/report.md",
               "docs/AUDIT-2026-01-02")), f, ran)
    _check("audit-record rule: review words beyond the first list (report, verdict, pass record)",
           all(audit_record_name(p) for p in (
               "docs/pass-record-2026-01-02.md", "docs/verdicts-2026-01-02.md",
               "security-report-2026-01-02.md", "postmortem-2026-01-02.md",
               "post-mortem-2026-01-02.md", "retrospective-2026-01-02.md",
               "followups-2026-01-02.md", "inspection-2026-01-02.md",
               "walkthrough-2026-01-02.md", "auditing-2026-01-02.md", "p97-pass-2026-01-02.md")),
           f, ran)
    _check("audit-record rule: a listed path in another letter case, and fullwidth digits",
           all(audit_record_name(p) for p in tuple(x.lower() for x in AUDIT_RECORD_PATHS)
               + ("docs/audit-２０２６-01-02.md",)), f, ran)
    _check("audit-record rule: the stated limits hold (unlisted word, bare year, look-alike "
           "letters, off-list suffix, undated name)",
           not any(audit_record_name(p) for p in (
               "docs/lessons-2026-01-02.md", "docs/audit-2026.md", "docs/аudit-2026-01-02.md",
               "docs/review-2026-01-02.png", "docs/findings.md", "docs/reviews/p97.md",
               "docs/securityaudit-2026-01-02.md", "docs/audit-26-01-02.md", "docs/audit-2026-W02.md",
               "docs/audit-2026-Q1.md", "docs/audit-2026-1-2.md", "docs/audit-jan-02.md")), f, ran)
    _check("audit-record rule: git-quoted, joined-word, format-character, timestamped and "
           "date-tailed names are flagged",
           all(audit_record_name(p) for p in (
               '"docs/audit-\\357\\274\\222\\357\\274\\220\\357\\274\\222\\357\\274\\226-01-02.md"',
               "docs/AuditReport_2026-01-02.md", "docs/SecurityReview-2026-01-02.md",
               "docs/au​dit-2026-01-02.md", "docs/audit-20260102120000.md",
               "docs/review.2026-01-02", "docs/.review-2026-01-02")), f, ran)
    # Finding-id tokens (AUDIT_RECORD_ID_PATTERNS). Fixtures are concatenated.
    def _fid(s):
        return any(x["pattern_id"] == "finding_id" for x in scan_text(s, "tools/a.py", None))
    _check("finding-id tokens are refused (D-F, phase-qualified and bare F forms)",
           all(_fid(s) for s in ("# P73 D6" + "-F3: guard", "creds (P57" + " F3).",
                                 "flow (P40" + " F1): x", "# 1b) F" + "5: guard", "seam (F" + "9).",
                                 "D12" + "-F104 here", "# P73 D6" + " F3 guard")), f, ran)
    _check("a function key in parentheses reads as a finding id (the stated limit)",
           _fid("DevTools (F" + "12)"), f, ran)
    _check("phase tags, letter-number ids and key names are not finding ids (the stated limit)",
           not any(_fid(s) for s in ("(P57).", "# P73: guard", "ADR 0041 (A3)", "press F5 to reload",
                                     "G1/G2 scenarios", "re-synced (E12).", "F-35 jet", "UTF-8)",
                                     "(p57" + " f3)", "P57/" + "F3", "per finding" + " F3")),
           f, ran)
    # Report pointers and severity tallies (AUDIT_RECORD_REPORT_PATTERNS).
    def _rep(s):
        return any(x["pattern_id"] in ("committed_report", "severity_tally")
                   for x in scan_text(s, "ledger/x.json", None))
    _check("report pointers and severity tallies are refused",
           all(_rep(s) for s in ("recorded as a committed" + " report",
                                 "in a committed audit" + " report", "(5 high" + ", 22 medium, 22 low)",
                                 "3 critical" + " / 4 low", "2 HIGH" + " and 1 MEDIUM",
                                 "5 high-severity" + ", 22 medium-severity", "| 5 high" + " | 22 medium |")),
           f, ran)
    _check("other report and tally phrasings are not read (the stated limit)",
           not any(_rep(s) for s in ("the parity report names the line",
                                     "committed to the repo; the report",
                                     "12 high-resolution images, 3 medium", "high: 5, medium: 22",
                                     "forty-nine findings", "we committed to" + " report monthly",
                                     "the committed parity" + " report",
                                     "critical 0" + ", high 5, medium 22")), f, ran)
    # Discovery narration in the decision records (AUDIT_RECORD_NARRATION_RE).
    def _nar(s, p="docs/adr/0001-x.md"):
        return any(x["pattern_id"] == "review_narration" for x in scan_text(s, p, None))
    _check("discovery narration in ADRs and the ledger is refused",
           all(_nar(s) for s in ("A review" + " found the registry", "the adaptability pass" + " found five",
                                 "Two defects were" + " found", "the planning" + " pass flagged it",
                                 "The auditors" + " caught it", "Several defects had" + " been found"))
           and _nar("A review" + " found x", "ledger/ledger.json"), f, ran)
    _check("narration outside the records, and other phrasings, are not read (the stated limit)",
           not _nar("A review" + " found x", "docs/AUDIT-PROTOCOL.md")
           and not any(_nar(s) for s in ("Turning it on showed that CI", "the file was not found",
                                         "the review of every rule in the file found",
                                         "the camera lens caught glare", "a render pass caught it",
                                         "the binary was found on PATH", "the review queue flagged posts",
                                         "the hash audit caught drift")), f, ran)
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
    # A fullwidth-dated name as git prints it (C-quoted, octal UTF-8 bytes).
    _gq = '"docs/audit-' + "\\357\\274\\222\\357\\274\\220\\357\\274\\222\\357\\274\\226" + '-01-02.md"'
    _g = globals()
    _real_git = _g["_git"]

    def _fake_git(args, check=True):
        if args[:2] == ["diff", "--cached"] and "--name-only" in args:
            if "--diff-filter=d" in args:
                return ("docs/review-2026-01-02.md\ndocs/2026-01-02/notes.md\ndocs/AUDIT-2026-01-02\n"
                        "docs/AuditReport_2026-01-02.md\n" + _gq + "\n")
            return "docs/review-2026-01-02.md\ndocs/remediation-2026-01-02.md\n"
        return ""
    _g["_git"] = _fake_git
    try:
        _staged = {x["path"] for x in scan_staged({"entries": []})
                   if x["pattern_id"] == "audit_record_file"}
    finally:
        _g["_git"] = _real_git
    _check("staged gate refuses an added audit record (a dated directory, an unsuffixed, a joined-word "
           "and a git-quoted name included) and passes a staged deletion",
           _staged == {"docs/review-2026-01-02.md", "docs/2026-01-02/notes.md", "docs/AUDIT-2026-01-02",
                       "docs/AuditReport_2026-01-02.md", _gq}, f, ran)
    # Drift invariant 20 consumes the rule: run its check on a stubbed tracked list.
    import sync_check as _sc
    _real_ls, _saved = _sc._git_ls_files, list(_sc.PROBLEMS)
    _sc._git_ls_files = lambda: ["docs/review-2026-01-02.md", "docs/AUDIT-PROTOCOL.md",
                                 "docs/2026-01-02/notes.md", "docs/AUDIT-2026-01-02",
                                 "docs/AuditReport_2026-01-02.md", _gq]
    try:
        del _sc.PROBLEMS[:]
        _sc.check_pipeline_allowlist()
        _inv20 = list(_sc.PROBLEMS)
    finally:
        _sc._git_ls_files = _real_ls
        _sc.PROBLEMS[:] = _saved
    _check("drift invariant 20 refuses a tracked audit record through this rule, including a "
           "dated directory, an unsuffixed, a joined-word and a git-quoted name",
           len(_inv20) == 5 and "docs/review-2026-01-02.md" in _inv20[0], f, ran)

    # Allowlist entries must still do work (allowlist_problems, run by --tracked).
    import hashlib as _hl
    pin = _hl.sha256(sess[len("https://"):].encode("utf-8")).hexdigest()
    files = {"live.md": ("see " + sess).encode("utf-8"), "clean.md": b"nothing here"}
    probs = allowlist_problems({"entries": [
        {"path": "live.md", "pattern_id": "session_link", "reason": "r" * 30, "match_sha256": pin},
        {"path": "clean.md", "pattern_id": "session_link", "reason": "r" * 30, "match_sha256": pin},
        {"path": "gone.md", "pattern_id": "session_link", "reason": "r" * 30, "match_sha256": pin},
        {"path": "live.md", "pattern_id": "no_such_id", "reason": "r" * 30},
        {"path": "commit-message", "pattern_id": "author_email", "reason": "short"},
    ]}, {"live.md", "clean.md"}, files.__getitem__)
    _check("allowlist: an entry that still exempts a match is kept",
           not any("(live.md, session_link)" in p for p in probs), f, ran)
    _check("allowlist: an entry whose file has no such match is reported",
           any("(clean.md, session_link): exempts nothing" in p for p in probs), f, ran)
    _check("allowlist: an entry for an untracked path is reported",
           any("(gone.md, session_link): the path is not tracked" in p for p in probs), f, ran)
    _check("allowlist: an unknown pattern id is reported",
           any("(live.md, no_such_id): unknown pattern_id" in p for p in probs), f, ran)
    _check("allowlist: a commit-message entry is held to a written reason",
           any("(commit-message, author_email): needs a written reason" in p for p in probs), f, ran)
    _check("allowlist: nothing else is reported", len(probs) == 4, f, ran)

    # Each entry pins the exact text it exempts (match_sha256).
    later = "https://claude." + "ai/code/session_" + "laterREAL999"
    _check("a pinned entry does not exempt a later, different match in the same file",
           [x["pattern_id"] for x in scan_text(sess + " " + later, "x.md", al)] == ["session_link"],
           f, ran)
    _check("an entry without match_sha256 exempts nothing",
           any(x["pattern_id"] == "session_link" for x in scan_text(
               sess, "x.md", {"entries": [{"path": "x.md", "pattern_id": "session_link",
                                           "reason": "test"}]})), f, ran)
    _check("a pinned pipeline amount exempts only that amount",
           [x["match"] for x in scan_text("fee $2,500.00 then $9,999.00", "pipeline/x.json", {
               "entries": [{"path": "pipeline/x.json", "pattern_id": "pipeline_amount",
                            "reason": "test", "match_sha256": _match_sha256("$2,500.00")}]})]
           == ["$9,999.00"], f, ran)

    # Folding (fold_text, _text_views). Fixtures are built from code points at run time.
    _ph = _area + "{d}" + _exch + "{d}" + _line
    _check("a phone number joined by an en dash, a non-breaking hyphen or a minus sign is detected",
           all(any(x["pattern_id"] == "phone_number" for x in scan_text(_ph.format(d=chr(c)), "docs/a.md"))
               for c in (0x2013, 0x2011, 0x2212)), f, ran)
    _check("a phone number in fullwidth or Arabic-Indic digits is detected",
           all(any(x["pattern_id"] == "phone_number" for x in scan_text(
               "".join(chr(z + int(ch)) if ch.isdigit() else ch for ch in _ph.format(d="-")),
               "docs/a.md")) for z in (0xFF10, 0x0660)), f, ran)
    _check("an address with a zero-width space after the at sign, a fullwidth or small at sign, or "
           "a percent-encoded at sign is detected",
           all(any(x["pattern_id"] == "email_address" for x in scan_text("jane" + a + "gmail.com", "a.md"))
               for a in ("@" + chr(0x200B), chr(0xFF20), chr(0xFE6B), "%" + "40")), f, ran)
    _check("the written text stays a reading: a phone number after an em dash is detected",
           any(x["pattern_id"] == "phone_number" for x in scan_text(
               "call" + chr(0x2014) + _area + "-" + _exch + "-" + _line, "docs/a.md")), f, ran)
    _check("a match found in the written and the folded reading is reported once",
           [x["pattern_id"] for x in scan_text(email + " " + chr(0x2013), "a.md")]
           == ["email_address"], f, ran)
    _check("a fullwidth dollar sign in a pipeline/ file and an en-dash finding id are detected",
           any(x["pattern_id"] == "pipeline_amount"
               for x in scan_text(chr(0xFF04) + "2,500", "pipeline/deals/x.json"))
           and _fid("D6" + chr(0x2013) + "F3 here"), f, ran)
    _check("audit-record rule: a date joined by a hyphen, non-breaking hyphen, en dash or minus "
           "sign is flagged",
           all(audit_record_name("docs/audit-2026" + chr(c) + "01" + chr(c) + "02.md")
               for c in (0x2010, 0x2011, 0x2013, 0x2212)), f, ran)
    _check("a phone number joined by a dash look-alike outside category Pd (a hyphen bullet, a "
           "modifier-letter minus) is detected, and a percent-encoded fullwidth at sign is folded "
           "after decoding",
           all(any(x["pattern_id"] == "phone_number" for x in scan_text(_ph.format(d=chr(c)), "docs/a.md"))
               for c in (0x2043, 0x02D7))
           and any(x["pattern_id"] == "email_address"
                   for x in scan_text("jane" + "%EF%BC" + "%A0" + "gmail.com", "a.md")), f, ran)
    _check("a doubly percent-encoded or HTML-entity at sign is not decoded (the stated limit)",
           not any(x["pattern_id"] == "email_address" for s in (
               "jane" + "%25" + "40gmail.com", "jane" + "&#" + "64;gmail.com")
               for x in scan_text(s, "a.md")), f, ran)
    _sl = ("https://CLAUDE." + "AI/CODE/session_" + "abc123XYZ", "https://Claude." + "ai/code/session_" + "abc123XYZ",
           "https://claude." + "ai%2Fcode%2F" + "session_" + "abc123XYZ")
    _check("a session link with the host in another letter case or with percent-encoded slashes "
           "is detected",
           all(any(x["pattern_id"] == "session_link" for x in scan_text(s, "a.md")) for s in _sl),
           f, ran)
    _check("a session link with JSON-escaped slashes is detected",
           any(x["pattern_id"] == "session_link" for x in scan_text(
               "https:\\/\\/claude." + "ai\\/code\\/session_" + "abc123XYZ", "a.json")), f, ran)
    _check("a session link with HTML-entity slashes is not read (the stated limit)",
           not any(x["pattern_id"] == "session_link" for x in scan_text(
               "https://claude." + "ai&#47;code&#47;session_" + "abc123XYZ", "a.md")), f, ran)
    _check("a session link whose host dot is the ideographic full stop, or its halfwidth form, "
           "is detected",
           all(any(x["pattern_id"] == "session_link" for x in scan_text(
               "https://claude" + chr(c) + "ai/code/session_" + "abc123XYZ", "a.md"))
               for c in (0x3002, 0xFF61)), f, ran)
    _check("an invisible code point outside category Cf splits a keyword, and a middle dot is "
           "not read as a dash (the stated limits)",
           not any(x["pattern_id"] == "session_link" for x in scan_text(
               "https://claude." + "ai/code/ses" + chr(0x034F) + "sion_" + "abc123XYZ", "a.md"))
           and not any(x["pattern_id"] == "phone_number"
                       for x in scan_text(_ph.format(d=chr(0xB7)), "docs/a.md")), f, ran)
    _b64 = "c29tZW9uZT" + "podW50ZXIyaHVudGVyMg=="
    _check("an Authorization bearer value under a quoted JSON key is detected",
           any(x["pattern_id"] == "bearer_header"
               for x in scan_text('{"Author' + 'ization": "Bearer ' + "t" * 24 + '"}', "a.json")),
           f, ran)
    _check("Authorization with the Basic or Token scheme, and an X-Api-Key header, are detected",
           all(any(x["pattern_id"] == "authorization_header" for x in scan_text(s, "a.md")) for s in (
               "Authorization: " + "Basic " + _b64, "Authorization: " + "Token " + "t" * 32,
               "X-Api-" + "Key: " + "k" * 32)), f, ran)
    _check("a placeholder or variable Authorization value is not a finding",
           not any(x["pattern_id"] in ("bearer_header", "authorization_header") for s in (
               "Authorization: Basic <base64 of user:pass>", "Authorization: token ${GITHUB_TOKEN}",
               "Authorization: " + "Bearer " + "t" * 8) for x in scan_text(s, "a.md")), f, ran)
    _check("a bearer credential with / or + in it is detected; prose after Authorization: is not",
           any(x["pattern_id"] == "bearer_header" for x in scan_text(
               "Authorization: " + "Bearer " + "ab/cd+ef" + "g" * 20, "a.md"))
           and not any(x["pattern_id"] in ("bearer_header", "authorization_header") for s in (
               "Authorization: uses OAuth2/OpenID-Connect", "authorization: see docs/security/overview.md")
               for x in scan_text(s, "a.md")), f, ran)
    _check("a Bearer header is one finding; a value with no scheme word or another scheme word, and "
           "an X-Auth-Token header, are not read by the header patterns (the stated limit)",
           [x["pattern_id"] for x in scan_text(bearer, "a.md")] == ["bearer_header"]
           and not any(x["pattern_id"] in ("bearer_header", "authorization_header") for s in (
               "Authorization: " + "k" * 32, "Authorization: " + "Custom " + "t" * 32,
               "curl -H 'X-Auth-" + "Token: " + "k" * 32 + "'") for x in scan_text(s, "a.md")), f, ran)
    _sv = "s" * 16
    _check("credential values under camelCase, upper-case and other credential keys, in a "
           "single-quoted dict, a YAML line and a .env line are detected",
           all(any(x["pattern_id"] == "credential_value" for x in scan_text(s, "a.txt")) for s in (
               '{"api' + 'Key": "' + _sv + '"}', '{"API' + '_KEY": "' + _sv + '"}',
               '{"sec' + 'ret": "' + _sv + '"}', '{"private' + '_key": "' + _sv + '"}',
               "{'pass" + "word': '" + _sv + "'}", "api" + "_key: " + _sv + "\n",
               "API" + "_KEY=" + _sv + "\n", "export GITHUB" + "_TOKEN=" + _sv + "\n")), f, ran)
    _check("an expression, a type, a placeholder and a CI secret reference are not credential values",
           not any(x["pattern_id"] == "credential_value" for s in (
               'API_KEY = os.environ["API_KEY"]\n', "    password: Optional[str]\n",
               "api_key: YOUR_API_KEY_HERE\n", "token: ${{ secrets.GITHUB_TOKEN }}\n",
               "password = get_password()\n") for x in scan_text(s, "a.txt")), f, ran)
    _check("credential values under a prefixed key and under passwd and auth_token keys are "
           "detected; a YAML or .env file path is not a value",
           all(any(x["pattern_id"] == "credential_value" for x in scan_text(s, "a.txt")) for s in (
               '{"stripe_api' + '_key": "' + _sv + '"}', '{"db_pass' + 'word": "' + _sv + '"}',
               '{"auth' + '_token": "' + _sv + '"}', "pass" + "wd: " + _sv + "\n",
               "AUTH" + "_TOKEN=" + _sv + "\n"))
           and not any(x["pattern_id"] == "credential_value" for s in (
               "  secret: /run/secrets/db" + "_password\n", "DB_PASS" + "WORD=/run/secrets/db" + "_password\n")
               for x in scan_text(s, "a.txt")), f, ran)
    _check("PGP, SSH2 and PuTTY private-key headers are detected",
           all(any(x["pattern_id"] == "private_key_block" for x in scan_text(s, "a.txt")) for s in (
               "-----BEGIN PGP " + "PRIVATE KEY BLOCK-----", "---- BEGIN SSH2 ENCRYPTED " + "PRIVATE KEY ----",
               "PuTTY-User-" + "Key-File-3: ssh-ed25519\n")), f, ran)
    _check("an indented PuTTY key-file header is detected",
           any(x["pattern_id"] == "private_key_block"
               for x in scan_text("    PuTTY-User-" + "Key-File-3: ssh-ed25519\n", "a.md")), f, ran)
    _kf = {"aws_access_key": "AS" + "IA" + "ABCDEFGHIJKLMNOP", "google_api_key": "AI" + "za" + "A" * 35,
           "gitlab_token": "gl" + "pat-" + "a" * 20, "slack_token": "xa" + "pp-1-" + "A1B2C3D4E5-123-abc",
           "slack_webhook": "https://hooks." + "slack.com/services/" + "T0000000/B0000000/" + "a" * 24,
           "stripe_key": "rk" + "_live_" + "a" * 24, "npm_token": "np" + "m_" + "a" * 36,
           "huggingface_token": "h" + "f_" + "a" * 34,
           "jwt": "ey" + "J" + "a" * 12 + ".ey" + "J" + "b" * 12 + "." + "c" * 12,
           "sendgrid_key": "S" + "G." + "a" * 22 + "." + "b" * 43, "pypi_token": "py" + "pi-AgE" + "a" * 60}
    _missed = [k for k, s in _kf.items() if not any(x["pattern_id"] == k for x in scan_text(s, "a.md"))]
    if _missed:
        print(f"  [note] key formats missed: {_missed}")
    _check("AWS temporary, Google, GitLab, Slack app and webhook, Stripe restricted, npm, Hugging "
           "Face, JWT, SendGrid and PyPI key formats are detected", not _missed, f, ran)
    _check("a Slack refresh token is detected",
           any(x["pattern_id"] == "slack_token" for x in scan_text("xo" + "xe-1-" + "abcdefghij12", "a.md")),
           f, ran)
    _check("a secret with no fixed prefix (a 40-character AWS secret access key body) and a vendor "
           "format not in PATTERNS (a Google OAuth client secret) are not read (the stated limit)",
           not scan_text("a" * 20 + "/" + "B" * 19, "a.md")
           and not scan_text("GOC" + "SPX-" + "a" * 28, "a.md"), f, ran)
    _check("a phone number after an underscore key prefix is detected; after a letter it is not",
           any(x["pattern_id"] == "phone_number"
               for x in scan_text("tel_" + _area + "-" + _exch + "-" + _line, "docs/a.md"))
           and not any(x["pattern_id"] == "phone_number"
                       for x in scan_text("id" + _area + "-" + _exch + "-" + _line, "docs/a.md")), f, ran)
    _check("a three-digit bare F-number, a dash-joined phase id and a bracketed id are refused",
           all(_fid(s) for s in ("item F" + "123: guard", "P101" + "-F3 here", "see [F" + "3]")), f, ran)
    _check("an F-number closed by a full stop is not read (the stated limit)",
           not _fid("see F" + "3."), f, ran)
    _check("an id joined by an underscore or a dot, and a bare F-number of four digits, are not read "
           "(the stated limit)",
           not any(_fid(s) for s in ("P101" + "_F3 here", "D6" + ".F3 here", "item F" + "1234: guard")),
           f, ran)
    _check("tallies on the major/minor, blocker/warning and P1/P2 scales are refused",
           all(_rep(s) for s in ("3 major" + ", 2 minor", "2 blockers" + ", 5 warnings", "4 P1" + ", 6 P2")),
           f, ran)
    _check("tallies pairing any two severity words, in either order, are refused",
           all(_rep(s) for s in ("3 critical" + ", 2 major", "2 medium" + ", 1 low", "4 minor" + ", 2 nits",
                                 "1 Sev1" + ", 2 Sev2", "1 P3" + ", 2 P0")), f, ran)
    _check("a count list on a word outside the severity set is not read (the stated limit)",
           not _rep("3 errors" + ", 5 warnings"), f, ran)
    _check("narration by a reviewer or verifier, and identified or detected, is refused",
           all(_nar(s) for s in ("A reviewer" + " found the gap", "the verifier" + " caught it",
                                 "The review" + " identified the gap", "Two gaps were" + " detected")),
           f, ran)
    _check("an unlisted adverb between the actor and the verb is not read (the stated limit)",
           not _nar("the review quickly" + " found it"), f, ran)
    _check("narration with uncovered, and passive flagged, surfaced and identified, is refused",
           all(_nar(s) for s in ("The review" + " uncovered the gap", "Two gaps were" + " flagged",
                                 "a gap was" + " surfaced", "the bug was" + " identified")), f, ran)
    _check("a verb outside _AR_VERB is not read (the stated limit)",
           not any(_nar(s) for s in ("the verifier" + " noticed it", "The reviewer" + " confirmed the gap")),
           f, ran)
    _check("pipeline/ figures with a k or M suffix, a currency code, a trailing dollars, a pound "
           "sign or two digits are detected",
           all(any(x["pattern_id"] == "pipeline_amount" for x in scan_text("fee " + s, "pipeline/deals/x.json"))
               for s in ("$" + "5k", "$" + "1.5M", "USD " + "5000", "5,000" + " dollars",
                         chr(0xA3) + "1,500", "$" + "12")), f, ran)
    _check("pipeline/ figures after a yen or rupee sign, before a euro sign, after CHF and before "
           "euros are detected",
           all(any(x["pattern_id"] == "pipeline_amount" for x in scan_text("fee " + s, "pipeline/deals/x.json"))
               for s in (chr(0xA5) + "5000", chr(0x20B9) + "5,000", "5000 " + chr(0x20AC), "CHF " + "5000",
                         "5,000" + " euros")), f, ran)
    _check("a k suffix is part of the pipeline/ match; a figure in words and a currency code outside "
           "_AMOUNT_CODE are not read (the stated limit)",
           [x["match"] for x in scan_text("fee $" + "5k", "pipeline/x.json")] == ["$" + "5k"]
           and not any(x["pattern_id"] == "pipeline_amount" for s in ("five thousand dollars", "SEK " + "5000")
                       for x in scan_text("fee " + s, "pipeline/deals/x.json")), f, ran)
    # The commit-message backstop skips the boundary commit and its ancestors (the stated limit)
    # and scans the commits after it, including a side-branch commit that git log lists after the
    # boundary. Each scripted commit carries a finding id, and the stub answers only the exact git
    # arguments the scan passes.
    _old_c, _bnd_c, _side_c, _new_c = "a" * 40, "b" * 40, "d" * 40, "c" * 40
    _fid_msg = "P1: tidy\n\nsee F" + "5: detail\n"
    _log_args = ["log", "x..y", "--format=%H%x00%ae%x00%B%x01"]

    def _log_git(args, check=True):
        # git log ends each record with a newline after the %x01 separator.
        if list(args) == _log_args:
            return "".join(f"{s}\x0012345+dev@users.noreply.github.com\x00{_fid_msg}\x01\n"
                           for s in (_new_c, _bnd_c, _side_c, _old_c))
        if list(args) == ["rev-list", _bnd_c]:
            return f"{_bnd_c}\n{_old_c}\n"
        return None

    def _backstop_holds(scan):
        every = sorted("commit:" + s[:12] for s in (_new_c, _bnd_c, _side_c, _old_c))
        bounded = scan("x..y", {"entries": [], "commit_policy_boundary": _bnd_c})
        unbounded = scan("x..y", {"entries": []})
        unresolved = scan("x..y", {"entries": [], "commit_policy_boundary": "e" * 40})
        unlisted = scan("x..z", {"entries": [], "commit_policy_boundary": _bnd_c})
        return (bounded is not None and unbounded is not None and unresolved is not None
                and unlisted is None
                and sorted(x["path"] for x in bounded)
                == sorted("commit:" + s[:12] for s in (_new_c, _side_c))
                and sorted(x["path"] for x in unbounded) == every
                and sorted(x["path"] for x in unresolved) == every)
    _saved_git = globals()["_git"]
    globals()["_git"] = _log_git
    try:
        _backstop_ok = _backstop_holds(scan_commit_messages)
    finally:
        globals()["_git"] = _saved_git
    _check("commit-message backstop: the boundary commit and its ancestors are not re-checked (the "
           "stated limit) and the commits after the boundary, a side-branch commit listed after it "
           "included, are scanned; a boundary git cannot resolve skips no commit, and a range git "
           "cannot list returns None", _backstop_ok, f, ran)
    # Falsifying mutations of scan_commit_messages, each run against the same scripted history;
    # the check above must fail for every one. An anchor that no longer occurs exactly once in the
    # source fails this check, so an edit to the scan updates these cases with it.
    import inspect as _inspect
    _scan_src = _inspect.getsource(scan_commit_messages)
    _mutants = (
        ("no skip", "        if sha in boundary_and_before:\n            continue\n", ""),
        ("skip every commit once a boundary resolves", "if sha in boundary_and_before:",
         "if boundary_and_before:"),
        ("skip stops at the boundary", "if sha in boundary_and_before:\n            continue",
         "if sha == boundary:\n            break"),
        ("only the boundary itself skipped",
         "{line.strip() for line in prior.splitlines() if line.strip()}", "{boundary}"),
        ("rev-list over every ref", '["rev-list", boundary]', '["rev-list", boundary, "--all"]'),
        ("rev-list capped at one commit", '["rev-list", boundary]',
         '["rev-list", boundary, "--max-count=1"]'),
        ("log walks first parents only", '["log", rng,', '["log", "--first-parent", rng,'),
        ("records read without trimming git's newline", "        record = record.strip()\n", ""),
        ("an unresolvable boundary skips every commit", "        if prior:\n",
         "        if not prior:\n            return []\n        if prior:\n"),
        ("a range git cannot list reads as clean", "    if log is None:\n        return None\n",
         "    if log is None:\n        return []\n"),
    )
    _survivors = []
    for _label, _old, _new in _mutants:
        if _scan_src.count(_old) != 1:
            _survivors.append(f"{_label} (anchor not found exactly once)")
            continue
        _ns = dict(globals(), _git=_log_git)
        exec(compile(_scan_src.replace(_old, _new), "<scan_commit_messages mutant>", "exec"), _ns)
        if _backstop_holds(_ns["scan_commit_messages"]):
            _survivors.append(_label)
    if _survivors:
        print(f"  [note] mutations the backstop check did not catch: {_survivors}")
    _check(f"commit-message backstop: each of {len(_mutants)} committed mutations of the scan fails "
           f"the boundary check", not _survivors, f, ran)
    _check("the committed commit-message boundary is written as 40 lowercase hex characters",
           re.fullmatch(r"[0-9a-f]{40}", str(_load_allowlist().get("commit_policy_boundary") or ""))
           is not None, f, ran)
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
            pin = f" [sha256 {x['sha256']}]" if x.get("sha256") else ""
            print(f"  - {x['path']}: {x['pattern_id']}: {x['match']}{pin}")
        print("If a finding is a verified false positive, exempt it in "
              "tools/secret-scan-allowlist.json with a reason and its sha256 as match_sha256.")
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
        findings = scan_tracked(allowlist)
        if findings is not None:
            tracked = {p.strip() for p in (_git(["ls-files"]) or "").splitlines() if p.strip()}
            findings += [{"path": "tools/secret-scan-allowlist.json", "pattern_id": "allowlist",
                          "match": msg} for msg in allowlist_problems(allowlist, tracked)]
        return _report(findings, "tracked")
    if a.staged:
        return _report(scan_staged(allowlist), "staged")
    if a.commit_messages:
        return _report(scan_commit_messages(a.commit_messages, allowlist), "commit-messages")
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
