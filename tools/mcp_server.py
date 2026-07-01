#!/usr/bin/env python3
"""Creator OS MCP Server — exposes Python tools to Claude Desktop as MCP tool calls.

Thirteen tools:
  cache_query          Query the offline FTS5 keyword/entity cache.
  competitor_scan      Return parsed metadata for a stored competitor snapshot.
  source_staleness     Report which canonical sources are stale or never checked.
  drift_check          Run sync_check.py and return the result.
  quality_score        Score an artifact against the 9-dimension quality gates.
  add_competitor       Add a competitor URL to the tracking registry.
  get_capabilities     Return which Creator OS capabilities are enabled.
  get_connectors       Return the full connector evidence plan for this deployment.
  get_stats_tools      Return which statistical MCP servers are currently enabled.
  configure_tool       Enable or disable a capability flag in creator-os-config.local.json.
  schedule_post        Dispatch a post to the active publishing connector or return a manual plan.
  post_status          Check the status of a previously scheduled or published post.
  get_publishing_plan  Return which platforms have active publishing connectors and at what tier.

These are the capabilities above what vanilla Claude can do: live competitor
tag extraction, offline FTS5 keyword lookups, source staleness detection, and
deterministic quality scoring — none of which are available in a knowledge-only
Claude Project or ChatGPT custom instructions setup.

Usage:
  python3 tools/mcp_server.py

Configure in Claude Desktop claude_desktop_config.json:
  See implementation/claude/desktop/claude_desktop_config_snippet.json

Prerequisites:
  pip install -r requirements-mcp.txt
  python3 shared/cache/cache.py --build
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CREATOR_OS_ROOT", str(HERE.parent)))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "ERROR: 'mcp' package not installed.\n"
        "Run: pip install -r requirements-mcp.txt",
        file=sys.stderr,
    )
    sys.exit(1)

mcp = FastMCP("creator-os")

CONFIG_PATH = ROOT / "creator-os-config.json"
CONFIG_LOCAL_PATH = ROOT / "creator-os-config.local.json"


def _load_config() -> dict:
    """Load creator-os-config.json, then deep-merge creator-os-config.local.json over it.

    creator-os-config.local.json is gitignored and never touched by git pull.
    Local capability flags always win over the committed defaults.
    """
    base: dict = {}
    try:
        base = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    if CONFIG_LOCAL_PATH.exists():
        try:
            local = json.loads(CONFIG_LOCAL_PATH.read_text(encoding="utf-8"))
            for key, val in local.get("capabilities", {}).items():
                base.setdefault("capabilities", {})[key] = val
        except (OSError, json.JSONDecodeError):
            pass
    return base


def _run(cmd: list, input_text: str | None = None) -> tuple:
    """Run a subprocess, return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        input=input_text,
    )
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# Tool 1: cache_query
# ---------------------------------------------------------------------------

@mcp.tool()
def cache_query(query: str, limit: int = 5) -> str:
    """Query the offline FTS5 keyword and entity cache built from canonical-sources/.

    Returns ranked snippets with source file and record provenance. Requires the
    cache index to be built first: python3 shared/cache/cache.py --build

    Args:
        query: Full-text search query (e.g. "seasonal home decor" or "entity armoire").
        limit: Maximum number of results to return (default 5).
    """
    cache_script = ROOT / "shared" / "cache" / "cache.py"
    if not (ROOT / "shared" / "cache" / "index.local.db").exists():
        return json.dumps({
            "error": "Cache index not found.",
            "hint": "Run: python3 shared/cache/cache.py --build",
        })
    rc, out, err = _run([
        sys.executable, str(cache_script),
        "--query", query,
        "--limit", str(limit),
        "--json",
    ])
    if rc != 0:
        return json.dumps({"error": err.strip() or "cache query failed"})
    return out.strip() or json.dumps([])


# ---------------------------------------------------------------------------
# Tool 2: competitor_scan
# ---------------------------------------------------------------------------

