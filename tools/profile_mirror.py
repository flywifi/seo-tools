#!/usr/bin/env python3
"""Profile mirror: copy the creator's own context files, one way, into the Drive hub.

The repo lives outside Google Drive (for example ~/CreatorOS), so its gitignored credential files
never enter a synced folder. The context an AI engine should see (voice, channel, setup answers,
content calendar) is copied from pipeline/user-context/ into the hub's Profile/ folder, which
Google Drive for desktop syncs. Only the files on PROFILE_ALLOWLIST are copied; the copy runs one
way (the local file wins) and never deletes anything in Drive.

Lanes:
- sync (local lane, no network): copy each allowlisted file into <hub>/Profile/ when its sha256
  changed. A file missing locally is logged and its Drive copy is kept. A Drive copy edited in
  Drive since the last run is logged as a warning, then overwritten (Drive version history keeps
  the edit). A file refuse() rejects is not copied.
- sync --api (opt-in, the drive_api_polling credential): also create or update one Google Doc,
  "About me and my voice", rendered from what <hub>/Profile holds, so a file missing or refused
  here keeps its section from its Drive copy; a Drive copy that cannot be read holds the Doc for
  that run. The drive.file scope sees only files this app created or opened, and the hub folders
  are made outside the app, so the Doc is found by its remembered id (checked every run: trashed
  or deleted means a new Doc, edited in Drive means rewritten, moved means updated where it is),
  then by name among the Docs the credential can see. A new Doc goes into Creator OS/Profile when
  the API can see that folder, otherwise into My Drive with a one-time note to move it there; a
  move keeps its id. A Doc error does not stop the file copy.
- check-file PATH: refuse() on one file; tools/profile-mirror.sh runs it as its content check.
- install-agent / uninstall-agent: a user-scoped launchd agent (~/Library/LaunchAgents) that runs
  the sync at minutes 7, 22, 37 and 52 of each hour, with the --api and --include-contact-profile
  choices given to install-agent. macOS only.

State: pipeline/user-context/profile-mirror-state.local.json (gitignored), written atomically: the
last run, the last RUN_HISTORY runs that copied, refused or failed something or acted on the
Doc, file hashes and the Doc record.
Log: ~/Library/Logs/CreatorOS/profile-mirror.log (rotating, one summary line per run), and
profile-mirror.last-run beside it (the last run's time, status and engine, written by both
engines). docs/PROFILE-MIRROR.md is the guide.

Usage:
  python3 tools/profile_mirror.py sync [--hub PATH] [--api] [--include-contact-profile] [--quiet]
  python3 tools/profile_mirror.py check [--hub PATH]
  python3 tools/profile_mirror.py check-file PATH
  python3 tools/profile_mirror.py status [--json]
  python3 tools/profile_mirror.py install-agent [--hub PATH] [--engine python|rsync] [--api]
                                                [--include-contact-profile]
  python3 tools/profile_mirror.py uninstall-agent
  python3 tools/profile_mirror.py --selftest
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import logging
import logging.handlers
import os
import plistlib
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import atomic_io  # noqa: E402
import project_docs as pd  # noqa: E402
import secret_scan  # noqa: E402
from handoff import drive_api as da  # noqa: E402

CONTEXT_DIR = ROOT / "pipeline" / "user-context"
STATE_PATH = CONTEXT_DIR / "profile-mirror-state.local.json"
LOG_DIR = Path.home() / "Library" / "Logs" / "CreatorOS"
LABEL = "com.creatoros.profile-mirror"
HUB_SUBDIR = "Profile"
HUB_FOLDER = "Creator OS"
DOC_NAME = "About me and my voice"
DOC_FIELDS = "id,trashed,modifiedTime,parents"
RSYNC_SCRIPT = ROOT / "tools" / "profile-mirror.sh"
RUN_MINUTES = (7, 22, 37, 52)
RUN_HISTORY = 20
STAMP_NAME = "profile-mirror.last-run"
STAMP_STATUSES = ("ok", "error", "eperm")

# The files copied, in this order. creator-profile.local.json holds contact and legal details, so
# it is copied only with --include-contact-profile.
PROFILE_ALLOWLIST = ("voice-profile.local.json", "channel-context.local.json",
                     "setup-context.local.json", "content-calendar.local.json")
CONTACT_PROFILE = "creator-profile.local.json"

# Files that hold credentials. They are refused by name even if a later edit adds them above.
REFUSED_NAMES = frozenset({"api-credentials.local.json", "google-credentials.local.json",
                           "microsoft-credentials.local.json"})
# secret_scan patterns that mark personal details rather than credentials; a context file may
# carry them (a contact email in the creator profile), so they do not refuse a copy.
_NON_CREDENTIAL_IDS = frozenset({"email_address", "phone_number", "committed_report",
                                 "severity_tally", "finding_id", "session_link"})
_ENV_NAME_RE = re.compile(r"^\.env(\.|$)")
# A key whose scalar value is a credential: the whole key, or its last word after _, - or a
# camelCase break (api_key, apiKeys, access_token, aws_secret_access_key, clientSecret, pwd). A key
# that holds one of these words elsewhere (api_credentials_configured) is not one.
_CRED_KEY_RE = re.compile(
    r"(?:^|_)(?:api_?keys?|(?:secret_)?access_?keys?|(?:access|refresh|id|auth|bearer|session)"
    r"_?tokens?|token|client_?secrets?|secret(?:_?keys?)?|private_?keys?|passwords?|passwd|pwd"
    r"|passphrases?|credentials?)$")
# Vendor formats tools/secret_scan.py does not read (its stated limits), refused here because a
# context file never needs them.
_LOCAL_PATTERNS = (
    ("google_oauth_client_secret", re.compile(r"\bGOCSPX-[A-Za-z0-9_-]{20,}")),
    ("google_oauth_access_token", re.compile(r"\bya29\.[0-9A-Za-z_-]{20,}")),
    ("stripe_test_key", re.compile(r"\b[spr]k_test_[A-Za-z0-9]{16,}")),
    ("stripe_webhook_secret", re.compile(r"\bwhsec_[A-Za-z0-9+/=]{20,}")),
    ("age_secret_key", re.compile(r"\bAGE-SECRET-KEY-1[0-9A-Z]{50,}")),
)
# A credential written in prose: a credential word (not inside a longer word), then is/was/:/= or
# a space, then a value _secret_shaped accepts ("my password is Hunter2Hunter2",
# "AWS_SECRET_ACCESS_KEY=wJalr...", "youtube_api_key=AbCd123..."). Other phrasings are not read.
_PROSE_CRED_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:password|passwd|passphrase|passcode|pwd"
    r"|secret(?:[ _-]?(?:access[ _-]?)?key)?|api[ _-]?key|access[ _-]?key|token|client[ _-]?secret)"
    r"(?![A-Za-z0-9])[ \t]*(?:(?:is|was)[ \t]+|[:=][ \t]*)?[\"']?([^\s\"',;]{8,})")
_CRED_SYMBOLS = frozenset("!@#$%^&*+=?~")
# Password-type keys, whose value is refused even when it has spaces (a passphrase).
_PASS_KEY_RE = re.compile(r"(?:^|_)(?:passwords?|passwd|pwd|passphrases?)$")


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def credential_ids() -> frozenset:
    """The secret_scan pattern ids that refuse a copy: every pattern but the personal-detail ones."""
    return frozenset(pid for pid, _ in secret_scan.PATTERNS) - _NON_CREDENTIAL_IDS


def _secret_shaped(val: str) -> bool:
    """A value that looks like a password or key rather than a word: 8+ characters with a letter
    and a digit, and either both letter cases or a _CRED_SYMBOLS character. "Hunter2Hunter2",
    "sunny2024!" and "Studio5G2024" are; "10minute" and "2025-roundup" are not."""
    return bool(len(val) >= 8 and re.search(r"[A-Za-z]", val) and re.search(r"\d", val)
                and ((re.search(r"[a-z]", val) and re.search(r"[A-Z]", val))
                     or any(c in _CRED_SYMBOLS for c in val)))


def _scalars(node, key=None):
    """Every (key, text) pair in decoded JSON: object keys with key None, and each scalar value
    (string or number, not a boolean) as text under the key it sits in (list items keep their
    list's key)."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield None, str(k)
            yield from _scalars(v, str(k))
    elif isinstance(node, list):
        for v in node:
            yield from _scalars(v, key)
    elif isinstance(node, (str, int, float)) and not isinstance(node, bool):
        yield key, str(node)


def _key_words(key: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).lower().replace("-", "_")


def _cred_key(key: str) -> bool:
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).lower().replace("-", "_")
    return bool(_CRED_KEY_RE.search(words))


def _credential_hits(text: str, where: str) -> set:
    hits = {f["pattern_id"] for f in secret_scan.scan_text(text, where)
            if f["pattern_id"] in credential_ids()}
    hits |= {pid for pid, rx in _LOCAL_PATTERNS if rx.search(text)}
    if any(_secret_shaped(m.group(1)) for m in _PROSE_CRED_RE.finditer(text)):
        hits.add("credential_in_prose")
    return hits


def refuse(name: str, data: bytes) -> str | None:
    """Why a file must not be copied into Drive, or None. Refused: a credential file name, a
    suffix on secret_scan.FORBIDDEN_DATA_SUFFIXES, an .env name, bytes that are not UTF-8 text,
    text that is not valid JSON, and a file in which, in the raw text or in any decoded key or
    scalar value, one of these reads a credential: a secret_scan credential pattern, a local
    vendor pattern (_LOCAL_PATTERNS), a credential in prose (_PROSE_CRED_RE with _secret_shaped),
    or a credential-named key (_CRED_KEY_RE) holding 8+ characters with no whitespace (any 8+
    characters under a password-type key, _PASS_KEY_RE). A secret written another way is not
    read; docs/PROFILE-MIRROR.md states the limit."""
    low = name.lower()
    if low in REFUSED_NAMES:
        return "a credential file"
    if _ENV_NAME_RE.match(low) or low.endswith(tuple(secret_scan.FORBIDDEN_DATA_SUFFIXES)):
        return "a file type that never leaves this computer"
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return "not UTF-8 text"
    try:
        doc = json.loads(text)
    except ValueError:
        return "not valid JSON (fix it in Creator OS; nothing was copied)"
    where = f"pipeline/user-context/{name}"
    hits = _credential_hits(text, where)
    for key, s in _scalars(doc):
        hits |= _credential_hits(s, where)
        if key is not None and _cred_key(key) and len(s.strip()) >= 8 \
                and (_PASS_KEY_RE.search(_key_words(key)) or not re.search(r"\s", s.strip())):
            hits.add("credential_key")
    if hits:
        return "looks like it holds a credential (" + ", ".join(sorted(hits)) + ")"
    return None


