"""Pinterest publishing client (P51) -- real API v5 create-Pin, gated OFF by default.

Creates a Pin via POST https://api.pinterest.com/v5/pins using the **image_base64** media source, so
a local image file is uploaded directly with NO public URL required (docs/PUBLISHING.md). The access
token comes from tools/oauth_flow (creds["pinterest"]["publish"]).

REALITY: with Pinterest **Trial** access, created Pins are Sandbox entities visible only to the
creator until the app is granted Standard access (a video-demo review). This client posts the same
way regardless; the wizard screen states the visibility limit. Video Pins need the separate
media-upload flow and are not handled here yet -- only image Pins.

SAFETY: only reached when live_publishing_enabled is on AND a human confirmed the post. Injected
`transport` keeps selftests off the network.
"""
from __future__ import annotations

import base64
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

CREATE_URL = "https://api.pinterest.com/v5/pins"
_IMAGE_CT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
_VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}


def _media_path(entry: dict):
    for key in ("image_path", "media_path", "file_path", "file", "path"):
        v = entry.get(key)
        if v:
            return v
    return None


def publish(entry: dict, creds: dict, *, transport=None, token_transport=None,
            persist=None, now=None) -> dict:
    """Create one image Pin. Returns {ok, status, post_id, permalink, error}."""
    transport = transport or _http.default_transport
    pub = (creds.get("pinterest") or {}).get("publish") or {}

    try:
        access_token, updated = oauth_flow.get_valid_access_token(
            "pinterest", pub, transport=token_transport, now=now)
    except oauth_flow.ReauthRequired as exc:
        return {"ok": False, "status": "auth_required", "post_id": None, "permalink": None,
                "error": f"Pinterest authorization expired or missing ({exc.code}). Reconnect Pinterest."}
    if updated is not None and callable(persist):
        try:
            persist(updated)
        except Exception:  # noqa: BLE001
            pass
    if not access_token:
        return {"ok": False, "status": "auth_required", "post_id": None, "permalink": None,
                "error": "No Pinterest access token available. Reconnect Pinterest in the setup wizard."}

    board_id = entry.get("board_id") or pub.get("default_board_id")
    if not board_id:
        return {"ok": False, "status": "no_board", "post_id": None, "permalink": None,
                "error": "A Pinterest board_id is required to create a Pin (entry['board_id'])."}

    media = _media_path(entry)
    if not media or not os.path.isfile(media):
        return {"ok": False, "status": "no_media", "post_id": None, "permalink": None,
                "error": "No local image file was found for this Pin (expected entry['image_path'])."}
    ext = os.path.splitext(media)[1].lower()
    if ext in _VIDEO_EXT:
        return {"ok": False, "status": "unsupported_media", "post_id": None, "permalink": None,
                "error": "Only image Pins are supported today. Video Pins need Pinterest's separate "
                         "media-upload flow, which is not wired up yet."}
    content_type = _IMAGE_CT.get(ext, "image/jpeg")

    with open(media, "rb") as f:
        data_b64 = base64.b64encode(f.read()).decode("ascii")
    body = {
        "board_id": board_id,
        "title": (entry.get("title") or "")[:100],
        "description": entry.get("description") or entry.get("caption") or "",
        "media_source": {"source_type": "image_base64", "content_type": content_type, "data": data_b64},
    }
    link = entry.get("link")
    if link:
        body["link"] = link

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    st, _hdrs, raw = transport("POST", CREATE_URL, headers, json.dumps(body).encode("utf-8"))
    resp = _http.parse_json(raw)
    if st in (200, 201):
        pid = resp.get("id")
        return {"ok": True, "status": "published", "post_id": pid,
                "permalink": f"https://www.pinterest.com/pin/{pid}/" if pid else None,
                "error": None}
    return {"ok": False, "status": "create_failed", "post_id": None, "permalink": None,
            "error": f"Pinterest rejected the Pin (HTTP {st}). {resp.get('message', '')}"}


# ── Selftest (no network) ────────────────────────────────────────────────────

def _selftest() -> int:
    import tempfile
    failures: list[str] = []
    sent: dict = {}

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    now = 1_700_000_000
    AT = "access_token"
    good = {"pinterest": {"publish": {AT: "PINA", "expires_at": now + 9999}}}

    img = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    img.close()

    def fake(method, url, headers, body):
        sent["url"] = url
        sent["auth"] = _http.header(headers, "Authorization")
        sent["body"] = json.loads(body.decode())
        return 201, {}, json.dumps({"id": "PIN123"}).encode()

    res = publish({"board_id": "B1", "image_path": img.name, "title": "Hi"}, good,
                  transport=fake, now=now)
    check(res["ok"] and res["post_id"] == "PIN123", f"pin create failed: {res}")
    check(res["permalink"] == "https://www.pinterest.com/pin/PIN123/", "permalink wrong")
    check(sent["url"] == CREATE_URL, "not the v5 pins endpoint")
    check((sent["auth"] or "").startswith("Bearer "), "missing bearer auth")
    ms = sent["body"]["media_source"]
    check(ms["source_type"] == "image_base64" and ms.get("data"), "must upload base64, no public URL")
    check(sent["body"]["board_id"] == "B1", "board_id not sent")

    # Missing board_id.
    res = publish({"image_path": img.name}, good, transport=fake, now=now)
    check(not res["ok"] and res["status"] == "no_board", "missing board_id not caught")

    # Video media -> explicitly unsupported (no silent failure).
    vid = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    vid.write(b"\x00" * 16)
    vid.close()
    res = publish({"board_id": "B1", "image_path": vid.name}, good, transport=fake, now=now)
    check(not res["ok"] and res["status"] == "unsupported_media", "video not flagged unsupported")

    # Dead token.
    res = publish({"board_id": "B1", "image_path": img.name},
                  {"pinterest": {"publish": {}}}, transport=fake, now=now)
    check(not res["ok"] and res["status"] == "auth_required", "no token not surfaced")

    os.unlink(img.name)
    os.unlink(vid.name)
    if failures:
        print("pinterest publish selftest FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("pinterest publish selftest OK (base64 image Pin, no public URL, 0 network)")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    print("tools/publishing/pinterest.py -- create-Pin client. Run with --selftest.")
