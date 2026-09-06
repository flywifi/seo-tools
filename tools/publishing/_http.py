"""Shared HTTP transport for the live publishing clients (P51). Stdlib only; honors the env proxy +
CA bundle. Unlike tools/oauth_flow.py's token transport (which needs only the body), publishing
uploads need the RESPONSE HEADERS too (e.g. the resumable-upload session URI arrives in `Location`),
so this transport returns (status, headers_dict, raw_bytes).

Every client takes `transport=` so selftests run with canned responses and ZERO network.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request

CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") or "/root/.ccr/ca-bundle.crt"


def default_transport(method: str, url: str, headers: dict, body):
    """Real HTTP via stdlib urllib. Returns (status:int, headers:dict, raw:bytes). Never raises on an
    HTTP error status; returns the error body so the caller can parse the platform error."""
    ctx = ssl.create_default_context()
    if os.path.exists(CA_BUNDLE):
        try:
            ctx.load_verify_locations(CA_BUNDLE)
        except Exception:  # noqa: BLE001
            pass
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            return getattr(r, "status", 200), {k: v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as exc:
        try:
            hdrs = {k: v for k, v in (exc.headers or {}).items()}
        except Exception:  # noqa: BLE001
            hdrs = {}
        try:
            raw = exc.read()
        except Exception:  # noqa: BLE001
            raw = b""
        return exc.code, hdrs, raw


def parse_json(raw: bytes) -> dict:
    try:
        return json.loads((raw or b"").decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        return {}


def header(headers: dict, name: str):
    """Case-insensitive header lookup (urllib preserves original case; HTTP headers are case-insensitive)."""
    if not headers:
        return None
    low = name.lower()
    for k, v in headers.items():
        if k.lower() == low:
            return v
    return None
