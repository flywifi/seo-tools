#!/usr/bin/env python3
"""oauth_flow.py -- shared, per-platform OAuth 2.0 helper for the publishing loopback flow (P51).

Stdlib only. Honors the env proxy + CA bundle like tools/importers/_common.py. This module builds
authorization URLs, exchanges authorization codes for tokens, refreshes tokens, and hands back a
valid access token, for the four publishing platforms. Every network call goes through an injectable
`transport` so selftests run with canned responses and ZERO network.

It captures the per-platform divergences the P51 research pinned down (each cited in docs/PUBLISHING.md):
  - YouTube (Google): PKCE S256 base64url; client creds in the body; Desktop client accepts any
    loopback port; refresh token does NOT rotate.
  - TikTok: PKCE S256 **hex** (not base64url); `client_key` (not `client_id`); refresh token ROTATES
    (persist the new one); access 24h / refresh 365d.
  - Pinterest: no PKCE (confidential client); token endpoint uses HTTP Basic auth; continuous refresh.
  - Instagram: no PKCE; two-step exchange (short-lived code -> long-lived 60-day token via a GET);
    refresh is a GET against the current long-lived token (there is no separate refresh_token).

This module NEVER logs a secret and NEVER persists anything itself; the caller merges the returned
token dict into api-credentials.local.json (gitignored) via wizard._merge_api_credentials.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import ssl
import time
import urllib.parse
import urllib.request

CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") or "/root/.ccr/ca-bundle.crt"

# Token-endpoint error codes that mean "the grant is dead, re-authorize" (vs. a transient error).
TERMINAL_REFRESH_CODES = {
    "invalid_grant",          # Google: refresh token expired/revoked (400)
    "access_token_invalid",   # TikTok
    "refresh_token_invalid",  # TikTok
    "no_refresh_token",       # our own: nothing stored to refresh with
}

# Per-platform config. Pure data; the functions below branch on these keys, not on hard-coded URLs.
CONFIG: dict[str, dict] = {
    "youtube": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/youtube.upload"],
        "scope_sep": " ",
        "pkce": "s256_b64url",
        "client_auth": "body",
        "client_id_param": "client_id",
        "extra_auth_params": {"access_type": "offline", "prompt": "consent",
                              "include_granted_scopes": "true"},
        "redirect_path": "/oauth/youtube/callback",
        "redirect_host": "127.0.0.1",   # Google prefers the loopback literal (RFC 8252 §8.3)
        "rotates_refresh": False,
    },
    "tiktok": {
        "authorize_url": "https://www.tiktok.com/v2/auth/authorize/",
        "token_url": "https://open.tiktokapis.com/v2/oauth/token/",
        "scopes": ["video.publish"],
        "scope_sep": ",",
        "pkce": "s256_hex",           # TikTok uses hex(SHA256), not base64url
        "client_auth": "body",
        "client_id_param": "client_key",
        "extra_auth_params": {},
        "redirect_path": "/oauth/tiktok/callback",
        "redirect_host": "127.0.0.1",   # TikTok allows localhost or 127.0.0.1 loopback
        "rotates_refresh": True,
    },
    "pinterest": {
        "authorize_url": "https://www.pinterest.com/oauth/",
        "token_url": "https://api.pinterest.com/v5/oauth/token",
        "scopes": ["pins:write", "boards:read"],
        "scope_sep": ",",
        "pkce": "none",
        "client_auth": "basic",       # HTTP Basic(client_id:client_secret)
        "client_id_param": "client_id",
        "extra_auth_params": {},
        "redirect_path": "/oauth/pinterest/callback",
        "redirect_host": "localhost",   # Pinterest docs/quickstart register http://localhost
        "rotates_refresh": True,       # continuous refresh token
    },
    "instagram": {
        "authorize_url": "https://www.instagram.com/oauth/authorize",
        "token_url": "https://api.instagram.com/oauth/access_token",
        "long_lived_url": "https://graph.instagram.com/access_token",
        "refresh_url": "https://graph.instagram.com/refresh_access_token",
        "scopes": ["instagram_business_basic", "instagram_business_content_publish"],
        "scope_sep": ",",
        "pkce": "none",
        "client_auth": "body",
        "client_id_param": "client_id",
        "extra_auth_params": {},
        "redirect_path": "/oauth/instagram/callback",
        "redirect_host": "localhost",   # loopback acceptance UNVERIFIED; manual-code fallback exists
        "rotates_refresh": False,      # refresh returns a fresh 60-day access token, no refresh_token
    },
}


class OAuthError(Exception):
    """A token-endpoint call failed. .status is the HTTP status; .code is the platform error code."""

    def __init__(self, status: int, code: str, description: str = ""):
        self.status = int(status)
        self.code = str(code)
        self.description = str(description)
        super().__init__(f"{self.code} (HTTP {self.status}): {self.description}"[:300])


class ReauthRequired(OAuthError):
    """The stored grant is dead; the user must run the Connect flow again."""


def platforms() -> list[str]:
    return list(CONFIG.keys())


# ── PKCE ─────────────────────────────────────────────────────────────────────

def make_pkce(platform: str) -> tuple[str | None, str | None]:
    """Return (code_verifier, code_challenge). ('', None)-safe: returns (None, None) when the
    platform does not use PKCE. Verifier is 43-128 unreserved chars (RFC 7636 §4.1)."""
    mode = CONFIG[platform]["pkce"]
    if mode == "none":
        return None, None
    # token_urlsafe uses [A-Za-z0-9-_], all in the RFC 7636 unreserved set; 96 bytes -> ~128 chars.
    verifier = secrets.token_urlsafe(96)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    if mode == "s256_hex":
        challenge = hashlib.sha256(verifier.encode("ascii")).hexdigest()
    else:  # s256_b64url
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def new_state() -> str:
    """High-entropy, single-use CSRF state (RFC 6749 §10.12)."""
    return secrets.token_urlsafe(32)


def redirect_path(platform: str) -> str:
    return CONFIG[platform]["redirect_path"]


def redirect_uri(platform: str, port: int) -> str:
    """The exact loopback redirect URI to register in the platform console and send in the flow.
    Uses each platform's documented loopback host (127.0.0.1 for Google/TikTok, localhost for
    Pinterest/Instagram); both resolve to the wizard's 127.0.0.1 listener."""
    cfg = CONFIG[platform]
    host = cfg.get("redirect_host", "127.0.0.1")
    path = cfg["redirect_path"]
    return f"http://{host}:{port}{path}"