def load_state(path=None) -> dict:
    """The state file (STATE_PATH unless `path`; module paths are read at call time, so a test
    that repoints them is honoured)."""
    try:
        data = json.loads(Path(path or STATE_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("schema", 1)
    data.setdefault("files", {})
    data.setdefault("doc", {})
    data.setdefault("runs", [])
    data.setdefault("last_run", None)
    return data


def save_state(state, path=None) -> None:
    path = Path(path or STATE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_io.atomic_write_text(path, json.dumps(state, indent=2, sort_keys=True) + "\n")


def write_stamp(status: str, engine: str, log_dir=None, now=None) -> None:
    """profile-mirror.last-run: '<UTC time> <ok|error|eperm> <engine>', replaced atomically.
    tools/profile-mirror.sh writes the same line, so install-agent reads either engine's run."""
    d = Path(log_dir or LOG_DIR)
    d.mkdir(parents=True, exist_ok=True)
    atomic_io.atomic_write_text(d / STAMP_NAME, f"{now or _utcnow()} {status} {engine}\n")


def read_stamp(log_dir=None):
    """{"at", "epoch", "status", "engine"} from the stamp, or None when absent or unreadable."""
    try:
        at, status, engine = (Path(log_dir or LOG_DIR) / STAMP_NAME).read_text(
            encoding="utf-8").split()
        epoch = datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc).timestamp()
    except (OSError, ValueError):
        return None
    if status not in STAMP_STATUSES:
        return None
    return {"at": at, "epoch": epoch, "status": status, "engine": engine}


def _copy_into(dest_dir: Path, name: str, data: bytes) -> None:
    """Write `data` to dest_dir/name through a temp file and os.replace, so a sync client never
    sees a half-written file."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    staging = dest_dir / f".{name}.mirror-tmp"
    staging.write_bytes(data)
    os.replace(staging, dest_dir / name)


def render_markdown(files: dict) -> str:
    """Deterministic Markdown for the Google Doc: one section per file, JSON shown as nested
    bullets. No timestamp, so the same files render the same bytes and the Doc is only updated
    when something changed."""
    out = [f"# {DOC_NAME}", "",
           "Copied from Creator OS on this computer. Edit the files in Creator OS, not this Doc;",
           "the next sync overwrites changes made here.", ""]

    def walk(value, depth):
        pad = "  " * depth
        if isinstance(value, dict):
            for k in sorted(value):
                v = value[k]
                if isinstance(v, (dict, list)):
                    out.append(f"{pad}- **{k}**")
                    walk(v, depth + 1)
                else:
                    out.append(f"{pad}- **{k}**: {v}")
        elif isinstance(value, list):
            for v in value:
                if isinstance(v, (dict, list)):
                    out.append(f"{pad}-")
                    walk(v, depth + 1)
                else:
                    out.append(f"{pad}- {v}")
        else:
            out.append(f"{pad}{value}")

    for name in sorted(files):
        out += [f"## {name.replace('.local.json', '').replace('-', ' ').title()}", ""]
        try:
            walk(json.loads(files[name]), 0)
        except ValueError:
            out.append(files[name].strip())
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# --- the Google Doc ----------------------------------------------------------------------------

def _doc_query(name: str) -> str:
    return (f"name = '{da.query_literal(name)}' and mimeType = '{pd.GOOGLE_DOC_MIME}' "
            "and trashed = false")


def _upload_doc(token, body: bytes, transport, doc_id=None, parent_id=None):
    """Create the Doc (multipart; Drive converts the Markdown into a Google Doc) or replace an
    existing Doc's content (media PATCH). Returns (metadata|None, err|None); the metadata is what
    Drive reports after the write (id, modifiedTime, parents). A new Doc gets "parents" only when a
    parent is known, so it lands in My Drive otherwise."""
    auth = {"Authorization": f"Bearer {token}"}
    if doc_id:
        status, resp = transport(
            "PATCH", f"{da.UPLOAD_API}/files/{doc_id}?uploadType=media&fields={DOC_FIELDS}",
            headers=dict(auth, **{"Content-Type": pd.MARKDOWN_MIME}), data=body)
    else:
        meta = {"name": DOC_NAME, "mimeType": pd.GOOGLE_DOC_MIME}
        if parent_id:
            meta["parents"] = [parent_id]
        boundary = "creatoros-profile-doc"
        payload = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                   f"{json.dumps(meta)}\r\n--{boundary}\r\nContent-Type: {pd.MARKDOWN_MIME}"
                   "\r\n\r\n").encode() + body + f"\r\n--{boundary}--".encode()
        status, resp = transport(
            "POST", f"{da.UPLOAD_API}/files?uploadType=multipart&fields={DOC_FIELDS}",
            headers=dict(auth, **{"Content-Type": f"multipart/related; boundary={boundary}"}),
            data=payload)
    if status not in (200, 201):
        return None, f"HTTP {status} {'updating' if doc_id else 'creating'} the Doc"
    try:
        return json.loads(resp.decode("utf-8")), None
    except (ValueError, AttributeError):
        return None, "bad JSON from Drive"


def _doc_texts(names, local: dict, dest: Path):
    """The text each file contributes to the Doc: this run's accepted local text, else the copy
    <hub>/Profile holds (a file missing or refused here keeps its Drive copy, so it keeps its
    section). Returns (texts, None, eperm) or (None, why, eperm) when a Drive copy cannot be read or
    is refused; the Doc is then held, not rendered without that section."""
    texts = {}
    for name in names:
        if name in local:
            texts[name] = local[name]
            continue
        target = dest / name
        try:
            if not target.is_file():
                continue
            data = target.read_bytes()
        except OSError as exc:
            return None, f"Doc held: cannot read the Drive copy of {name}: {exc}", \
                exc.errno == errno.EPERM
        why = refuse(name, data)
        if why:
            return None, f"Doc held: the Drive copy of {name} {why}", False
        texts[name] = data.decode("utf-8-sig")
    return texts, None, False


def sync_doc(token, markdown: str, state: dict, transport=None, now=None, log=None) -> dict:
    """Create or update the Google Doc. Returns {"action", "error", "placed"} and changes
    state["doc"]. drive.file sees only files this app created or opened, so the Doc is found by
    its remembered id (checked every run: trashed or deleted means a new Doc, edited in Drive
    means rewritten, moved means updated where it is), then by name among the Docs this
    credential can see; a new Doc goes into Creator OS/Profile when the API sees that folder,
    else into My Drive with a one-time note to move it there (a move keeps its id)."""
    transport = transport or da._default_transport
    log = log or logging.getLogger("profile_mirror")
    now = now or _utcnow()
    doc = state.setdefault("doc", {})
    sha = _sha_bytes(markdown.encode("utf-8"))
    placed = doc.get("placed")
    doc_id, adopted = doc.get("id"), False
    if doc_id:
        meta, err = da._get_json(token, f"{da.API}/files/{doc_id}?fields={DOC_FIELDS}", transport)
        if err and not err.startswith("HTTP 404"):
            return {"action": "failed", "error": f"Doc check failed: {err}", "placed": placed}
        if err or meta.get("trashed"):
            log.warning("the Doc %s is gone from Drive or in its trash; a trashed Doc is left "
                        "there and a new one is made", doc_id)
            doc_id = None
        else:
            if "modified_time" not in doc:  # a record written before P99-2: take a baseline
                doc.update(modified_time=meta.get("modifiedTime"), parents=meta.get("parents"))
            edited = meta.get("modifiedTime") != doc["modified_time"]
            if doc.get("parents") is not None and meta.get("parents") != doc["parents"]:
                log.info("the Doc was moved in Drive; it is updated where it is")
                placed = "moved"
                doc.update(parents=meta.get("parents"), placed=placed)
            if doc.get("sha256") == sha and not edited:
                return {"action": "unchanged", "error": None, "placed": placed}
            if edited:
                log.warning("the Doc was edited in Drive; rewriting it from this computer "
                            "(Version history keeps the edit)")
    if not doc_id:
        q = urllib.parse.quote(_doc_query(DOC_NAME))
        data, err = da._get_json(
            token, f"{da.API}/files?q={q}&orderBy={urllib.parse.quote('modifiedTime desc')}"
                   f"&fields=files({DOC_FIELDS})&pageSize=10", transport)
        if err:
            return {"action": "failed", "error": f"Doc search failed: {err}", "placed": placed}
        found = data.get("files", [])
        if len(found) > 1:
            log.warning("%d Docs named %r are visible to this app; updating the newest (%s)",
                        len(found), DOC_NAME, found[0]["id"])
        if found:
            doc_id, adopted, placed = found[0]["id"], True, "found"
    body = markdown.encode("utf-8")
    meta = None
    if doc_id:
        meta, err = _upload_doc(token, body, transport, doc_id=doc_id)
        if err and err.startswith("HTTP 404"):
            doc_id, meta = None, None
        elif err:
            return {"action": "failed", "error": err, "placed": placed}
        action = "adopted" if adopted else "updated"
    if not doc_id:
        parent_id, err = None, None
        root_id, err = da.find_folder(token, HUB_FOLDER, transport)
        if not err:
            parent_id, err = da.find_folder(token, HUB_SUBDIR, transport, parent_id=root_id)
        if err and err.startswith(("HTTP", "bad JSON")):
            return {"action": "failed", "error": f"Doc folder lookup failed: {err}",
                    "placed": placed}
        meta, err = _upload_doc(token, body, transport, parent_id=parent_id)
        if err:
            return {"action": "failed", "error": err, "placed": placed}
        action, placed = "created", ("profile" if parent_id else "my-drive")
        if placed == "my-drive":
            log.warning("created the Doc %r in My Drive: the API cannot see the hub's Profile "
                        "folder (drive.file). Move it into Creator OS/Profile once; later runs "
                        "update it by id wherever it is.", DOC_NAME)
    state["doc"] = {"id": meta.get("id") or doc_id, "sha256": sha, "updated_at": now,
                    "modified_time": meta.get("modifiedTime"), "parents": meta.get("parents"),
                    "placed": placed}
    return {"action": action, "error": None, "placed": placed}


# --- a run --------------------------------------------------------------------------------------

def _record_run(res: dict, state: dict, state_path, log, log_dir, eperm: bool) -> None:
    """Write the run into the state (last_run always; runs only when something happened), one
    summary log line, and the stamp. A failure to save is an error of the run, not a crash."""
    doc_action = res["doc"]["action"] if res["doc"] else None
    summary = {k: (len(v) if isinstance(v, list) else v) for k, v in res.items()
               if k not in ("doc", "status")}
    summary["doc"] = doc_action
    changed = any(res[k] for k in ("copied", "refused", "errors", "overwrote_drive_edit")) or \
        doc_action not in (None, "unchanged")
    state["last_run"] = summary
    if changed:
        state["runs"] = (state["runs"] + [summary])[-RUN_HISTORY:]
    try:
        save_state(state, state_path)
    except OSError as exc:
        res["errors"].append(f"state file: {exc}")
        eperm = eperm or exc.errno == errno.EPERM
    res["status"] = "eperm" if eperm else "error" if (res["errors"] or res["refused"]) else "ok"
    log.info("run %s: copied %d, unchanged %d, missing %d, refused %d, errors %d, Doc %s",
             res["status"], len(res["copied"]), len(res["unchanged"]), len(res["missing"]),
             len(res["refused"]), len(res["errors"]), doc_action or "off")
    try:
        write_stamp(res["status"], "python", log_dir, res["at"])
    except OSError as exc:
        log.error("could not write the run stamp: %s", exc)


def sync(hub, *, include_contact=False, api=False, token=None, transport=None, state_path=None,
         src_dir=None, log_dir=None, now=None, log=None) -> dict:
    """One-way copy of the allowlisted context files into <hub>/Profile/, and, with api, the Doc
    rendered from what <hub>/Profile holds. Every run, including one that fails partway, is
    recorded (_record_run: state, one summary log line, the stamp)."""
    log = log or logging.getLogger("profile_mirror")
    now = now or _utcnow()
    src_dir = Path(src_dir or CONTEXT_DIR)
    state = load_state(state_path)
    dest = Path(hub) / HUB_SUBDIR
    names = list(PROFILE_ALLOWLIST) + ([CONTACT_PROFILE] if include_contact else [])
    res = {"at": now, "copied": [], "unchanged": [], "missing": [], "refused": [],
           "overwrote_drive_edit": [], "errors": [], "doc": None}
    flags = {"eperm": False}
    local = {}

    def failed(what, exc):
        res["errors"].append(f"{what}: {exc}")
        log.error("%s: %s", what, exc)
        flags["eperm"] = flags["eperm"] or getattr(exc, "errno", None) == errno.EPERM

    try:
        for name in names:
            try:
                data = (src_dir / name).read_bytes()
            except FileNotFoundError:
                res["missing"].append(name)
                log.info("missing locally, Drive copy kept: %s", name)
                continue
            except OSError as exc:
                failed(name, exc)
                continue
            why = refuse(name, data)
            if why:
                res["refused"].append(f"{name}: {why}")
                log.warning("refused %s: %s", name, why)
                continue
            local[name] = data.decode("utf-8-sig")
            sha = _sha_bytes(data)
            rec = state["files"].get(name, {})
            target = dest / name
            try:
                drive_sha = _sha_bytes(target.read_bytes()) if target.is_file() else None
            except OSError as exc:
                failed(f"{name} (Drive copy)", exc)
                continue
            if drive_sha == sha:
                res["unchanged"].append(name)
                state["files"][name] = {"sha256": sha, "written_at": rec.get("written_at", now)}
                continue
            if drive_sha and rec.get("sha256") and drive_sha != rec["sha256"]:
                res["overwrote_drive_edit"].append(name)
                log.warning("%s was edited in Drive; overwriting it (Drive version history keeps "
                            "the edit)", name)
            try:
                _copy_into(dest, name, data)
            except OSError as exc:
                failed(f"could not copy {name}", exc)
                continue
            res["copied"].append(name)
            state["files"][name] = {"sha256": sha, "written_at": now}
            log.info("copied %s", name)
        if api:
            texts, held, held_eperm = _doc_texts(names, local, dest)
            if held:
                res["doc"] = {"action": "held", "error": held,
                              "placed": state["doc"].get("placed")}
                flags["eperm"] = flags["eperm"] or held_eperm
            else:
                note = None
                if token is None:
                    token, note = pd._api_token(transport=transport)
                if token is None:
                    res["doc"] = {"action": "failed", "error": note,
                                  "placed": state["doc"].get("placed")}
                else:
                    res["doc"] = sync_doc(token, render_markdown(texts), state, transport, now,
                                          log)
            if res["doc"]["error"]:
                res["errors"].append(res["doc"]["error"])
                log.error("%s", res["doc"]["error"])
    except Exception as exc:  # noqa: BLE001 - recorded below, so the run is logged and stamped
        failed("unexpected error", exc)
        log.exception("the run stopped early")
    finally:
        _record_run(res, state, state_path, log, log_dir, flags["eperm"])
    return res


def hub_status(path) -> str:
    """'eperm' when macOS refuses to read the hub path (a privacy block: os.path.isdir reads it
    as missing), else 'error'."""
    if path:
        try:
            os.stat(os.path.expanduser(str(path)))
        except PermissionError as exc:
            if exc.errno == errno.EPERM:
                return "eperm"
        except OSError:
            pass
    return "error"


def check(hub, include_contact=False, state_path=None, src_dir=None) -> list:
    """Read-only: one row per file with the local, recorded and Drive sha256 and a verdict."""
    state = load_state(state_path)
    src_dir = Path(src_dir or CONTEXT_DIR)
    rows = []
    for name in list(PROFILE_ALLOWLIST) + ([CONTACT_PROFILE] if include_contact else []):
        src, target = src_dir / name, Path(hub) / HUB_SUBDIR / name
        local = _sha_bytes(src.read_bytes()) if src.is_file() else None
        drive = _sha_bytes(target.read_bytes()) if target.is_file() else None
        rec = state["files"].get(name, {}).get("sha256")
        verdict = ("missing locally" if local is None else "not copied yet" if drive is None
                   else "current" if drive == local
                   else "edited in Drive" if rec and drive != rec else "stale")
        rows.append({"file": name, "verdict": verdict, "local": local, "drive": drive})
    return rows


# --- launchd agent ---------------------------------------------------------------------------

def plist_path(home=None) -> Path:
    return Path(home or Path.home()) / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def build_plist(hub, engine="python", *, api=False, include_contact=False, python=None,
                log_dir=None, root=ROOT, home=None) -> dict:
    """The launchd job. launchd needs absolute paths, so the interpreter, the script and the hub
    are fixed now; moving the repo or changing Python means running install-agent again."""
    hub = str(Path(hub).expanduser().resolve())
    import env_paths
    # abspath, not resolve(): the venv is found from the path Python was started by.
    py = os.path.abspath(str(python or env_paths.app_python(Path(root))))
    if engine == "rsync":
        args = ["/bin/bash", str(Path(root) / "tools" / "profile-mirror.sh"),
                str(Path(root) / "pipeline" / "user-context"), str(Path(hub) / HUB_SUBDIR), py]
    else:
        args = [py, str(Path(root) / "tools" / "profile_mirror.py"), "sync", "--quiet",
                "--hub", hub]
        args += ["--api"] if api else []
        args += ["--include-contact-profile"] if include_contact else []
    log = str(Path(log_dir or LOG_DIR) / "profile-mirror.launchd.log")
    return {"Label": LABEL, "ProgramArguments": args, "WorkingDirectory": str(root),
            "EnvironmentVariables": {"HOME": str(home or Path.home())},
            "StartCalendarInterval": [{"Minute": m} for m in RUN_MINUTES],
            "ProcessType": "Background", "LowPriorityIO": True,
            "StandardOutPath": log, "StandardErrorPath": log}


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _write_plist(target: Path, job: dict, log_dir: Path) -> None:
    """The plist, mode 0644, through a temp file and os.replace; the log folder beside it."""
    log_dir.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f".{target.name}.tmp"
    staging.write_bytes(plistlib.dumps(job))
    os.chmod(staging, 0o644)
    os.replace(staging, target)


def install_agent(hub, engine="python", *, api=False, include_contact=False, runner=_run,
                  sleep=time.sleep, clock=time.monotonic, now=time.time, home=None, uid=None,
                  platform=None, python=None, log_dir=None, wait=30) -> dict:
    """Write the plist, (re)load it and start one run now. Returns {"ok", "detail"}: ok only when
    that run's stamp says ok."""
    if (platform or sys.platform) != "darwin":
        return {"ok": False, "detail": "install-agent needs macOS (launchd); run sync by hand "
                                       "or from your own scheduler elsewhere."}
    if engine == "rsync" and (api or include_contact):
        return {"ok": False, "detail": "the rsync engine copies the four allowlisted files only; "
                                       "--api and --include-contact-profile need --engine python."}
    uid = os.getuid() if uid is None else uid
    log_dir = Path(log_dir or LOG_DIR)
    job = build_plist(hub, engine, api=api, include_contact=include_contact, python=python,
                      log_dir=log_dir, home=home)
    target = plist_path(home)
    _write_plist(target, job, log_dir)
    runner(["launchctl", "bootout", f"gui/{uid}/{LABEL}"])
    boot = runner(["launchctl", "bootstrap", f"gui/{uid}", str(target)])
    if boot.returncode != 0:
        return {"ok": False, "detail": f"launchctl bootstrap failed: {boot.stderr.strip()}"}
    try:
        (log_dir / STAMP_NAME).unlink()  # any stamp after this is the agent's own first run
    except FileNotFoundError:
        pass
    started = int(now())
    runner(["launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"])
    prog = job["ProgramArguments"][0]
    real = os.path.realpath(prog)
    fda = (f"macOS blocked the background job from the Drive folder or the repo. Either move the "
           f"repo out of Desktop, Documents and Downloads, or open System Settings > Privacy & "
           f"Security > Full Disk Access and allow {prog}"
           + (f" (it runs {real})" if real != prog else "")
           + "; that lets every script this program runs read all your files. Then run "
             "install-agent again.")
    deadline = clock() + wait
    while clock() < deadline:
        st = read_stamp(log_dir)
        if st and st["epoch"] >= started:
            if st["status"] == "ok":
                return {"ok": True, "detail": f"installed {target}; the first run finished"}
            if st["status"] == "eperm":
                return {"ok": False, "detail": f"installed {target}, but {fda}"}
            return {"ok": False, "detail": (
                f"installed {target}; the first run finished with errors (the agent keeps "
                f"running on schedule). See {log_dir / 'profile-mirror.log'}.")}
        sleep(1)
    return {"ok": False, "detail": (
        f"installed {target}, but no run finished within {wait}s. See "
        f"{log_dir / 'profile-mirror.launchd.log'}; if it says 'Operation not permitted', {fda}")}


def uninstall_agent(*, runner=_run, home=None, uid=None, platform=None) -> dict:
    if (platform or sys.platform) != "darwin":
        return {"ok": False, "detail": "uninstall-agent needs macOS (launchd)."}
    uid = os.getuid() if uid is None else uid
    runner(["launchctl", "bootout", f"gui/{uid}/{LABEL}"])
    target = plist_path(home)
    if target.exists():
        target.unlink()
    return {"ok": True, "detail": f"removed {target}; nothing in Drive was touched"}


def status(state_path=None, home=None, log_dir=None) -> dict:
    """Read-only: the last run, the last 5 runs kept in the history, the stamp (either
    engine), the installed agent (engine, program, hub, options) and the Doc record."""
    st = load_state(state_path)
    agent, p = None, plist_path(home)
    if p.exists():
        try:
            job = plistlib.loads(p.read_bytes())
            args = job.get("ProgramArguments") if isinstance(job, dict) else None
            if not isinstance(args, list) or not args:
                raise ValueError("no ProgramArguments")
            rsync = args[0] == "/bin/bash"
            agent = {"plist": str(p), "engine": "rsync" if rsync else "python",
                     "program": args[0],
                     "hub": (str(Path(args[3]).parent) if rsync and len(args) > 3
                             else args[args.index("--hub") + 1] if "--hub" in args[:-1] else None),
                     "api": "--api" in args, "include_contact": "--include-contact-profile" in args}
        except Exception:  # noqa: BLE001 - a damaged plist is reported, never a crash of status
            agent = {"plist": str(p), "error": "unreadable plist; run install-agent again"}
    return {"last_run": st["last_run"], "recent_changes": st["runs"][-5:],
            "stamp": read_stamp(log_dir), "agent": agent, "doc": st["doc"]}


def _status_text(st: dict) -> str:
    lines = [f"last run: {st['last_run'] or 'none yet'}"]
    s = st["stamp"]
    lines.append(f"last stamp: {s['at']} {s['status']} ({s['engine']} engine)" if s
                 else "last stamp: none")
    a = st["agent"]
    if not a:
        lines.append("agent: not installed (python3 tools/profile_mirror.py install-agent)")
    elif a.get("error"):
        lines.append(f"agent: {a['plist']}: {a['error']}")
    else:
        lines.append(f"agent: {a['engine']} engine, {a['program']}, hub {a['hub']}"
                     + (", with the Doc (--api)" if a["api"] else "")
                     + (", with the contact profile" if a["include_contact"] else ""))
    d = st["doc"] or {}
    if not d.get("id"):
        lines.append("Doc: none")
    else:
        line = f"Doc: {d['id']} ({d.get('placed') or 'placed before P99-2'}), " \
               f"updated {d.get('updated_at')}"
        if d.get("placed") == "my-drive":
            line += "; if you have not moved it yet, move it into Creator OS/Profile once"
        lines.append(line)
    if st["recent_changes"]:
        lines.append("recent changes:")
        lines += [f"  {r}" for r in st["recent_changes"]]
    return "\n".join(lines)


# --- CLI -------------------------------------------------------------------------------------

def _logger(quiet: bool) -> logging.Logger:
    """The run log: UTC ISO times, the file handler added once per log path, so repeated main()
    calls in one process do not write each line twice."""
    log = logging.getLogger("profile_mirror")
    log.setLevel(logging.INFO)
    path = str(Path(LOG_DIR) / "profile-mirror.log")
    have = [h for h in log.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
    if not any(h.baseFilename == path for h in have):
        try:
            Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(path, maxBytes=512_000, backupCount=3,
                                                      encoding="utf-8")
            fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%SZ")
            fmt.converter = time.gmtime
            fh.setFormatter(fmt)
            log.addHandler(fh)
        except OSError:
            pass
    if not quiet and not any(type(h) is logging.StreamHandler for h in log.handlers):
        log.addHandler(logging.StreamHandler(sys.stderr))
    return log


def _hub(arg):
    from handoff import watcher as w
    return w.resolve_hub(arg)


def _hub_config_mirror():
    """The hub path saved on the wizard's Drive hub screen, or None."""
    try:
        from handoff import watcher as w
        return w.load_hub_config().get("local_mirror")
    except Exception:  # noqa: BLE001 - only used to classify a missing hub
        return None


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Copy the creator's context files into the Drive hub.")
    ap.add_argument("command", nargs="?", choices=["sync", "check", "check-file", "status",
                                                   "install-agent", "uninstall-agent"])
    ap.add_argument("path", nargs="?", help="the file check-file reads")
    ap.add_argument("--hub", help="the local Drive hub folder (default: the wizard's setting)")
    ap.add_argument("--api", action="store_true", help="also write the Google Doc")
    ap.add_argument("--include-contact-profile", action="store_true")
    ap.add_argument("--engine", choices=["python", "rsync"], default="python")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.command in (None, "status"):
        st = status()
        print(json.dumps(st, indent=2) if a.json else _status_text(st))
        return 0
    if a.command == "check-file":
        if not a.path:
            print("check-file needs a PATH", file=sys.stderr)
            return 2
        try:
            data = Path(a.path).read_bytes()
        except OSError as exc:
            print(f"cannot read: {exc}")
            return 2
        why = refuse(Path(a.path).name, data)
        print(why or "ok")
        return 1 if why else 0
    if a.command == "uninstall-agent":
        r = uninstall_agent()
        print(r["detail"])
        return 0 if r["ok"] else 1
    hub, note = _hub(a.hub)
    if hub is None:
        if a.command == "sync":
            log = _logger(a.quiet)
            log.error("no hub: %s", note)
            try:
                hub_state = hub_status(a.hub or _hub_config_mirror())
                log.info("run %s: the Drive hub folder could not be read", hub_state)
                write_stamp(hub_state, "python")
            except Exception as exc:  # noqa: BLE001 - the exit code still reports the failure
                log.error("could not write the run stamp: %s", exc)
        print(f"profile mirror: {note}", file=sys.stderr)
        return 2
    if a.command == "check":
        rows = check(hub, a.include_contact_profile)
        for r in rows:
            print(f"  {r['verdict']:<16} {r['file']}")
        return 0 if all(r["verdict"] in ("current", "missing locally") for r in rows) else 1
    if a.command == "install-agent":
        r = install_agent(hub, a.engine, api=a.api, include_contact=a.include_contact_profile)
        print(r["detail"])
        return 0 if r["ok"] else 1
    res = sync(hub, include_contact=a.include_contact_profile, api=a.api, log=_logger(a.quiet))
    if a.json:
        print(json.dumps(res, indent=2))
    elif not a.quiet:
        print(f"copied {len(res['copied'])}, unchanged {len(res['unchanged'])}, "
              f"missing {len(res['missing'])}, refused {len(res['refused'])}"
              + (f", Doc {res['doc']['action']}" if res["doc"] else ""))
    return 1 if res["errors"] or res["refused"] else 0


# --- selftest: everything below is test code; the committed mutations apply above this line ---

_SELFTEST_MARK = ("# --- selftest: everything below is test code; the committed mutations apply "
                  "above this line ---")


def _part(*parts) -> str:
    """Fixtures shaped like credentials are built from parts, so this file never holds one
    whole (tools/secret_scan.py reads tracked text; see its DEV-TRAP note)."""
    return "".join(parts)


def _put(path, text: str) -> None:
    """Test fixtures are written through atomic_io (drift invariant: atomic writers)."""
    atomic_io.atomic_write_text(path, text)


class _FakeDrive:
    """A Drive API stand-in for the pins: it checks the bearer header, sees only the files it
    created (as drive.file does), refuses a folder create, and fails on request."""

    def __init__(self, token, folders_visible=False):
        self.token, self.files, self.n, self.t, self.calls = token, {}, 0, 0, []
        self.folders_visible, self.fail_get, self.patch_404_once = folders_visible, None, False
        self.raise_on = None

    def tick(self):
        self.t += 1
        return f"2026-10-01T00:{self.t // 60:02d}:{self.t % 60:02d}.000Z"

    def meta(self, fid):
        f = self.files[fid]
        return {"id": fid, "trashed": f["trashed"], "modifiedTime": f["modifiedTime"],
                "parents": f["parents"]}

    def __call__(self, method, url, headers=None, data=None, timeout=30):
        self.calls.append((method, url, dict(headers or {}), data))
        if self.raise_on and self.raise_on in url:
            raise RuntimeError("transport stand-in failure")
        if (headers or {}).get("Authorization") != f"Bearer {self.token}" or self.token in url \
                or not url.startswith("https://www.googleapis.com/"):
            return 401, b"bad auth"
        u = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(u.query)
        fid = re.search(r"/files/([^/?]+)", u.path)
        if method == "GET" and self.fail_get:
            return self.fail_get, b"denied"
        if method == "GET" and u.path.endswith("/files") and "q" in qs:
            q = qs["q"][0]
            name = re.search(r"name = '((?:[^'\\]|\\.)*)'", q)
            name = re.sub(r"\\(.)", r"\1", name.group(1)) if name else None
            parent = re.search(r"'([^']+)' in parents", q)
            parent = parent.group(1) if parent else None
            if "folder" in q:
                folders = {"fld-Decoy": ("Profile", "root"), "fld-Creator": ("Creator OS", "root"),
                           "fld-Profile": ("Profile", "fld-Creator")} if self.folders_visible else {}
                hits = [{"id": i} for i, (n, p) in folders.items()
                        if n == name and (parent is None or p == parent)]
                return 200, json.dumps({"files": hits}).encode()
            hits = [self.meta(i) for i, f in self.files.items() if f["name"] == name
                    and not (f["trashed"] and "trashed = false" in q)]
            if "modifiedTime desc" in qs.get("orderBy", [""])[0]:
                hits.sort(key=lambda f: f["modifiedTime"], reverse=True)
            return 200, json.dumps({"files": hits}).encode()
        if method == "GET" and fid:
            if fid.group(1) not in self.files:
                return 404, b"{}"
            return 200, json.dumps(self.meta(fid.group(1))).encode()
        if method == "POST" and qs.get("uploadType") == ["multipart"]:
            if da.FOLDER_MIME.encode() in (data or b""):
                return 403, b"folder create refused"
            meta = json.loads(data.split(b"\r\n\r\n", 1)[1].split(b"\r\n--", 1)[0])
            self.n += 1
            new = f"doc-{self.n}"
            self.files[new] = {"name": meta["name"], "trashed": False, "modifiedTime": self.tick(),
                               "parents": meta.get("parents", ["root"]), "content": data}
            return 200, json.dumps(self.meta(new)).encode()
        if method == "PATCH" and fid:
            if self.patch_404_once:
                self.patch_404_once = False
                return 404, b"{}"
            if fid.group(1) not in self.files:
                return 404, b"{}"
            f = self.files[fid.group(1)]
            f.update(modifiedTime=self.tick(), content=data)
            return 200, json.dumps(self.meta(fid.group(1))).encode()
        return 418, b"unexpected"


class _Captured(logging.Handler):
    def __init__(self):
        super().__init__()
        self.msgs = []

    def emit(self, record):
        self.msgs.append(f"{record.levelname} {record.getMessage()}")


def _quiet_log(name):
    log = logging.getLogger(f"profile_mirror.selftest.{name}")
    log.handlers[:] = []
    cap = _Captured()
    log.addHandler(cap)
    log.propagate = False
    log.setLevel(logging.INFO)
    return log, cap


def _eperm_path(blocked: set):
    """A Path class whose read_bytes and is_file raise EPERM ("Operation not permitted", the
    macOS privacy block) for the paths in `blocked`."""
    class EpermPath(type(Path())):
        def _check(self):
            if str(self) in blocked:
                raise PermissionError(errno.EPERM, "Operation not permitted", str(self))

        def read_bytes(self):
            self._check()
            return super().read_bytes()

        def is_file(self, **kw):
            self._check()
            return super().is_file(**kw)
    return EpermPath


class _StatEperm:
    """Stands in for the os module: os.stat raises EPERM, as macOS does for a folder the job
    may not read."""
    path = os.path

    @staticmethod
    def stat(p, *a, **k):
        raise PermissionError(errno.EPERM, "Operation not permitted", p)


def _pins_refuse(m, tmp) -> list:
    J = json.dumps
    a40 = _part("wJalrXUtnFEMI/K7MDENG/", "bPxRfiCYEXAMPLEKEY")
    hunter = _part("Hunter2", "Hunter2x")
    must_refuse = {
        "an AWS access key id": J({"note": _part("AKIA", "ABCDEFGHIJKLMNOP")}),
        "a Google OAuth client secret": J({"note": _part("GOCSPX-", "a1B2c3D4e5F6g7H8i9J0k1L2m3N4")}),
        "a JSON-escaped credential key": _part('{"api\\u005f', 'key": "', "Zq8" * 4, '"}'),
        "a password in prose": J({"bio": "my password is " + hunter}),
        "an AWS secret in prose": J({"notes": "aws secret " + a40}),
        "a Stripe test key": J({"notes": _part("sk_", "test_", "a" * 24)}),
        "a camelCase credential key": J({_part("client", "Secret"): "Zq8" * 4}),
        "a nested list under a token key": J({"tokens": {_part("refresh_", "token"): ["Zq8" * 4]}}),
        "aws_secret_access_key": J({_part("aws_secret_", "access_key"): a40}),
        "secretAccessKey": J({_part("secret", "AccessKey"): a40}),
        "an env line in a note": J({"notes": _part("AWS_SECRET_", "ACCESS_KEY=") + a40}),
        "a snake_case api key in a note": J({"notes": _part("youtube_api_", "key=AbCdEf123456789")}),
        "a passwords list": J({_part("pass", "words"): [_part("Hunter2", "Hunter2")]}),
        "a pwd key": J({_part("p", "wd"): _part("Hunter2", "Hunter2")}),
        "an apiKeys list": J({_part("api", "Keys"): ["AbCdEf123456789"]}),
        "a number under a credential key": J({_part("api_", "key"): 12345678901234}),
        "a Google access token": J({"notes": _part("ya29.", "a0AfH6SMB", "x" * 30)}),
        "a wifi passcode": J({"notes": "wifi passcode is " + _part("Studio5G", "2024")}),
        "a password with a symbol": J({"notes": "instagram password: " + _part("sunny", "2024!")}),
        "the unchanged secret_scan limit: prose under a key named secret":
            J({_part("sec", "ret"): "consistency is the key"}),
        "invalid JSON": '{"tone": "warm",}',
        "a Stripe webhook secret": J({"notes": _part("whsec_", "AbCdEf0123456789AbCdEf0123")}),
        "an age secret key": J({"notes": _part("AGE-SECRET-KEY-1", "QX" * 29)}),
        "a vendor token visible only after JSON decoding":
            _part('{"note": "GOCSPX\\u002d', "a1B2c3D4e5F6g7H8i9J0k1L2m3N4", '"}'),
        "a vendor token in the middle of a sentence":
            J({"note": "the client " + _part("GOCSPX-", "a1B2c3D4e5F6g7H8i9J0k1L2m3N4") + " here"}),
        "exactly 8 characters under a credential key": J({_part("p", "wd"): "Zq8Zq8Zq"}),
        "a passphrase with spaces": J({_part("pass", "phrase"): "correct horse battery staple"}),
        "a camelCase pwd key with spaces": J({_part("wifi", "Pwd"): "correct horse battery staple"}),
        "a hyphenated Pwd key with spaces": J({_part("Wifi-", "Pwd"): "correct horse battery staple"}),
        "a password list with spaces": J({_part("pass", "word"): ["correct horse battery staple"]}),
    }
    must_pass = {
        "a contact email": J({"contact_email": "jane@example.com"}),
        "a secret ingredient": J({"bio": "my secret ingredient is consistency"}),
        "a token of thanks": J({"bio": "a token of thanks to everyone"}),
        "the configured-credentials list": J({"api_credentials_configured":
                                                 ["youtube_data_api", "pinterest"]}),
        "a short password value": J({"password": "none"}),
        "'my secret: 10minute edits'": J({"actual_phrases": ["my secret: 10minute edits"]}),
        "an 'API key:' video title": J({"entries": [{"title": "API key: 2025-roundup"}]}),
        "a byte-order mark": "﻿" + J({"tone": "warm"}),
        "a signature phrase": J({"signature_phrases": ["let's goooo"]}),
        "a money note": J({"notes": "rate card 2025 is 1,500 per video"}),
        "a word that starts with token": J({"bio": "I avoid tokenism2025 in casting"}),
        "a word that starts with password": J({"bio": "see the passwordReset2025 flow"}),
        "prose under a credentials key": J({"credentials": "ask the studio manager"}),
        "the stated limit: a prose password with no digit":
            J({"bio": "my password is " + _part("Hunter", "HunterX")}),
    }
    out = [(f"refused: {k}", m.refuse("voice-profile.local.json", v.encode("utf-8")) is not None)
           for k, v in must_refuse.items()]
    out += [(f"accepted: {k}", m.refuse("voice-profile.local.json", v.encode("utf-8")) is None)
            for k, v in must_pass.items()]
    templates = sorted((m.ROOT / "pipeline" / "user-context").glob("*.json"))
    out.append(("the committed user-context templates are all accepted",
                templates and all(m.refuse(t.name, t.read_bytes()) is None for t in templates)))
    out.append(("credential names, .env names, forbidden suffixes and non-UTF-8 bytes are refused",
                m.refuse("api-credentials.local.json", b"{}")
                and m.refuse(".env.local", b"A=1") and m.refuse("export.csv", b"a,b")
                and m.refuse("x.local.json", b"\xff\xfe")))
    return out


def _pins_doc(m, tmp) -> list:
    tok = _part("fixture-", "access", "_token")
    log, cap = _quiet_log("doc")
    out = []

    def run(d, st, md):
        cap.msgs.clear()
        n0 = len(d.calls)
        r = m.sync_doc(tok, md, st, d, "now", log)
        return r, d.calls[n0:], list(cap.msgs)

    d, st = _FakeDrive(tok), {"doc": {}}
    r, c, msgs = run(d, st, "# v1\n")
    out.append(("A: hub folders invisible: the Doc is created in My Drive, no parents, with the "
                "move note", r == {"action": "created", "error": None, "placed": "my-drive"}
                and b'"parents"' not in c[-1][3]
                and any("Move it into Creator OS/Profile" in x for x in msgs)))
    r, c, _ = run(d, st, "# v1\n")
    out.append(("B: unchanged text: one metadata GET, no write",
                r["action"] == "unchanged" and [x[0] for x in c] == ["GET"]))
    r, c, _ = run(d, st, "# v2\n")
    out.append(("C: changed text: GET, then PATCH of the same id",
                r["action"] == "updated" and [x[0] for x in c] == ["GET", "PATCH"]
                and st["doc"]["id"] == "doc-1"))
    d.files["doc-1"]["parents"] = ["fld-moved"]
    r, c, _ = run(d, st, "# v3\n")
    out.append(("D: a Doc the owner moved is updated where it is (placed: moved)",
                r == {"action": "updated", "error": None, "placed": "moved"}
                and st["doc"]["id"] == "doc-1"))
    d.files["doc-1"]["modifiedTime"] = d.tick()
    r, c, msgs = run(d, st, "# v4\n")
    out.append(("E: a Doc edited in Drive is reported, then rewritten",
                r["action"] == "updated" and any("edited in Drive" in x for x in msgs)))
    d.files["doc-1"]["trashed"] = True
    trashed_content = d.files["doc-1"]["content"]
    r, c, _ = run(d, st, "# v5\n")
    out.append(("F: a trashed Doc is left in the trash and a new one is made",
                r["action"] == "created" and st["doc"]["id"] == "doc-2"
                and d.files["doc-1"]["content"] == trashed_content))
    st2 = {"doc": {}}
    r, c, _ = run(d, st2, "# v6\n")
    out.append(("G: a lost state file adopts the visible Doc instead of making a second one",
                r["action"] == "adopted" and st2["doc"]["id"] == "doc-2" and len(d.files) == 2))
    d.files["doc-9"] = {"name": m.DOC_NAME, "trashed": False, "parents": ["root"],
                        "modifiedTime": "2026-10-01T09:59:59.000Z", "content": b""}
    r, c, msgs = run(d, {"doc": {}}, "# v7\n")
    out.append(("H: with two visible Docs the newest is adopted and the duplicate reported",
                r["action"] == "adopted" and any("2 Docs named" in x for x in msgs)
                and r.get("placed") == "found" and d.calls[-1][1].split("?")[0].endswith("/doc-9")))
    d3, st3 = _FakeDrive(tok, folders_visible=True), {"doc": {}}
    r, c, _ = run(d3, st3, "# v1\n")
    out.append(("I: hub folders visible: the Doc is created in Creator OS/Profile",
                r["placed"] == "profile" and st3["doc"]["parents"] == ["fld-Profile"]))
    d.fail_get = 401
    snap = json.dumps(st, sort_keys=True)
    r, c, _ = run(d, st, "# v8\n")
    out.append(("J: an HTTP error fails the Doc and leaves its record unchanged",
                r["action"] == "failed" and "401" in r["error"]
                and json.dumps(st, sort_keys=True) == snap))
    d.fail_get, d.patch_404_once = None, True
    r, c, _ = run(d, st, "# v9\n")
    out.append(("K: a 404 between the check and the write makes a new Doc", r["action"] == "created"))
    out.append(("L: query names escape a quote and a backslash",
                m.da.query_literal("Jo's \\ hub") == "Jo\\'s \\\\ hub"
                and "Jo\\'s" in m._doc_query("Jo's")))
    saved = m.da._default_transport
    d4 = _FakeDrive(tok)
    m.da._default_transport = d4
    try:
        r = m.sync_doc(tok, "# x\n", {"doc": {}}, None, "now", log)
    finally:
        m.da._default_transport = saved
    out.append(("M: no transport given uses drive_api's, looked up when called",
                r["action"] == "created" and d4.calls))
    out.append(("N: no folder is ever created (no POST body carries the folder type)",
                not any(x[0] == "POST" and x[3] and m.da.FOLDER_MIME.encode() in x[3]
                        for dd in (d, d3, d4) for x in dd.calls)))
    d5, st5 = _FakeDrive(tok), {"doc": {}}
    run(d5, st5, "# same\n")
    first = st5["doc"]["id"]
    d5.files[first]["trashed"] = True
    r, c, _ = run(d5, st5, "# same\n")
    out.append(("D1: a trashed Doc is replaced even when the text did not change",
                r["action"] == "created" and st5["doc"]["id"] != first))
    d5.files[st5["doc"]["id"]]["parents"] = ["fld-elsewhere"]
    r, c, _ = run(d5, st5, "# same\n")
    out.append(("D2: a move with unchanged text writes nothing and records placed: moved",
                r == {"action": "unchanged", "error": None, "placed": "moved"}
                and [x[0] for x in c] == ["GET"]))
    d5.files[st5["doc"]["id"]]["modifiedTime"] = d5.tick()
    r, c, _ = run(d5, st5, "# same\n")
    out.append(("D3: an edit in Drive with unchanged local text is rewritten (local wins)",
                r["action"] == "updated"))
    old = {"doc": {"id": st5["doc"]["id"], "sha256": m._sha_bytes(b"# same\n"),
                   "updated_at": "2026-09-30T00:00:00Z"}}
    r, c, _ = run(d5, old, "# same\n")
    out.append(("D4: a Doc record written before P99-2 takes a baseline instead of a rewrite",
                r["action"] == "unchanged" and old["doc"].get("modified_time")))
    d6, st6 = _FakeDrive(tok), {"doc": {}}
    run(d6, st6, "# kept\n")
    gone = st6["doc"]["id"]
    del d6.files[gone]
    r, c, _ = run(d6, st6, "# kept\n")
    out.append(("F-gone: a Doc deleted from Drive (404 on its id) is made again",
                r["action"] == "created" and st6["doc"]["id"] != gone))
    d7 = _FakeDrive(tok)
    run(d7, {"doc": {}}, "# old\n")
    for f in d7.files.values():
        f["trashed"] = True
    r, c, _ = run(d7, {"doc": {}}, "# new\n")
    out.append(("G2: a lost state file does not adopt a Doc that is in the trash",
                r["action"] == "created" and len(d7.files) == 2))
    return out


def _pins_sync(m, tmp) -> list:
    tok = _part("fixture-", "access", "_token")
    log, cap = _quiet_log("sync")
    src, hub, logs, state = tmp / "ctx", tmp / "hub", tmp / "logs", tmp / "state.json"
    src.mkdir()
    hub.mkdir()
    vp, cc, ct = "voice-profile.local.json", "channel-context.local.json", m.CONTACT_PROFILE
    _put(src / vp, '{"tone": "warm", "avoid": ["jargon"]}')
    _put(src / cc, '{"niche": "home decor"}')
    _put(src / ct, '{"contact_email": "jane@example.com"}')
    _put(src / "api-credentials.local.json", "{}")
    prof = hub / m.HUB_SUBDIR
    out = []

    def run(**kw):
        cap.msgs.clear()
        return m.sync(hub, state_path=state, src_dir=src, log_dir=logs, log=log, **kw)

    def stamp():
        st = m.read_stamp(logs)
        return st and st["status"]

    r = run(now="2026-01-01T00:00:00Z")
    out.append(("the first run copies the allowlisted files present",
                sorted(r["copied"]) == [cc, vp]))
    out.append(("a missing allowlisted file is reported, not an error",
                sorted(r["missing"]) == ["content-calendar.local.json", "setup-context.local.json"]
                and not r["errors"]))
    out.append(("the contact profile and the credential files are not copied by default",
                not (prof / ct).exists() and not (prof / "api-credentials.local.json").exists()))
    out.append(("no temp file is left behind", not list(prof.glob(".*mirror-tmp"))))
    out.append(("a run writes one summary line and stamps ok",
                sum(x.startswith("INFO run ok:") for x in cap.msgs) == 1 and stamp() == "ok"))
    r = run()
    st = m.load_state(state)
    out.append(("an unchanged run copies nothing, records last_run, and adds no history entry",
                r["copied"] == [] and len(r["unchanged"]) == 2 and len(st["runs"]) == 1
                and st["last_run"]["unchanged"] == 2))
    _put(prof / vp, '{"tone": "edited in Drive"}')
    r = run()
    out.append(("a Drive-side edit is reported and overwritten by the local file",
                r["overwrote_drive_edit"] == [vp] and "warm" in (prof / vp).read_text("utf-8")))
    r = run(include_contact=True)
    out.append(("--include-contact-profile copies the creator profile",
                ct in r["copied"] and (prof / ct).exists()))
    _put(src / "setup-context.local.json", 
        json.dumps({"note": _part("AKIA", "ABCDEFGHIJKLMNOP")}))
    r = run()
    out.append(("a context file holding a credential is refused, not copied, and stamps error",
                any(x.startswith("setup-context.local.json") for x in r["refused"])
                and not (prof / "setup-context.local.json").exists() and stamp() == "error"))
    (src / "setup-context.local.json").unlink()
    st = m.load_state(state)
    st["runs"] = [{"at": str(i)} for i in range(m.RUN_HISTORY)]
    m.save_state(st, state)
    _put(src / vp, '{"tone": "warm", "avoid": ["jargon", "hype"]}')
    run()
    st = m.load_state(state)
    out.append(("history keeps RUN_HISTORY runs, the newest last",
                len(st["runs"]) == m.RUN_HISTORY and st["runs"][-1]["copied"] == 1))
    # The Doc lane over the stand-in Drive.
    d = _FakeDrive(tok)

    def doc():
        return d.files[m.load_state(state)["doc"]["id"]]["content"].decode("utf-8")

    r = run(api=True, token=tok, transport=d)
    out.append(("sync --api writes the Doc with a section per file",
                r["doc"]["action"] == "created" and "## Voice Profile" in doc()
                and "## Channel Context" in doc()))
    _put(src / vp, json.dumps({"bio": "my password is " + _part("Hunter2", "Hunter2x")}))
    r = run(api=True, token=tok, transport=d)
    out.append(("a refused local file keeps its Drive copy and its Doc section",
                any(x.startswith(vp) for x in r["refused"]) and "hype" in doc()
                and "hype" in (prof / vp).read_text("utf-8")))
    _put(src / vp, '{"tone": "warm", "avoid": ["jargon", "hype"]}')
    (src / cc).unlink()
    r = run(api=True, token=tok, transport=d)
    out.append(("a file deleted locally keeps its Drive copy and its Doc section",
                cc in r["missing"] and (prof / cc).exists() and "home decor" in doc()))
    good_copy = (prof / cc).read_text("utf-8")
    _put(prof / cc, json.dumps({"notes": _part("AKIA", "ABCDEFGHIJKLMNOP")}))
    held_before = doc()
    r = run(api=True, token=tok, transport=d)
    out.append(("a Drive copy that is itself refused holds the Doc",
                r["doc"]["action"] == "held" and doc() == held_before
                and "Drive copy" in r["doc"]["error"] and stamp() == "error"))
    _put(prof / cc, good_copy)
    before = doc()
    saved_path = m.Path
    m.Path = _eperm_path({str(prof / cc)})
    try:
        r = run(api=True, token=tok, transport=d)
    finally:
        m.Path = saved_path
    out.append(("a Drive copy macOS will not let us read holds the Doc and stamps eperm",
                r["doc"]["action"] == "held" and doc() == before and stamp() == "eperm"))
    _put(src / cc, '{"niche": "home decor"}')
    m.Path = _eperm_path({str(prof / vp)})
    try:
        r = run()
    finally:
        m.Path = saved_path
    out.append(("an EPERM reading a Drive copy is recorded, not raised",
                any("Drive copy" in e for e in r["errors"]) and stamp() == "eperm"))
    _put(src / vp, '{"tone": "warmer"}')
    d.raise_on = "/files/"
    try:
        r = run(api=True, token=tok, transport=d)
        raised = False
    except Exception:  # noqa: BLE001 - the pin is that nothing escapes
        raised = True
    d.raise_on = None
    out.append(("an exception in the Doc lane is recorded and stamped, never raised",
                not raised and any("unexpected error" in e for e in r["errors"])
                and stamp() == "error" and m.load_state(state)["last_run"]["errors"] >= 1))
    saved_token = m.pd._api_token
    m.pd._api_token = lambda transport=None, **k: (None, "no google_drive credential; connect "
                                                         "it on the wizard /drive-hub screen")
    try:
        r = run(api=True, transport=d)
    finally:
        m.pd._api_token = saved_token
    out.append(("with no Drive credential the files are still copied and the Doc fails with "
                "the wizard remedy", r["doc"]["action"] == "failed" and "wizard" in r["doc"]["error"]
                and stamp() == "error" and (prof / vp).read_text("utf-8") == '{"tone": "warmer"}'))
    saved_save = m.save_state

    def denied(state_, path=None):
        raise PermissionError(errno.EPERM, "Operation not permitted", str(path))
    m.save_state = denied
    try:
        r = run()
    finally:
        m.save_state = saved_save
    out.append(("a state file the job may not write is an eperm run, not a crash",
                r["status"] == "eperm" and stamp() == "eperm"))
    rows = {x["file"]: x["verdict"] for x in m.check(hub, state_path=state, src_dir=src)}
    out.append(("check reports current and missing-locally files",
                rows[vp] == "current" and rows["content-calendar.local.json"] == "missing locally"))
    return out


def _pins_agent(m, tmp) -> list:
    hub, logs, home = tmp / "hub", tmp / "logs", tmp / "home"
    hub.mkdir()
    venv = tmp / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python3").symlink_to(sys.executable)
    py = str(venv / "python3")
    out = []
    job = m.build_plist(hub, python=py, api=True, include_contact=True, log_dir=logs, home=home)
    args = job["ProgramArguments"]
    out.append(("the plist keeps the venv interpreter path (abspath, not the resolved binary)",
                args[0] == py))
    out.append(("the plist carries sync --quiet, --api and --include-contact-profile",
                args[2:4] == ["sync", "--quiet"] and args[-2:] == ["--api",
                                                                    "--include-contact-profile"]))
    plain = m.build_plist(hub, python=py, log_dir=logs, home=home)["ProgramArguments"]
    out.append(("without them the plist carries neither",
                "--api" not in plain and "--include-contact-profile" not in plain))
    out.append(("the job runs at minutes 7, 22, 37 and 52, not at load, in the background, "
                "with HOME set", [e["Minute"] for e in job["StartCalendarInterval"]]
                == list(m.RUN_MINUTES) and "RunAtLoad" not in job
                and job["ProcessType"] == "Background"
                and job["EnvironmentVariables"] == {"HOME": str(home)}))
    rjob = m.build_plist(hub, "rsync", python=py, log_dir=logs, home=home)["ProgramArguments"]
    out.append(("the rsync engine runs the script into <hub>/Profile with the content-check "
                "Python", rjob[:2] == ["/bin/bash", str(m.RSYNC_SCRIPT)]
                and rjob[3].endswith(m.HUB_SUBDIR) and rjob[4] == py))
    out.append(("the plist round-trips through plistlib",
                plistlib.loads(plistlib.dumps(job)) == job))

    class Done:
        def __init__(self, rc=0):
            self.returncode, self.stdout, self.stderr = rc, "", ""

    epoch = 1_790_000_000
    at = datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    early = datetime.fromtimestamp(epoch - 1, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    seen = {}

    def install(write, **kw):
        cmds = []
        m.write_stamp("ok", "python", logs, "2026-01-01T00:00:00Z")  # a stale stamp

        def runner(cmd):
            cmds.append(cmd)
            if cmd[1] == "kickstart":
                seen["stale_gone"] = not (logs / m.STAMP_NAME).exists()
                if write:
                    m.write_stamp(write[0], "python", logs, write[1])
            return Done()
        ticks = iter(range(1000))
        r = m.install_agent(hub, runner=runner, sleep=lambda s: None, clock=lambda: next(ticks),
                            now=lambda: epoch + 0.4, home=home, uid=501, platform="darwin",
                            python=py, log_dir=logs, wait=5, **kw)
        return r, cmds

    r, cmds = install(("ok", at), api=True)
    target = m.plist_path(home)
    # P101: NTFS keeps no POSIX mode bits, so the 0644 half applies off Windows only.
    out.append(("install-agent writes the plist mode 0644, bootstraps, then kickstarts",
                r["ok"] and target.exists()
                and (os.name == "nt" or (target.stat().st_mode & 0o777) == 0o644)
                and [c[1] for c in cmds] == ["bootout", "bootstrap", "kickstart"]
                and cmds[1] == ["launchctl", "bootstrap", "gui/501", str(target)]))
    out.append(("the old stamp is removed before kickstart, so only the new run counts",
                seen.get("stale_gone") is True))
    out.append(("install-agent --api writes a job that runs sync --api",
                "--api" in plistlib.loads(target.read_bytes())["ProgramArguments"]))
    a = m.status(state_path=tmp / "state.json", home=home, log_dir=logs)["agent"] or {}
    out.append(("status shows the agent's engine, program, hub and options",
                a.get("engine") == "python" and a.get("program") == py
                and a.get("hub") == str(hub.resolve()) and a.get("api") is True
                and a.get("include_contact") is False))
    r, _ = install(("eperm", at))
    out.append(("an eperm first run names Full Disk Access", not r["ok"]
                and "Full Disk Access" in r["detail"]))
    r, _ = install(("error", at))
    out.append(("an error first run does not blame Full Disk Access", not r["ok"]
                and "Full Disk Access" not in r["detail"] and "with errors" in r["detail"]))
    r, _ = install(("ok", early))
    out.append(("a stamp older than the kickstart second is not taken as the first run",
                not r["ok"] and "no run finished" in r["detail"]))
    r, _ = install(None)
    out.append(("no run at all reports where to look", not r["ok"]
                and "no run finished" in r["detail"]))
    r, cmds = install(("ok", at), engine="rsync", api=True)
    out.append(("the rsync engine refuses --api before writing anything",
                not r["ok"] and "--engine python" in r["detail"] and cmds == []))
    out.append(("install-agent and uninstall-agent refuse outside macOS",
                not m.install_agent(hub, platform="linux")["ok"]
                and not m.uninstall_agent(platform="linux")["ok"]))
    m._write_plist(target, m.build_plist(hub, "rsync", python=py, log_dir=logs, home=home), logs)
    a = m.status(state_path=tmp / "state.json", home=home, log_dir=logs)["agent"] or {}
    out.append(("status shows an rsync agent's hub, not its Profile folder",
                a.get("engine") == "rsync" and a.get("hub") == str(hub.resolve())
                and a.get("program") == "/bin/bash"))
    for label, raw in (("truncated XML", b'<?xml version="1.0"?><plist version="1.0"><dict>'),
                       ("a list root", plistlib.dumps(["/bin/bash"]))):
        target.write_bytes(raw)
        try:
            bad = m.status(state_path=tmp / "state.json", home=home, log_dir=logs)["agent"]
            good = bool(bad.get("error"))
        except Exception:  # noqa: BLE001 - the pin is that status never raises
            good = False
        out.append((f"status reports a plist with {label} instead of raising", good))
    un = m.uninstall_agent(runner=lambda c: Done(), home=home, uid=501, platform="darwin")
    out.append(("uninstall-agent removes the plist and leaves the hub alone",
                un["ok"] and not target.exists() and hub.exists()))
    m.write_stamp("ok", "rsync", logs, "2026-01-02T03:04:05Z")
    s = m.read_stamp(logs)
    (logs / "bad").mkdir()
    out.append(("the stamp round-trips, and a damaged or unknown-status stamp reads as none",
                s == {"at": "2026-01-02T03:04:05Z", "status": "ok", "engine": "rsync",
                      "epoch": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc).timestamp()}
                and m.read_stamp(logs / "bad") is None
                and (atomic_io.atomic_write_text(logs / m.STAMP_NAME, "x maybe python\n")
                     or m.read_stamp(logs) is None)))
    saved_os = m.os
    m.os = _StatEperm
    try:
        blocked = m.hub_status("/Users/x/Library/CloudStorage/hub")
    finally:
        m.os = saved_os
    out.append(("a hub macOS refuses to read stamps eperm; a missing one stamps error",
                blocked == "eperm" and m.hub_status(tmp / "nope") == "error"
                and m.hub_status(None) == "error"))
    return out


def _pins_cli(m, tmp) -> list:
    import contextlib
    import io
    tok = _part("fixture-", "access", "_token")
    ctx, hub, logs = tmp / "ctx", tmp / "hub", tmp / "logs"
    ctx.mkdir()
    hub.mkdir()
    _put(ctx / "voice-profile.local.json", '{"tone": "warm"}')
    saved = (m.STATE_PATH, m.CONTEXT_DIR, m.LOG_DIR, m.da._default_transport, m.pd._api_token)
    drive = _FakeDrive(tok)
    out = []

    def call(*argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            rc = m.main(list(argv))
        return rc, buf.getvalue()
    try:
        m.STATE_PATH, m.CONTEXT_DIR, m.LOG_DIR = ctx / "state.local.json", ctx, logs
        m.da._default_transport = drive
        m.pd._api_token = lambda transport=None, **k: (tok, None)
        rc, _ = call("sync", "--api", "--quiet", "--hub", str(hub))
        st = m.read_stamp(logs)
        out.append(("CLI: sync --api exits 0, writes the Doc through drive_api's transport, logs "
                    "and stamps ok", rc == 0 and drive.files and st and st["status"] == "ok"
                    and "INFO run ok:" in (logs / "profile-mirror.log").read_text("utf-8")))
        rc, text = call("status", "--json")
        j = json.loads(text)
        out.append(("CLI: status --json shows the stamp and the Doc, and no agent in a fresh home",
                    rc == 0 and j["stamp"]["status"] == "ok" and j["doc"].get("id")
                    and j["agent"] is None))
        good = ctx / "voice-profile.local.json"
        bad = ctx / "setup-context.local.json"
        _put(bad, json.dumps({"notes": "my password is " + _part("Hunter2", "Hunter2x")}))
        out.append(("CLI: check-file exits 0 on an accepted file, 1 on a refused one, 2 on an "
                    "unreadable one", call("check-file", str(good))[0] == 0
                    and call("check-file", str(bad))[0] == 1
                    and call("check-file", str(ctx / "absent.json"))[0] == 2))
        rc, _ = call("sync", "--quiet", "--hub", str(tmp / "no-such-hub"))
        st0 = (m.read_stamp(logs) or {}).get("status")
        text0 = (logs / "profile-mirror.log").read_text("utf-8")
        from handoff import watcher as w
        blocked_hub = "/Users/x/Library/CloudStorage/GoogleDrive-x/My Drive/Creator OS"
        saved_os, saved_cfg = m.os, w.load_hub_config
        try:
            m.os = _StatEperm
            rc1, _ = call("sync", "--quiet", "--hub", blocked_hub)
            st1 = (m.read_stamp(logs) or {}).get("status")
            w.load_hub_config = lambda: {"local_mirror": blocked_hub}
            rc2, _ = call("sync", "--quiet")
            st2 = (m.read_stamp(logs) or {}).get("status")
            m.os = saved_os
            w.load_hub_config = lambda: {"local_mirror": "/tmp/bad\x00hub"}
            try:
                rc3, _ = call("sync", "--quiet")
            except Exception:  # noqa: BLE001 - the pin is that nothing escapes main
                rc3 = None
        finally:
            m.os, w.load_hub_config = saved_os, saved_cfg
        text = (logs / "profile-mirror.log").read_text("utf-8")
        out.append(("CLI: a hub macOS will not let the job read stamps eperm, through --hub and "
                    "through the saved hub", rc1 == 2 and st1 == "eperm" and rc2 == 2
                    and st2 == "eperm"
                    and "INFO run eperm: the Drive hub folder could not be read" in text))
        out.append(("CLI: a saved hub path that cannot be stat'ed still exits 2", rc3 == 2))
        out.append(("CLI: sync with no reachable hub exits 2, logs a run summary and stamps error",
                    rc == 2 and st0 == "error"
                    and "INFO run error: the Drive hub folder could not be read" in text0))
    finally:
        m.STATE_PATH, m.CONTEXT_DIR, m.LOG_DIR, m.da._default_transport, m.pd._api_token = saved
        lg = logging.getLogger("profile_mirror")
        for h in list(lg.handlers):
            if str(getattr(h, "baseFilename", "")).startswith(str(tmp)):
                lg.removeHandler(h)
                h.close()
    return out


# P101: the script group runs tools/profile-mirror.sh, the macOS launchd agent's job, under
# /bin/bash. Windows has no such agent (the mirror runs by hand there) and no /bin/bash, so the
# group and its mutation cases do not run on Windows; the selftest says so instead of passing them.
SCRIPT_PINS_RUN = os.name != "nt"


def _pins_script(m, tmp, script=None) -> list:
    script = Path(script or m.RSYNC_SCRIPT)
    text = script.read_text(encoding="utf-8")
    out = []
    allow = re.search(r"^ALLOWLIST=\(\s*(.*?)\)", text, re.S | re.M)
    out.append(("the script copies exactly PROFILE_ALLOWLIST",
                allow is not None and tuple(allow.group(1).split()) == m.PROFILE_ALLOWLIST))
    out.append(("the script refuses the credential file names",
                all(n in text for n in m.REFUSED_NAMES)))
    bash = "/bin/bash"
    out.append(("the script parses (bash -n)",
                subprocess.run([bash, "-n", str(script)], capture_output=True).returncode == 0))
    standin, eperm = tmp / "rsync-standin", tmp / "rsync-eperm"
    standin.write_text('#!/bin/bash\n# stand-in for: rsync -t SRC DEST\ncp -p "$2" "$3"\n',
                       encoding="utf-8")
    eperm.write_text('#!/bin/bash\necho "rsync: open \\"$2\\" failed: Operation not permitted '
                     '(1)" >&2\nexit 23\n', encoding="utf-8")
    standin.chmod(0o755)
    eperm.chmod(0o755)
    home, src, dest = tmp / "home", tmp / "src", tmp / "hub" / "Profile"
    src.mkdir()
    dest.mkdir(parents=True)
    vp, cc = "voice-profile.local.json", "channel-context.local.json"
    _put(src / vp, '{"tone": "warm"}')
    _put(src / cc, '{"niche": "home decor"}')
    log = home / "Library" / "Logs" / "CreatorOS" / "profile-mirror.log"
    stamp = log.parent / m.STAMP_NAME

    def run(dst=dest, rsync=standin, py=sys.executable):
        env = dict(os.environ, HOME=str(home), PROFILE_MIRROR_RSYNC=str(rsync),
                   PROFILE_MIRROR_ROOT=str(m.ROOT))
        argv = [bash, str(script), str(src), str(dst)] + ([py] if py else [])
        before = log.read_text("utf-8") if log.exists() else ""
        p = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=120)
        after = log.read_text("utf-8") if log.exists() else ""
        new = after[len(before):] if after.startswith(before) else after
        st = stamp.read_text("utf-8").split() if stamp.exists() else []
        return p.returncode, new, st[1:]

    rc, new, st = run()
    out.append(("R1: the script copies, logs each copy and a summary, and stamps ok",
                rc == 0 and (dest / vp).read_text("utf-8") == '{"tone": "warm"}'
                and f"INFO copied {vp}" in new and "run ok: copied 2" in new
                and st == ["ok", "rsync"]))
    rc, new, st = run()
    out.append(("R2: an unchanged run logs unchanged, not copied",
                rc == 0 and "unchanged 2" in new and "copied " + vp not in new))
    _put(src / vp, '{"tone": "warmer"}')
    rc, new, st = run(rsync=eperm)
    out.append(("R3: rsync's 'Operation not permitted' stamps eperm and exits 1",
                rc == 1 and st == ["eperm", "rsync"]))
    log.write_text("x" * 512_000, encoding="utf-8")
    rc, new, st = run()
    rotated = log.with_name(log.name + ".1")
    out.append(("R4: a log past 512000 bytes rotates to .1",
                rotated.exists() and rotated.stat().st_size >= 512_000
                and log.stat().st_size < 10_000))
    rc, new, st = run(dst=tmp / "no-hub" / "Profile")
    out.append(("R5: a missing Drive folder is logged and stamps error",
                rc == 1 and "Drive folder not found" in new and st == ["error", "rsync"]))
    _put(src / "setup-context.local.json", 
        json.dumps({"notes": "my password is " + _part("Hunter2", "Hunter2x")}))
    rc, new, st = run()
    out.append(("R6: the content check refuses a pasted credential, which is not copied",
                rc == 1 and "refused setup-context.local.json" in new
                and not (dest / "setup-context.local.json").exists()
                and st == ["error", "rsync"]))
    (src / "setup-context.local.json").unlink()
    rc, new, st = run(py=None)
    out.append(("R7: without a Python the run says file contents were not checked",
                "file contents are not checked" in new))
    return out


_PIN_GROUPS = {"refuse": _pins_refuse, "doc": _pins_doc, "sync": _pins_sync,
               "agent": _pins_agent, "cli": _pins_cli, "script": _pins_script}

# Falsifying mutations, chosen by a reviewer who did not write the pins (docs/AUDIT-PROTOCOL.md):
# (label, pin group, anchor, replacement). A "script" anchor applies to tools/profile-mirror.sh;
# every other anchor applies to this file above _SELFTEST_MARK and must occur there exactly once.
# The named pin group must fail on every mutant.
_MUTANTS = (
    ('refuse: invalid JSON is decoded as nothing and scanned instead of refused', 'refuse', '        return "not valid JSON (fix it in Creator OS; nothing was copied)"', '        doc = None'),
    ('refuse: a lenient decoder strips trailing commas before json.loads', 'refuse', '        doc = json.loads(text)', '        doc = json.loads(re.sub(r",\\s*([}\\]])", r"\\1", text))'),
    ('refuse: invalid JSON is accepted outright', 'refuse', '        return "not valid JSON (fix it in Creator OS; nothing was copied)"', '        return None'),
    ('cred key: camelCase keys are no longer split into words', 'refuse', '    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).lower().replace("-", "_")', '    words = key.lower().replace("-", "_")'),
    ('cred key: the value length floor rises from 8 to 16', 'refuse', 'len(s.strip()) >= 8', 'len(s.strip()) >= 16'),
    ('cred key: _CRED_KEY_RE must match the whole key, not its last word', 'refuse', '    r"(?:^|_)(?:api_?keys?|', '    r"^(?:api_?keys?|'),
    ("cred key: list items lose their list's key", 'refuse', '            yield from _scalars(v, key)', '            yield from _scalars(v, None)'),
    ('cred key: numbers are no longer scanned as scalars', 'refuse', '    elif isinstance(node, (str, int, float)) and not isinstance(node, bool):', '    elif isinstance(node, str):'),
    ('cred key: pwd dropped from _CRED_KEY_RE', 'refuse', '|private_?keys?|passwords?|passwd|pwd"', '|private_?keys?|passwords?|passwd"'),
    ('local patterns: GOCSPX body needs 40 characters', 'refuse', 'r"\\bGOCSPX-[A-Za-z0-9_-]{20,}"', 'r"\\bGOCSPX-[A-Za-z0-9_-]{40,}"'),
    ('local patterns: ya29 token expects a dash, not a dot', 'refuse', 'r"\\bya29\\.[0-9A-Za-z_-]{20,}"', 'r"\\bya29-[0-9A-Za-z_-]{20,}"'),
    ('local patterns: Stripe sk_test_ prefix dropped', 'refuse', 'r"\\b[spr]k_test_[A-Za-z0-9]{16,}"', 'r"\\b[pr]k_test_[A-Za-z0-9]{16,}"'),
    ('local patterns: the scan skips the first pattern (GOCSPX)', 'refuse', '    hits |= {pid for pid, rx in _LOCAL_PATTERNS if rx.search(text)}', '    hits |= {pid for pid, rx in _LOCAL_PATTERNS[1:] if rx.search(text)}'),
    ('prose: _secret_shaped ignores the symbol alternative', 'refuse', '                     or any(c in _CRED_SYMBOLS for c in val)))', '                     or False))'),
    ("prose: 'is'/'was' no longer joins the word and the value", 'refuse', '(?:(?:is|was)[ \\t]+|[:=][ \\t]*)?', '(?:[:=][ \\t]*)?'),
    ('prose: _secret_shaped needs one letter case, not both', 'refuse', '(re.search(r"[a-z]", val) and re.search(r"[A-Z]", val))', '(re.search(r"[a-z]", val) or re.search(r"[A-Z]", val))'),
    ('prose: api key no longer matches with an underscore', 'refuse', '|api[ _-]?key|', '|api[ -]?key|'),
    ('prose: passcode dropped from the credential words', 'refuse', '(?:password|passwd|passphrase|passcode|pwd"', '(?:password|passwd|passphrase|pwd"'),
    ('doc: a trashed Doc is kept and updated', 'doc', '        if err or meta.get("trashed"):', '        if err:'),
    ('doc: a 404 on the write is read as a 410', 'doc', '        if err and err.startswith("HTTP 404"):', '        if err and err.startswith("HTTP 410"):'),
    ('doc: a 404 on the write fails the Doc instead of creating one', 'doc', '            doc_id, meta = None, None', '            return {"action": "failed", "error": err, "placed": placed}'),
    ('doc: a name match is adopted only when unique', 'doc', '        if found:\n            doc_id, adopted, placed', '        if len(found) == 1:\n            doc_id, adopted, placed'),
    ('doc: an adopted Doc is reported as updated', 'doc', 'doc_id, adopted, placed = found[0]["id"], True, "found"', 'doc_id, adopted, placed = found[0]["id"], False, "found"'),
    ("doc: the search reads the v2 'items' field", 'doc', '        found = data.get("files", [])', '        found = data.get("items", [])'),
    ('doc: duplicates are reported only above two', 'doc', '        if len(found) > 1:', '        if len(found) > 2:'),
    ('doc: a new Doc always carries a parents key (empty when unknown)', 'doc', '        if parent_id:\n            meta["parents"] = [parent_id]', '        meta["parents"] = [parent_id] if parent_id else []'),
    ('doc: Profile is looked up only when the hub lookup failed', 'doc', '        if not err:\n            parent_id, err = da.find_folder', '        if err:\n            parent_id, err = da.find_folder'),
    ('doc: the Doc goes into the hub root, not Profile', 'doc', '            parent_id, err = da.find_folder(token, HUB_SUBDIR, transport, parent_id=root_id)', '            parent_id, err = root_id, None'),
    ('doc: a created Doc is always recorded as my-drive', 'doc', '        action, placed = "created", ("profile" if parent_id else "my-drive")', '        action, placed = "created", "my-drive"'),
    ('doc: the move-it note is logged for the wrong placement', 'doc', '        if placed == "my-drive":', '        if placed == "moved":'),
    ('doc: edits in Drive are never detected', 'doc', '            edited = meta.get("modifiedTime") != doc["modified_time"]', '            edited = False'),
    ('doc: move detection runs only when no parents were recorded', 'doc', '            if doc.get("parents") is not None and meta.get("parents") != doc["parents"]:', '            if doc.get("parents") is None and meta.get("parents") != doc["parents"]:'),
    ('doc: the pre-P99-2 baseline records no modifiedTime', 'doc', '                doc.update(modified_time=meta.get("modifiedTime"), parents=meta.get("parents"))', '                doc.update(modified_time=None, parents=meta.get("parents"))'),
    ('doc: unchanged text skips the write even after a Drive edit', 'doc', '            if doc.get("sha256") == sha and not edited:', '            if doc.get("sha256") == sha:'),
    ('doc: a moved Doc is recorded as found', 'doc', '                placed = "moved"', '                placed = "found"'),
    ('sync: Drive-copy text is read but not used', 'sync', 'texts[name] = data.decode("utf-8-sig")', 'pass'),
    ('sync: an unreadable Drive copy is skipped instead of holding the Doc', 'sync', '            return None, f"Doc held: cannot read the Drive copy of {name}: {exc}", \\\n                exc.errno == errno.EPERM', '            continue'),
    ('sync: Drive copies are looked up in the hub root instead of Profile', 'sync', '            texts, held, held_eperm = _doc_texts(names, local, dest)', '            texts, held, held_eperm = _doc_texts(names, local, Path(hub))'),
    ('record: a run with the Doc off counts as a change', 'sync', '        doc_action not in (None, "unchanged")', '        doc_action != "unchanged"'),
    ('record: history keeps RUN_HISTORY + 1 runs', 'sync', '        state["runs"] = (state["runs"] + [summary])[-RUN_HISTORY:]', '        state["runs"] = (state["runs"] + [summary])[-RUN_HISTORY - 1:]'),
    ('record: last_run is written only when something changed', 'sync', '    state["last_run"] = summary\n    if changed:\n        state["runs"]', '    if changed:\n        state["last_run"] = summary\n        state["runs"]'),
    ('record: the summary keeps lists instead of counts', 'sync', '    summary = {k: (len(v) if isinstance(v, list) else v) for k, v in res.items()', '    summary = {k: v for k, v in res.items()'),
    ('status: a refused file no longer makes the run an error', 'sync', '"error" if (res["errors"] or res["refused"]) else "ok"', '"error" if res["errors"] else "ok"'),
    ('status: failed() tests EACCES instead of EPERM', 'sync', 'getattr(exc, "errno", None) == errno.EPERM', 'getattr(exc, "errno", None) == errno.EACCES'),
    ('status: the broad except is removed, so an exception escapes sync after the finally', 'sync', '    except Exception as exc:  # noqa: BLE001 - recorded below, so the run is logged and stamped\n        failed("unexpected error", exc)\n        log.exception("the run stopped early")\n', ''),
    ('status: an EPERM hold of the Doc does not set the eperm flag', 'sync', '                flags["eperm"] = flags["eperm"] or held_eperm', '                flags["eperm"] = flags["eperm"]'),
    ('status: errors outrank eperm', 'sync', '    res["status"] = "eperm" if eperm else "error" if (res["errors"] or res["refused"]) else "ok"', '    res["status"] = "error" if (res["errors"] or res["refused"]) else "eperm" if eperm else "ok"'),
    ('install-agent: the old stamp is not removed before kickstart', 'agent', '(log_dir / STAMP_NAME).unlink()', 'pass'),
    ('install-agent: a stamp one second before the kickstart is accepted', 'agent', '        if st and st["epoch"] >= started:', '        if st and st["epoch"] >= started - 1:'),
    ('install-agent: started keeps sub-second precision, so a same-second stamp is ignored', 'agent', '    started = int(now())', '    started = now()'),
    ('install-agent: an error stamp also names Full Disk Access', 'agent', '            if st["status"] == "eperm":', '            if st["status"] in ("eperm", "error"):'),
    ('build_plist: the interpreter is resolved through the venv symlink', 'agent', '    py = os.path.abspath(str(python or env_paths.app_python(Path(root))))', '    py = os.path.realpath(str(python or env_paths.app_python(Path(root))))'),
    ('build_plist: --include-contact-profile follows the api flag', 'agent', '        args += ["--include-contact-profile"] if include_contact else []', '        args += ["--include-contact-profile"] if api else []'),
    ('build_plist: HOME ignores the home argument', 'agent', '            "EnvironmentVariables": {"HOME": str(home or Path.home())},', '            "EnvironmentVariables": {"HOME": str(Path.home())},'),
    ('build_plist: the rsync engine gets a bare python3 for check-file', 'agent', 'str(Path(hub) / HUB_SUBDIR), py]', 'str(Path(hub) / HUB_SUBDIR), "python3"]'),
    ('build_plist: --api is never written into the job', 'agent', '        args += ["--api"] if api else []\n', ''),
    ('hub_status: tests EACCES instead of EPERM', 'agent', '            if exc.errno == errno.EPERM:\n                return "eperm"', '            if exc.errno == errno.EACCES:\n                return "eperm"'),
    ('hub_status: catches FileNotFoundError where PermissionError belongs', 'agent', '        except PermissionError as exc:', '        except FileNotFoundError as exc:'),
    ('hub_status: defaults to eperm', 'agent', '            pass\n    return "error"', '            pass\n    return "eperm"'),
    ('cli: check-file exits 2 on a refused file', 'cli', '        return 1 if why else 0', '        return 2 if why else 0'),
    ('cli: check-file exits 1 on an unreadable file', 'cli', '            print(f"cannot read: {exc}")\n            return 2', '            print(f"cannot read: {exc}")\n            return 1'),
    ('cli: the no-hub stamp is written for check instead of sync', 'cli', '        if a.command == "sync":', '        if a.command == "check":'),
    ('cli: no hub exits 1', 'cli', '        print(f"profile mirror: {note}", file=sys.stderr)\n        return 2', '        print(f"profile mirror: {note}", file=sys.stderr)\n        return 1'),
    ('script: the cmp test is inverted', 'script', 'if [ -f "$DEST/$f" ] && cmp -s "$SRC/$f" "$DEST/$f"; then', 'if [ -f "$DEST/$f" ] && ! cmp -s "$SRC/$f" "$DEST/$f"; then'),
    ('script: an unchanged file is still copied (continue dropped)', 'script', '    unchanged=$((unchanged + 1)); continue', '    unchanged=$((unchanged + 1))'),
    ('script: cmp compares the source with itself', 'script', 'cmp -s "$SRC/$f" "$DEST/$f"', 'cmp -s "$SRC/$f" "$SRC/$f"'),
    ('script: rotation needs more than MAX_LOG_BYTES', 'script', '-ge "$MAX_LOG_BYTES"', '-gt "$MAX_LOG_BYTES"'),
    ('script: the rotation limit gains a zero', 'script', 'MAX_LOG_BYTES=512000', 'MAX_LOG_BYTES=5120000'),
    ('script: the log rotates to .2', 'script', '  mv -f "$LOG" "$LOG.1"', '  mv -f "$LOG" "$LOG.2"'),
    ("script: eperm matches 'Permission denied' instead of 'Operation not permitted'", 'script', 'case "$out" in *"Operation not permitted"*) eperm=1 ;; esac', 'case "$out" in *"Permission denied"*) eperm=1 ;; esac'),
    ('script: errors outrank eperm in the run status', 'script', 'if [ "$eperm" = 1 ]; then st=eperm; elif [ $((errors + refused)) -gt 0 ]; then st=error; else st=ok; fi', 'if [ $((errors + refused)) -gt 0 ]; then st=error; elif [ "$eperm" = 1 ]; then st=eperm; else st=ok; fi'),
    ('script: the final stamp always says ok', 'script', 'stamp "$st"\nif [ "$st" = ok ]; then exit 0; fi', 'stamp ok\nif [ "$st" = ok ]; then exit 0; fi'),
    ('script: the stamp names the python engine', 'script', 'printf \'%s %s rsync\\n\' "$(now)" "$1"', 'printf \'%s %s python\\n\' "$(now)" "$1"'),
    ("script: check-file's exit status is inverted", 'script', 'if [ -n "$PY" ] && ! why=$(', 'if [ -n "$PY" ] && why=$('),
    ('script: the content check runs only when no Python is given', 'script', 'if [ -n "$PY" ] && ! why=$(', 'if [ -z "$PY" ] && ! why=$('),
    ('script: a refused file is still copied (continue dropped)', 'script', 'log WARNING "refused $f: $why"; refused=$((refused + 1)); continue', 'log WARNING "refused $f: $why"; refused=$((refused + 1))'),
    ('script: no warning when contents go unchecked', 'script', '  log WARNING "file contents are not checked (no Python given); names are"', '  :'),
    ('refuse: passphrase dropped from _PASS_KEY_RE', 'refuse', '|pwd|passphrases?)$")', '|pwd)$")'),
    ('refuse: a value with spaces is never refused under a credential key (_PASS_KEY_RE unused)', 'refuse', '(_PASS_KEY_RE.search(_key_words(key)) or not re.search(r"\\s", s.strip()))', '(not re.search(r"\\s", s.strip()))'),
    ('refuse: spaces are allowed under every credential key', 'refuse', '_PASS_KEY_RE.search(_key_words(key)) or not', 'True or not'),
    ('refuse: credentials joins the password-type keys', 'refuse', '|pwd|passphrases?)$")', '|pwd|passphrases?|credentials?)$")'),
    ('cred key: exactly 8 characters is no longer enough', 'refuse', 'len(s.strip()) >= 8', 'len(s.strip()) > 8'),
    ('refuse: _key_words returns the key unchanged', 'refuse', '    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).lower().replace("-", "_")', '    return key'),
    ('refuse: _key_words keeps the letter case', 'refuse', '    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).lower().replace("-", "_")', '    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).replace("-", "_")'),
    ('refuse: _key_words does not split camelCase', 'refuse', '    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).lower().replace("-", "_")', '    return key.lower().replace("-", "_")'),
    ('refuse: _key_words keeps hyphens', 'refuse', '    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).lower().replace("-", "_")', '    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).lower()'),
    ('refuse: _PASS_KEY_RE reads the raw key', 'refuse', '_PASS_KEY_RE.search(_key_words(key))', '_PASS_KEY_RE.search(key)'),
    ('refuse: _PASS_KEY_RE must match the whole key', 'refuse', '_PASS_KEY_RE = re.compile(r"(?:^|_)', '_PASS_KEY_RE = re.compile(r"^'),
    ('refuse: pwd dropped from _PASS_KEY_RE', 'refuse', '|passwd|pwd|passphrases?)$")', '|passwd|passphrases?)$")'),
    ('refuse: password and passwd dropped from _PASS_KEY_RE', 'refuse', '(?:passwords?|passwd|pwd|passphrases?)$")', '(?:pwd|passphrases?)$")'),
    ("status: an rsync agent's hub is its Profile folder again", 'agent', '"hub": (str(Path(args[3]).parent) if rsync', '"hub": (args[3] if rsync'),
    ('status: the rsync hub is read from the source folder argument', 'agent', 'str(Path(args[3]).parent)', 'str(Path(args[2]).parent)'),
    ("status: the rsync hub is the Profile folder's grandparent", 'agent', 'str(Path(args[3]).parent)', 'str(Path(args[3]).parent.parent)'),
    ('status: the rsync hub needs more than 5 arguments', 'agent', 'if rsync and len(args) > 3', 'if rsync and len(args) > 5'),
    ('status: the rsync hub is read from the interpreter argument', 'agent', 'str(Path(args[3]).parent)', 'str(Path(args[-1]).parent)'),
    ('cli: the no-hub run summary line is dropped', 'cli', '                log.info("run %s: the Drive hub folder could not be read", hub_state)\n', ''),
    ('cli: the no-hub run summary is logged as a warning', 'cli', 'log.info("run %s: the Drive hub folder could not be read"', 'log.warning("run %s: the Drive hub folder could not be read"'),
    ('cli: the no-hub run summary names the note instead of the status', 'cli', '"run %s: the Drive hub folder could not be read", hub_state)', '"run %s: the Drive hub folder could not be read", note)'),
    ('cli: the no-hub run summary loses its wording', 'cli', '"run %s: the Drive hub folder could not be read"', '"run %s: no hub"'),
    ('cli: the saved hub is never read', 'cli', '        return w.load_hub_config().get("local_mirror")', '        return None'),
    ('cli: the saved hub is read from the wrong key', 'cli', '.get("local_mirror")\n    except Exception:', '.get("hub")\n    except Exception:'),
    ('cli: the no-hub summary always says error', 'cli', '"run %s: the Drive hub folder could not be read", hub_state)', '"run %s: the Drive hub folder could not be read", "error")'),
    ('cli: the no-hub stamp always says error', 'cli', '                write_stamp(hub_state, "python")', '                write_stamp("error", "python")'),
    ('cli: --hub is ignored when classifying a missing hub', 'cli', 'hub_status(a.hub or _hub_config_mirror())', 'hub_status(_hub_config_mirror())'),
    ('doc: Profile is looked up anywhere, not under the hub', 'doc', 'da.find_folder(token, HUB_SUBDIR, transport, parent_id=root_id)', 'da.find_folder(token, HUB_SUBDIR, transport)'),
)


def _mutant_module(source: str):
    import types
    mod = types.ModuleType("profile_mirror_mutant")
    mod.__file__ = __file__
    exec(compile(source, "<profile_mirror mutant>", "exec"), mod.__dict__)
    return mod


def _run_mutants(tmp: Path) -> list:
    """The labels of mutants their pin group did not catch (or whose anchor is not unique)."""
    head, mark, tail = Path(__file__).read_text(encoding="utf-8").partition(_SELFTEST_MARK)
    script = RSYNC_SCRIPT.read_text(encoding="utf-8")
    me = sys.modules[__name__]
    survivors = []
    for i, (label, group, old, new) in enumerate(_MUTANTS):
        sub = tmp / f"mutant-{i}"
        sub.mkdir(parents=True)
        if group == "script":
            if not SCRIPT_PINS_RUN:
                continue
            if script.count(old) != 1:
                survivors.append(f"{label} (anchor not found exactly once)")
                continue
            path = sub / "profile-mirror.sh"
            path.write_text(script.replace(old, new), encoding="utf-8")
            try:
                results = _pins_script(me, sub, script=path)
            except Exception:  # noqa: BLE001 - a mutant that crashes its pins is caught
                results = [("crashed", False)]
        else:
            if head.count(old) != 1:
                survivors.append(f"{label} (anchor not found exactly once)")
                continue
            try:
                results = _PIN_GROUPS[group](_mutant_module(head.replace(old, new) + mark + tail),
                                             sub)
            except Exception:  # noqa: BLE001 - a mutant that crashes its pins is caught
                results = [("crashed", False)]
        if all(c for _, c in results):
            survivors.append(label)
    return survivors


def _snapshot(paths) -> list:
    snap = []
    for p in paths:
        try:
            snap.append(sorted((e.name, e.stat().st_mtime_ns, e.stat().st_size)
                               for e in p.iterdir()))
        except OSError:
            snap.append(None)
    return snap


def _no_network(method, url, headers=None, data=None, timeout=30):
    return 0, b"selftest: no network"


def selftest() -> int:
    import shutil
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    real_home = Path.home()
    watched = [real_home / "Library" / "LaunchAgents", real_home / "Library" / "Logs" / "CreatorOS"]
    before = _snapshot(watched)
    g = globals()
    saved = {k: g[k] for k in ("STATE_PATH", "CONTEXT_DIR", "LOG_DIR")}
    saved_home = os.environ.get("HOME")
    saved_transport, saved_token = da._default_transport, pd._api_token
    tmp = Path(tempfile.mkdtemp(prefix="profile-mirror-selftest-"))
    me = sys.modules[__name__]
    try:
        os.environ["HOME"] = str(tmp / "home")
        g.update(STATE_PATH=tmp / "default-state.local.json", CONTEXT_DIR=tmp / "default-ctx",
                 LOG_DIR=tmp / "default-logs")
        da._default_transport = _no_network
        pd._api_token = lambda transport=None, **k: (None, "selftest: no credential")
        for group, pins in _PIN_GROUPS.items():
            if group == "script" and not SCRIPT_PINS_RUN:
                print("  [skip] script: the macOS launchd helper script does not run on Windows")
                continue
            sub = tmp / group
            sub.mkdir()
            for name, cond in pins(me, sub):
                ok(f"{group}: {name}", cond)
        survivors = _run_mutants(tmp / "mutants")
        if survivors:
            print(f"  [note] mutations the pins did not catch: {survivors}")
        ran = [r for r in _MUTANTS if r[1] != "script" or SCRIPT_PINS_RUN]
        ok(f"each of {len(ran)} committed mutations fails its pin group"
           + ("" if len(ran) == len(_MUTANTS) else
              f" ({len(_MUTANTS) - len(ran)} script cases not run on Windows)"),
           ran and not survivors)
    finally:
        g.update(saved)
        if saved_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = saved_home
        da._default_transport, pd._api_token = saved_transport, saved_token
        shutil.rmtree(tmp, ignore_errors=True)
    ok("the real ~/Library/LaunchAgents and ~/Library/Logs/CreatorOS are as they were",
       _snapshot(watched) == before)
    passed = sum(1 for _, c in checks if c)
    print(f"profile_mirror selftest: {passed}/{len(checks)} passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
