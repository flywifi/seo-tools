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
  the edit). A file refuse() rejects is never copied.
- sync --api (opt-in, the drive_api_polling credential): also create or update one Google Doc,
  "About me and my voice", in the hub's Profile folder, rendered from the same files. The Doc id
  is remembered so later runs update the same Doc. drive.file only sees folders this app created
  or opened, so a folder the API cannot find is reported and the Doc is skipped; the files are
  still copied.
- install-agent / uninstall-agent: a user-scoped launchd agent (~/Library/LaunchAgents) that runs
  the sync at minutes 7, 22, 37 and 52 of each hour. macOS only.

State: pipeline/user-context/profile-mirror-state.local.json (gitignored), written atomically.
Log: ~/Library/Logs/CreatorOS/profile-mirror.log (rotating). docs/PROFILE-MIRROR.md is the guide.

Usage:
  python3 tools/profile_mirror.py sync [--hub PATH] [--api] [--include-contact-profile] [--quiet]
  python3 tools/profile_mirror.py check [--hub PATH]
  python3 tools/profile_mirror.py status
  python3 tools/profile_mirror.py install-agent [--hub PATH] [--engine python|rsync]
  python3 tools/profile_mirror.py uninstall-agent
  python3 tools/profile_mirror.py --selftest
"""
from __future__ import annotations

import argparse
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
RSYNC_SCRIPT = ROOT / "tools" / "profile-mirror.sh"
RUN_MINUTES = (7, 22, 37, 52)
RUN_HISTORY = 20

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


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def credential_ids() -> frozenset:
    """The secret_scan pattern ids that refuse a copy: every pattern but the personal-detail ones."""
    return frozenset(pid for pid, _ in secret_scan.PATTERNS) - _NON_CREDENTIAL_IDS


def refuse(name: str, data: bytes) -> str | None:
    """Why a file must not be copied into Drive, or None. Refused: a credential file name, a
    suffix on secret_scan.FORBIDDEN_DATA_SUFFIXES, an .env name, bytes that are not UTF-8 text,
    and text in which secret_scan finds a credential pattern."""
    low = name.lower()
    if low in REFUSED_NAMES:
        return "a credential file"
    if _ENV_NAME_RE.match(low) or low.endswith(tuple(secret_scan.FORBIDDEN_DATA_SUFFIXES)):
        return "a file type that never leaves this computer"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "not UTF-8 text"
    hits = sorted({f["pattern_id"] for f in secret_scan.scan_text(text, f"pipeline/user-context/{name}")
                   if f["pattern_id"] in credential_ids()})
    if hits:
        return "looks like it holds a credential (" + ", ".join(hits) + ")"
    return None


def load_state(path=STATE_PATH) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("schema", 1)
    data.setdefault("files", {})
    data.setdefault("doc", {})
    data.setdefault("runs", [])
    return data


def save_state(state, path=STATE_PATH) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    atomic_io.atomic_write_text(path, json.dumps(state, indent=2, sort_keys=True) + "\n")


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


def sync_doc(token, markdown: str, state: dict, transport=None, now=None) -> dict:
    """Create or update the Google Doc. Returns {"action", "error"}; changes state["doc"]."""
    doc = state.setdefault("doc", {})
    sha = _sha_bytes(markdown.encode("utf-8"))
    if doc.get("id") and doc.get("sha256") == sha:
        return {"action": "unchanged", "error": None}
    root_id, err = da.find_folder(token, HUB_FOLDER, transport)
    if not err:
        parent_id, err = da.find_folder(token, HUB_SUBDIR, transport, parent_id=root_id)
    if err:
        return {"action": "skipped", "error": f"Doc skipped: {err}"}
    body = markdown.encode("utf-8")
    if doc.get("id"):
        ok, err = pd._update_doc(token, doc["id"], body, transport)
        if ok:
            doc.update(sha256=sha, updated_at=now or _utcnow())
            return {"action": "updated", "error": None}
        if not str(err).startswith("HTTP 404"):
            return {"action": "failed", "error": err}
    new_id, err = pd._create_doc(token, parent_id, DOC_NAME, body, transport)
    if err:
        return {"action": "failed", "error": err}
    state["doc"] = {"id": new_id, "sha256": sha, "updated_at": now or _utcnow()}
    return {"action": "created", "error": None}


def sync(hub, *, include_contact=False, api=False, token=None, transport=None,
         state_path=STATE_PATH, src_dir=CONTEXT_DIR, now=None, log=None) -> dict:
    """One-way copy of the allowlisted context files into <hub>/Profile/, and, with api, the Doc."""
    log = log or logging.getLogger("profile_mirror")
    now = now or _utcnow()
    state = load_state(state_path)
    dest = Path(hub) / HUB_SUBDIR
    names = list(PROFILE_ALLOWLIST) + ([CONTACT_PROFILE] if include_contact else [])
    res = {"at": now, "copied": [], "unchanged": [], "missing": [], "refused": [],
           "overwrote_drive_edit": [], "errors": [], "doc": None}
    rendered = {}
    for name in names:
        src = Path(src_dir) / name
        try:
            data = src.read_bytes()
        except FileNotFoundError:
            res["missing"].append(name)
            log.info("missing locally, Drive copy kept: %s", name)
            continue
        except OSError as exc:
            res["errors"].append(f"{name}: {exc}")
            continue
        why = refuse(name, data)
        if why:
            res["refused"].append(f"{name}: {why}")
            log.warning("refused %s: %s", name, why)
            continue
        rendered[name] = data.decode("utf-8")
        sha = _sha_bytes(data)
        rec = state["files"].get(name, {})
        target = dest / name
        drive_sha = _sha_bytes(target.read_bytes()) if target.is_file() else None
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
            res["errors"].append(f"{name}: {exc}")
            log.error("could not copy %s: %s", name, exc)
            continue
        res["copied"].append(name)
        state["files"][name] = {"sha256": sha, "written_at": now}
        log.info("copied %s", name)
    if api:
        if token is None:
            token, note = pd._api_token(transport=transport)
            if token is None:
                res["errors"].append(note)
        if token is not None:
            res["doc"] = sync_doc(token, render_markdown(rendered), state, transport, now)
            if res["doc"]["error"]:
                res["errors"].append(res["doc"]["error"])
                log.error("%s", res["doc"]["error"])
    state["runs"] = (state["runs"] + [{k: (len(v) if isinstance(v, list) else v)
                                        for k, v in res.items() if k != "doc"}])[-RUN_HISTORY:]
    save_state(state, state_path)
    return res


def check(hub, include_contact=False, state_path=STATE_PATH, src_dir=CONTEXT_DIR) -> list:
    """Read-only: one row per file with the local, recorded and Drive sha256 and a verdict."""
    state = load_state(state_path)
    rows = []
    for name in list(PROFILE_ALLOWLIST) + ([CONTACT_PROFILE] if include_contact else []):
        src, target = Path(src_dir) / name, Path(hub) / HUB_SUBDIR / name
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


def build_plist(hub, engine="python", *, python=None, log_dir=LOG_DIR, root=ROOT) -> dict:
    """The launchd job. launchd needs absolute paths, so the interpreter, the script and the hub
    are resolved now; moving the repo means running install-agent again."""
    hub = str(Path(hub).expanduser().resolve())
    if engine == "rsync":
        args = ["/bin/bash", str(Path(root) / "tools" / "profile-mirror.sh"),
                str(Path(root) / "pipeline" / "user-context"), str(Path(hub) / HUB_SUBDIR)]
    else:
        import env_paths
        py = python or env_paths.app_python(Path(root))
        args = [str(Path(py).resolve()), str(Path(root) / "tools" / "profile_mirror.py"),
                "sync", "--quiet", "--hub", hub]
    log = str(Path(log_dir) / "profile-mirror.launchd.log")
    return {"Label": LABEL, "ProgramArguments": args, "WorkingDirectory": str(root),
            "StartCalendarInterval": [{"Minute": m} for m in RUN_MINUTES],
            "ProcessType": "Background", "LowPriorityIO": True,
            "StandardOutPath": log, "StandardErrorPath": log}


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def install_agent(hub, engine="python", *, runner=_run, sleep=time.sleep, clock=time.monotonic,
                  home=None, uid=None, platform=None, state_path=STATE_PATH, python=None,
                  log_dir=LOG_DIR, wait=30) -> dict:
    """Write the plist, (re)load it and start one run now. Returns {"ok", "detail"}."""
    if (platform or sys.platform) != "darwin":
        return {"ok": False, "detail": "install-agent needs macOS (launchd); run sync by hand "
                                       "or from your own scheduler elsewhere."}
    uid = os.getuid() if uid is None else uid
    job = build_plist(hub, engine, python=python, log_dir=log_dir)
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    target = plist_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f".{target.name}.tmp"
    staging.write_bytes(plistlib.dumps(job))
    os.chmod(staging, 0o644)
    os.replace(staging, target)
    runs_before = len(load_state(state_path)["runs"])
    runner(["launchctl", "bootout", f"gui/{uid}/{LABEL}"])
    boot = runner(["launchctl", "bootstrap", f"gui/{uid}", str(target)])
    if boot.returncode != 0:
        return {"ok": False, "detail": f"launchctl bootstrap failed: {boot.stderr.strip()}"}
    runner(["launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"])
    deadline = clock() + wait
    while clock() < deadline:
        if len(load_state(state_path)["runs"]) > runs_before:
            return {"ok": True, "detail": f"installed {target}; the first run finished"}
        sleep(1)
    return {"ok": False, "detail": (
        f"installed {target}, but no run finished within {wait}s. Check "
        f"{Path(log_dir) / 'profile-mirror.launchd.log'}. 'Operation not permitted' there means "
        "macOS blocked the background job from the repo or Drive folder: open System Settings > "
        "Privacy & Security > Full Disk Access (or Files and Folders), allow the Python named in "
        "the plist, then run install-agent again.")}


def uninstall_agent(*, runner=_run, home=None, uid=None, platform=None) -> dict:
    if (platform or sys.platform) != "darwin":
        return {"ok": False, "detail": "uninstall-agent needs macOS (launchd)."}
    uid = os.getuid() if uid is None else uid
    runner(["launchctl", "bootout", f"gui/{uid}/{LABEL}"])
    target = plist_path(home)
    if target.exists():
        target.unlink()
    return {"ok": True, "detail": f"removed {target}; nothing in Drive was touched"}


# --- selftest --------------------------------------------------------------------------------

def selftest() -> int:
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    tmp = Path(tempfile.mkdtemp(prefix="profile-mirror-selftest-"))
    src, hub, state_file = tmp / "ctx", tmp / "hub", tmp / "state.json"
    src.mkdir()
    hub.mkdir()
    (src / "voice-profile.local.json").write_text('{"tone": "warm", "avoid": ["jargon"]}',
                                                  encoding="utf-8")
    (src / "channel-context.local.json").write_text('{"niche": "home decor"}', encoding="utf-8")
    (src / CONTACT_PROFILE).write_text('{"contact_email": "jane@example.com"}', encoding="utf-8")
    (src / "api-credentials.local.json").write_text("{}", encoding="utf-8")
    quiet = logging.getLogger("profile_mirror.selftest")
    quiet.addHandler(logging.NullHandler())
    quiet.propagate = False

    def run(**kw):
        return sync(hub, state_path=state_file, src_dir=src, log=quiet, **kw)

    r1 = run(now="2026-01-01T00:00:00Z")
    ok("first sync copies the allowlisted files present", sorted(r1["copied"]) == [
        "channel-context.local.json", "voice-profile.local.json"])
    ok("a missing allowlisted file is reported, not an error",
       sorted(r1["missing"]) == ["content-calendar.local.json", "setup-context.local.json"]
       and not r1["errors"])
    ok("the contact profile and credential files are not copied by default",
       not (hub / HUB_SUBDIR / CONTACT_PROFILE).exists()
       and not (hub / HUB_SUBDIR / "api-credentials.local.json").exists())
    ok("no temp file is left behind", not list((hub / HUB_SUBDIR).glob(".*mirror-tmp")))
    r2 = run()
    ok("an unchanged file is not rewritten", r2["copied"] == [] and len(r2["unchanged"]) == 2)
    (hub / HUB_SUBDIR / "voice-profile.local.json").write_text('{"tone": "edited in Drive"}',
                                                               encoding="utf-8")
    r3 = run()
    ok("a Drive-side edit is reported and overwritten by the local file",
       r3["overwrote_drive_edit"] == ["voice-profile.local.json"]
       and "warm" in (hub / HUB_SUBDIR / "voice-profile.local.json").read_text(encoding="utf-8"))
    (src / "channel-context.local.json").unlink()
    r4 = run()
    ok("a file deleted locally keeps its Drive copy",
       "channel-context.local.json" in r4["missing"]
       and (hub / HUB_SUBDIR / "channel-context.local.json").exists())
    r5 = run(include_contact=True)
    ok("--include-contact-profile copies the creator profile",
       CONTACT_PROFILE in r5["copied"] and (hub / HUB_SUBDIR / CONTACT_PROFILE).exists())
    key = "AKIA" + "ABCDEFGHIJKLMNOP"
    (src / "setup-context.local.json").write_text('{"note": "' + key + '"}', encoding="utf-8")
    r6 = run()
    ok("a context file holding a credential pattern is refused and not copied",
       any(x.startswith("setup-context.local.json") for x in r6["refused"])
       and not (hub / HUB_SUBDIR / "setup-context.local.json").exists())
    ok("refuse(): credential names, .env names, forbidden suffixes and non-UTF-8 bytes",
       refuse("api-credentials.local.json", b"{}") and refuse(".env.local", b"A=1")
       and refuse("export.csv", b"a,b") and refuse("x.local.json", b"\xff\xfe")
       and refuse("voice-profile.local.json", b'{"tone": "warm"}') is None)
    ok("a contact email alone does not refuse a copy",
       refuse(CONTACT_PROFILE, b'{"contact_email": "jane@example.com"}') is None)
    st = load_state(state_file)
    ok("the state file records each copy and caps the run history",
       st["files"]["voice-profile.local.json"]["sha256"] and len(st["runs"]) <= RUN_HISTORY)
    rows = {r["file"]: r["verdict"] for r in check(hub, state_path=state_file, src_dir=src)}
    ok("check reports current, missing-locally and not-copied-yet files",
       rows["voice-profile.local.json"] == "current"
       and rows["channel-context.local.json"] == "missing locally"
       and rows["content-calendar.local.json"] == "missing locally")

    # Doc lane over a fake Drive.
    calls = []
    fake_state = {"missing_folder": False, "update_status": 200}

    class _Resp:
        def __init__(self, status, body):
            self.status, self.body = status, body

    def fake_transport(method, url, headers=None, data=None, timeout=30):
        calls.append((method, url, dict(headers or {})))
        if "/files?q=" in url:
            if fake_state["missing_folder"] and "Profile" in url:
                return 200, json.dumps({"files": []}).encode()
            name = "Creator OS" if "Creator%20OS" in url else "Profile"
            return 200, json.dumps({"files": [{"id": f"id-{name}"}]}).encode()
        if "uploadType=multipart" in url:
            return 200, json.dumps({"id": "doc-1"}).encode()
        if "uploadType=media" in url:
            return fake_state["update_status"], json.dumps({"id": "doc-1"}).encode()
        return 404, b"{}"

    tok = "fixture-" + "access" + "_token"
    md = render_markdown({"voice-profile.local.json": '{"tone": "warm"}'})
    ok("render_markdown is deterministic and names the source file",
       md == render_markdown({"voice-profile.local.json": '{"tone": "warm"}'})
       and "## Voice Profile" in md and "- **tone**: warm" in md)
    dstate = {"doc": {}}
    a1 = sync_doc(tok, md, dstate, fake_transport, "t1")
    a2 = sync_doc(tok, md, dstate, fake_transport, "t2")
    a3 = sync_doc(tok, md + "more\n", dstate, fake_transport, "t3")
    ok("the Doc is created once, skipped when unchanged, updated when the text changes",
       (a1["action"], a2["action"], a3["action"]) == ("created", "unchanged", "updated"))
    fake_state["update_status"] = 404
    a4 = sync_doc(tok, md + "again\n", dstate, fake_transport, "t4")
    ok("a Doc deleted in Drive (HTTP 404 on update) is created again", a4["action"] == "created")
    fake_state["missing_folder"] = True
    a5 = sync_doc(tok, md + "x\n", {"doc": {}}, fake_transport, "t5")
    ok("a hub folder the API cannot see skips the Doc with an error, creating no folder",
       a5["action"] == "skipped" and a5["error"]
       and not any("folder" in u and m == "POST" and "multipart" not in u for m, u, _ in calls))
    ok("every Doc call goes to googleapis with the bearer in a header, never in the URL",
       calls and all(u.startswith("https://www.googleapis.com/") and tok not in u
                     and h.get("Authorization") == f"Bearer {tok}" for _, u, h in calls))
    fake_state["missing_folder"] = False
    r7 = run(api=True, token=tok, transport=fake_transport)
    ok("sync --api copies the files and writes the Doc in the same run",
       r7["doc"] and r7["doc"]["action"] in ("created", "updated", "unchanged"))
    fake_state["missing_folder"] = True
    changed = b'{"tone": "warm", "avoid": ["jargon", "hype"]}'
    (src / "voice-profile.local.json").write_bytes(changed)
    r8 = run(api=True, token=tok, transport=fake_transport)
    ok("a Doc error does not stop the file copy",
       r8["doc"]["action"] == "skipped" and r8["errors"]
       and "voice-profile.local.json" in r8["copied"]
       and (hub / HUB_SUBDIR / "voice-profile.local.json").read_bytes() == changed)

    # launchd agent.
    job = build_plist(hub, python="/usr/bin/python3", log_dir=tmp / "logs")
    back = plistlib.loads(plistlib.dumps(job))
    ok("the plist round-trips through plistlib and uses absolute paths",
       back == job and all(Path(a).is_absolute() for a in job["ProgramArguments"][:2])
       and job["ProgramArguments"][2:4] == ["sync", "--quiet"])
    ok("the job runs on four calendar minutes, not at load, as a background process",
       [e["Minute"] for e in job["StartCalendarInterval"]] == list(RUN_MINUTES)
       and "RunAtLoad" not in job and job["ProcessType"] == "Background")
    rjob = build_plist(hub, engine="rsync", log_dir=tmp / "logs")
    ok("the rsync engine runs tools/profile-mirror.sh from the repo into <hub>/Profile",
       rjob["ProgramArguments"][:2] == ["/bin/bash", str(RSYNC_SCRIPT)]
       and rjob["ProgramArguments"][3].endswith(HUB_SUBDIR))
    ran_cmds = []

    class _Done:
        def __init__(self, rc=0):
            self.returncode, self.stdout, self.stderr = rc, "", ""

    def fake_runner(cmd):
        ran_cmds.append(cmd)
        if cmd[1] == "kickstart":
            st2 = load_state(state_file)
            st2["runs"].append({"at": "kick"})
            save_state(st2, state_file)
        return _Done()

    home = tmp / "home"
    inst = install_agent(hub, runner=fake_runner, sleep=lambda s: None, home=home, uid=501,
                         platform="darwin", state_path=state_file, python="/usr/bin/python3",
                         log_dir=tmp / "logs")
    ok("install-agent writes the plist mode 0644 and bootstraps, then kickstarts the job",
       inst["ok"] and plist_path(home).exists()
       and (plist_path(home).stat().st_mode & 0o777) == 0o644
       and [c[1] for c in ran_cmds] == ["bootout", "bootstrap", "kickstart"]
       and ran_cmds[1] == ["launchctl", "bootstrap", "gui/501", str(plist_path(home))])
    ticks = iter(range(0, 100, 10))
    silent = install_agent(hub, runner=lambda c: _Done(), sleep=lambda s: None,
                           clock=lambda: next(ticks), home=home, uid=501, platform="darwin",
                           state_path=state_file, python="/usr/bin/python3", log_dir=tmp / "logs")
    ok("a run that never finishes reports the Full Disk Access remedy",
       not silent["ok"] and "Full Disk Access" in silent["detail"])
    ok("install-agent and uninstall-agent refuse outside macOS",
       not install_agent(hub, platform="linux")["ok"]
       and not uninstall_agent(platform="linux")["ok"])
    un = uninstall_agent(runner=lambda c: _Done(), home=home, uid=501, platform="darwin")
    ok("uninstall-agent removes the plist and leaves Drive alone",
       un["ok"] and not plist_path(home).exists() and (hub / HUB_SUBDIR).exists())

    # The rsync recipe copies the same files.
    script = RSYNC_SCRIPT.read_text(encoding="utf-8")
    m = re.search(r"^ALLOWLIST=\(\s*(.*?)\)", script, re.S | re.M)
    ok("tools/profile-mirror.sh copies exactly PROFILE_ALLOWLIST",
       m is not None and tuple(m.group(1).split()) == PROFILE_ALLOWLIST)
    ok("tools/profile-mirror.sh refuses the credential file names",
       all(n in script for n in REFUSED_NAMES))
    bash = "/bin/bash" if Path("/bin/bash").exists() else None
    if bash:
        parse = subprocess.run([bash, "-n", str(RSYNC_SCRIPT)], capture_output=True, text=True)
        ok("tools/profile-mirror.sh parses (bash -n)", parse.returncode == 0)

    passed = sum(1 for _, c in checks if c)
    print(f"profile_mirror selftest: {passed}/{len(checks)} passed")
    return 0 if passed == len(checks) else 1


# --- CLI -------------------------------------------------------------------------------------

def _logger(quiet: bool) -> logging.Logger:
    log = logging.getLogger("profile_mirror")
    log.setLevel(logging.INFO)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(LOG_DIR / "profile-mirror.log",
                                                  maxBytes=512_000, backupCount=3,
                                                  encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(fh)
    except OSError:
        pass
    if not quiet:
        log.addHandler(logging.StreamHandler(sys.stderr))
    return log


def _hub(arg):
    from handoff import watcher as w
    return w.resolve_hub(arg)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Copy the creator's context files into the Drive hub.")
    ap.add_argument("command", nargs="?",
                    choices=["sync", "check", "status", "install-agent", "uninstall-agent"])
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
        st = load_state()
        last = st["runs"][-1] if st["runs"] else None
        print(json.dumps({"last_run": last, "doc": st["doc"], "files": sorted(st["files"])},
                         indent=2) if a.json else f"last run: {last}\nDoc: {st['doc'] or 'none'}")
        return 0
    if a.command == "uninstall-agent":
        r = uninstall_agent()
        print(r["detail"])
        return 0 if r["ok"] else 1
    hub, note = _hub(a.hub)
    if hub is None:
        print(f"profile mirror: {note}", file=sys.stderr)
        return 2
    if a.command == "check":
        rows = check(hub, a.include_contact_profile)
        for r in rows:
            print(f"  {r['verdict']:<16} {r['file']}")
        return 0 if all(r["verdict"] in ("current", "missing locally") for r in rows) else 1
    if a.command == "install-agent":
        r = install_agent(hub, a.engine)
        print(r["detail"])
        return 0 if r["ok"] else 1
    res = sync(hub, include_contact=a.include_contact_profile, api=a.api, log=_logger(a.quiet))
    if a.json:
        print(json.dumps(res, indent=2))
    elif not a.quiet:
        print(f"copied {len(res['copied'])}, unchanged {len(res['unchanged'])}, "
              f"missing {len(res['missing'])}, refused {len(res['refused'])}")
    return 1 if res["errors"] or res["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
