"""TikTok publishing client (P51) -- real Content Posting API direct post, gated OFF by default.

Flow (docs.PUBLISHING.md / developers.tiktok.com):
  1. POST .../v2/post/publish/creator_info/query/   -> allowed privacy_level_options, duration cap.
  2. POST .../v2/post/publish/video/init/           -> {publish_id, upload_url}, source=FILE_UPLOAD.
  3. PUT the local video bytes to upload_url in 5-64 MB chunks (Content-Range); NO public URL needed.
  4. POST .../v2/post/publish/status/fetch/          -> processing/published state.

REALITY: an **unaudited** app can only post at SELF_ONLY (private); public posting needs TikTok's
audit. We query creator_info and REFUSE any privacy level the account/app isn't allowed to use, and
default to SELF_ONLY. `post_info.is_aigc` is set from the entry's AIGC flag. Access token via
oauth_flow (creds["tiktok"]["publish"]); refresh tokens rotate and are persisted.

SAFETY: only reached when live_publishing_enabled is on AND a human confirmed the post. Injected
`transport` keeps selftests off the network.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
_TOOLS = _HERE.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
import oauth_flow  # noqa: E402
from publishing import _http  # noqa: E402

_BASE = "https://open.tiktokapis.com/v2/post/publish"
CREATOR_INFO_URL = f"{_BASE}/creator_info/query/"
INIT_URL = f"{_BASE}/video/init/"
STATUS_URL = f"{_BASE}/status/fetch/"

_CHUNK_MIN = 5 * 1024 * 1024      # 5 MiB
_CHUNK_TARGET = 10 * 1024 * 1024  # 10 MiB (within the 5-64 MiB window)


def _media_path(entry: dict):
    for key in ("media_path", "video_path", "file_path", "file", "path"):
        v = entry.get(key)
        if v:
            return v
    return None


def _tt_error(resp: dict):
    """Return an error string if the TikTok envelope indicates failure, else None."""
    err = resp.get("error") or {}
    code = err.get("code")
    if code and code != "ok":
        return f"{code}: {err.get('message', '')}".strip()
    return None


def _chunk_plan(size: int):
    """(chunk_size, total_chunk_count) per TikTok's rules: files < 5 MiB go whole; otherwise
    total_chunk_count = floor(size/chunk_size) and the final chunk carries the remainder."""
    if size <= _CHUNK_MIN:
        return size, 1
    chunk_size = _CHUNK_TARGET
    total = max(1, size // chunk_size)
    return chunk_size, total


def publish(entry: dict, creds: dict, *, transport=None, token_transport=None,
            persist=None, now=None) -> dict:
    """Post one video. Returns {ok, status, post_id, permalink, error}."""
    transport = transport or _http.default_transport
    pub = (creds.get("tiktok") or {}).get("publish") or {}

    try:
        access_token, updated = oauth_flow.get_valid_access_token(
            "tiktok", pub, transport=token_transport, now=now)
    except oauth_flow.ReauthRequired as exc:
        return {"ok": False, "status": "auth_required", "post_id": None, "permalink": None,
                "error": f"TikTok authorization expired or missing ({exc.code}). Reconnect TikTok."}
    if updated is not None and callable(persist):
        try:
            persist(updated)   # TikTok rotates refresh tokens; persist the new one
        except Exception:  # noqa: BLE001
            pass
    if not access_token:
        return {"ok": False, "status": "auth_required", "post_id": None, "permalink": None,
                "error": "No TikTok access token available. Reconnect TikTok in the setup wizard."}
    auth = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}

    media = _media_path(entry)
    if not media or not os.path.isfile(media):
        return {"ok": False, "status": "no_media", "post_id": None, "permalink": None,
                "error": "No local video file was found for this entry (expected entry['media_path'])."}
    size = os.path.getsize(media)
    # A2a: refuse an empty file BEFORE any network init. _chunk_plan(0) would otherwise build a
    # malformed 'Content-Range: bytes 0--1/0' and PUT a zero-length chunk.
    if size <= 0:
        return {"ok": False, "status": "empty_media", "post_id": None, "permalink": None,
                "error": "The video file is empty (0 bytes). Re-download or re-export it, then retry."}

    # 1) creator_info: which privacy levels is this (possibly unaudited) app/account allowed to use?
    st, _h, raw = transport("POST", CREATOR_INFO_URL, auth, b"{}")
    info = _http.parse_json(raw)
    err = _tt_error(info) if st < 400 else f"HTTP {st}"
    if err:
        return {"ok": False, "status": "creator_info_failed", "post_id": None, "permalink": None,
                "error": f"Could not read your TikTok posting options ({err})."}
    options = ((info.get("data") or {}).get("privacy_level_options")) or ["SELF_ONLY"]

    requested = str(entry.get("privacy_level") or "SELF_ONLY").upper()
    if requested not in options:
        return {"ok": False, "status": "privacy_not_allowed", "post_id": None, "permalink": None,
                "error": (f"TikTok will not allow privacy level {requested} for this app yet. Allowed: "
                          f"{', '.join(options)}. Public posting needs TikTok to audit your app; until "
                          f"then posts can only be private (SELF_ONLY).")}

    # 2) init the FILE_UPLOAD (local bytes, no public URL).
    chunk_size, total = _chunk_plan(size)
    post_info = {
        "title": (entry.get("title") or entry.get("caption") or "")[:2200],
        "privacy_level": requested,
        "disable_comment": bool(entry.get("disable_comment", False)),
        "disable_duet": bool(entry.get("disable_duet", False)),
        "disable_stitch": bool(entry.get("disable_stitch", False)),
        "is_aigc": bool(entry.get("is_aigc", False)),
    }
    if entry.get("video_cover_timestamp_ms") is not None:
        post_info["video_cover_timestamp_ms"] = int(entry["video_cover_timestamp_ms"])
    init_body = {"post_info": post_info,
                 "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                                 "chunk_size": chunk_size, "total_chunk_count": total}}
    st, _h, raw = transport("POST", INIT_URL, auth, json.dumps(init_body).encode("utf-8"))
    init = _http.parse_json(raw)
    err = _tt_error(init) if st < 400 else f"HTTP {st}"
    if err:
        return {"ok": False, "status": "init_failed", "post_id": None, "permalink": None,
                "error": f"TikTok would not start the upload ({err})."}
    data = init.get("data") or {}
    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")
    if not publish_id or not upload_url:
        return {"ok": False, "status": "init_failed", "post_id": None, "permalink": None,
                "error": "TikTok did not return an upload URL."}

    # 3) upload the bytes in sequential chunks.
    with open(media, "rb") as f:
        for i in range(total):
            first = i * chunk_size
            last = size - 1 if i == total - 1 else first + chunk_size - 1
            f.seek(first)
            chunk = f.read(last - first + 1)
            put_headers = {
                "Content-Type": entry.get("content_type") or "video/mp4",
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {first}-{last}/{size}",
            }
            st, _h, _raw = transport("PUT", upload_url, put_headers, chunk)
            if st not in (200, 201, 206, 308):
                return {"ok": False, "status": "upload_failed", "post_id": publish_id, "permalink": None,
                        "error": f"Chunk upload to TikTok failed (HTTP {st})."}

    # 4) status (best-effort; TikTok processing is async).
    st, _h, raw = transport("POST", STATUS_URL, auth,
                            json.dumps({"publish_id": publish_id}).encode("utf-8"))
    status_data = (_http.parse_json(raw).get("data") or {})
    tt_status = status_data.get("status") or "PROCESSING"
    return {"ok": True, "status": "published" if tt_status in ("PUBLISH_COMPLETE",) else "processing",
            "post_id": publish_id, "permalink": None, "tiktok_status": tt_status,
            "privacy_level": requested, "error": None}


# ── Selftest (no network) ────────────────────────────────────────────────────

def _selftest() -> int:
    import tempfile
    failures: list[str] = []
    calls: list[dict] = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    now = 1_700_000_000
    AT = "access_token"
    good = {"tiktok": {"publish": {AT: "TT", "expires_at": now + 9999}}}

    vid = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    vid.write(b"\x00" * 2048)   # < 5 MiB -> single whole chunk
    vid.close()

    def fake(method, url, headers, body):
        rec = {"method": method, "url": url}
        if body and headers.get("Content-Type", "").startswith("application/json"):
            rec["body"] = json.loads(body.decode())
        calls.append(rec)
        if url == CREATOR_INFO_URL:
            return 200, {}, json.dumps({"data": {"privacy_level_options": ["SELF_ONLY"]},
                                        "error": {"code": "ok"}}).encode()
        if url == INIT_URL:
            return 200, {}, json.dumps({"data": {"publish_id": "PUB1",
                                        "upload_url": "https://open-upload.tiktokapis.com/x"},
                                        "error": {"code": "ok"}}).encode()
        if url.startswith("https://open-upload.tiktokapis.com"):
            return 200, {}, b""
        if url == STATUS_URL:
            return 200, {}, json.dumps({"data": {"status": "PROCESSING_UPLOAD"},
                                        "error": {"code": "ok"}}).encode()
        return 404, {}, b"{}"

    res = publish({"media_path": vid.name, "title": "hi", "is_aigc": True}, good,
                  transport=fake, now=now)
    check(res["ok"] and res["post_id"] == "PUB1", f"post failed: {res}")
    check(res["status"] == "processing", "async status not surfaced")
    # creator_info queried FIRST.
    check(calls[0]["url"] == CREATOR_INFO_URL, "creator_info must be queried before init")
    init_call = next(c for c in calls if c["url"] == INIT_URL)
    check(init_call["body"]["post_info"]["is_aigc"] is True, "is_aigc flag not carried")
    check(init_call["body"]["post_info"]["privacy_level"] == "SELF_ONLY", "default privacy not SELF_ONLY")
    check(init_call["body"]["source_info"]["source"] == "FILE_UPLOAD", "must upload local file, not a URL")
    check(init_call["body"]["source_info"]["total_chunk_count"] == 1, "small file should be one chunk")
    # A PUT actually happened to the upload URL (bytes, not a public URL fetch).
    check(any(c["url"].startswith("https://open-upload") and c["method"] == "PUT" for c in calls),
          "no chunk PUT to the upload URL")
    # No public content URL anywhere (source_info has no video_url).
    check("video_url" not in init_call["body"]["source_info"], "must not use PULL_FROM_URL")

    # Requesting a public level an unaudited app cannot use -> refused.
    res = publish({"media_path": vid.name, "privacy_level": "PUBLIC_TO_EVERYONE"}, good,
                  transport=fake, now=now)
    check(not res["ok"] and res["status"] == "privacy_not_allowed", "public-when-unaudited not refused")

    # Dead token.
    res = publish({"media_path": vid.name}, {"tiktok": {"publish": {}}}, transport=fake, now=now)
    check(not res["ok"] and res["status"] == "auth_required", "no token not surfaced")

    # A2a: a 0-byte file -> empty_media before any network init (no malformed 'bytes 0--1/0').
    empty = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    empty.close()
    seen = []
    res = publish({"media_path": empty.name}, good, transport=(lambda m, u, h, b: seen.append(u) or (200, {}, b"{}")),
                  now=now)
    check(not res["ok"] and res["status"] == "empty_media", "0-byte file not refused")
    check(not seen, "empty_media must not make any network call")
    os.unlink(empty.name)

    os.unlink(vid.name)
    if failures:
        print("tiktok publish selftest FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("tiktok publish selftest OK (creator_info gate, FILE_UPLOAD local bytes, is_aigc, SELF_ONLY default, 0 network)")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    print("tools/publishing/tiktok.py -- Content Posting client. Run with --selftest.")