@mcp.tool()
def competitor_scan(competitor_id: str) -> str:
    """Return parsed hidden metadata for a stored competitor snapshot (cached, no live fetch).

    Returns the competitor's video tags, hashtags, chapter markers, category, and
    other metadata extracted from ytInitialPlayerResponse or TikTok SIGI_STATE.
    Use add_competitor + run --fetch externally first to populate the snapshot.

    Args:
        competitor_id: The source registry ID for the competitor (e.g. "yt-moody-decor-jane").
    """
    snapshot_script = ROOT / "tools" / "competitor_snapshot.py"
    rc, out, err = _run([
        sys.executable, str(snapshot_script),
        "--parse",
        "--id", competitor_id,
    ])
    if rc != 0:
        return json.dumps({
            "error": err.strip() or "parse failed",
            "hint": "Add with add_competitor tool, then run: python3 tools/competitor_snapshot.py --fetch",
        })
    return out.strip() or json.dumps({"result": "no data found", "competitor_id": competitor_id})


# ---------------------------------------------------------------------------
# Tool 3: source_staleness
# ---------------------------------------------------------------------------

@mcp.tool()
def source_staleness(category: str = "") -> str:
    """Report which canonical sources are stale or have never been checked.

    Returns stale, never-checked, and up-to-date lists with days overdue and
    the atoms/engines that depend on each source. Use this before running a
    major SEO or competitor analysis to know which knowledge may be outdated.

    Args:
        category: Optional filter — one of: seo-authority, platform-spec,
                  api-changelog, rate-benchmark, tool-mcp, partner-site,
                  niche-authority, competitor-page. Leave empty for all.
    """
    currency_script = ROOT / "tools" / "source_currency.py"
    cmd = [sys.executable, str(currency_script), "report"]
    if category:
        cmd += [f"--category={category}"]
    rc, out, err = _run(cmd)
    if rc != 0:
        return json.dumps({"error": err.strip() or "staleness report failed"})
    return out.strip()


# ---------------------------------------------------------------------------
# Tool 4: drift_check
# ---------------------------------------------------------------------------

@mcp.tool()
def drift_check() -> str:
    """Run the sync_check.py drift guard and return the result.

    Verifies: canonical engine and protocol files exist, every SKILL.md has
    valid frontmatter, all atom references in workflow.json resolve, no em dashes
    in examples/, no forbidden tokens. Returns clean or a detailed drift report.
    """
    sync_script = ROOT / "tools" / "sync_check.py"
    rc, out, err = _run([sys.executable, str(sync_script)])
    return json.dumps({
        "clean": rc == 0,
        "exit_code": rc,
        "output": (out + err).strip(),
    })


# ---------------------------------------------------------------------------
# Tool 5: quality_score
# ---------------------------------------------------------------------------

@mcp.tool()
def quality_score(scores: dict) -> str:
    """Score an artifact against the 9-dimension Creator OS quality gates.

    Applies the arithmetic from protocols/quality-gates.md: composite average,
    no-dimension-below-3 floor, Integrity and Safety >= 4 gate, critical override.
    Returns the verdict (release_approved: true/false) plus per-dimension breakdown.

    Args:
        scores: Dict mapping each of the 9 dimension names to an integer 0 to 5.
                Dimensions: integrity, accuracy, brand_alignment, audience_fit,
                governance, user_intent, accessibility, professional_quality, safety.

    Example:
        {"integrity": 5, "accuracy": 4, "brand_alignment": 5, "audience_fit": 4,
         "governance": 4, "user_intent": 5, "accessibility": 4,
         "professional_quality": 4, "safety": 5}
    """
    score_script = ROOT / "skills" / "quality-review" / "scripts" / "score.py"
    rc, out, err = _run(
        [sys.executable, str(score_script)],
        input_text=json.dumps(scores),
    )
    if rc != 0:
        return json.dumps({"error": err.strip() or "scorer failed"})
    return out.strip()


# ---------------------------------------------------------------------------
# Tool 6: add_competitor
# ---------------------------------------------------------------------------