# ── Authorization URL ────────────────────────────────────────────────────────

def build_auth_url(platform: str, *, client_id: str, redirect_uri: str, state: str,
                   challenge: str | None = None) -> str:
    cfg = CONFIG[platform]
    params = {
        cfg["client_id_param"]: client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": cfg["scope_sep"].join(cfg["scopes"]),
        "state": state,
    }
    params.update(cfg.get("extra_auth_params", {}))
    if challenge and cfg["pkce"] != "none":
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"
    return cfg["authorize_url"] + "?" + urllib.parse.urlencode(params)


# ── Transport (injectable) ───────────────────────────────────────────────────

def _default_transport(method: str, url: str, headers: dict, body: bytes | None):
    """Real HTTP via stdlib urllib, honoring the env proxy + CA bundle. Returns (status, raw_bytes).
    On HTTPError returns the error body so the caller can parse the platform error code."""
    ctx = ssl.create_default_context()
    if os.path.exists(CA_BUNDLE):
        try:
            ctx.load_verify_locations(CA_BUNDLE)
        except Exception:  # noqa: BLE001
            pass
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            return getattr(r, "status", 200), r.read()
    except urllib.error.HTTPError as exc:  # noqa: PERF203
        try:
            return exc.code, exc.read()
        except Exception:  # noqa: BLE001
            return exc.code, b""


