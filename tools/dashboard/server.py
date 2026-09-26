#!/usr/bin/env python3
"""Creator OS Scheduling Dashboard — browser-based GUI for managing social media posts.

Serves static HTML/CSS/JS on port 8766 and exposes a JSON API for managing the
scheduling queue. The dashboard is a human-in-the-loop scheduler: the "Confirm and
Schedule" click IS the human confirmation step, and it runs the shared FTC/AIGC/tier
compliance checks (tools/publishing_compliance.py) before any status change.

No live platform publishing happens here unless the `live_publishing_enabled`
capability flag is set (see tools/publishing/). While that flag is off (default),
the background scheduler only advances due items to `ready_to_post` for manual
posting — it makes NO network call to any platform.

Usage:
    python3 tools/dashboard/server.py

Requires no external dependencies (stdlib only).
"""

import json
import os
import re
import sys
import threading
import uuid
import webbrowser
from datetime import datetime, timezone
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# tools/ on the path so we can import the shared compliance helper + publishing seam
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import publishing_compliance as compliance  # noqa: E402
import publishing  # noqa: E402
import atomic_io  # noqa: E402  (the one atomic writer, P81)
import finance  # noqa: E402  (P31: read-only AR view)
import tasks as _tasks  # noqa: E402  (P35: read-only task view)

ROOT = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
QUEUE_PATH = ROOT / "pipeline" / "user-context" / "scheduling-queue.local.json"
CREDS_PATH = ROOT / "pipeline" / "user-context" / "api-credentials.local.json"

PORT = 8766
PLATFORMS = ["instagram", "tiktok", "pinterest", "youtube"]

# Only same-origin browser requests are allowed to mutate state (localhost CSRF defense).
ALLOWED_ORIGINS = {f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"}
MAX_BODY_BYTES = 2 * 1024 * 1024  # 2 MiB cap on request bodies
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_shutdown = threading.Event()
# One lock serializes every read-modify-write of the queue file across the HTTP
# thread and the background scheduler thread (prevents lost updates).
_queue_lock = threading.Lock()


def _safe_id(raw):
    """Accept an id only if it is a safe slug/UUID; otherwise mint a fresh UUID.
    Prevents crafted ids (e.g. containing quotes) from reaching the DOM."""
    if isinstance(raw, str) and _ID_RE.match(raw):
        return raw
    return str(uuid.uuid4())


def _load_config():
    return compliance.load_config()


def _load_queue():
    if QUEUE_PATH.exists():
        try:
            return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"queue": []}


def _save_queue(data):
    """Atomic write: temp file + os.replace so readers never see a truncated file."""
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE_PATH.with_name(QUEUE_PATH.name + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, QUEUE_PATH)


def _get_publishing_plan(config):
    plan = {}
    for plat in PLATFORMS:
        flag = f"{plat}_publishing"
        if compliance.flag_enabled(config, flag):
            plan[plat] = {"tier": "direct_api", "connector": f"{plat}_publish_api"}
        else:
            plan[plat] = {"tier": "manual", "connector": "manual_post"}
    return plan


def _get_credentials_status():
    creds = compliance.load_credentials()
    return {plat: bool(creds.get(plat)) for plat in PLATFORMS}


# Control fields that ONLY the human Confirm path (_handle_schedule) or the
# scheduler may set. Stripped from any add-to-queue / import payload so an injected
# status='scheduled' (or a forged post_id/permalink/schedule) cannot masquerade as
# human confirmation and get dispatched to the real API.
_PROTECTED_PLATFORM_FIELDS = frozenset({
    "status", "scheduled_datetime", "post_id", "permalink", "error",
    "publishing_tier", "human_review_required", "ftc_prepended", "aigc_flag_set",
})


def _sanitize_platform_input(pdata):
    """Return a copy of caller-supplied platform data with protected control fields
    removed. Content fields (enabled, caption, ftc_disclosure, is_aigc, ...)
    pass through; confirmation/scheduling state does not."""
    if not isinstance(pdata, dict):
        return {}
    return {k: v for k, v in pdata.items() if k not in _PROTECTED_PLATFORM_FIELDS}


