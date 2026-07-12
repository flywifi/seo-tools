#!/usr/bin/env python3
"""_common.py -- shared plumbing for the live-API importers (P45): flag gate, stdlib HTTP, credentials.

Stdlib only; honors the env proxy + CA bundle like tools/dependency_currency.py. Never raises on a
fetch failure (returns (None, error)). The gate refuses unless the content_import_live master flag and
the per-platform read flag are both on, so a live network call is impossible by default.
"""
import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CREATOR_OS_ROOT", str(HERE.parent.parent)))
CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") or "/root/.ccr/ca-bundle.crt"
CREDS_PATH = ROOT / "pipeline" / "user-context" / "api-credentials.local.json"

# per-platform read flag that must also be on
PLATFORM_READ_FLAG = {
    "youtube": "youtube_api",
    "youtube_analytics": "youtube_analytics",
    "instagram": "instagram_api",
    "tiktok": "tiktok_api",
    "pinterest": "pinterest_api",
}


def _flag_enabled(config, name):
    caps = (config or {}).get("capabilities", {})
    v = caps.get(name)
    if isinstance(v, dict):
        return bool(v.get("enabled"))
    return bool(v)


def gate(config, platform):
    """content_import_live master + the per-platform read flag must both be on. Returns
    {proceed, code, reason}. Only proceed True permits a network call."""
    if not _flag_enabled(config, "content_import_live"):
        return {"proceed": False, "code": "master_off",
                "reason": "content_import_live is off; the live-API importer makes no network call. "
                          "Use the export-bundle tier (download your data) instead."}
    flag = PLATFORM_READ_FLAG.get(platform, platform)
    if not _flag_enabled(config, flag):
        return {"proceed": False, "code": "platform_off",
                "reason": f"{flag} is off; enable it and add your own OAuth credentials to use the live "
                          f"{platform} importer."}
    return {"proceed": True, "code": "ok", "reason": "live import enabled"}


def load_credentials():
    """Read the gitignored api-credentials.local.json, or {} when absent. Never committed."""
    if not CREDS_PATH.exists():
        return {}
    try:
        return json.loads(CREDS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def http_get_json(url, headers=None, timeout=15):
    """GET JSON with the env proxy + CA bundle. Returns (data, error); never raises."""
    ctx = ssl.create_default_context()
    if os.path.exists(CA_BUNDLE):
        try:
            ctx.load_verify_locations(CA_BUNDLE)
        except Exception:  # noqa: BLE001
            pass
    h = {"Accept": "application/json", "User-Agent": "creator-os-content-import"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode("utf-8")), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {str(exc)[:160]}"


def http_post_json(url, body, headers=None, timeout=15):
    """POST JSON with the env proxy + CA bundle. Returns (data, error); never raises."""
    ctx = ssl.create_default_context()
    if os.path.exists(CA_BUNDLE):
        try:
            ctx.load_verify_locations(CA_BUNDLE)
        except Exception:  # noqa: BLE001
            pass
    h = {"Accept": "application/json", "Content-Type": "application/json",
         "User-Agent": "creator-os-content-import"}
    h.update(headers or {})
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode("utf-8")), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {str(exc)[:160]}"


def load_config():
    """Read creator-os-config.json merged with creator-os-config.local.json (local wins)."""
    base = {}
    p = ROOT / "creator-os-config.json"
    if p.exists():
        try:
            base = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            base = {}
    lp = ROOT / "creator-os-config.local.json"
    if lp.exists():
        try:
            local = json.loads(lp.read_text(encoding="utf-8"))
            for k, v in local.get("capabilities", {}).items():
                base.setdefault("capabilities", {})[k] = v
        except (OSError, json.JSONDecodeError):
            pass
    return base