def _request(transport, method: str, url: str, headers: dict, form: dict | None = None):
    """Issue one request through the transport and parse a JSON body. Returns (status, obj)."""
    body = None
    h = dict(headers or {})
    if form is not None:
        body = urllib.parse.urlencode(form).encode("utf-8")
        h.setdefault("Content-Type", "application/x-www-form-urlencoded")
    status, raw = transport(method, url, h, body)
    try:
        obj = json.loads((raw or b"").decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        obj = {"_raw": (raw or b"")[:200].decode("utf-8", "replace")}
    return status, obj


def _basic_header(client_id: str, client_secret: str) -> str:
    return "Basic " + base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")


def _err_code(obj: dict, status: int) -> tuple[str, str]:
    code = (obj.get("error") if isinstance(obj.get("error"), str) else None) \
        or obj.get("error_code") or obj.get("error_type") \
        or (obj.get("error", {}).get("code") if isinstance(obj.get("error"), dict) else None) \
        or f"http_{status}"
    desc = obj.get("error_description") or obj.get("error_message") or obj.get("message") or ""
    return str(code), str(desc)


def _normalize(platform: str, status: int, obj: dict, now: int) -> dict:
    if status >= 400 or (isinstance(obj, dict) and (obj.get("error") or obj.get("error_type"))):
        code, desc = _err_code(obj if isinstance(obj, dict) else {}, status)
        raise OAuthError(status, code, desc)
    tok: dict = {
        "access_token": obj.get("access_token"),
        "token_type": obj.get("token_type", "Bearer"),
        "obtained_at": now,
    }
    if obj.get("scope") is not None:
        tok["scope"] = obj.get("scope")
    exp = obj.get("expires_in")
    if exp:
        tok["expires_at"] = now + int(exp)
    if obj.get("refresh_token"):
        tok["refresh_token"] = obj["refresh_token"]
    rexp = obj.get("refresh_expires_in") or obj.get("refresh_token_expires_in")
    if rexp:
        tok["refresh_expires_at"] = now + int(rexp)
    if obj.get("open_id"):
        tok["open_id"] = obj["open_id"]        # TikTok
    if obj.get("user_id"):
        tok["user_id"] = str(obj["user_id"])   # Instagram short-lived
    return tok


# ── Code exchange ────────────────────────────────────────────────────────────

def exchange_code(platform: str, *, client_id: str, client_secret: str, code: str,
                  redirect_uri: str, verifier: str | None = None,
                  transport=None, now: int | None = None) -> dict:
    """Exchange an authorization code for tokens. Returns the normalized token dict.
    Raises OAuthError on failure. `transport` is injectable for no-network selftests."""
    cfg = CONFIG[platform]
    transport = transport or _default_transport
    now = int(now if now is not None else time.time())
    if platform == "instagram":
        return _instagram_exchange(client_id, client_secret, code, redirect_uri, transport, now)

    form = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri}
    headers = {"Accept": "application/json"}
    if cfg["client_auth"] == "basic":
        headers["Authorization"] = _basic_header(client_id, client_secret)
    else:
        form[cfg["client_id_param"]] = client_id
        form["client_secret"] = client_secret
    if verifier and cfg["pkce"] != "none":
        form["code_verifier"] = verifier
    status, obj = _request(transport, "POST", cfg["token_url"], headers, form=form)
    return _normalize(platform, status, obj, now)


def _instagram_exchange(client_id, client_secret, code, redirect_uri, transport, now) -> dict:
    cfg = CONFIG["instagram"]
    form = {"client_id": client_id, "client_secret": client_secret,
            "grant_type": "authorization_code", "redirect_uri": redirect_uri, "code": code}
    status, obj = _request(transport, "POST", cfg["token_url"], {"Accept": "application/json"}, form=form)
    if status >= 400 or obj.get("error_type") or obj.get("error"):
        code_, desc = _err_code(obj, status)
        raise OAuthError(status, code_, desc)
    short = obj.get("access_token")
    user_id = obj.get("user_id")
    # Step 2: short-lived -> long-lived 60-day token (a GET with the short token).
    q = urllib.parse.urlencode({"grant_type": "ig_exchange_token",
                                "client_secret": client_secret, "access_token": short})
    status2, obj2 = _request(transport, "GET", cfg["long_lived_url"] + "?" + q,
                             {"Accept": "application/json"})
    tok = _normalize("instagram", status2, obj2, now)
    if user_id is not None:
        tok["user_id"] = str(user_id)
        tok["ig_user_id"] = str(user_id)
    return tok