def _new_platform_entry():
    return {
        "enabled": False,
        "scheduled_datetime": None,
        "caption": "",
        "hashtags": [],
        "content_type": None,
        "media_url": None,
        "ftc_disclosure": None,
        "ftc_disclosure_verified": False,
        "ftc_prepended": False,
        "is_aigc": False,
        "aigc_flag_set": False,
        "publishing_tier": None,
        "status": "draft",
        "post_id": None,
        "permalink": None,
        "error": None,
        "human_review_required": False,
    }


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format, *args):
        pass

    # ── request helpers ────────────────────────────────────────────

    def _origin_ok(self):
        """Reject a mutating request only when a browser sent a foreign Origin.
        Non-browser clients (curl, local scripts) send no Origin and are allowed;
        they are not a browser-CSRF vector and there is no ambient auth to abuse."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        return origin in ALLOWED_ORIGINS

    def _read_body(self):
        # Enforce JSON content type: blocks the CORS "simple request" bypass, since
        # a cross-origin application/json POST triggers a preflight we never approve.
        ctype = self.headers.get("Content-Type", "")
        if not ctype.split(";")[0].strip() == "application/json":
            self._json_response(
                {"error": "Content-Type must be application/json"}, status=415
            )
            return None
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self._json_response({"error": "invalid Content-Length"}, status=400)
            return None
        if length <= 0:
            self._json_response({"error": "empty body"}, status=400)
            return None
        if length > MAX_BODY_BYTES:
            self._json_response({"error": "request body too large"}, status=413)
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self._json_response({"error": "invalid JSON"}, status=400)
            return None

    def _json_response(self, data, status=200):
        # No Access-Control-Allow-Origin header: the SPA is same-origin, and a
        # wildcard would let any page read the queue/credentials cross-origin.
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── routing ────────────────────────────────────────────────────

    def do_OPTIONS(self):
        # Deny cross-origin preflight cleanly (no CORS headers emitted anywhere).
        self.send_response(403)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "":
            self.path = "/index.html"
            return super().do_GET()

        if path.startswith("/static/"):
            self.path = path[len("/static"):]
            return super().do_GET()

        if path == "/api/queue":
            with _queue_lock:
                return self._json_response(_load_queue())

        if path == "/api/ar":
            # P31: read-only accounts-receivable view over pipeline/finance/*.local.json.
            # Real money data; the server binds localhost only and this route never writes.
            try:
                return self._json_response(finance.ar_scan(None, None))
            except Exception as exc:  # noqa: BLE001
                return self._json_response({"error": str(exc)}, status=500)

        if path == "/api/tasks":
            # P35: read-only task view over pipeline/user-context/task-register.local.json.
            # Waiting-on-counterparty vs I-owe split + due-soon/overdue bands. Never writes; localhost only.
            try:
                from datetime import date as _date
                reg = _tasks.load_register("local_fs")
                return self._json_response(_tasks.scan(reg, _date.today()))
            except Exception as exc:  # noqa: BLE001
                return self._json_response({"error": str(exc)}, status=500)

        if path == "/api/publishing-plan":
            return self._json_response(_get_publishing_plan(_load_config()))

        if path == "/api/credentials-status":
            return self._json_response(_get_credentials_status())

        if path.startswith("/api/status/"):
            item_id = path.split("/api/status/", 1)[1]
            with _queue_lock:
                queue = _load_queue()
            for item in queue.get("queue", []):
                if item.get("id") == item_id:
                    return self._json_response(item)
            return self._json_response({"error": "not found"}, status=404)

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if not self._origin_ok():
            return self._json_response(
                {"error": "cross-origin request rejected"}, status=403
            )

        body = self._read_body()
        if body is None:
            return

        handlers = {
            "/api/queue": self._handle_add_to_queue,
            "/api/import-report": self._handle_import_report,
            "/api/schedule": self._handle_schedule,
            "/api/toggle-platform": self._handle_toggle_platform,
            "/api/update-caption": self._handle_update_caption,
            "/api/update-schedule": self._handle_update_schedule,
            "/api/delete-item": self._handle_delete_item,
        }
        handler = handlers.get(path)
        if handler is None:
            return self._json_response({"error": "not found"}, status=404)
        return handler(body)

    # ── mutation handlers (all guarded by _queue_lock) ─────────────

    def _handle_add_to_queue(self, body):
        item_id = _safe_id(body.get("item_id") or body.get("id"))
        title = body.get("title", "Untitled post")
        source = body.get("source", "manual")

        with _queue_lock:
            queue = _load_queue()
            existing = None
            for item in queue["queue"]:
                if item.get("id") == item_id:
                    existing = item
                    break

            if existing:
                for key in ("title", "source"):
                    if key in body:
                        existing[key] = body[key]
                if isinstance(body.get("platforms"), dict):
                    plats = existing.setdefault("platforms", {})
                    for plat, pdata in body["platforms"].items():
                        if not isinstance(pdata, dict):
                            continue
                        if plat not in plats:
                            plats[plat] = _new_platform_entry()
                        plats[plat].update(_sanitize_platform_input(pdata))
            else:
                platforms = {}
                body_platforms = body.get("platforms") if isinstance(body.get("platforms"), dict) else {}
                for plat in PLATFORMS:
                    entry = _new_platform_entry()
                    if isinstance(body_platforms.get(plat), dict):
                        entry.update(_sanitize_platform_input(body_platforms[plat]))
                    platforms[plat] = entry
                queue["queue"].append({
                    "id": item_id,
                    "title": title,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "source": source,
                    "platforms": platforms,
                })
            _save_queue(queue)
        self._json_response({"ok": True, "id": item_id})

    def _handle_import_report(self, body):
        """Flatten a content-distribution report (flat posts[] rows, one per platform)
        into a single queue item. Maps the report's field names to the queue schema
        (ftc_disclosure_verified/aigc_flag_set -> ftc_disclosure/is_aigc)."""
        posts = body.get("posts")
        if not isinstance(posts, list) or not posts:
            return self._json_response({"error": "posts[] array required"}, status=400)
        item_id = _safe_id(body.get("item_id") or body.get("id"))
        title = body.get("title") or "Imported content package"

        platforms = {}
        for row in posts:
            if not isinstance(row, dict):
                continue
            plat = (row.get("platform") or "").lower()
            if plat not in PLATFORMS:
                continue
            entry = _new_platform_entry()
            entry["enabled"] = True
            entry["caption"] = row.get("caption") or ""
            entry["hashtags"] = row.get("hashtags") or []
            entry["content_type"] = row.get("content_type")
            entry["media_url"] = row.get("media_url")
            entry["scheduled_datetime"] = row.get("scheduled_datetime")
            entry["ftc_disclosure"] = row.get("ftc_disclosure")
            entry["is_aigc"] = bool(row.get("aigc_flag_set") or row.get("is_aigc"))
            entry["status"] = "draft"
            platforms[plat] = entry

        if not platforms:
            return self._json_response(
                {"error": "no recognizable platform rows in posts[]"}, status=400
            )

        with _queue_lock:
            queue = _load_queue()
            existing = next((i for i in queue["queue"] if i.get("id") == item_id), None)
            if existing:
                existing["title"] = title
                existing.setdefault("platforms", {}).update(platforms)
            else:
                queue["queue"].append({
                    "id": item_id,
                    "title": title,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "source": "content-distributor",
                    "platforms": platforms,
                })
            _save_queue(queue)
        self._json_response({"ok": True, "id": item_id, "platforms_imported": sorted(platforms)})

    def _handle_schedule(self, body):
        item_id = body.get("item_id")
        platform = body.get("platform")
        if not item_id or not platform:
            return self._json_response(
                {"error": "item_id and platform required"}, status=400
            )

        config = _load_config()
        with _queue_lock:
            queue = _load_queue()
            for item in queue["queue"]:
                if item.get("id") != item_id:
                    continue
                pdata = item.get("platforms", {}).get(platform)
                if not pdata:
                    return self._json_response(
                        {"error": f"platform {platform} not found on item"}, status=404
                    )
                if not pdata.get("enabled"):
                    return self._json_response(
                        {"error": f"platform {platform} is not enabled"}, status=400
                    )

                # Compliance gate — refuse rather than schedule a non-compliant post.
                result = compliance.check(
                    platform,
                    caption=pdata.get("caption", ""),
                    ftc_disclosure=pdata.get("ftc_disclosure") or "",
                    is_aigc=bool(pdata.get("is_aigc")),
                    config=config,
                )
                if not result["ok"]:
                    return self._json_response(
                        {"error": result["error"], "compliance": result}, status=400
                    )

                pdata["caption"] = result["effective_caption"]
                pdata["ftc_disclosure_verified"] = result["ftc_disclosure_verified"]
                pdata["ftc_prepended"] = result["ftc_prepended"]
                pdata["aigc_flag_set"] = result["aigc_flag_set"]
                pdata["publishing_tier"] = result["tier"]
                pdata["status"] = "scheduled"
                pdata["human_review_required"] = True
                _save_queue(queue)
                return self._json_response({
                    "ok": True,
                    "item_id": item_id,
                    "platform": platform,
                    "status": "scheduled",
                    "publishing_tier": result["tier"],
                    "ftc_disclosure_verified": result["ftc_disclosure_verified"],
                    "aigc_flag_set": result["aigc_flag_set"],
                    "human_review_required": True,
                })
        self._json_response({"error": "item not found"}, status=404)

    def _handle_toggle_platform(self, body):
        item_id = body.get("item_id")
        platform = body.get("platform")
        enabled = body.get("enabled")
        if not item_id or not platform or enabled is None:
            return self._json_response(
                {"error": "item_id, platform, and enabled required"}, status=400
            )

        with _queue_lock:
            queue = _load_queue()
            for item in queue["queue"]:
                if item.get("id") == item_id:
                    if platform not in item.get("platforms", {}):
                        item.setdefault("platforms", {})[platform] = _new_platform_entry()
                    item["platforms"][platform]["enabled"] = bool(enabled)
                    _save_queue(queue)
                    return self._json_response({"ok": True})
        self._json_response({"error": "item not found"}, status=404)

    def _handle_update_caption(self, body):
        item_id = body.get("item_id")
        platform = body.get("platform")
        if not item_id or not platform:
            return self._json_response(
                {"error": "item_id and platform required"}, status=400
            )

        with _queue_lock:
            queue = _load_queue()
            for item in queue["queue"]:
                if item.get("id") == item_id:
                    pdata = item.get("platforms", {}).get(platform)
                    if not pdata:
                        return self._json_response(
                            {"error": f"platform {platform} not found"}, status=404
                        )
                    for field in ("caption", "hashtags", "content_type",
                                  "media_url", "ftc_disclosure", "is_aigc"):
                        if field in body:
                            pdata[field] = body[field]
                    _save_queue(queue)
                    return self._json_response({"ok": True})
        self._json_response({"error": "item not found"}, status=404)

    def _handle_update_schedule(self, body):
        item_id = body.get("item_id")
        platform = body.get("platform")
        scheduled_datetime = body.get("scheduled_datetime")
        if not item_id or not platform:
            return self._json_response(
                {"error": "item_id and platform required"}, status=400
            )

        with _queue_lock:
            queue = _load_queue()
            for item in queue["queue"]:
                if item.get("id") == item_id:
                    pdata = item.get("platforms", {}).get(platform)
                    if not pdata:
                        return self._json_response(
                            {"error": f"platform {platform} not found"}, status=404
                        )
                    pdata["scheduled_datetime"] = scheduled_datetime
                    _save_queue(queue)
                    return self._json_response({"ok": True})
        self._json_response({"error": "item not found"}, status=404)

    def _handle_delete_item(self, body):
        item_id = body.get("item_id")
        if not item_id:
            return self._json_response({"error": "item_id required"}, status=400)

        with _queue_lock:
            queue = _load_queue()
            before = len(queue["queue"])
            queue["queue"] = [i for i in queue["queue"] if i.get("id") != item_id]
            if len(queue["queue"]) == before:
                return self._json_response({"error": "item not found"}, status=404)
            _save_queue(queue)
        self._json_response({"ok": True})


def _save_publish_creds(platform, updated):
    """Persist a client's refreshed/rotated publish-creds (P57 F3).

    Called by a publishing client (via the persist callable threaded through
    dispatch) when a token refresh occurred -- notably TikTok, whose refresh_token
    ROTATES, so dropping the update would force a reconnect next cycle. Merges
    `updated` under creds[platform]['publish'] and writes the gitignored
    api-credentials.local.json. Best-effort: never raises into the scheduler.
    """
    if not isinstance(updated, dict) or not platform:
        return
    try:
        with atomic_io.locked(CREDS_PATH):
            existed = CREDS_PATH.exists()
            current = {}
            if existed:
                current = json.loads(CREDS_PATH.read_text(encoding="utf-8")) or {}
            if not isinstance(current, dict):
                current = {}
            plat = current.setdefault(platform, {})
            if not isinstance(plat, dict):
                plat = current[platform] = {}
            pub = plat.get("publish")
            if isinstance(pub, dict):
                pub.update(updated)
            else:
                plat["publish"] = dict(updated)
            CREDS_PATH.parent.mkdir(parents=True, exist_ok=True)
            atomic_io.atomic_write_text(CREDS_PATH, json.dumps(current, indent=2) + "\n")
            if not existed:
                os.chmod(CREDS_PATH, 0o600)  # tokens at rest: the wizard's convention for this file
    except (OSError, ValueError) as exc:
        # background path: must not raise into the scheduler, but must not be silent either (P81)
        print(f"[dashboard] WARNING: could not persist refreshed {platform} token to "
              f"{CREDS_PATH.name}: {exc}", file=sys.stderr)


def _apply_dispatch_result(pdata, res):
    """Record a dispatch() result on the queue item honestly.

    Success is keyed on res['ok'], not on status-string membership: the clients
    return many ok=False refusals (empty_media, needs_public_url, upload_failed,
    no_board, ...) and every one of them must land as 'failed' with its error,
    never as 'published' with a null post_id.
    """
    status = res.get("status")
    if status in ("gated", "unconfirmed", "auth_required"):
        # Defense-in-depth refusal or a dead token: do not mark published.
        pdata["status"] = "ready_to_post" if status != "auth_required" else "auth_required"
        pdata["error"] = res.get("error")
    elif res.get("ok"):
        pdata["status"] = "published"
        pdata["post_id"] = res.get("post_id")
        pdata["permalink"] = res.get("permalink")
        pdata["error"] = None
    else:
        pdata["status"] = "failed"
        pdata["error"] = res.get("error") or status or "publish failed"


def _scheduler_tick(queue, config, creds, now):
    """One scheduler pass over an in-memory queue; returns True when any entry changed.

    Only a due entry whose status is 'scheduled' (set only by a human clicking Confirm) is
    touched. While `live_publishing_enabled` is off (default), it advances to 'ready_to_post'
    for manual posting and no platform network call is made. An entry goes to
    publishing.dispatch() only when the master flag AND its platform's `{platform}_publishing`
    flag are on; a manual-tier entry advances to ready_to_post even with the master flag on.
    dispatch() is called with allow_live=None, so it reads the master flag from `config` again
    and refuses with `gated` when it is off. The result is recorded as 'published' with the
    real post_id/permalink, or 'failed' with the error.
    """
    live = compliance.live_publishing_enabled(config)
    changed = False
    for item in queue.get("queue", []):
        for platform, pdata in item.get("platforms", {}).items():
            if not (
                pdata.get("enabled")
                and pdata.get("status") == "scheduled"
                and pdata.get("scheduled_datetime")
            ):
                continue
            try:
                sched = datetime.fromisoformat(pdata["scheduled_datetime"])
                if sched.tzinfo is None:
                    sched = sched.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
            if sched > now:
                continue
            # Due now, and a human confirmed it (status == 'scheduled'). The master flag and the
            # platform's own flag must both be on before a network call.
            tier_live = live and compliance.flag_enabled(config, f"{platform}_publishing")
            if tier_live:
                try:
                    # The full creds map (each client re-indexes creds[platform]['publish']) and a
                    # persist callback so a rotated token is saved. allow_live=None: dispatch reads
                    # the master flag from `config` itself and refuses when it is off.
                    res = publishing.dispatch(
                        platform, pdata, creds,
                        config=config, allow_live=None, confirmed=True,
                        persist=(lambda upd, _p=platform: _save_publish_creds(_p, upd)),
                    )
                    _apply_dispatch_result(pdata, res)
                except NotImplementedError as exc:
                    pdata["status"] = "ready_to_post"
                    pdata["error"] = str(exc)
                except Exception as exc:  # noqa: BLE001
                    pdata["status"] = "failed"
                    pdata["error"] = str(exc)
            else:
                # No network call; the entry is due for manual posting.
                pdata["status"] = "ready_to_post"
            changed = True
    return changed


def _scheduler_loop():
    """Every 60 seconds: load the config, credentials and queue, run one _scheduler_tick over
    them, and save the queue when the tick changed it. The config reaches the tick exactly as
    loaded; the selftest drives this loop for one pass to pin that."""
    while not _shutdown.is_set():
        _shutdown.wait(60)
        if _shutdown.is_set():
            break
        config = _load_config()
        creds = compliance.load_credentials()
        now = datetime.now(timezone.utc)
        with _queue_lock:
            queue = _load_queue()
            if _scheduler_tick(queue, config, creds, now):
                _save_queue(queue)


class _NetRecorder:
    """Selftest seam: records every outbound connection attempt at urllib.request.urlopen and
    socket.create_connection, the stdlib calls the publishing clients' HTTP goes through, and
    refuses each one with OSError, so a check can observe network calls instead of inferring
    them from a status string."""

    def __enter__(self):
        import socket
        import urllib.request
        self.calls = []
        self._saved = (urllib.request.urlopen, socket.create_connection)

        def _urlopen(req, *args, **kwargs):
            self.calls.append(getattr(req, "full_url", req))
            raise OSError("selftest: network refused")

        def _connect(address, *args, **kwargs):
            self.calls.append(address)
            raise OSError("selftest: network refused")

        urllib.request.urlopen, socket.create_connection = _urlopen, _connect
        return self

    def __exit__(self, *exc):
        import socket
        import urllib.request
        urllib.request.urlopen, socket.create_connection = self._saved
        return False


def _run_scheduler_once(queue, config, creds):
    """Selftest seam: run the real _scheduler_loop for exactly one pass with `queue`, `config` and
    `creds` injected at its module-level seams (no wait, no file read or write), then restore
    every seam. Returns the queue as the pass left it."""
    g = globals()
    names = ("_shutdown", "_load_config", "_load_queue", "_save_queue", "_save_publish_creds")
    saved = {n: g[n] for n in names}
    saved_creds = compliance.load_credentials

    class _OnePass:
        polls = 0

        def is_set(self):
            self.polls += 1
            return self.polls > 2

        def wait(self, timeout=None):
            return False

    g.update(_shutdown=_OnePass(), _load_config=lambda: config, _load_queue=lambda: queue,
             _save_queue=lambda data: None, _save_publish_creds=lambda platform, updated: None)
    compliance.load_credentials = lambda: creds
    try:
        _scheduler_loop()
    finally:
        g.update(saved)
        compliance.load_credentials = saved_creds
    return queue


def _selftest_fixtures():
    """Selftest data: publish credentials for every platform (a far-future epoch expiry, so no
    token refresh) and the content fields each of the four clients needs before its first
    request (a real local file as media, a public image URL, a board id, an Instagram account id)."""
    creds = {p: {"publish": {"access_token": "AT", "expires_at": 4102444800}} for p in PLATFORMS}
    creds["instagram"]["ig_user_id"] = "1"
    content = {"media_path": __file__, "image_path": __file__, "board_id": "board1",
               "image_url": "https://example.invalid/x.jpg"}
    return creds, content


def _selftest_due_queue(content, status="scheduled"):
    """One queue item, due since 2000, enabled on every platform with the given status."""
    entry = dict(content, enabled=True, status=status,
                 scheduled_datetime="2000-01-01T00:00:00+00:00")
    return {"queue": [{"id": "selftest", "platforms": {p: dict(entry) for p in PLATFORMS}}]}


def _selftest() -> int:
    """Offline: _apply_dispatch_result records every dispatch outcome honestly."""
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    p = {}
    _apply_dispatch_result(p, {"ok": True, "status": "published", "post_id": "X1", "permalink": "https://example/x1"})
    ok("ok=True -> published with post_id", p["status"] == "published" and p["post_id"] == "X1" and p["error"] is None)

    for refusal in ("empty_media", "needs_public_url", "upload_failed", "no_board", "privacy_not_allowed"):
        p = {}
        _apply_dispatch_result(p, {"ok": False, "status": refusal, "post_id": None,
                                   "permalink": None, "error": f"{refusal} detail"})
        ok(f"ok=False {refusal} -> failed, never published",
           p["status"] == "failed" and p["error"] == f"{refusal} detail")

    p = {}
    _apply_dispatch_result(p, {"ok": False, "status": "gated", "error": "flag off"})
    ok("gated -> ready_to_post", p["status"] == "ready_to_post")
    p = {}
    _apply_dispatch_result(p, {"ok": False, "status": "auth_required", "error": "reconnect"})
    ok("auth_required kept as auth_required", p["status"] == "auth_required")
    p = {}
    _apply_dispatch_result(p, {"ok": False})
    ok("statusless failure still carries an error string", p["status"] == "failed" and p["error"])

    # Human confirmation: only the Confirm endpoint (_handle_schedule) marks a post 'scheduled'.
    # Forged confirmation fields go through the add, import, caption, toggle and schedule-edit
    # endpoints, then the real scheduler loop runs with every publishing flag on and the network
    # observed.
    store = {"queue": []}
    replies = []

    class _Request:
        def _json_response(self, data, status=200):
            replies.append(status)

    g = globals()
    saved = {n: g[n] for n in ("_load_queue", "_save_queue", "_load_config")}
    saved_creds = compliance.load_credentials
    g.update(_load_queue=lambda: store, _save_queue=lambda data: None, _load_config=lambda: {})
    compliance.load_credentials = lambda: {}
    try:
        creds, content = _selftest_fixtures()
        due = "2000-01-01T00:00:00+00:00"
        forged = dict(content, enabled=True, status="scheduled", human_review_required=True,
                      post_id="forged", scheduled_datetime=due, caption="x")
        req = _Request()
        for _ in range(2):  # a new item, then an update to the same item
            DashboardHandler._handle_add_to_queue(
                req, {"id": "hc", "platforms": {p: dict(forged) for p in PLATFORMS}})
        DashboardHandler._handle_import_report(
            req, {"id": "hc2", "posts": [dict(forged, platform=p) for p in PLATFORMS]})
        for p in PLATFORMS:
            for item_id in ("hc", "hc2"):
                DashboardHandler._handle_update_caption(req, dict(forged, item_id=item_id, platform=p))
                DashboardHandler._handle_toggle_platform(
                    req, {"item_id": item_id, "platform": p, "enabled": True})
                DashboardHandler._handle_update_schedule(
                    req, {"item_id": item_id, "platform": p, "scheduled_datetime": due})
        entries = [pd for it in store["queue"] for pd in it["platforms"].values()]
        ok("only the Confirm endpoint marks a post confirmed: add, import, caption, toggle and "
           "schedule edits cannot set its status or human_review_required",
           len(entries) == 8 and not any(pd.get("status") == "scheduled" or pd.get("post_id")
                                         or pd.get("human_review_required") for pd in entries))
        every_flag_on = {"capabilities": dict({f"{p}_publishing": True for p in PLATFORMS},
                                              live_publishing_enabled=True)}
        with _NetRecorder() as net:
            _run_scheduler_once(store, every_flag_on, creds)
        ok("every flag on: a post no human confirmed never reaches the network",
           net.calls == [] and len(entries) == 8)
        DashboardHandler._handle_schedule(req, {"item_id": "hc", "platform": "youtube"})
        confirmed = store["queue"][0]["platforms"]["youtube"]
        ok("Confirm marks the post scheduled with human_review_required (the probe sees the transition)",
           confirmed.get("status") == "scheduled" and confirmed.get("human_review_required") is True)
    finally:
        g.update(saved)
        compliance.load_credentials = saved_creds

    # The scheduler, run through the real _scheduler_loop, with the network observed.
    creds, content = _selftest_fixtures()
    platform_flags = {f"{p}_publishing": True for p in PLATFORMS}
    states = set()
    with _NetRecorder() as net:
        for cfg in ({}, {"capabilities": dict(platform_flags)}):
            q = _run_scheduler_once(_selftest_due_queue(content), cfg, creds)
            states |= {pd["status"] for pd in q["queue"][0]["platforms"].values()}
    ok("scheduler flag off: every due item advances to ready_to_post and no network call is made",
       net.calls == [] and states == {"ready_to_post"})
    # The tick's own master-flag check, observed at dispatch(): with the master flag off the tick
    # never calls it, even with every platform flag on; with both flags on it calls it per platform.
    routed = []
    real_dispatch = publishing.dispatch

    def _dispatch_probe(platform, *args, **kwargs):
        routed.append(platform)
        return {"ok": False, "status": "gated", "post_id": None, "permalink": None,
                "error": "selftest probe"}

    publishing.dispatch = _dispatch_probe
    try:
        with _NetRecorder() as net:
            q = _selftest_due_queue(content)
            changed = _scheduler_tick(q, {"capabilities": dict(platform_flags)}, creds,
                                      datetime.now(timezone.utc))
        ok("scheduler tick, master flag off with every platform flag on: dispatch() is never called, "
           "every item is ready_to_post, no network call",
           changed and routed == [] and net.calls == []
           and {pd["status"] for pd in q["queue"][0]["platforms"].values()} == {"ready_to_post"})
        del routed[:]
        _scheduler_tick(_selftest_due_queue(content),
                        {"capabilities": dict(platform_flags, live_publishing_enabled=True)}, creds,
                        datetime.now(timezone.utc))
        ok("scheduler tick, master and platform flags on: dispatch() is called for every platform "
           "(the probe sees calls)", sorted(routed) == sorted(PLATFORMS))
    finally:
        publishing.dispatch = real_dispatch
    with _NetRecorder() as net:
        _run_scheduler_once(_selftest_due_queue(content), {"capabilities": {
            "live_publishing_enabled": True, "youtube_publishing": True}}, creds)
    ok("scheduler flag on: the network recorder sees the upload attempt (the probe sees calls)",
       len(net.calls) >= 1)

    failed = [n for n, c in checks if not c]
    for n, c in checks:
        print(("ok   " if c else "FAIL ") + n)
    print(f"dashboard selftest: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0


def main():
    if "--selftest" in sys.argv[1:]:
        raise SystemExit(_selftest())
    print("Creator OS Scheduling Dashboard")
    print(f"  URL: http://localhost:{PORT}")
    print(f"  Queue: {QUEUE_PATH}")
    live = compliance.live_publishing_enabled()
    print(f"  Live publishing: {'ON' if live else 'OFF (manual posting; no platform calls)'}")
    print("  Press Ctrl+C to stop.\n")

    handler = partial(DashboardHandler)
    server = HTTPServer(("127.0.0.1", PORT), handler)

    scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    scheduler_thread.start()

    try:
        webbrowser.open(f"http://localhost:{PORT}")
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        _shutdown.set()
        server.shutdown()


if __name__ == "__main__":
    main()
