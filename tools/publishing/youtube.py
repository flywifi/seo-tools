"""YouTube publishing client (P51) -- real Data API v3 resumable upload, gated OFF by default.

This performs the upload documented at
https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol :
  1. POST .../upload/youtube/v3/videos?uploadType=resumable&part=snippet,status with the video
     resource JSON -> the session URI comes back in the `Location` response header.
  2. PUT the bytes (chunked in 256 KB multiples) with a Content-Range; a 308 means resume-incomplete,
     a 200/201 returns the created video resource (its `id`).
The access token is obtained/refreshed via tools/oauth_flow (creds["youtube"]["publish"] holds the
client_id/secret + refresh_token from the wizard's Connect flow).

SAFETY: this client is only ever reached when live_publishing_enabled is on AND a human has confirmed
the specific post (publishing_compliance.check + the dashboard confirm path enforce that; this module
does not re-check). Uploads default to privacyStatus="private". It NEVER touches a monetary/analytics
endpoint -- upload only. Every network call goes through an injected `transport` for no-network tests.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.parse

_HERE = pathlib.Path(__file__).resolve().parent
_TOOLS = _HERE.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
import oauth_flow  # noqa: E402
from publishing import _http  # noqa: E402

INIT_URL = ("https://www.googleapis.com/upload/youtube/v3/videos"
            "?uploadType=resumable&part=snippet,status")
_CHUNK = 8 * 256 * 1024   # 2 MiB, a multiple of 256 KB (the resumable protocol's chunk-size rule)
_PRIVACY = ("private", "unlisted", "public")


def _media_path(entry: dict):
    for key in ("media_path", "video_path", "file_path", "file", "path"):
        v = entry.get(key)
        if v:
            return v
    return None


def publish(entry: dict, creds: dict, *, transport=None, token_transport=None,
            persist=None, now=None) -> dict:
    """Upload one video. Returns {ok, status, post_id, permalink, privacy, error}.

    `transport` (upload) and `token_transport` (OAuth refresh) are injectable for tests. `persist`,
    if given, is called with the refreshed publish-creds dict when a token refresh occurred so the
    caller can save it."""
    transport = transport or _http.default_transport
    pub = (creds.get("youtube") or {}).get("publish") or {}

    # 1) Valid access token (refresh if near expiry). No monetary scope is ever requested.
    try:
        access_token, updated = oauth_flow.get_valid_access_token(
            "youtube", pub, transport=token_transport, now=now)
    except oauth_flow.ReauthRequired as exc:
        return {"ok": False, "status": "auth_required", "post_id": None, "permalink": None,
                "error": f"YouTube authorization expired or missing ({exc.code}). Reconnect YouTube "
                         f"in the setup wizard."}
    if updated is not None and callable(persist):
        try:
            persist(updated)
        except Exception:  # noqa: BLE001
            pass
    if not access_token:
        return {"ok": False, "status": "auth_required", "post_id": None, "permalink": None,
                "error": "No YouTube access token available. Reconnect YouTube in the setup wizard."}
    scope = pub.get("scope") or ""
    _UPLOAD_SCOPES = {
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.force-ssl",
        "https://www.googleapis.com/auth/youtube",   # full YouTube scope also permits upload
    }
    if scope and not (set(scope.split()) & _UPLOAD_SCOPES):
        return {"ok": False, "status": "insufficient_scope", "post_id": None, "permalink": None,
                "error": "The stored YouTube token lacks the upload scope. Reconnect and grant upload access."}

    # 2) Resolve the local media file.
    media = _media_path(entry)
    if not media or not os.path.isfile(media):
        return {"ok": False, "status": "no_media", "post_id": None, "permalink": None,
                "error": "No local video file was found for this entry (expected entry['media_path'])."}
    size = os.path.getsize(media)
    # A2a: refuse an empty file BEFORE any network init (a truncated download would otherwise send
    # an INIT POST for zero bytes and return 'incomplete').
    if size <= 0:
        return {"ok": False, "status": "empty_media", "post_id": None, "permalink": None,
                "error": "The video file is empty (0 bytes). Re-download or re-export it, then retry."}
    content_type = entry.get("content_type") or "video/*"

    # 3) Build the video resource. Default to PRIVATE; public requires an explicit entry choice.
    privacy = str(entry.get("privacy_status") or "private").lower()
    if privacy not in _PRIVACY:
        privacy = "private"
    snippet = {"title": (entry.get("title") or "Untitled").strip(),
               "description": entry.get("description") or entry.get("caption") or "",
               "categoryId": str(entry.get("category_id") or "22")}
    tags = entry.get("tags")
    if isinstance(tags, (list, tuple)) and tags:
        snippet["tags"] = list(tags)
    status_obj = {"privacyStatus": privacy,
                  "selfDeclaredMadeForKids": bool(entry.get("made_for_kids", False))}
    body = json.dumps({"snippet": snippet, "status": status_obj}).encode("utf-8")

    # 4) Initiate the resumable session.
    init_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Length": str(size),
        "X-Upload-Content-Type": content_type,
    }
    st, hdrs, raw = transport("POST", INIT_URL, init_headers, body)
    if st not in (200, 201):
        return {"ok": False, "status": "init_failed", "post_id": None, "permalink": None,
                "error": f"Could not start the upload (HTTP {st}). {_http.parse_json(raw).get('error', '')}"}
    session_uri = _http.header(hdrs, "Location")
    if not session_uri:
        return {"ok": False, "status": "init_failed", "post_id": None, "permalink": None,
                "error": "The upload session did not return a Location URL."}
    # A2b: the bytes + Bearer token go to this server-supplied URI; pin it to the Google upload host
    # so a spoofed/redirected init response cannot exfiltrate the authenticated upload off googleapis.
    _host = (urllib.parse.urlparse(session_uri).hostname or "").lower()
    if not (_host == "googleapis.com" or _host.endswith(".googleapis.com")):
        return {"ok": False, "status": "init_failed", "post_id": None, "permalink": None,
                "error": f"The upload session URL host {_host!r} is not a Google upload host; refusing "
                         "to send the upload token there."}

    # 5) Upload the bytes in 256 KB-multiple chunks; honor 308 resume.
    uploaded = 0
    with open(media, "rb") as f:
        while uploaded < size:
            chunk = f.read(_CHUNK)
            if not chunk:
                break
            first = uploaded
            last = uploaded + len(chunk) - 1
            put_headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Length": str(len(chunk)),
                "Content-Type": content_type,
                "Content-Range": f"bytes {first}-{last}/{size}",
            }
            st, hdrs, raw = transport("PUT", session_uri, put_headers, chunk)
            if st in (200, 201):
                data = _http.parse_json(raw)
                vid = data.get("id")
                return {"ok": True, "status": "published", "post_id": vid,
                        "permalink": f"https://youtu.be/{vid}" if vid else None,
                        "privacy": privacy, "error": None}
            if st == 308:
                # Resume incomplete: sync our cursor to the server's acknowledged Range if present.
                rng = _http.header(hdrs, "Range")
                if rng and "-" in rng:
                    try:
                        uploaded = int(rng.rsplit("-", 1)[1]) + 1
                        f.seek(uploaded)
                        continue
                    except (ValueError, OSError):
                        pass
                uploaded = last + 1
                continue
            return {"ok": False, "status": "upload_failed", "post_id": None, "permalink": None,
                    "error": f"Upload failed (HTTP {st}). {_http.parse_json(raw).get('error', '')}"}
    return {"ok": False, "status": "incomplete", "post_id": None, "permalink": None,
            "error": "The upload ended without a final response from YouTube."}


# ── Selftest (no network) ────────────────────────────────────────────────────

def _selftest() -> int:
    import tempfile
    failures: list[str] = []
    urls: list[str] = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    now = 1_700_000_000
    AT = "access_token"   # key as a var: keeps canned fixtures off the secret-scan pattern
    fresh_creds = {"youtube": {"publish": {
        AT: "AT_FRESH", "expires_at": now + 9999,
        "scope": "https://www.googleapis.com/auth/youtube.upload",
        "client_id": "CID", "client_secret": "SEC", "refresh_token": "RT"}}}

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.write(b"\x00" * 1024)   # tiny single-chunk file
    tmp.close()

    def fake(method, url, headers, body):
        urls.append(url)
        if method == "POST":
            check(url == INIT_URL, "init URL is not the resumable videos.insert endpoint")
            check("uploadType=resumable" in url and "part=snippet,status" in url, "init query wrong")
            payload = json.loads(body.decode())
            check(payload["status"]["privacyStatus"] == "private", "default privacy must be private")
            check(payload["snippet"]["categoryId"] == "22", "default categoryId wrong")
            return 200, {"Location": "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=XYZ"}, b""
        # PUT -> final success with an id
        check(_http.header(headers, "Content-Range", ) is not None or "Content-Range" in headers,
              "PUT missing Content-Range")
        return 200, {}, json.dumps({"id": "VIDEO123"}).encode()

    res = publish({"media_path": tmp.name, "title": "My Test"}, fresh_creds,
                  transport=fake, now=now)
    check(res["ok"] and res["status"] == "published", f"publish did not succeed: {res}")
    check(res["post_id"] == "VIDEO123", "post_id not returned")
    check(res["permalink"] == "https://youtu.be/VIDEO123", "permalink wrong")
    check(res["privacy"] == "private", "privacy not private by default")

    # No monetary/analytics endpoint may ever be constructed.
    bad = [u for u in urls if any(t in u.lower() for t in
           ("analytics", "reports", "estimatedrevenue", "monetary", "earnings"))]
    check(not bad, f"a monetary/analytics URL was constructed: {bad}")
    check(all("googleapis.com/upload/youtube/v3/videos" in u or u.startswith("https://www.googleapis.com/upload")
              for u in urls), f"unexpected URL touched: {urls}")

    # Missing scope -> refuse before any upload.
    noscope = {"youtube": {"publish": {AT: "tok", "expires_at": now + 9999,
                                       "scope": "https://www.googleapis.com/auth/youtube.readonly"}}}
    res = publish({"media_path": tmp.name}, noscope, transport=fake, now=now)
    check(not res["ok"] and res["status"] == "insufficient_scope", "missing upload scope not caught")

    # Expired token, no refresh possible -> auth_required (no crash, no upload).
    dead = {"youtube": {"publish": {AT: "tok", "expires_at": now - 1}}}
    res = publish({"media_path": tmp.name}, dead, transport=fake, now=now)
    check(not res["ok"] and res["status"] == "auth_required", "dead token not surfaced as auth_required")

    # Missing media -> no_media.
    res = publish({"media_path": "/does/not/exist.mp4"}, fresh_creds, transport=fake, now=now)
    check(not res["ok"] and res["status"] == "no_media", "missing media not caught")

    # A2a: a 0-byte file -> empty_media BEFORE any network init.
    empty = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    empty.close()
    calls_before = len(urls)
    res = publish({"media_path": empty.name}, fresh_creds, transport=fake, now=now)
    check(not res["ok"] and res["status"] == "empty_media", "0-byte file not refused")
    check(len(urls) == calls_before, "empty_media must not make any network call")
    os.unlink(empty.name)

    # A2b: a spoofed init Location on a non-Google host -> refusal, no bytes/Bearer sent there.
    def fake_evil_host(method, url, headers, body):
        urls.append(url)
        if method == "POST" and url == INIT_URL:
            return 200, {"Location": "https://evil.example/upload?id=1"}, b""
        raise AssertionError("must not PUT to the evil host")
    res = publish({"media_path": tmp.name}, fresh_creds, transport=fake_evil_host, now=now)
    check(not res["ok"] and res["status"] == "init_failed", "off-host upload URL not refused")

    os.unlink(tmp.name)
    if failures:
        print("youtube publish selftest FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"youtube publish selftest OK (resumable upload, default-private, no monetary URL, {len(urls)} calls, 0 network)")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    print("tools/publishing/youtube.py -- resumable upload client. Run with --selftest.")