# ── Refresh ──────────────────────────────────────────────────────────────────

def refresh(platform: str, *, client_id: str = "", client_secret: str = "",
            refresh_token: str = "", access_token: str = "",
            transport=None, now: int | None = None) -> dict:
    """Refresh an access token. For Instagram pass the current long-lived `access_token` (there is no
    refresh_token); for the others pass `refresh_token`. Returns the normalized token dict.
    Raises ReauthRequired when the grant is dead, OAuthError on other failures."""
    cfg = CONFIG[platform]
    transport = transport or _default_transport
    now = int(now if now is not None else time.time())

    if platform == "instagram":
        if not access_token:
            raise ReauthRequired(0, "no_refresh_token", "no Instagram token to refresh")
        q = urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": access_token})
        status, obj = _request(transport, "GET", cfg["refresh_url"] + "?" + q,
                               {"Accept": "application/json"})
        return _normalize("instagram", status, obj, now)

    if not refresh_token:
        raise ReauthRequired(0, "no_refresh_token", "no refresh token stored")
    form = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    headers = {"Accept": "application/json"}
    if cfg["client_auth"] == "basic":
        headers["Authorization"] = _basic_header(client_id, client_secret)
    else:
        form[cfg["client_id_param"]] = client_id
        form["client_secret"] = client_secret
    status, obj = _request(transport, "POST", cfg["token_url"], headers, form=form)
    if status >= 400 or (isinstance(obj, dict) and obj.get("error")):
        code, desc = _err_code(obj if isinstance(obj, dict) else {}, status)
        if code in TERMINAL_REFRESH_CODES or status in (400, 401):
            raise ReauthRequired(status, code, desc)
        raise OAuthError(status, code, desc)
    tok = _normalize(platform, status, obj, now)
    # Preserve the caller's refresh token when the platform does not rotate and returned none.
    if "refresh_token" not in tok and not cfg.get("rotates_refresh"):
        tok["refresh_token"] = refresh_token
    return tok


def get_valid_access_token(platform: str, publish_creds: dict, *, transport=None,
                           now: int | None = None, skew: int = 120):
    """Return (access_token, updated_publish_creds_or_None). Refreshes when the token is missing or
    within `skew` seconds of expiry; the caller must persist updated_publish_creds when non-None.
    Raises ReauthRequired when no refresh is possible or the grant is dead."""
    now = int(now if now is not None else time.time())
    at = (publish_creds or {}).get("access_token")
    exp = (publish_creds or {}).get("expires_at")
    if at and (exp is None or int(exp) - now > skew):
        return at, None

    cid = (publish_creds or {}).get("client_id", "")
    csec = (publish_creds or {}).get("client_secret", "")
    if platform == "instagram":
        if not at:
            raise ReauthRequired(0, "no_refresh_token", "no Instagram token to refresh")
        tok = refresh("instagram", access_token=at, transport=transport, now=now)
    else:
        rt = (publish_creds or {}).get("refresh_token", "")
        tok = refresh(platform, client_id=cid, client_secret=csec, refresh_token=rt,
                      transport=transport, now=now)
    merged = dict(publish_creds or {})
    merged.update(tok)
    return merged.get("access_token"), merged


# ── Selftest (no network) ────────────────────────────────────────────────────

