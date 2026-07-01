#!/usr/bin/env python3
"""Creator OS Scheduling Dashboard — browser-based GUI for managing social media posts.

Serves static HTML/CSS/JS on port 8766 and exposes a JSON API for managing the
scheduling queue. The scheduling dashboard click IS the human confirmation step.

Usage:
    python3 tools/dashboard/server.py

Requires no external dependencies (stdlib only).
"""

import json
import os
import sys
import threading
import uuid
import webbrowser
from datetime import datetime, timezone
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
QUEUE_PATH = ROOT / "pipeline" / "user-context" / "scheduling-queue.local.json"
CONFIG_PATH = ROOT / "creator-os-config.json"
CONFIG_LOCAL_PATH = ROOT / "creator-os-config.local.json"
CREDS_PATH = ROOT / "pipeline" / "user-context" / "api-credentials.local.json"

PORT = 8766

_shutdown = threading.Event()


def _load_config():
    base = {}
    try:
        base = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    if CONFIG_LOCAL_PATH.exists():
        try:
            local = json.loads(CONFIG_LOCAL_PATH.read_text(encoding="utf-8"))
            for k, v in local.get("capabilities", {}).items():
                base.setdefault("capabilities", {})[k] = v
        except (OSError, json.JSONDecodeError):
            pass
    return base


def _load_queue():
    if QUEUE_PATH.exists():
        try:
            return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"queue": []}


def _save_queue(data):
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _flag_enabled(config, name):
    caps = config.get("capabilities", {})
    meta = caps.get(name, {})
    return meta.get("enabled", False) if isinstance(meta, dict) else bool(meta)


def _get_publishing_plan(config):
    platforms = ["instagram", "tiktok", "pinterest", "youtube"]
    plan = {}
    for plat in platforms:
        flag = f"{plat}_publishing"
        if _flag_enabled(config, flag):
            plan[plat] = {"tier": "direct_api", "connector": flag}
        else:
            plan[plat] = {"tier": "manual", "connector": "none"}
    return plan


def _get_credentials_status():
    if CREDS_PATH.exists():
        try:
            creds = json.loads(CREDS_PATH.read_text(encoding="utf-8"))
            return {
                "youtube": bool(creds.get("youtube")),
                "instagram": bool(creds.get("instagram")),
                "tiktok": bool(creds.get("tiktok")),
                "pinterest": bool(creds.get("pinterest")),
            }
        except (OSError, json.JSONDecodeError):
            pass
    return {"youtube": False, "instagram": False, "tiktok": False, "pinterest": False}


