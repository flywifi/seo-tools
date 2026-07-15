"""Instagram publishing client (P51) -- real Instagram Platform content publishing, gated OFF.

Two-step publish (developers.facebook.com/docs/instagram-platform/content-publishing):
  1. POST /{ig-user-id}/media  (IMAGE: image_url; REELS: media_type=REELS + video_url) -> container id
  2. GET /{container-id}?fields=status_code  until FINISHED
  3. POST /{ig-user-id}/media_publish?creation_id=...  -> the published media id
Access token via tools/oauth_flow (creds["instagram"]["publish"]; long-lived 60-day token, refreshed
by a GET). The IG user id is the shared identity at creds["instagram"]["ig_user_id"].

HARD REALITY (surfaced, never faked): Instagram does NOT accept a local file. Meta fetches the media
from a **public https URL** at publish time, so this client requires entry['image_url'] or
entry['video_url']. If only a local path is available, it returns needs_public_url and the caller
routes the post to manual. Also requires a professional account; publishing for others needs Meta
App Review.

SAFETY: only reached when live_publishing_enabled is on AND a human confirmed the post. Injected
`transport` keeps selftests off the network.
"""
from __future__ import annotations

import pathlib
import sys
import time
import urllib.parse

_HERE = pathlib.Path(__file__).resolve().parent
_TOOLS = _HERE.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
import oauth_flow  # noqa: E402
from publishing import _http  # noqa: E402

GRAPH = "https://graph.instagram.com"
_GRAPH_MAJOR = 25          # Meta rotates the Graph version ~quarterly; observed v25.0 (2026-07). Adjust as needed.
GRAPH_VERSION = f"v{_GRAPH_MAJOR}.0"
_MAX_POLLS = 6
_POLL_SECONDS = 3


def publish(entry: dict, creds: dict, *, transport=None, token_transport=None,
            persist=None, now=None, sleep_fn=None) -> dict:
    """Publish one IMAGE or REELS post from a PUBLIC url. Returns {ok, status, post_id, permalink, error}."""
    transport = transport or _http.default_transport
    sleep_fn = sleep_fn or time.sleep
    ig = creds.get("instagram") or {}
    pub = ig.get("publish") or {}

    try:
        access_token, updated = oauth_flow.get_valid_access_token(
            "instagram", pub, transport=token_transport, now=now)
    except oauth_flow.ReauthRequired as exc:
        return {"ok": False, "status": "auth_required", "post_id": None, "permalink": None,
                "error": f"Instagram authorization expired or missing ({exc.code}). Reconnect Instagram."}
    if updated is not None and callable(persist):
        try:
            persist(updated)
        except Exception:  # noqa: BLE001
            pass
    if not access_token:
        return {"ok": False, "status": "auth_required", "post_id": None, "permalink": None,
                "error": "No Instagram access token available. Reconnect Instagram in the setup wizard."}

    ig_user_id = ig.get("ig_user_id") or pub.get("ig_user_id") or ig.get("account_id")
    if not ig_user_id:
        return {"ok": False, "status": "no_account", "post_id": None, "permalink": None,
                "error": "No Instagram professional account id (ig_user_id) is saved. Reconnect Instagram."}

    image_url = entry.get("image_url")
    video_url = entry.get("video_url")
    if not image_url and not video_url:
        return {"ok": False, "status": "needs_public_url", "post_id": None, "permalink": None,
                "error": ("Instagram fetches media from a public https URL and cannot upload a local "
                          "file. Provide entry['image_url'] or entry['video_url'] (a public link), or "
                          "post this one by hand.")}
    caption = entry.get("caption") or entry.get("description") or ""
    base = f"{GRAPH}/{GRAPH_VERSION}"
    form_ct = {"Content-Type": "application/x-www-form-urlencoded"}

    # 1) create the media container.
    params = {"caption": caption, "access_token": access_token}
    if video_url:
        params["media_type"] = "REELS"
        params["video_url"] = video_url
    else:
        params["image_url"] = image_url
    st, _h, raw = transport("POST", f"{base}/{ig_user_id}/media", form_ct,
                            urllib.parse.urlencode(params).encode("utf-8"))
    resp = _http.parse_json(raw)
    if st >= 400 or resp.get("error"):
        return {"ok": False, "status": "container_failed", "post_id": None, "permalink": None,
                "error": f"Instagram would not create the post: {_graph_err(resp, st)}"}
    creation_id = resp.get("id")
    if not creation_id:
        return {"ok": False, "status": "container_failed", "post_id": None, "permalink": None,
                "error": "Instagram did not return a container id."}

    # 2) poll until the container is FINISHED (media is fetched + processed async).
    finished = False
    for attempt in range(_MAX_POLLS):
        st, _h, raw = transport(
            "GET", f"{base}/{creation_id}?fields=status_code&access_token={access_token}", {}, None)
        code = (_http.parse_json(raw).get("status_code") or "").upper()
        if code == "FINISHED":
            finished = True
            break
        if code in ("ERROR", "EXPIRED"):
            return {"ok": False, "status": "container_error", "post_id": creation_id, "permalink": None,
                    "error": f"Instagram could not process the media (status {code})."}
        if attempt < _MAX_POLLS - 1:
            sleep_fn(_POLL_SECONDS)
    if not finished:
        return {"ok": False, "status": "processing_timeout", "post_id": creation_id, "permalink": None,
                "error": "Instagram is still processing the media. Try publishing again shortly."}

    # 3) publish the container.
    st, _h, raw = transport("POST", f"{base}/{ig_user_id}/media_publish", form_ct,
                            urllib.parse.urlencode({"creation_id": creation_id,
                                                    "access_token": access_token}).encode("utf-8"))
    resp = _http.parse_json(raw)
    if st >= 400 or resp.get("error"):
        return {"ok": False, "status": "publish_failed", "post_id": creation_id, "permalink": None,
                "error": f"Instagram would not publish the post: {_graph_err(resp, st)}"}
    media_id = resp.get("id")

    # 4) best-effort permalink.
    permalink = None
    if media_id:
        st, _h, raw = transport(
            "GET", f"{base}/{media_id}?fields=permalink&access_token={access_token}", {}, None)
        permalink = _http.parse_json(raw).get("permalink")
    return {"ok": True, "status": "published", "post_id": media_id, "permalink": permalink, "error": None}