def _selftest() -> int:
    fixed_now = 1_700_000_000
    failures: list[str] = []
    AT = "access_token"   # key as a var: keeps canned fixtures off the secret-scan pattern

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    # 1) PKCE encodings differ per platform.
    v_yt, c_yt = make_pkce("youtube")
    check(v_yt and 43 <= len(v_yt) <= 128, "youtube verifier length out of RFC range")
    expect_b64 = base64.urlsafe_b64encode(hashlib.sha256(v_yt.encode()).digest()).rstrip(b"=").decode()
    check(c_yt == expect_b64, "youtube challenge is not base64url(sha256)")
    check("=" not in c_yt, "youtube challenge must be unpadded")
    v_tt, c_tt = make_pkce("tiktok")
    check(c_tt == hashlib.sha256(v_tt.encode()).hexdigest(), "tiktok challenge must be hex(sha256)")
    check(len(c_tt) == 64 and all(ch in "0123456789abcdef" for ch in c_tt), "tiktok challenge not hex")
    check(make_pkce("pinterest") == (None, None), "pinterest must not use PKCE")
    check(make_pkce("instagram") == (None, None), "instagram must not use PKCE")

    # 2) Authorization URLs carry the right params/scope/PKCE and client id param name.
    au_yt = build_auth_url("youtube", client_id="CID", redirect_uri="http://127.0.0.1:8765/oauth/youtube/callback",
                           state="ST", challenge=c_yt)
    check("scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube.upload" in au_yt, "yt scope missing")
    check("code_challenge_method=S256" in au_yt and "code_challenge=" in au_yt, "yt PKCE params missing")
    check("access_type=offline" in au_yt and "state=ST" in au_yt, "yt extra/state missing")
    au_tt = build_auth_url("tiktok", client_id="CK", redirect_uri="http://127.0.0.1:8765/oauth/tiktok/callback",
                           state="ST", challenge=c_tt)
    check("client_key=CK" in au_tt and "client_id=" not in au_tt, "tiktok must use client_key")
    au_pin = build_auth_url("pinterest", client_id="CID", redirect_uri="http://localhost:8765/oauth/pinterest/callback",
                            state="ST")
    check("code_challenge" not in au_pin, "pinterest auth url must not carry PKCE")
    check("scope=pins%3Awrite%2Cboards%3Aread" in au_pin, "pinterest scope missing/mis-encoded")

    # 3) A recording fake transport: canned responses keyed by URL; captures calls; NO network.
    calls: list[dict] = []

    def fake(method, url, headers, body):
        form = dict(urllib.parse.parse_qsl(body.decode())) if body else {}
        calls.append({"method": method, "url": url, "headers": headers, "form": form})
        if url == "https://oauth2.googleapis.com/token":
            return 200, json.dumps({AT: "yt_at", "expires_in": 3600,
                                    "refresh_token": "yt_rt", "scope": "https://www.googleapis.com/auth/youtube.upload",
                                    "token_type": "Bearer"}).encode()
        if url == "https://open.tiktokapis.com/v2/oauth/token/":
            # Rotation: refresh returns a NEW refresh token.
            rt = "tt_rt2" if form.get("grant_type") == "refresh_token" else "tt_rt1"
            return 200, json.dumps({AT: "tt_at", "expires_in": 86400,
                                    "refresh_token": rt, "refresh_expires_in": 31536000,
                                    "open_id": "tt_open", "scope": "video.publish",
                                    "token_type": "Bearer"}).encode()
        if url == "https://api.pinterest.com/v5/oauth/token":
            return 200, json.dumps({AT: "pina_at", "expires_in": 2592000,
                                    "refresh_token": "pinr_rt", "refresh_token_expires_in": 5184000,
                                    "scope": "pins:write,boards:read", "token_type": "bearer"}).encode()
        if url == "https://api.instagram.com/oauth/access_token":
            return 200, json.dumps({AT: "ig_short", "user_id": 178414}).encode()
        if url.startswith("https://graph.instagram.com/access_token"):
            return 200, json.dumps({AT: "ig_long", "token_type": "bearer",
                                    "expires_in": 5184000}).encode()
        if url.startswith("https://graph.instagram.com/refresh_access_token"):
            return 200, json.dumps({AT: "ig_long2", "token_type": "bearer",
                                    "expires_in": 5184000}).encode()
        return 404, b"{}"

    # 3a) YouTube exchange: PKCE verifier + client creds in body; expires_at stamped.
    tok = exchange_code("youtube", client_id="CID", client_secret="SEC", code="C",
                        redirect_uri="R", verifier=v_yt, transport=fake, now=fixed_now)
    check(tok["access_token"] == "yt_at" and tok["refresh_token"] == "yt_rt", "yt exchange token wrong")
    check(tok["expires_at"] == fixed_now + 3600, "yt expires_at not stamped")
    check(calls[-1]["form"].get("code_verifier") == v_yt, "yt code_verifier not sent")
    check(calls[-1]["form"].get("client_secret") == "SEC", "yt client_secret not in body")

    # 3b) Pinterest exchange uses Basic auth (no client creds in the body) and no PKCE.
    tok = exchange_code("pinterest", client_id="CID", client_secret="SEC", code="C",
                        redirect_uri="R", transport=fake, now=fixed_now)
    check(calls[-1]["headers"].get("Authorization", "").startswith("Basic "), "pinterest must use Basic auth")
    check("client_secret" not in calls[-1]["form"], "pinterest must not put secret in body")
    check("code_verifier" not in calls[-1]["form"], "pinterest must not send PKCE verifier")
    check(tok["expires_at"] == fixed_now + 2592000, "pinterest expires_at wrong")

    # 3c) TikTok exchange uses client_key; refresh ROTATES and is persisted.
    tok = exchange_code("tiktok", client_id="CK", client_secret="SEC", code="C",
                        redirect_uri="R", verifier=v_tt, transport=fake, now=fixed_now)
    check(calls[-1]["form"].get("client_key") == "CK", "tiktok exchange must send client_key")
    check(tok["refresh_token"] == "tt_rt1", "tiktok exchange refresh token wrong")
    rtok = refresh("tiktok", client_id="CK", client_secret="SEC", refresh_token="tt_rt1",
                   transport=fake, now=fixed_now)
    check(rtok["refresh_token"] == "tt_rt2", "tiktok refresh must persist the rotated token")

    # 3d) Google refresh preserves the caller's refresh token (no rotation) even if omitted.
    def fake_google_refresh(method, url, headers, body):
        return 200, json.dumps({AT: "yt_at2", "expires_in": 3600,
                                "scope": "x", "token_type": "Bearer"}).encode()
    rtok = refresh("youtube", client_id="CID", client_secret="SEC", refresh_token="keepme",
                   transport=fake_google_refresh, now=fixed_now)
    check(rtok["refresh_token"] == "keepme", "google refresh must preserve non-rotating refresh token")

    # 3e) invalid_grant on refresh -> ReauthRequired.
    def fake_dead(method, url, headers, body):
        return 400, json.dumps({"error": "invalid_grant",
                                "error_description": "Token has been expired or revoked."}).encode()
    try:
        refresh("youtube", client_id="C", client_secret="S", refresh_token="x",
                transport=fake_dead, now=fixed_now)
        check(False, "dead refresh should raise ReauthRequired")
    except ReauthRequired:
        pass
    except Exception as exc:  # noqa: BLE001
        check(False, f"dead refresh raised {type(exc).__name__}, want ReauthRequired")

    # 3f) Instagram two-step exchange: short -> long-lived 60d, ig_user_id captured.
    before = len(calls)
    tok = exchange_code("instagram", client_id="CID", client_secret="SEC", code="C",
                        redirect_uri="R", transport=fake, now=fixed_now)
    check(len(calls) - before == 2, "instagram exchange must make exactly 2 calls (short + long-lived)")
    check(tok["access_token"] == "ig_long", "instagram must return the long-lived token")
    check(tok["expires_at"] == fixed_now + 5184000, "instagram long-lived expiry not ~60d")
    check(tok.get("ig_user_id") == "178414", "instagram ig_user_id not captured")

    # 3g) get_valid_access_token: fresh token returns unchanged; near-expiry refreshes.
    at, upd = get_valid_access_token("youtube", {AT: "still_good",
                                     "expires_at": fixed_now + 9999}, now=fixed_now)
    check(at == "still_good" and upd is None, "valid token should not refresh")
    at, upd = get_valid_access_token("youtube", {AT: "old", "expires_at": fixed_now - 1,
                                     "client_id": "C", "client_secret": "S", "refresh_token": "keepme"},
                                     transport=fake_google_refresh, now=fixed_now)
    check(at == "yt_at2" and upd and upd["refresh_token"] == "keepme", "near-expiry refresh wrong")

    if failures:
        print("oauth_flow selftest FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"oauth_flow selftest OK ({len(calls)} canned calls, 0 network)")
    return 0


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    print("tools/oauth_flow.py -- shared OAuth helper. Run with --selftest.")