def _new_platform_entry():
    return {
        "enabled": False,
        "scheduled_datetime": None,
        "caption": "",
        "hashtags": [],
        "content_type": None,
        "media_url": None,
        "ftc_disclosure": None,
        "is_aigc": False,
        "status": "draft",
        "post_id": None,
        "permalink": None,
        "error": None,
    }


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format, *args):
        pass

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
            return self._json_response(_load_queue())

        if path == "/api/publishing-plan":
            config = _load_config()
            return self._json_response(_get_publishing_plan(config))

        if path == "/api/credentials-status":
            return self._json_response(_get_credentials_status())

        if path.startswith("/api/status/"):
            post_id = path.split("/api/status/", 1)[1]
            queue = _load_queue()
            for item in queue.get("queue", []):
                if item.get("id") == post_id:
                    return self._json_response(item)
            return self._json_response({"error": "not found"}, status=404)

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        body = self._read_body()
        if body is None:
            return

        if path == "/api/queue":
            return self._handle_add_to_queue(body)

        if path == "/api/schedule":
            return self._handle_schedule(body)

        if path == "/api/toggle-platform":
            return self._handle_toggle_platform(body)

        if path == "/api/update-caption":
            return self._handle_update_caption(body)

        if path == "/api/update-schedule":
            return self._handle_update_schedule(body)

        if path == "/api/delete-item":
            return self._handle_delete_item(body)

        self._json_response({"error": "not found"}, status=404)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            self._json_response({"error": "empty body"}, status=400)
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self._json_response({"error": "invalid JSON"}, status=400)
            return None

    def _json_response(self, data, status=200):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _handle_add_to_queue(self, body):
        queue = _load_queue()
        item_id = body.get("id", str(uuid.uuid4()))
        title = body.get("title", "Untitled post")
        source = body.get("source", "manual")

        existing = None
        for item in queue["queue"]:
            if item.get("id") == item_id:
                existing = item
                break

        if existing:
            for key in ("title", "source"):
                if key in body:
                    existing[key] = body[key]
            if "platforms" in body:
                for plat, pdata in body["platforms"].items():
                    if plat not in existing["platforms"]:
                        existing["platforms"][plat] = _new_platform_entry()
                    existing["platforms"][plat].update(pdata)
        else:
            platforms = {}
            for plat in ["instagram", "tiktok", "pinterest", "youtube"]:
                entry = _new_platform_entry()
                if "platforms" in body and plat in body["platforms"]:
                    entry.update(body["platforms"][plat])
                platforms[plat] = entry

            new_item = {
                "id": item_id,
                "title": title,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source": source,
                "platforms": platforms,
            }
            queue["queue"].append(new_item)

        _save_queue(queue)
        self._json_response({"ok": True, "id": item_id})

    def _handle_schedule(self, body):
        item_id = body.get("item_id")
        platform = body.get("platform")
        if not item_id or not platform:
            return self._json_response(
                {"error": "item_id and platform required"}, status=400
            )

        queue = _load_queue()
        for item in queue["queue"]:
            if item.get("id") == item_id:
                pdata = item.get("platforms", {}).get(platform)
                if not pdata:
                    return self._json_response(
                        {"error": f"platform {platform} not found on item"}, status=404
                    )
                if not pdata.get("enabled"):
                    return self._json_response(
                        {"error": f"platform {platform} is not enabled"}, status=400
                    )
                pdata["status"] = "scheduled"
                pdata["human_review_required"] = True
                _save_queue(queue)
                return self._json_response({
                    "ok": True,
                    "item_id": item_id,
                    "platform": platform,
                    "status": "scheduled",
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

        queue = _load_queue()
        for item in queue["queue"]:
            if item.get("id") == item_id:
                pdata = item.get("platforms", {}).get(platform)
                if not pdata:
                    return self._json_response(
                        {"error": f"platform {platform} not found"}, status=404
                    )
                if "caption" in body:
                    pdata["caption"] = body["caption"]
                if "hashtags" in body:
                    pdata["hashtags"] = body["hashtags"]
                if "content_type" in body:
                    pdata["content_type"] = body["content_type"]
                if "media_url" in body:
                    pdata["media_url"] = body["media_url"]
                if "ftc_disclosure" in body:
                    pdata["ftc_disclosure"] = body["ftc_disclosure"]
                if "is_aigc" in body:
                    pdata["is_aigc"] = body["is_aigc"]
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

        queue = _load_queue()
        before = len(queue["queue"])
        queue["queue"] = [i for i in queue["queue"] if i.get("id") != item_id]
        if len(queue["queue"]) == before:
            return self._json_response({"error": "item not found"}, status=404)
        _save_queue(queue)
        self._json_response({"ok": True})


def _scheduler_loop():
    """Background scheduler for platforms without native scheduled_at (TikTok)."""
    while not _shutdown.is_set():
        _shutdown.wait(60)
        if _shutdown.is_set():
            break
        queue = _load_queue()
        now = datetime.now(timezone.utc)
        changed = False
        for item in queue.get("queue", []):
            for platform, pdata in item.get("platforms", {}).items():
                if (
                    pdata.get("enabled")
                    and pdata.get("status") == "scheduled"
                    and pdata.get("scheduled_datetime")
                ):
                    try:
                        sched = datetime.fromisoformat(pdata["scheduled_datetime"])
                        if sched.tzinfo is None:
                            sched = sched.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        continue
                    if sched <= now:
                        pdata["status"] = "dispatched"
                        changed = True
        if changed:
            _save_queue(queue)


def main():
    print(f"Creator OS Scheduling Dashboard")
    print(f"  URL: http://localhost:{PORT}")
    print(f"  Queue: {QUEUE_PATH}")
    print(f"  Press Ctrl+C to stop.\n")

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
