#!/usr/bin/env python3
"""Shared publishing compliance + tier resolution for Creator OS.

Single source of truth for the FTC-disclosure, AIGC-flag, publishing-tier, and
credential-presence checks that must run before any post is scheduled. Both the
MCP `schedule_post` tool (tools/mcp_server.py) and the Scheduling Dashboard
(tools/dashboard/server.py) import `check()` so the two surfaces cannot diverge.

The dashboard is the human-confirmation surface: it ENFORCES the `ok` gate
(refuses to schedule when `ok` is False). The MCP tool is a plan/summary
generator: it REPORTS the same fields (including any credential gap) without
hard-failing. Neither surface performs a live network publish today — real
platform API calls live behind the `live_publishing_enabled` flag in
tools/publishing/ (feature-flagged off).

Stdlib only. No network.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "creator-os-config.json"
CONFIG_LOCAL_PATH = ROOT / "creator-os-config.local.json"
CREDS_PATH = ROOT / "pipeline" / "user-context" / "api-credentials.local.json"

PLATFORMS = ("youtube", "instagram", "tiktok", "pinterest")


def load_config() -> dict:
    """Load creator-os-config.json with the .local.json capability override merged on top."""
    base: dict = {}
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


def load_credentials() -> dict:
    """Load api-credentials.local.json (gitignored). Returns {} if absent/unreadable."""
    if CREDS_PATH.exists():
        try:
            return json.loads(CREDS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def flag_enabled(config: dict, name: str) -> bool:
    """A capability flag is either a bare bool or a {"enabled": bool, ...} object."""
    caps = config.get("capabilities", {}) if isinstance(config, dict) else {}
    meta = caps.get(name)
    if isinstance(meta, dict):
        return bool(meta.get("enabled", False))
    return bool(meta)


def live_publishing_enabled(config: dict | None = None) -> bool:
    """Master gate for the tools/publishing/ real API clients. Default OFF.

    While False, the schedule/dispatch paths run compliance + status only and make
    NO network call. Set live_publishing_enabled: true (and configure per-platform
    credentials) to activate real publishing in a future phase.
    """
    cfg = config if config is not None else load_config()
    return flag_enabled(cfg, "live_publishing_enabled")


def check(
    platform: str,
    caption: str = "",
    ftc_disclosure: str = "",
    is_aigc: bool = False,
    config: dict | None = None,
    creds: dict | None = None,
) -> dict:
    """Resolve publishing tier and run the compliance gates for one platform post.

    Returns a dict with:
      platform, tier ('direct_api'|'manual'), connector,
      ftc_disclosure, ftc_disclosure_verified, ftc_prepended, effective_caption,
      aigc_flag_set, has_credentials, human_review_required,
      ok (bool), error (str|None).

    `ok` is False only when a hard gate fails (currently: direct_api tier selected
    but no credentials configured). Callers that enforce (the dashboard) refuse the
    schedule on ok=False; callers that report (the MCP tool) surface the fields and
    the note without hard-failing.
    """
    plat = (platform or "").strip().lower()
    cfg = config if config is not None else load_config()
    credentials = creds if creds is not None else load_credentials()

    # Publishing tier: direct_api iff the {platform}_publishing flag is enabled.
    tier = "direct_api" if flag_enabled(cfg, f"{plat}_publishing") else "manual"
    connector = f"{plat}_publish_api" if tier == "direct_api" else "manual_post"

    # FTC disclosure: prepend to the caption if a disclosure is required and absent.
    ftc = (ftc_disclosure or "").strip()
    caption = caption or ""
    ftc_in_caption = bool(ftc) and ftc in caption
    ftc_prepended = False
    effective_caption = caption
    if ftc and not ftc_in_caption:
        effective_caption = f"{ftc} {caption}".strip()
        ftc_prepended = True

    # AIGC flag applies only to TikTok (TikTok Content Posting API is_aigc).
    aigc_flag_set = bool(is_aigc) and plat == "tiktok"

    # A usable publishing credential means a token exists -- under the publish namespace
    # (creds[plat]["publish"], written by the wizard's Connect flow) or, for back-compat, at the
    # platform root. Merely having imported read creds under creds[plat] does not count.
    plat_creds = credentials.get(plat) if isinstance(credentials, dict) else None
    pub_creds = plat_creds.get("publish") if isinstance(plat_creds, dict) else None
    has_credentials = bool(
        (isinstance(pub_creds, dict) and (pub_creds.get("access_token") or pub_creds.get("refresh_token")))
        or (isinstance(plat_creds, dict) and (plat_creds.get("access_token") or plat_creds.get("refresh_token")))
    )

    ok = True
    error = None
    if plat not in PLATFORMS:
        ok = False
        error = f"Unknown platform '{platform}'. Expected one of: {', '.join(PLATFORMS)}."
    elif tier == "direct_api" and not has_credentials:
        # The flag claims direct API, but nothing can publish without credentials.
        ok = False
        error = (
            f"{plat}_publishing is enabled (direct_api tier) but no {plat} API "
            f"credentials are configured. Run python3 tools/wizard.py to add "
            f"credentials, or disable the flag to schedule for manual posting."
        )

    return {
        "platform": plat,
        "tier": tier,
        "connector": connector,
        "ftc_disclosure": ftc or None,
        "ftc_disclosure_verified": bool(ftc),
        "ftc_prepended": ftc_prepended,
        "effective_caption": effective_caption,
        "aigc_flag_set": aigc_flag_set,
        "has_credentials": has_credentials,
        "human_review_required": True,
        "ok": ok,
        "error": error,
    }