def _graph_err(resp: dict, status: int) -> str:
    err = resp.get("error") or {}
    if isinstance(err, dict) and err:
        return f"{err.get('message', '')} (code {err.get('code', status)})".strip()
    return f"HTTP {status}"


# ── Selftest (no network) ────────────────────────────────────────────────────

def _selftest() -> int:
    failures: list[str] = []
    calls: list[dict] = []
    state = {"polls": 0}

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    now = 1_700_000_000
    AT = "access_token"
    creds = {"instagram": {"ig_user_id": "17841400000000000",
                           "publish": {AT: "IGTOK", "expires_at": now + 9999}}}

    def fake(method, url, headers, body):
        form = dict(urllib.parse.parse_qsl(body.decode())) if body else {}
        calls.append({"method": method, "url": url, "form": form})
        if method == "POST" and url.endswith("/media"):
            check("image_url" in form or "video_url" in form, "container must carry a public media url")
            return 200, {}, b'{"id": "CONTAINER1"}'
        if method == "GET" and "status_code" in url:
            state["polls"] += 1
            code = "IN_PROGRESS" if state["polls"] < 2 else "FINISHED"
            return 200, {}, ('{"status_code": "%s"}' % code).encode()
        if method == "POST" and url.endswith("/media_publish"):
            check(form.get("creation_id") == "CONTAINER1", "media_publish must use the container id")
            return 200, {}, b'{"id": "MEDIA1"}'
        if method == "GET" and "permalink" in url:
            return 200, {}, b'{"permalink": "https://www.instagram.com/p/ABC/"}'
        return 404, {}, b"{}"

    # Happy path: a public image_url.
    res = publish({"image_url": "https://cdn.example.com/x.jpg", "caption": "hi"}, creds,
                  transport=fake, now=now, sleep_fn=lambda _s: None)
    check(res["ok"] and res["post_id"] == "MEDIA1", f"publish failed: {res}")
    check(res["permalink"] == "https://www.instagram.com/p/ABC/", "permalink wrong")
    check(any("/17841400000000000/media" in c["url"] for c in calls), "ig_user_id not used in path")
    check(state["polls"] >= 2, "did not poll container status to FINISHED")
    check(not any(c["method"] == "PUT" for c in calls), "must not upload local bytes")

    # The wall: local file only, no public URL.
    res = publish({"media_path": "/tmp/local.jpg"}, creds, transport=fake, now=now,
                  sleep_fn=lambda _s: None)
    check(not res["ok"] and res["status"] == "needs_public_url", "public-URL wall not surfaced")

    # No account id.
    res = publish({"image_url": "https://cdn.example.com/x.jpg"},
                  {"instagram": {"publish": {AT: "T", "expires_at": now + 9999}}},
                  transport=fake, now=now, sleep_fn=lambda _s: None)
    check(not res["ok"] and res["status"] == "no_account", "missing ig_user_id not caught")

    # Dead token.
    res = publish({"image_url": "https://cdn.example.com/x.jpg"},
                  {"instagram": {"ig_user_id": "1", "publish": {}}},
                  transport=fake, now=now, sleep_fn=lambda _s: None)
    check(not res["ok"] and res["status"] == "auth_required", "no token not surfaced")

    if failures:
        print("instagram publish selftest FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("instagram publish selftest OK (container->poll->publish, public-URL wall, ig_user_id, 0 network)")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    print("tools/publishing/instagram.py -- content publishing client. Run with --selftest.")
