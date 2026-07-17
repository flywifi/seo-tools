#!/usr/bin/env python3
"""Transport B: Drive API polling for the compute hand-off (P60, opt-in).

For machines WITHOUT Google Drive for desktop. The watcher authenticates with a desktop OAuth
client under the narrow drive.file scope (only files this app created or the user opened with it),
pulls queue tickets from the hub's Jobs/queue folder into a local staging hub, lets the SAME gated
runner execute them, then uploads results and archives the handled tickets. Every HTTP call goes
through an injectable transport (the P51 importer idiom) so the selftest runs with canned
responses and zero network. Gated on BOTH drive_api_polling and compute_handoff_enabled.

Usage:
  python3 tools/handoff/drive_api.py --selftest
  (production entry: python3 tools/handoff/watcher.py --transport api)
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from handoff import queue as q  # noqa: E402

API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
FOLDER_MIME = "application/vnd.google-apps.folder"


def _default_transport(method, url, headers=None, data=None, timeout=30):
    """(status, body_bytes). Stdlib, env-proxy aware; errors return their status, never raise
    through to the caller unhandled."""
    req = urllib.request.Request(url, method=method, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        return 0, str(exc.reason).encode()


def _get_json(token, url, transport):
    status, body = transport("GET", url, headers={"Authorization": f"Bearer {token}"})
    if status != 200:
        return None, f"HTTP {status}: {body[:200]!r}"
    try:
        return json.loads(body.decode("utf-8")), None
    except ValueError as exc:
        return None, f"bad JSON from Drive: {exc}"


def find_folder(token, name, transport, parent_id=None):
    """Resolve a folder id by exact name (optionally under a parent). Returns (id|None, err|None)."""
    query = f"name = '{name}' and mimeType = '{FOLDER_MIME}' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    url = f"{API}/files?q={urllib.parse.quote(query)}&fields=files(id,name)&pageSize=10"
    data, err = _get_json(token, url, transport)
    if err:
        return None, err
    files = data.get("files", [])
    if not files:
        return None, f"folder '{name}' not found (drive.file only sees files this app created or opened)"
    return files[0]["id"], None


def resolve_hub_folders(token, folder_name, transport):
    """Hub root -> Jobs -> {queue, results, archive} ids. Returns (ids|None, err|None)."""
    root_id, err = find_folder(token, folder_name, transport)
    if err:
        return None, err
    jobs_id, err = find_folder(token, "Jobs", transport, parent_id=root_id)
    if err:
        return None, err
    ids = {"root": root_id, "jobs": jobs_id}
    for sub in ("queue", "results", "archive"):
        sid, err = find_folder(token, sub, transport, parent_id=jobs_id)
        if err:
            return None, err
        ids[sub] = sid
    # P61 C18: Outbox is a direct child of the hub root. A missing Outbox folder never fails the
    # pass (older hubs may lack it); delivery just degrades to Jobs/results only.
    ob_id, ob_err = find_folder(token, "Outbox", transport, parent_id=root_id)
    ids["outbox"] = None if ob_err else ob_id
    return ids, None


def list_tickets(token, queue_id, transport):
    """JSON files currently in Jobs/queue. Returns (list of {id,name}, err|None)."""
    query = f"'{queue_id}' in parents and trashed = false and name contains '.json'"
    url = f"{API}/files?q={urllib.parse.quote(query)}&fields=files(id,name)&pageSize=100"
    data, err = _get_json(token, url, transport)
    if err:
        return [], err
    return [f for f in data.get("files", []) if f.get("name", "").endswith(".json")], None


def download(token, file_id, transport):
    status, body = transport("GET", f"{API}/files/{file_id}?alt=media",
                             headers={"Authorization": f"Bearer {token}"})
    if status != 200:
        return None, f"HTTP {status} downloading {file_id}"
    return body, None


def upload_file(token, parent_id, name, content_bytes, transport, mime="application/json"):
    """Create (never update) a file in a hub folder: the append-only rule holds on this transport
    too. Multipart related upload."""
    boundary = "creatoros-hub-upload"
    meta = json.dumps({"name": name, "parents": [parent_id]})
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
            f"--{boundary}\r\nContent-Type: {mime}\r\n\r\n").encode() + content_bytes + \
           f"\r\n--{boundary}--".encode()
    status, resp = transport(
        "POST", f"{UPLOAD_API}/files?uploadType=multipart&fields=id,name",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": f"multipart/related; boundary={boundary}"},
        data=body)
    if status not in (200, 201):
        return None, f"HTTP {status} uploading {name}"
    try:
        return json.loads(resp.decode("utf-8")).get("id"), None
    except ValueError:
        return None, "bad JSON from Drive upload"


def archive_remote(token, file_id, queue_id, archive_id, transport):
    """Move a handled ticket queue -> archive (the local machine is the only mover)."""
    url = f"{API}/files/{file_id}?addParents={archive_id}&removeParents={queue_id}&fields=id"
    status, _ = transport("PATCH", url, headers={"Authorization": f"Bearer {token}"})
    return status == 200


def poll_once(staging_hub, token, folder_name, transport=_default_transport, run=None) -> dict:
    """One API pass: pull tickets into the local staging hub, run the SAME gated runner, upload
    each result, archive handled tickets remotely. Returns an honest summary dict; never raises."""
    from handoff import runner as _runner
    run = run or _runner.run_pass
    ids, err = resolve_hub_folders(token, folder_name, transport)
    if err:
        return {"ok": False, "error": err, "pulled": 0}
    tickets, err = list_tickets(token, ids["queue"], transport)
    if err:
        return {"ok": False, "error": err, "pulled": 0}
    q.ensure_hub_dirs(staging_hub)
    pulled = []
    for t in tickets:
        body, derr = download(token, t["id"], transport)
        if derr:
            continue
        local = q.hub_paths(staging_hub)["queue"] / t["name"]
        local.write_bytes(body)
        pulled.append(t)
    results = run(staging_hub)
    uploaded = 0
    outbox_uploaded = 0
    if not (results and results[0].get("status") == "gated"):
        rdir = q.hub_paths(staging_hub)["results"]
        for rf in sorted(rdir.iterdir()):
            if rf.suffix in (".json", ".txt") and not rf.name.endswith(".tmp"):
                fid, uerr = upload_file(token, ids["results"], rf.name, rf.read_bytes(), transport,
                                        mime="application/json" if rf.suffix == ".json" else "text/plain")
                if fid:
                    uploaded += 1
        # P61 C18: Outbox artifacts written by the runner into the LOCAL staging hub would be
        # stranded on this transport; upload them too (create-only, same rule as results).
        ob_dir = Path(staging_hub) / "Outbox"
        if ids.get("outbox") and ob_dir.is_dir():
            for of in sorted(ob_dir.iterdir()):
                if of.suffix == ".json" and not of.name.endswith(".tmp"):
                    fid, uerr = upload_file(token, ids["outbox"], of.name, of.read_bytes(),
                                            transport, mime="application/json")
                    if fid:
                        outbox_uploaded += 1
        for t in pulled:
            archive_remote(token, t["id"], ids["queue"], ids["archive"], transport)
    return {"ok": True, "pulled": len(pulled), "ran": results, "uploaded": uploaded,
            "outbox_uploaded": outbox_uploaded}


def selftest() -> int:
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    ticket = {
        "job_id": "11111111-2222-3333-4444-555555555555", "created_at": "2026-07-16T00:00:00Z",
        "origin": "web", "requested_by": None, "job_type": "library_analyze", "params": {},
        "input_refs": [], "priority": "normal", "consent_note": None, "schema_version": "0.1.0",
    }
    seen = {"urls": [], "uploads": [], "patches": []}

    def canned(method, url, headers=None, data=None, timeout=30):
        seen["urls"].append((method, url))
        if method == "GET" and "/files?q=" in url:
            query = urllib.parse.unquote(url.split("q=")[1].split("&")[0])
            if FOLDER_MIME in query:
                name = query.split("name = '")[1].split("'")[0]
                return 200, json.dumps({"files": [{"id": f"id-{name}", "name": name}]}).encode()
            return 200, json.dumps({"files": [{"id": "tick-1", "name": "job.t.web.json"}]}).encode()
        if method == "GET" and "alt=media" in url:
            return 200, json.dumps(ticket).encode()
        if method == "POST" and "uploadType=multipart" in url:
            seen["uploads"].append(url)
            return 200, json.dumps({"id": "up-1"}).encode()
        if method == "PATCH":
            seen["patches"].append(url)
            return 200, b"{}"
        return 404, b"unexpected"

    def fake_run(hub):
        entries = q.read_queue(hub)
        for e in entries:
            q.write_result(hub, e["data"]["job_id"], "done", outputs=[])
            q.archive_ticket(hub, e["path"])
        # P61 C18: the runner also writes Outbox deliverables into the staging hub; poll_once
        # must upload them or they are stranded on this transport.
        ob = Path(hub) / "Outbox"
        ob.mkdir(parents=True, exist_ok=True)
        (ob / "library_analyze.2026-07-17T000000Z.mac.json").write_text('{"ok": true}',
                                                                       encoding="utf-8")
        return [{"job_id": ticket["job_id"], "status": "done"}]

    staging = tempfile.mkdtemp()
    out = poll_once(staging, "TOK", "Creator OS", transport=canned, run=fake_run)
    ok("poll pulls, runs, and reports ok", out["ok"] and out["pulled"] == 1)
    ok("result uploaded back to Drive", out["uploaded"] >= 1 and seen["uploads"])
    ok("Outbox artifact uploaded too (create-only)", out.get("outbox_uploaded") == 1)
    ok("handled ticket archived remotely", len(seen["patches"]) == 1 and "removeParents=id-queue" in seen["patches"][0])
    ok("bearer never in a URL", all("TOK" not in u for _m, u in seen["urls"]))
    ok("only googleapis hosts called",
       all(urllib.parse.urlparse(u).hostname.endswith("googleapis.com") for _m, u in seen["urls"]))

    # A gated runner means nothing is uploaded or archived (results stay local-only and empty).
    seen["uploads"].clear(); seen["patches"].clear()
    staging2 = tempfile.mkdtemp()
    out = poll_once(staging2, "TOK", "Creator OS", transport=canned,
                    run=lambda hub: [{"status": "gated"}])
    ok("gated pass uploads and archives nothing", not seen["uploads"] and not seen["patches"])

    # Honest failure when the hub folder is invisible to drive.file.
    def not_found(method, url, headers=None, data=None, timeout=30):
        return 200, json.dumps({"files": []}).encode()
    out = poll_once(tempfile.mkdtemp(), "TOK", "Creator OS", transport=not_found)
    ok("missing hub folder is a plain error, not a crash",
       out["ok"] is False and "not found" in out["error"])

    failed = [n for n, c in checks if not c]
    for n, c in checks:
        print(("ok   " if c else "FAIL ") + n)
    print(f"handoff.drive_api selftest: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv[1:] else selftest())
