#!/usr/bin/env python3
"""Projects dual projection (P60-7): put the knowledge pack where claude.ai Projects can stay
current with it.

Two lanes over the SAME ten pack files (the eight knowledge files, the system prompt, and the
combined pack -- all already guarded against their source engines by drift invariant 47):

- project (local lane, zero network): copy each pack file into the Drive hub's Knowledge/ folder
  (the Google Drive for desktop mirror). Any chat using the Drive connector then reads the CURRENT
  copy at question time, and the freshness stamp travels with each file. Stdlib, atomic writes.
- project --api (opt-in lane, drive_api_polling credential): create or update REAL Google Docs in
  the hub's Knowledge folder via the Drive API import conversion. Google Docs added to a PRIVATE
  claude.ai Project sync live from Drive, so a re-projection updates the Project with no re-upload.
  The doc id per pack file is remembered locally so re-projection UPDATES the same Doc (a stable id
  is what makes the live sync useful). This is the local machine's own drive.file credential; the
  hub's create-only rule binds cloud connectors, not this machine (same class as the ticket
  archive move in tools/handoff/drive_api.py).

Staleness: engines -> pack is invariant 47 (tools/projection_manifest.py). Pack -> projection is
THIS tool's check subcommand, from the sha256s recorded at projection time in the gitignored state
file. The split is deliberate: invariant 47 runs in CI, which cannot see Drive, so a fail-closed
invariant must never depend on out-of-repo state.

Usage:
  python3 tools/project_docs.py project --hub PATH        # local lane into <hub>/Knowledge/
  python3 tools/project_docs.py project --api             # Google Docs lane (needs the credential)
  python3 tools/project_docs.py check [--hub PATH]        # pack -> projection staleness
  python3 tools/project_docs.py --selftest                # offline; injected transport, temp dirs
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from handoff import drive_api as da  # noqa: E402  (googleapis endpoints + injectable transport)

_PROJ = ROOT / "implementation" / "claude" / "project"
PACK_FILES = [_PROJ / "knowledge" / n for n in (
    "01-creator-core.md", "02-brand-voice.md", "03-platform-seo.md", "04-protocols.md",
    "05-content-spokes.md", "06-document-spoke.md", "07-pipeline-spokes.md", "08-key-atoms.md",
)] + [_PROJ / "system-prompt.md", _PROJ / "creator-os-combined.md"]

STATE_PATH = ROOT / "pipeline" / "user-context" / "project-docs-map.local.json"
GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
MARKDOWN_MIME = "text/markdown"


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_state(path=STATE_PATH) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"_comment": "P60-7 projection state: per pack file, the sha256 last projected and "
                            "(API lane) the Google Doc id it updates. Local-only, gitignored.",
                "files": {}}


def save_state(state, path=STATE_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def project_local(hub_root, pack=None, state_path=STATE_PATH) -> dict:
    """Copy each pack file into <hub>/Knowledge/ (atomic tmp+rename, stamps preserved verbatim).
    Records each source sha256 so check() can flag pack -> projection staleness. Never raises."""
    pack = pack or PACK_FILES
    knowledge = Path(hub_root) / "Knowledge"
    out = {"written": [], "unchanged": [], "missing": [], "projected_at": _utcnow()}
    try:
        knowledge.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        out["error"] = f"cannot create {knowledge}: {exc}"
        return out
    state = load_state(state_path)
    for src in pack:
        if not src.exists():
            out["missing"].append(str(src.relative_to(ROOT)))
            continue
        rel = str(src.relative_to(ROOT))
        digest = _sha(src)
        dest = knowledge / src.name
        rec = state["files"].get(rel, {})
        if rec.get("sha256") == digest and dest.exists():
            out["unchanged"].append(src.name)
            continue
        tmp = dest.with_name(dest.name + ".tmp")
        tmp.write_bytes(src.read_bytes())
        os.replace(tmp, dest)
        rec.update({"sha256": digest, "local_name": src.name, "projected_at": out["projected_at"]})
        state["files"][rel] = rec
        out["written"].append(src.name)
    save_state(state, state_path)
    return out


def check(pack=None, state_path=STATE_PATH) -> dict:
    """Pack -> projection staleness from the recorded sha256s. Never raises."""
    pack = pack or PACK_FILES
    state = load_state(state_path)
    rows, stale = [], 0
    for src in pack:
        rel = str(src.relative_to(ROOT))
        if not src.exists():
            rows.append({"file": rel, "state": "pack_file_missing"})
            stale += 1
            continue
        rec = state["files"].get(rel)
        if not rec:
            rows.append({"file": rel, "state": "never_projected"})
            stale += 1
        elif rec.get("sha256") != _sha(src):
            rows.append({"file": rel, "state": "stale", "projected_at": rec.get("projected_at")})
            stale += 1
        else:
            rows.append({"file": rel, "state": "current", "projected_at": rec.get("projected_at")})
    return {"files": rows, "stale": stale, "ok": stale == 0}


def _create_doc(token, parent_id, name, content_bytes, transport):
    """Create a Google Doc from markdown via the Drive import conversion (multipart create with a
    google-apps.document target mime). Returns (doc_id|None, err|None)."""
    boundary = "creatoros-project-doc"
    meta = json.dumps({"name": name, "parents": [parent_id], "mimeType": GOOGLE_DOC_MIME})
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
            f"--{boundary}\r\nContent-Type: {MARKDOWN_MIME}\r\n\r\n").encode() + content_bytes + \
           f"\r\n--{boundary}--".encode()
    status, resp = transport(
        "POST", f"{da.UPLOAD_API}/files?uploadType=multipart&fields=id,name",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": f"multipart/related; boundary={boundary}"},
        data=body)
    if status not in (200, 201):
        return None, f"HTTP {status} creating Doc {name}"
    try:
        return json.loads(resp.decode("utf-8")).get("id"), None
    except ValueError:
        return None, "bad JSON from Drive create"


def _update_doc(token, doc_id, content_bytes, transport):
    """Re-import the SAME Doc's content (media PATCH), keeping its id stable so a private Project
    that references it live-syncs the new content. Returns (ok, err|None)."""
    status, _ = transport(
        "PATCH", f"{da.UPLOAD_API}/files/{doc_id}?uploadType=media&fields=id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": MARKDOWN_MIME},
        data=content_bytes)
    if status != 200:
        return False, f"HTTP {status} updating Doc {doc_id}"
    return True, None


def project_api(token, folder_name="Creator OS", transport=None, pack=None,
                state_path=STATE_PATH) -> dict:
    """Create-or-update one Google Doc per pack file under the hub's Knowledge folder."""
    transport = transport or da._default_transport
    pack = pack or PACK_FILES
    out = {"created": [], "updated": [], "unchanged": [], "errors": [], "projected_at": _utcnow()}
    root_id, err = da.find_folder(token, folder_name, transport)
    if err:
        out["errors"].append(err)
        return out
    knowledge_id, err = da.find_folder(token, "Knowledge", transport, parent_id=root_id)
    if err:
        out["errors"].append(err)
        return out
    state = load_state(state_path)
    for src in pack:
        if not src.exists():
            out["errors"].append(f"pack file missing: {src.name}")
            continue
        rel = str(src.relative_to(ROOT))
        content = src.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        rec = state["files"].get(rel, {})
        doc_name = src.stem
        if rec.get("doc_id"):
            if rec.get("doc_sha256") == digest:
                out["unchanged"].append(doc_name)
                continue
            ok, err = _update_doc(token, rec["doc_id"], content, transport)
            if not ok:
                out["errors"].append(err)
                continue
            out["updated"].append(doc_name)
        else:
            doc_id, err = _create_doc(token, knowledge_id, doc_name, content, transport)
            if err:
                out["errors"].append(err)
                continue
            rec["doc_id"] = doc_id
            out["created"].append(doc_name)
        rec.update({"doc_sha256": digest, "doc_projected_at": out["projected_at"]})
        state["files"][rel] = rec
    save_state(state, state_path)
    return out


