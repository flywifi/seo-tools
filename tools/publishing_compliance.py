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
        # A3 honesty: this means disclosure TEXT is present (supplied or prepended). It is NOT a
        # content validation of the disclosure's adequacy. The key name is kept for schema/MCP
        # back-compat; do not present it downstream as "the disclosure was verified."
        "ftc_disclosure_verified": bool(ftc),
        "ftc_prepended": ftc_prepended,
        "effective_caption": effective_caption,
        "aigc_flag_set": aigc_flag_set,
        "has_credentials": has_credentials,
        "human_review_required": True,
        "ok": ok,
        "error": error,
    }


def _selftest() -> int:
    """Offline test of the publishing gate (config + creds injected; no filesystem, no network).

    Locks the safety-relevant contract the dashboard and MCP surfaces both depend on: the master flag
    is OFF by default, an unknown platform and a direct_api tier without credentials both hard-fail,
    a stored publish (or back-compat root) token is detected, human review is always required, the FTC
    disclosure is prepended when missing, and the AIGC flag is TikTok-only. Added in P56 (the module
    previously had no selftest, so `publishing_compliance.py --selftest` was a silent no-op)."""
    failures: list[str] = []

    ran = [0]
    def ok(cond, msg):
        ran[0] += 1
        if not cond:
            failures.append(msg)

    ON = {"capabilities": {"live_publishing_enabled": True}}
    YT_ON = {"capabilities": {"youtube_publishing": True}}

    # 1) Master gate defaults OFF; explicit flag turns it on; flag accepts bool or {"enabled":...}.
    ok(live_publishing_enabled({}) is False, "live_publishing_enabled default should be False")
    ok(live_publishing_enabled(ON) is True, "live_publishing_enabled should honor the flag")
    ok(flag_enabled({"capabilities": {"x": True}}, "x") is True, "flag_enabled bare bool")
    ok(flag_enabled({"capabilities": {"x": {"enabled": True}}}, "x") is True, "flag_enabled object form")
    ok(flag_enabled({"capabilities": {"x": {"enabled": False}}}, "x") is False, "flag_enabled disabled object")

    # 2) Unknown platform hard-fails.
    r = check("vimeo", config={}, creds={})
    ok(r["ok"] is False and "Unknown platform" in (r["error"] or ""), "unknown platform must fail")

    # 3) direct_api tier without credentials hard-fails; with a publish token it passes.
    r = check("youtube", config=YT_ON, creds={})
    ok(r["tier"] == "direct_api" and r["ok"] is False and "credentials" in (r["error"] or ""),
       "direct_api without creds must fail")
    r = check("youtube", config=YT_ON, creds={"youtube": {"publish": {"access_token": "t"}}})
    ok(r["tier"] == "direct_api" and r["ok"] is True and r["has_credentials"] is True,
       "direct_api with a publish token must pass")
    # Back-compat: a root-level token also counts.
    r = check("youtube", config=YT_ON, creds={"youtube": {"access_token": "t"}})
    ok(r["has_credentials"] is True, "root-level token should count (back-compat)")

    # 4) manual tier passes with no creds (documents F7: the network gate is separate from this tier gate).
    r = check("youtube", config={}, creds={})
    ok(r["tier"] == "manual" and r["ok"] is True and r["has_credentials"] is False,
       "manual tier should pass with no creds")

    # 5) human_review_required is always True.
    ok(check("tiktok", config={}, creds={})["human_review_required"] is True,
       "human_review_required must always be True")

    # 6) FTC disclosure prepended when missing; not double-prepended when present.
    r = check("youtube", caption="hello", ftc_disclosure="#ad", config={}, creds={})
    ok(r["ftc_prepended"] is True and r["effective_caption"].startswith("#ad")
       and r["ftc_disclosure_verified"] is True, "FTC disclosure should prepend when absent")
    r = check("youtube", caption="#ad hello", ftc_disclosure="#ad", config={}, creds={})
    ok(r["ftc_prepended"] is False, "FTC disclosure should not double-prepend")

    # 7) AIGC flag is TikTok-only.
    ok(check("tiktok", is_aigc=True, config={}, creds={})["aigc_flag_set"] is True, "tiktok AIGC on")
    ok(check("youtube", is_aigc=True, config={}, creds={})["aigc_flag_set"] is False, "non-tiktok AIGC off")

    for msg in failures:
        print(f"FAIL {msg}")
    n = ran[0]
    print(f"publishing_compliance selftest: {n - len(failures)}/{n} checks passed"
          if not failures else f"publishing_compliance selftest FAILED ({len(failures)} of {n})")
    return 1 if failures else 0


if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Publishing compliance / tier gate.")
    ap.add_argument("--selftest", action="store_true", help="run the offline gate selftest")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(_selftest())
    ap.print_help()
    sys.exit(0)