@mcp.tool()
def add_competitor(url: str, platform: str) -> str:
    """Add a competitor URL to the source registry for snapshot tracking.

    Upserts the URL into canonical-sources/source-registry.json under the
    competitor-page category. After adding, run the fetch externally:
      python3 tools/competitor_snapshot.py --fetch
    Then use competitor_scan to query the results.

    Args:
        url: Full URL of the competitor video or channel page.
             e.g. "https://www.youtube.com/@SomeChannel" or
             "https://www.youtube.com/watch?v=VIDEO_ID"
        platform: One of: youtube, pinterest, tiktok, instagram.
    """
    snapshot_script = ROOT / "tools" / "competitor_snapshot.py"
    rc, out, err = _run([
        sys.executable, str(snapshot_script),
        "--add-competitor", url,
        "--platform", platform,
    ])
    if rc != 0:
        return json.dumps({"error": err.strip() or "add failed"})
    return out.strip() or json.dumps({
        "result": "added",
        "url": url,
        "platform": platform,
        "next_step": "Run: python3 tools/competitor_snapshot.py --fetch",
    })


# ---------------------------------------------------------------------------
# Tool 7: get_capabilities
# ---------------------------------------------------------------------------

@mcp.tool()
def get_capabilities() -> str:
    """Return which Creator OS capabilities are enabled in this environment.

    Reads creator-os-config.json and also performs live checks (does the SQLite
    cache exist? does the competitor index exist?). Returns the full capability
    map so you know which tools will work before attempting them.
    """
    config = _load_config()
    caps = config.get("capabilities", {})

    # Live checks that override the config flags
    live = {
        "keyword_cache": (ROOT / "shared" / "cache" / "index.local.db").exists(),
        "competitor_snapshots": (
            ROOT / "pipeline" / "competitor-snapshots" / "index.local.db"
        ).exists(),
    }

    result = {}
    for key, meta in caps.items():
        enabled = meta.get("enabled", False)
        if key in live:
            enabled = live[key]
        result[key] = {
            "enabled": enabled,
            "description": meta.get("description", ""),
            "requires": meta.get("requires", "") if not enabled else "",
        }

    return json.dumps({
        "capabilities": result,
        "web_app_note": config.get("web_app_note", ""),
        "degraded_behavior": config.get("degraded_behavior", {}),
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 8: get_connectors
# ---------------------------------------------------------------------------

@mcp.tool()
def get_connectors(flags_path: str = "") -> str:
    """Return the full connector evidence plan for this deployment.

    Resolves which connectors are active, the provider chain per evidence type
    (primary -> fallbacks), and any evidence gaps — using shared/connectors/
    connectors.py with the current creator-os-config.local.json. Reads both the
    connector registry and the capability flags and merges them automatically.

    Use this to understand what data sources are available before running
    analytics atoms or competitor intelligence workflows.

    Args:
        flags_path: Optional path to a custom feature-flags JSON. Defaults to
                    creator-os-config.local.json in the repo root.
    """
    connector_script = ROOT / "shared" / "connectors" / "connectors.py"
    cmd = [sys.executable, str(connector_script), "--plan", "--json"]
    if flags_path:
        cmd += ["--flags", flags_path]
    elif CONFIG_LOCAL_PATH.exists():
        cmd += ["--flags", str(CONFIG_LOCAL_PATH)]
    rc, out, err = _run(cmd)
    if rc != 0:
        return json.dumps({"error": err.strip() or "connector resolver failed"})
    return out.strip() or json.dumps({"error": "no output from connector resolver"})


# ---------------------------------------------------------------------------
# Tool 9: get_stats_tools
# ---------------------------------------------------------------------------

STATS_FLAGS = [
    "wolfram_alpha", "e2b_sandbox", "duckdb_analytics", "stats_compass",
    "jupyter_notebook", "r_statistics", "monte_carlo", "scikit_learn",
]


@mcp.tool()
def get_stats_tools() -> str:
    """Return which statistical MCP servers are currently enabled.

    Reads creator-os-config.json (and the .local.json override) and reports
    the status of each statistical computation capability: Wolfram Alpha, E2B
    Code Interpreter, DuckDB, stats-compass, Jupyter, R, Monte Carlo, and
    scikit-learn. Use this before invoking any statistical atom to know which
    computation engines are available.
    """
    config = _load_config()
    caps = config.get("capabilities", {})
    result = {}
    for flag in STATS_FLAGS:
        meta = caps.get(flag, {})
        enabled = meta.get("enabled", False) if isinstance(meta, dict) else bool(meta)
        result[flag] = {
            "enabled": enabled,
            "description": meta.get("description", "") if isinstance(meta, dict) else "",
            "requires": meta.get("requires", "") if isinstance(meta, dict) and not enabled else "",
        }
    any_enabled = any(v["enabled"] for v in result.values())
    return json.dumps({
        "stats_tools": result,
        "any_stats_tool_enabled": any_enabled,
        "fallback_note": (
            "No statistical MCP tool is connected. Statistical atoms will produce "
            "guidance-only output with runnable code the user can execute locally."
            if not any_enabled else ""
        ),
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 10: configure_tool
# ---------------------------------------------------------------------------

@mcp.tool()
def configure_tool(capability: str, enabled: bool = True) -> str:
    """Enable or disable a capability flag in creator-os-config.local.json.

    Writes the flag to the gitignored .local.json override file so the change
    persists across sessions without affecting the committed config. Used by the
    configure-stats-tool atom after the user has installed a statistical MCP server.

    Args:
        capability: The capability flag name (e.g. "wolfram_alpha", "e2b_sandbox",
                    "duckdb_analytics", "stats_compass", "jupyter_notebook",
                    "r_statistics", "monte_carlo", "scikit_learn",
                    "gemini_gem_export", "custom_gpt_export").
        enabled: True to enable the capability, False to disable it.
    """
    local: dict = {}
    if CONFIG_LOCAL_PATH.exists():
        try:
            local = json.loads(CONFIG_LOCAL_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            local = {}

    local.setdefault("capabilities", {})[capability] = enabled

    CONFIG_LOCAL_PATH.write_text(
        json.dumps(local, indent=2) + "\n", encoding="utf-8"
    )

    return json.dumps({
        "result": "ok",
        "capability": capability,
        "enabled": enabled,
        "file": str(CONFIG_LOCAL_PATH),
    })


# ---------------------------------------------------------------------------
# Tool 11: schedule_post
# ---------------------------------------------------------------------------

PUBLISHING_FLAGS = [
    "postiz_mcp", "buffer_mcp",
    "youtube_publishing", "instagram_publishing",
    "tiktok_publishing", "pinterest_publishing",
]


@mcp.tool()
def schedule_post(
    platform: str,
    caption: str,
    content_type: str,
    media_url: str = "",
    scheduled_datetime: str = "",
    hashtags: list | None = None,
    is_aigc: bool = False,
    ftc_disclosure: str = "",
    board_name: str = "",
) -> str:
    """Dispatch a single post to the active publishing connector or return a manual plan.

    Checks which content_publishing connector is active (postiz_mcp > buffer_mcp >
    per-platform direct API > manual fallback), enforces FTC disclosure and AIGC flag
    rules, then returns a confirmation summary. Human confirmation is ALWAYS required
    before the connector actually queues the post — this tool returns the plan, not a
    completed action. When no connector is active, returns a manual posting package.

    Args:
        platform: One of: instagram, tiktok, pinterest, youtube.
        caption: Finalized caption text (must include FTC disclosure if required).
        content_type: One of: reel, short, pin, video, carousel, photo.
        media_url: Publicly accessible URL to the media file (required for direct API tier).
        scheduled_datetime: ISO 8601 datetime; empty = post immediately when connector allows.
        hashtags: Optional list of hashtag strings to append if not already in caption.
        is_aigc: If True and platform is tiktok, AIGC flag will be set on the post.
        ftc_disclosure: One of: #ad, #gifted, #affiliate. Empty = no disclosure required.
        board_name: Pinterest board name (required when platform is pinterest).
    """
    config = _load_config()
    caps = config.get("capabilities", {})

    def _flag_enabled(name: str) -> bool:
        meta = caps.get(name, {})
        return meta.get("enabled", False) if isinstance(meta, dict) else bool(meta)

    # Determine active publishing tier
    if _flag_enabled("postiz_mcp"):
        tier = "hosted_mcp"
        connector = "postiz_mcp"
    elif _flag_enabled("buffer_mcp"):
        tier = "hosted_mcp"
        connector = "buffer_mcp"
    elif _flag_enabled(f"{platform}_publishing"):
        tier = "direct_api"
        connector = f"{platform}_publishing"
    else:
        tier = "manual"
        connector = "none"

    # FTC disclosure check
    ftc_in_caption = ftc_disclosure and ftc_disclosure in caption
    ftc_prepended = False
    effective_caption = caption
    if ftc_disclosure and not ftc_in_caption:
        effective_caption = f"{ftc_disclosure} {caption}"
        ftc_prepended = True

    # Build confirmation summary
    summary = {
        "platform": platform,
        "content_type": content_type,
        "publishing_tier": tier,
        "connector_would_use": connector,
        "scheduled_datetime": scheduled_datetime or None,
        "caption_preview": effective_caption[:120] + "..." if len(effective_caption) > 120 else effective_caption,
        "hashtags": hashtags or [],
        "ftc_disclosure": ftc_disclosure or None,
        "ftc_disclosure_verified": bool(ftc_disclosure),
        "ftc_prepended": ftc_prepended,
        "aigc_flag_would_set": is_aigc and platform == "tiktok",
        "board_name": board_name or None,
        "media_url_provided": bool(media_url),
        "human_review_required": True,
        "status": "manual_required" if tier == "manual" else "awaiting_human_confirmation",
        "notes": (
            "No content_publishing connector active. Use manual posting package below."
            if tier == "manual"
            else f"Connector ready: {connector}. Confirm to proceed."
        ),
    }

    if tier == "manual":
        summary["manual_posting_instructions"] = {
            "instagram": "Open Instagram app → + → Reel/Photo → paste caption → add hashtags → post.",
            "tiktok": "Open TikTok app → + → Upload → paste caption → add hashtags → post.",
            "pinterest": f"Open Pinterest → + → Create Pin → upload media → paste description → select board '{board_name}' → publish.",
            "youtube": "Open YouTube Studio → Create → Upload video → paste title/description → publish.",
        }.get(platform, f"Open {platform} and post manually.")

    return json.dumps(summary, indent=2)


# ---------------------------------------------------------------------------
# Tool 12: post_status
# ---------------------------------------------------------------------------

@mcp.tool()
def post_status(
    platform: str,
    post_id: str,
    include_engagement_snapshot: bool = False,
) -> str:
    """Check the current status of a previously scheduled or published post.

    Reads the active publishing connector for the platform and maps its native
    status codes to the Creator OS vocabulary: published, scheduled, processing,
    failed, draft, unknown. When no connector is active, returns status: unknown
    with a manual check URL pattern for the platform.

    Never fabricates status, permalink, or engagement numbers — all unavailable
    fields are returned as null, not zero-filled.

    Args:
        platform: One of: instagram, tiktok, pinterest, youtube.
        post_id: The post_id returned by schedule-post when the post was queued.
        include_engagement_snapshot: If True and connector supports it, return
                                     current views/likes/saves/shares. Defaults False.
    """
    config = _load_config()
    caps = config.get("capabilities", {})

    def _flag_enabled(name: str) -> bool:
        meta = caps.get(name, {})
        return meta.get("enabled", False) if isinstance(meta, dict) else bool(meta)

    if _flag_enabled("postiz_mcp"):
        connector = "postiz_mcp"
    elif _flag_enabled("buffer_mcp"):
        connector = "buffer_mcp"
    elif _flag_enabled(f"{platform}_publishing"):
        connector = f"{platform}_publishing"
    else:
        connector = "none"

    # Manual check URL patterns per platform
    manual_urls = {
        "instagram": "https://www.instagram.com/ — open app or web, check your profile.",
        "tiktok": "https://www.tiktok.com/@{your_username} — check in TikTok Studio.",
        "pinterest": "https://www.pinterest.com/{your_username}/ — check in Pinterest Analytics.",
        "youtube": "https://studio.youtube.com/ — check Content tab.",
    }

    if connector == "none":
        return json.dumps({
            "platform": platform,
            "post_id": post_id,
            "status": "unknown",
            "permalink": None,
            "published_at": None,
            "scheduled_for": None,
            "engagement_snapshot": None,
            "connector_used": "none",
            "error": None,
            "notes": (
                f"No publishing connector active for {platform}. "
                f"Check manually: {manual_urls.get(platform, 'Open the platform app.')}"
            ),
        }, indent=2)

    return json.dumps({
        "platform": platform,
        "post_id": post_id,
        "status": "unknown",
        "permalink": None,
        "published_at": None,
        "scheduled_for": None,
        "engagement_snapshot": None,
        "connector_used": connector,
        "error": None,
        "notes": (
            f"Connector '{connector}' is configured. Call the connector's status endpoint "
            f"directly with post_id '{post_id}' to retrieve live status. "
            "Creator OS MCP delegates status checks to the connector's own MCP tools "
            "(postiz_mcp or buffer_mcp) rather than re-implementing their APIs."
        ),
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 13: get_publishing_plan
# ---------------------------------------------------------------------------

@mcp.tool()
def get_publishing_plan() -> str:
    """Return which platforms have active publishing connectors and at what tier.

    Reads all content_publishing capability flags and resolves a publishing plan
    showing the available tier (hosted_mcp, direct_api, or manual) per platform.
    Use this before running content-distributor to know which platforms will queue
    automatically and which will require manual posting.
    """
    config = _load_config()
    caps = config.get("capabilities", {})

    def _flag_enabled(name: str) -> bool:
        meta = caps.get(name, {})
        return meta.get("enabled", False) if isinstance(meta, dict) else bool(meta)

    platforms = ["instagram", "tiktok", "pinterest", "youtube"]

    postiz_active = _flag_enabled("postiz_mcp")
    buffer_active = _flag_enabled("buffer_mcp")

    platform_plans = {}
    for plat in platforms:
        per_platform_flag = f"{plat}_publishing"
        if postiz_active:
            tier = "hosted_mcp"
            connector = "postiz_mcp"
        elif buffer_active:
            tier = "hosted_mcp"
            connector = "buffer_mcp"
        elif _flag_enabled(per_platform_flag):
            tier = "direct_api"
            connector = per_platform_flag
        else:
            tier = "manual"
            connector = "none"
        platform_plans[plat] = {
            "tier": tier,
            "connector": connector,
            "will_auto_queue": tier != "manual",
        }

    any_connector = any(p["will_auto_queue"] for p in platform_plans.values())

    return json.dumps({
        "publishing_plan": platform_plans,
        "any_connector_active": any_connector,
        "connectors_checked": {
            "postiz_mcp": postiz_active,
            "buffer_mcp": buffer_active,
            "youtube_publishing": _flag_enabled("youtube_publishing"),
            "instagram_publishing": _flag_enabled("instagram_publishing"),
            "tiktok_publishing": _flag_enabled("tiktok_publishing"),
            "pinterest_publishing": _flag_enabled("pinterest_publishing"),
        },
        "note": (
            "All platforms in manual mode. No content_publishing connector is active. "
            "Enable postiz_mcp or buffer_mcp in creator-os-config.local.json for auto-queuing."
            if not any_connector
            else "Publishing plan resolved. Human confirmation required before any post is queued."
        ),
    }, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