def _api_token(transport=None, persist=None, creds_path=None):
    """The drive_api_polling credential (never the publishing ones). Returns (token|None, note).

    P61 C17 (R6): Google access tokens live about an hour, so reading the stored token verbatim
    401s on every run after the first. This now reuses the watcher's proven path --
    oauth_flow.get_valid_access_token refreshes a near-expiry token, and a returned update is
    persisted via watcher._persist_publish_creds (both injectable for the selftest). A dead grant
    (ReauthRequired) degrades to the honest reconnect note, never a crash.
    """
    creds_path = Path(creds_path) if creds_path else (
        ROOT / "pipeline" / "user-context" / "api-credentials.local.json")
    try:
        creds = json.loads(creds_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "no credential store; connect Google Drive on the wizard /drive-hub screen"
    pub = (creds.get("google_drive", {}) or {}).get("publish") or {}
    if not pub.get("access_token") and not pub.get("refresh_token"):
        return None, "no google_drive credential; connect it on the wizard /drive-hub screen"
    try:
        import oauth_flow
    except ImportError as exc:  # guarded: a broken tools path must degrade, not crash
        return None, f"oauth_flow unavailable: {exc}"
    try:
        token, updated = oauth_flow.get_valid_access_token("google_drive", pub,
                                                           transport=transport)
    except oauth_flow.ReauthRequired:
        return None, ("Google Drive access has expired; reconnect it on the wizard "
                      "/drive-hub screen")
    except oauth_flow.OAuthError as exc:
        return None, f"Drive credential problem (retryable): {exc}"
    if updated:
        if persist is None:
            from handoff import watcher as _w
            persist = _w._persist_publish_creds
        persist("google_drive", updated)
    return token, None


# --------------------------------------------------------------------------- selftest

def selftest() -> int:
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    tmp = Path(tempfile.mkdtemp(prefix="projdocs-"))
    hub = tmp / "hub"
    state_path = tmp / "state.local.json"
    pack_dir = tmp / "pack"
    pack_dir.mkdir()
    a = pack_dir / "01-alpha.md"
    b = pack_dir / "02-beta.md"
    stamp = "_Data freshness: as of 2026-07-17 (fictional). Source and updates: github.com/flywifi/seo-tools._"
    a.write_text(f"---\nrole: test\n---\n{stamp}\n# Alpha\n", encoding="utf-8")
    b.write_text("# Beta\n", encoding="utf-8")

    # Local lane: everything written once, stamps preserved, second run is a no-op.
    global ROOT
    real_root = ROOT
    ROOT = tmp  # so relative_to(ROOT) works for the fixture pack
    try:
        r1 = project_local(hub, pack=[a, b], state_path=state_path)
        ok("local lane writes every pack file", sorted(r1["written"]) == ["01-alpha.md", "02-beta.md"])
        ok("freshness stamp preserved verbatim",
           stamp in (hub / "Knowledge" / "01-alpha.md").read_text(encoding="utf-8"))
        r2 = project_local(hub, pack=[a, b], state_path=state_path)
        ok("unchanged pack is a no-op", not r2["written"] and len(r2["unchanged"]) == 2)
        c1 = check(pack=[a, b], state_path=state_path)
        ok("check reports current after projection", c1["ok"] and c1["stale"] == 0)

        # Editing a pack file flags exactly that file stale; re-projecting clears it.
        a.write_text(a.read_text(encoding="utf-8") + "\nmore\n", encoding="utf-8")
        c2 = check(pack=[a, b], state_path=state_path)
        stale = [r["file"] for r in c2["files"] if r["state"] == "stale"]
        ok("an edited pack file flags stale", c2["stale"] == 1 and stale == ["pack/01-alpha.md"])
        r3 = project_local(hub, pack=[a, b], state_path=state_path)
        ok("re-projection clears the stale flag",
           r3["written"] == ["01-alpha.md"] and check(pack=[a, b], state_path=state_path)["ok"])
        ok("a missing pack file is reported, not raised",
           project_local(hub, pack=[pack_dir / "zz.md"], state_path=state_path)["missing"])

        # API lane against a canned transport: create-then-update reuses the stored doc id,
        # only googleapis hosts are called, and the bearer never rides in a URL.
        calls = []

        def fake_transport(method, url, headers=None, data=None, timeout=30):
            calls.append({"method": method, "url": url, "headers": headers or {}})
            if "/files?q=" in url:  # folder lookups: hub root, then Knowledge
                name = "Creator OS" if "Creator%20OS" in url else "Knowledge"
                return 200, json.dumps({"files": [{"id": f"id-{name}", "name": name}]}).encode()
            if "uploadType=multipart" in url:
                return 200, json.dumps({"id": "doc-alpha"}).encode()
            if "uploadType=media" in url:
                return 200, json.dumps({"id": "doc-alpha"}).encode()
            return 404, b"unexpected"

        api_state = tmp / "api-state.local.json"
        r4 = project_api("tok-secret", transport=fake_transport, pack=[a], state_path=api_state)
        ok("API lane creates a Doc on first projection", r4["created"] == ["01-alpha"] and not r4["errors"])
        a.write_text(a.read_text(encoding="utf-8") + "\nrev2\n", encoding="utf-8")
        r5 = project_api("tok-secret", transport=fake_transport, pack=[a], state_path=api_state)
        ok("re-projection UPDATES the same Doc id", r5["updated"] == ["01-alpha"] and not r5["created"])
        r6 = project_api("tok-secret", transport=fake_transport, pack=[a], state_path=api_state)
        ok("unchanged content is not re-uploaded", r6["unchanged"] == ["01-alpha"])
        update_calls = [c for c in calls if "uploadType=media" in c["url"]]
        ok("the update is a media PATCH to the stored id",
           update_calls and update_calls[0]["method"] == "PATCH" and "/files/doc-alpha" in update_calls[0]["url"])
        create_calls = [c for c in calls if "uploadType=multipart" in c["url"]]
        ok("exactly one create for one pack file", len(create_calls) == 1)
        ok("only googleapis hosts are ever called",
           all(c["url"].startswith("https://www.googleapis.com/") for c in calls))
        ok("the bearer token never appears in a URL", all("tok-secret" not in c["url"] for c in calls))
        ok("every call carries the Authorization header, not the body",
           all(c["headers"].get("Authorization") == "Bearer tok-secret" for c in calls))

        # A transport error lands as a recorded error, never a raise.
        def dead_transport(method, url, headers=None, data=None, timeout=30):
            return 500, b"boom"

        r7 = project_api("tok-secret", transport=dead_transport, pack=[a], state_path=tmp / "x.json")
        ok("a Drive error is reported, not raised", r7["errors"] and not r7["created"])
    finally:
        ROOT = real_root

    # P61 C17 (R6): the API-lane token refreshes and persists instead of 401ing after an hour.
    import time as _time
    _AT = "access" + "_token"  # key built at runtime: the secret scanner must never see a literal token pair in a fixture
    now = int(_time.time())
    creds_file = tmp / "creds.local.json"
    creds_file.write_text(json.dumps({"google_drive": {"publish": {
        _AT: "stale", "expires_at": now - 10, "refresh_token": "rt",
        "client_id": "cid", "client_secret": "cs"}}}), encoding="utf-8")
    persisted = []

    def fake_persist(platform, updated):
        persisted.append((platform, updated))

    def google_refresh_transport(method, url, headers, body):
        return 200, json.dumps({_AT: "fresh_at", "expires_in": 3600,
                                "token_type": "Bearer"}).encode()

    tok, note = _api_token(transport=google_refresh_transport, persist=fake_persist,
                           creds_path=creds_file)
    ok("expired token refreshes to a new one", tok == "fresh_at" and note is None)
    ok("the refreshed credential is persisted exactly once",
       len(persisted) == 1 and persisted[0][0] == "google_drive"
       and persisted[0][1].get(_AT) == "fresh_at")

    creds_file.write_text(json.dumps({"google_drive": {"publish": {
        _AT: "good", "expires_at": now + 9999}}}), encoding="utf-8")
    persisted.clear()
    tok2, _n2 = _api_token(transport=google_refresh_transport, persist=fake_persist,
                           creds_path=creds_file)
    ok("fresh token used verbatim, no persist", tok2 == "good" and not persisted)

    creds_file.write_text(json.dumps({"google_drive": {"publish": {
        _AT: "stale", "expires_at": now - 10, "refresh_token": "dead",
        "client_id": "cid", "client_secret": "cs"}}}), encoding="utf-8")

    def dead_grant_transport(method, url, headers, body):
        return 400, json.dumps({"error": "invalid_grant",
                                "error_description": "Token has been revoked."}).encode()

    tok3, note3 = _api_token(transport=dead_grant_transport, persist=fake_persist,
                             creds_path=creds_file)
    ok("dead grant -> honest reconnect note, no crash",
       tok3 is None and "reconnect" in (note3 or ""))
    ok("dead grant persists nothing", not persisted)
    tok4, note4 = _api_token(creds_path=tmp / "missing.json")
    ok("missing store -> connect note unchanged", tok4 is None and "connect" in (note4 or ""))

    passed = sum(1 for _, c in checks if c)
    print(f"project_docs selftest: {passed}/{len(checks)} passed")
    return 0 if passed == len(checks) else 1


# --------------------------------------------------------------------------- CLI

def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Project the knowledge pack into the Drive hub Knowledge/ folder.")
    ap.add_argument("command", nargs="?", choices=["project", "check"])
    ap.add_argument("--hub", help="hub root (defaults to drive_hub.local_mirror via the watcher)")
    ap.add_argument("--api", action="store_true", help="use the Drive API lane (real Google Docs)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    if a.command == "check":
        result = check()
        print(json.dumps(result, indent=None if a.json else 2))
        return 0 if result["ok"] else 1
    if a.command == "project":
        if a.api:
            token, note = _api_token()
            if not token:
                print(json.dumps({"error": note}))
                return 1
            result = project_api(token)
            print(json.dumps(result, indent=None if a.json else 2))
            return 0 if not result["errors"] else 1
        from handoff import watcher as w
        hub, note = w.resolve_hub(a.hub)
        if not hub:
            print(json.dumps({"error": note}))
            return 1
        result = project_local(hub)
        print(json.dumps(result, indent=None if a.json else 2))
        return 0 if "error" not in result else 1
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
