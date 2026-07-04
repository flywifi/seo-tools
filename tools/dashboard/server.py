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
import finance  # noqa: E402  (P31: read-only AR view)

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
                        plats[plat].update(pdata)
            else:
                platforms = {}
                body_platforms = body.get("platforms") if isinstance(body.get("platforms"), dict) else {}
                for plat in PLATFORMS:
                    entry = _new_platform_entry()
                    if isinstance(body_platforms.get(plat), dict):
                        entry.update(body_platforms[plat])
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


def _scheduler_loop():
    """Advance due, human-confirmed posts.

    While `live_publishing_enabled` is off (default), this makes NO platform
    network call — a due item (status 'scheduled', set only by a human clicking
    Confirm) is advanced to 'ready_to_post' for manual posting. When live
    publishing is enabled, it calls tools/publishing/ and records the real
    post_id/permalink/error, setting status to 'published' or 'failed'.
    """
    while not _shutdown.is_set():
        _shutdown.wait(60)
        if _shutdown.is_set():
            break
        config = _load_config()
        live = compliance.live_publishing_enabled(config)
        creds = compliance.load_credentials()
        now = datetime.now(timezone.utc)
        with _queue_lock:
            queue = _load_queue()
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
                    # Due now, and the human already confirmed (status == 'scheduled').
                    if live:
                        try:
                            res = publishing.dispatch(platform, pdata, creds.get(platform, {}))
                            pdata["status"] = "published"
                            pdata["post_id"] = res.get("post_id")
                            pdata["permalink"] = res.get("permalink")
                            pdata["error"] = None
                        except NotImplementedError as exc:
                            pdata["status"] = "ready_to_post"
                            pdata["error"] = str(exc)
                        except Exception as exc:  # noqa: BLE001
                            pdata["status"] = "failed"
                            pdata["error"] = str(exc)
                    else:
                        # Honest scaffold: no network call; item is due for manual posting.
                        pdata["status"] = "ready_to_post"
                    changed = True
            if changed:
                _save_queue(queue)


def main():
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
