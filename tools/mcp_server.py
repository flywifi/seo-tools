#!/usr/bin/env python3
"""Creator OS MCP Server — exposes Python tools to Claude Desktop as MCP tool calls.

Tools (the docstrings below and tools/list are authoritative; the set has grown by phase):
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

sys.path.insert(0, str(HERE))
import publishing_compliance as compliance  # noqa: E402

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


def _construction_query(query, limit):
    """Run the offline cache query and keep only construction-dictionary results."""
    cache_script = ROOT / "shared" / "cache" / "cache.py"
    if not (ROOT / "shared" / "cache" / "index.local.db").exists():
        return None, {"error": "Cache index not found.", "hint": "Run: python3 shared/cache/cache.py --build"}
    rc, out, err = _run([sys.executable, str(cache_script), "--query", query,
                         "--limit", str(max(limit * 5, 20)), "--json"])
    if rc != 0:
        return None, {"error": err.strip() or "cache query failed"}
    try:
        data = json.loads(out or "{}")
    except json.JSONDecodeError:
        return None, {"error": "could not parse cache output"}
    results = data.get("results", data if isinstance(data, list) else [])
    kept = [r for r in results if str(r.get("source", "")).startswith("canonical-sources/construction")]
    return kept[:limit], None


@mcp.tool()
def construction_lookup(query: str, limit: int = 6) -> str:
    """Query the offline residential-construction dictionary (P34): dimensions, required steps, common
    mistakes, and code citations for framing, stairs, decks, foundations, roofing, electrical,
    plumbing, HVAC, drywall, insulation, egress, siding/flashing, plus the glossary, assemblies, and
    FL/NC specifics. Returns ranked entries with their source file and record id (read the record for
    the full dimensions and citations). Every entry carries the verify-locally boundary. Do NOT treat
    results as code-compliance or engineering advice. Requires the cache: python3 shared/cache/cache.py
    --build."""
    kept, err = _construction_query(query, limit)
    if err is not None:
        return json.dumps(err)
    return json.dumps({"query": query, "results": kept}, indent=2, ensure_ascii=False)


@mcp.tool()
def code_lookup(topic: str, jurisdiction: str = "both", limit: int = 6) -> str:
    """Resolve a residential requirement by topic and jurisdiction (P34), returning the matching
    dictionary entries (with their IRC/NEC/IPC section citations) plus the adopted code edition for the
    jurisdiction: Florida (2023 FBC 8th Edition, 2021 I-Codes) or North Carolina (2018 NC RC, 2015 IRC,
    with the pending 2024 transition). jurisdiction is 'fl', 'nc', or 'both'. Codes are cited by section
    with a link to the free viewer; text and tables are never reproduced. Carries the verify-locally
    boundary; not code-compliance advice. Requires the cache built."""
    kept, err = _construction_query(topic, limit)
    if err is not None:
        return json.dumps(err)
    edition = []
    est = ROOT / "canonical-sources" / "construction" / "edition-status.json"
    try:
        entries = json.loads(est.read_text(encoding="utf-8"))
        want = {"fl": {"FL", "model"}, "nc": {"NC", "model"}, "both": {"FL", "NC", "model"}}.get(
            jurisdiction.lower(), {"FL", "NC", "model"})
        edition = [{"jurisdiction": e.get("jurisdiction"), "adopted_edition": e.get("adopted_edition"),
                    "model_basis": e.get("model_basis"), "pending": e.get("pending")}
                   for e in entries if e.get("jurisdiction") in want]
    except (OSError, json.JSONDecodeError):
        edition = []
    return json.dumps({"topic": topic, "jurisdiction": jurisdiction, "edition_status": edition,
                       "requirements": kept,
                       "boundary": "Verify against the adopted code edition and your permit office; not code-compliance advice."},
                      indent=2, ensure_ascii=False)


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


@mcp.tool()
def currency_scan(category: str = "", overlay_path: str = "") -> str:
    """Report your sources' freshness, merging YOUR personal freshness overlay when given (P36).

    Read-only. With overlay_path, union-merges your own store's freshness stamps onto the read-only
    baseline so you see YOUR up-to-date view. Writes nothing; never touches GitHub.

    Args:
        category: Optional category filter (seo-authority, api-changelog, platform-spec, ...).
        overlay_path: Path to your personal freshness overlay JSON (your store). Omit for baseline-only.
    """
    cmd = [sys.executable, str(ROOT / "tools" / "source_currency.py"), "report"]
    if category:
        cmd += [f"--category={category}"]
    if overlay_path:
        cmd += ["--overlay", overlay_path]
    rc, out, err = _run(cmd)
    if rc != 0:
        return json.dumps({"error": err.strip() or "currency scan failed"})
    return out.strip()


@mcp.tool()
def currency_detect_changes(overlay_path: str, apply: bool = False, category: str = "", only: str = "") -> str:
    """Token-free change detection over your web sources; stamps go to YOUR overlay only (P36).

    Conditional-GET + sha256 per source; unchanged/first-seen are stamped, changed pages are queued
    for you to interpret. With apply=true, freshness stamps are written to overlay_path (your own
    store) -- NEVER the repo registry and NEVER GitHub. Requires an overlay_path so writes stay in
    your control.

    Args:
        overlay_path: Path to your personal freshness overlay JSON (required as the write target).
        apply: Write the freshness stamps to your overlay (default false = report only).
        category: Optional category filter.
        only: Optional single source id.
    """
    if not overlay_path:
        return json.dumps({"error": "overlay_path is required so all writes stay in your own store"})
    cmd = [sys.executable, str(ROOT / "tools" / "source_currency.py"), "check",
           "--detect-changes", "--overlay", overlay_path]
    if apply:
        cmd += ["--apply"]
    if category:
        cmd += [f"--category={category}"]
    if only:
        cmd += ["--only", only]
    rc, out, err = _run(cmd)
    if rc != 0:
        return json.dumps({"error": err.strip() or "detect-changes failed"})
    return out.strip()


@mcp.tool()
def freshness_refresh(overlay_path: str, source_id: str, field: str, value: str,
                      source_citation: str, publish_date: str = "") -> str:
    """Record ONE cited, refreshed reference value into YOUR freshness overlay (P36 Flow B).

    Writes an {as_of, source_citation, publish_date} envelope to overlay_path (your own store) so the
    value can be aged/flagged rather than silently trusted. Writes only your store; never GitHub, never
    shared. Provide a real source_citation (no-fabrication): if you cannot cite it, do not record it.

    Args:
        overlay_path: Path to your personal freshness overlay JSON (your store; the only write target).
        source_id: The registry source id this value came from.
        field: The field name being refreshed (e.g. "instagram_reels_max_hashtags").
        value: The refreshed value (as a string).
        source_citation: The URL/citation the value came from (required).
        publish_date: The source's publish date if known (ISO), for aging.
    """
    if not overlay_path or not source_citation:
        return json.dumps({"error": "overlay_path and source_citation are required (no-fabrication)"})
    sys.path.insert(0, str(HERE))
    import freshness_overlay as _fo  # noqa: E402
    overlay = _fo.load_overlay(overlay_path)
    env = _fo.record_value(overlay, source_id, field, value, source_citation,
                           publish_date=publish_date or None)
    _fo.save_overlay(overlay, overlay_path)
    return json.dumps({"recorded": {"source_id": source_id, "field": field}, "envelope": env,
                       "wrote_to": overlay_path,
                       "boundary": "your store only; never GitHub, never shared"}, ensure_ascii=False)


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

    Checks which content_publishing connector is active (per-platform direct API >
    manual fallback), enforces FTC disclosure and AIGC flag rules, then returns a
    confirmation summary. Human confirmation is ALWAYS required before the connector
    actually queues the post — this tool returns the plan, not a completed action.
    When no connector is active, returns a manual posting package.

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

    # Shared compliance + tier resolution (same helper the dashboard confirm path uses).
    result = compliance.check(
        platform,
        caption=caption,
        ftc_disclosure=ftc_disclosure,
        is_aigc=is_aigc,
        config=config,
    )
    tier = result["tier"]
    connector = result["connector"]
    effective_caption = result["effective_caption"]

    if tier == "manual":
        notes = "No direct-API publishing connector active. Use manual posting package below."
    elif not result["has_credentials"]:
        # This tool reports (does not hard-fail); the dashboard confirm path refuses instead.
        notes = result["error"]
    else:
        notes = f"Connector ready: {connector}. Confirm to proceed."

    # Build confirmation summary
    summary = {
        "platform": platform,
        "content_type": content_type,
        "publishing_tier": tier,
        "connector_would_use": connector,
        "scheduled_datetime": scheduled_datetime or None,
        "caption_preview": effective_caption[:120] + "..." if len(effective_caption) > 120 else effective_caption,
        "hashtags": hashtags or [],
        "ftc_disclosure": result["ftc_disclosure"],
        "ftc_disclosure_verified": result["ftc_disclosure_verified"],
        "ftc_prepended": result["ftc_prepended"],
        "aigc_flag_would_set": result["aigc_flag_set"],
        "board_name": board_name or None,
        "media_url_provided": bool(media_url),
        "has_credentials": result["has_credentials"],
        "human_review_required": True,
        "status": "manual_required" if tier == "manual" else "awaiting_human_confirmation",
        "notes": notes,
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

    if _flag_enabled(f"{platform}_publishing"):
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
            "Creator OS MCP delegates status checks to the platform's direct API "
            "rather than re-implementing their interfaces."
        ),
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 13: get_publishing_plan
# ---------------------------------------------------------------------------

@mcp.tool()
def get_publishing_plan() -> str:
    """Return which platforms have active publishing connectors and at what tier.

    Reads all content_publishing capability flags and resolves a publishing plan
    showing the available tier (direct_api or manual) per platform.
    Use this before running content-distributor to know which platforms will queue
    automatically and which will require manual posting.
    """
    config = _load_config()
    caps = config.get("capabilities", {})

    def _flag_enabled(name: str) -> bool:
        meta = caps.get(name, {})
        return meta.get("enabled", False) if isinstance(meta, dict) else bool(meta)

    platforms = ["instagram", "tiktok", "pinterest", "youtube"]

    platform_plans = {}
    for plat in platforms:
        per_platform_flag = f"{plat}_publishing"
        if _flag_enabled(per_platform_flag):
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
            "youtube_publishing": _flag_enabled("youtube_publishing"),
            "instagram_publishing": _flag_enabled("instagram_publishing"),
            "tiktok_publishing": _flag_enabled("tiktok_publishing"),
            "pinterest_publishing": _flag_enabled("pinterest_publishing"),
        },
        "dashboard_url": "http://localhost:8766",
        "note": (
            "All platforms in manual mode. No per-platform publishing connector is active. "
            "Enable per-platform flags in creator-os-config.local.json or use the scheduling dashboard."
            if not any_connector
            else "Publishing plan resolved. Human confirmation required before any post is queued."
        ),
    }, indent=2)


# ---------------------------------------------------------------------------
# Tools 14 to 18: video editing bridge (P22)
# ---------------------------------------------------------------------------

@mcp.tool()
def edit_preflight() -> str:
    """Report what the video-editing bridge can do on this machine (OS, tools, flags, lanes).
    Thin wrapper over tools/videoedit/preflight.py; launches nothing."""
    code, out, err = _run([sys.executable, str(HERE / "videoedit" / "preflight.py"), "--json"])
    return out if code == 0 else json.dumps({"error": err or "preflight failed"})


@mcp.tool()
def edit_build_fcpxml(edit_package: dict) -> str:
    """Build a validated FCPXML timeline scaffold from a neutral edit-package.
    Returns the FCPXML plus a validation result. File generation is allowed even while
    video_editing_enabled is off (it drives no app). See shared/videoedit-engine.md."""
    import tempfile as _tf
    sys.path.insert(0, str(HERE / "videoedit"))
    sys.path.insert(0, str(HERE))
    import fcpxml as _f  # type: ignore
    import videoedit_validate as _v  # type: ignore
    xml = _f.build(edit_package)
    val = _v.validate_fcpxml(xml)
    return json.dumps({"fcpxml": xml, "validation": val}, indent=2)


@mcp.tool()
def edit_parse_fcpxml(fcpxml_path: str) -> str:
    """Parse an exported FCPXML/.fcpxmld into a neutral edit-package (markers, chapters,
    keywords, roles). This is the offline-to-online handoff feeding SEO and scheduling."""
    sys.path.insert(0, str(HERE / "videoedit"))
    import fcpxml as _f  # type: ignore
    try:
        return json.dumps(_f.parse(fcpxml_path), indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def import_edit_artifact(fcpxml_path: str) -> str:
    """Import an editor export and surface the pieces that feed the rest of Creator OS:
    chapters -> geo-optimize / description timestamps / scheduling, keywords -> entity-extract,
    roles -> audio-stem plan. Mirrors the dashboard /api/import-report handoff."""
    sys.path.insert(0, str(HERE / "videoedit"))
    import fcpxml as _f  # type: ignore
    try:
        pkg = _f.parse(fcpxml_path)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})
    tl = pkg.get("timeline", {})
    return json.dumps({
        "edit_package": pkg,
        "handoff": {
            "chapters_for_geo_optimize_and_scheduling": tl.get("chapters", []),
            "keywords_for_entity_extract": [k.get("keyword") for k in tl.get("keywords", [])],
            "roles_for_audio_stems": tl.get("roles", []),
            "marker_count": len(tl.get("markers", [])),
        },
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def resolve_status() -> str:
    """Report the DaVinci Resolve lane status (env bootstrap + whether live control is available).
    Live control needs Resolve Studio + the resolve_scripting/video_editing_enabled flags; this
    only inspects, it does not launch Resolve."""
    sys.path.insert(0, str(HERE / "videoedit"))
    import resolve as _r  # type: ignore
    from preflight import _resolve_present, _python_ok  # type: ignore
    return json.dumps({
        "bootstrap": _r.bootstrap_env(),
        "resolve_detected": _resolve_present(),
        "python_ok_for_resolve": _python_ok(),
        "note": "Live methods are stubs until video_editing_enabled + resolve_scripting are on and Resolve Studio is running.",
    }, indent=2)


@mcp.tool()
def edit_captions(source: str, direction: str = "from_editor", format: str = "srt") -> str:
    """Caption round-trip (feature 2). direction='to_editor' converts a transcript/caption file to
    SRT/VTT/iTT text; direction='from_editor' parses an editor caption file into edit-package
    captions[]. Reuses the offline transcript stack; drives no app."""
    sys.path.insert(0, str(HERE / "videoedit"))
    import captions as _c  # type: ignore
    try:
        if direction == "to_editor":
            return json.dumps({"format": format, "caption_text": _c.to_editor(source, format)}, ensure_ascii=False)
        return json.dumps(_c.from_editor(source), indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def chapter_map(chapters: dict) -> str:
    """Chapter fan-out (feature 8). Accepts an edit-package, a {chapters:[...]} object, or a bare
    list, and returns the geo-optimize chapter_outline, a paste-ready YouTube description timestamp
    block, scheduling metadata, and YouTube-rule validation flags. Pure transform."""
    sys.path.insert(0, str(HERE / "videoedit"))
    import chapters as _ch  # type: ignore
    try:
        return json.dumps(_ch.fan_out(chapters), indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def silence_scan(media_path: str | None = None, transcript_path: str | None = None,
                 noise_db: float = -50.0, min_silence_seconds: float = 2.0) -> str:
    """Silence (dead air) detection with provenance (P29). Local analysis, no flag, no app:
    ffmpeg silencedetect when present, PyAV RMS as fallback, degrading to the transcript gap
    floor. Result carries computed_by and the backend_chain audit trail; no backend means an
    honest gaps[] entry, never invented numbers."""
    sys.path.insert(0, str(HERE / "videoedit"))
    import mediaprobe as _mp  # type: ignore
    try:
        return json.dumps(_mp.detect_silence(media_path, transcript_path, noise_db,
                                             min_silence_seconds), indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def scene_scan(media_path: str | None = None, transcript_path: str | None = None,
               threshold: float = 27.0) -> str:
    """Scene-change detection and chapter candidates with provenance (P29). Local analysis, no
    flag, no app: PySceneDetect when installed, ffmpeg scdet as fallback (luma-only caveat rides
    on the result), degrading to the transcript chapter floor. Chapter titles are never
    invented (suggested_title is always null)."""
    sys.path.insert(0, str(HERE / "videoedit"))
    import mediaprobe as _mp  # type: ignore
    try:
        return json.dumps(_mp.detect_scenes(media_path, transcript_path, threshold),
                          indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def reframe_shorts(source_width: int, source_height: int, aspect: str = "9:16",
                   x_center: float | None = None) -> str:
    """Shorts crop geometry (P29, feature 3). Pure math, always available: the centered (or
    offset, clamped) crop rectangle plus the ffmpeg filter string, as an edit-package reframe
    block. Local rendering is CLI-only (tools/videoedit/reframe.py render, gated on the
    shorts_reframe flag); this tool never renders."""
    sys.path.insert(0, str(HERE / "videoedit"))
    import reframe as _rf  # type: ignore
    try:
        return json.dumps(_rf.crop_geometry(source_width, source_height, aspect, x_center),
                          indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def edit_build_mlt(edit_package: dict) -> str:
    """Build MLT XML (Shotcut-native, Kdenlive substrate) from an edit-package (P29, feature 9).
    Mirrors edit_build_fcpxml: returns the XML plus a well-formedness validation verdict. File
    generation only; rendering is CLI-only behind the media_render flag."""
    sys.path.insert(0, str(HERE / "videoedit"))
    import mltxml as _mlt  # type: ignore
    try:
        xml = _mlt.build(edit_package)
        verdict = _mlt.validate(xml)
        return json.dumps({"mlt_xml": xml, "validation": verdict}, indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def obligation_scan(rows: dict | None = None, today: str | None = None, lead_days: int = 3) -> str:
    """Read-only deadline scan for contract obligations (P23 Phase 3). Deterministic date math runs
    in local Python (tools/obligations.py), so the model spends no tokens on arithmetic. Pass `rows`
    (obligation-extract output) to scan them, or omit to scan the stored register. Always available,
    even when contract_obligations is off; never writes."""
    sys.path.insert(0, str(HERE))
    import obligations as _ob  # type: ignore
    try:
        anchor = _ob._today(today)
        data = rows if rows is not None else (
            json.loads(_ob.REGISTER_PATH.read_text(encoding="utf-8")) if _ob.REGISTER_PATH.exists() else None
        )
        if data is None:
            return json.dumps({"error": "no_source", "message": "pass rows or build the register first"})
        return json.dumps(_ob.scan(data, anchor, lead_days), indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def obligation_build(rows: dict, today: str | None = None, lead_days: int = 3, write: bool = False) -> str:
    """Compute the dated obligation register from obligation-extract rows (P23 Phase 3). The date math
    (send-by, weekend/US-holiday roll-back, urgency bands) runs in local Python, not tokens. Returns
    the computed register JSON. Persisting it (write=True) is gated behind contract_obligations; while
    off, the register is computed and returned with a gate note but not written."""
    sys.path.insert(0, str(HERE))
    import obligations as _ob  # type: ignore
    try:
        anchor = _ob._today(today)
        reg = _ob.build_register(rows, anchor, lead_days)
        if write:
            cfg = _ob.load_config()
            if not _ob.flag_enabled(cfg, "contract_obligations"):
                reg = dict(reg)
                reg["_gate"] = ("contract_obligations is off: register computed but NOT written. "
                                "Enable it to persist (see degraded_behavior).")
            else:
                _ob.REGISTER_PATH.parent.mkdir(parents=True, exist_ok=True)
                _ob.REGISTER_PATH.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                reg = dict(reg)
                reg["_written"] = _ob.REGISTER_PATH.relative_to(_ob.ROOT).as_posix()
        return json.dumps(reg, indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def import_obligations() -> str:
    """Import the computed obligation register and surface the pieces that feed the rest of Creator OS:
    deadlines -> content-calendar (publish_target_date / ftc_disclosure via linked_deal_id),
    send-by dates -> production-task (D-minus-N offsets), payment terms -> deal-resourcing / invoice-status.
    Mirrors import_edit_artifact and the dashboard /api/import-report handoff. Read-only."""
    sys.path.insert(0, str(HERE))
    import obligations as _ob  # type: ignore
    if not _ob.REGISTER_PATH.exists():
        return json.dumps({"error": "no_register",
                           "message": "no obligation register yet; run obligation_build with write=True (contract_obligations on)"})
    try:
        reg = json.loads(_ob.REGISTER_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})
    obs = reg.get("obligations", [])
    return json.dumps({
        "boundary": reg.get("_boundary"),
        "contract_ref": reg.get("contract_ref"),
        "deal_id": reg.get("deal_id"),
        "band_counts": reg.get("band_counts", {}),
        "handoff": {
            "calendar_deadlines": [
                {"required_action": o.get("required_action"), "effective_date": o.get("effective_date"),
                 "send_by_date": o.get("send_by_date"), "urgency_band": o.get("urgency_band")}
                for o in obs
            ],
            "production_send_by_dates": [o.get("send_by_date") for o in obs if o.get("send_by_date")],
            "payment_obligations": [
                {"required_action": o.get("required_action"), "send_by_date": o.get("send_by_date")}
                for o in obs if (o.get("clause_family") == "payment_terms_and_kill_fee"
                                 or (o.get("required_action") or "").lower().find("invoice") >= 0
                                 or (o.get("required_action") or "").lower().find("payment") >= 0)
            ],
        },
        "human_review_required": True,
        "note": "Deterministic register from tools/obligations.py; map these onto content-calendar, production-task, and deal-resourcing. A human confirms before any calendar or invoice action.",
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def finance_scan(invoices: list | None = None, today: str | None = None) -> str:
    """Accounts-receivable scan (P30). Read-only and always available: aging buckets, per-brand
    totals, accrued late penalties under each invoice's frozen terms, and the chase queue. Pass
    invoice records inline, or omit to read pipeline/finance/*.local.json. All arithmetic runs in
    tools/finance.py (exact decimal, no tokens); the model never re-adds figures."""
    sys.path.insert(0, str(HERE))
    import finance as _fin  # type: ignore
    from datetime import date as _date
    try:
        t = _date.fromisoformat(today) if today else None
        return json.dumps(_fin.ar_scan(invoices, t), indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def invoice_build(payload: dict, today: str | None = None, write: bool = False) -> str:
    """Draft a standalone invoice record (P30). Numbers only from the payload (deal figures);
    deterministic INV-<deal_id>-<seq> id; due date derived from structured net terms offline.
    write=True persists to pipeline/finance/ ONLY when finance_management AND invoice_generation
    are on; otherwise the computed draft returns with a _gate note. Nothing is ever sent; the
    human reviews and sends (consequential-action gate, shared/finance-engine.md)."""
    sys.path.insert(0, str(HERE))
    import finance as _fin  # type: ignore
    import obligations as _ob  # type: ignore
    from datetime import date as _date
    try:
        t = _date.fromisoformat(today) if today else _date.today()
        inv = _fin.build_invoice(payload, t)
        if write:
            ok, reason = _fin._write_allowed(_ob.load_config())
            if not ok:
                inv["_gate"] = reason
            else:
                _fin.FINANCE_DIR.mkdir(parents=True, exist_ok=True)
                out = _fin.FINANCE_DIR / f"{inv['invoice_id']}.local.json"
                out.write_text(json.dumps(inv, indent=2) + "\n", encoding="utf-8")
                inv["_written_to"] = str(out)
        return json.dumps(inv, indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def cost_rollup(line_items: list, time: dict | None = None) -> str:
    """Cost-estimate totals (P30): category sums, expense vs capex split, time cost (hours x
    hourly rate), grand total. Exact decimal via tools/finance.py; null amounts come back as
    gaps and are excluded from totals, never guessed in. Carries the CPA boundary downstream."""
    sys.path.insert(0, str(HERE))
    import finance as _fin  # type: ignore
    try:
        return json.dumps(_fin.cost_rollup(line_items, time), indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def proposal_price(cost_total: float | None = None, margin_percent: float | None = None,
                   rate_floor: float | None = None, benchmark_range: dict | None = None) -> str:
    """Standardized proposal price floor (P30): max(cost floor, negotiation floor) with the
    binding constraint named and benchmark-range flags. Decision support only; the
    consequential-action gate applies before any number is quoted externally."""
    sys.path.insert(0, str(HERE))
    import finance as _fin  # type: ignore
    try:
        return json.dumps(_fin.proposal_price(cost_total, margin_percent, rate_floor,
                                              benchmark_range), indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def cashflow_view(scheduled: list | None = None, estimates: list | None = None,
                  horizon_days: int = 90, today: str | None = None,
                  redacted: bool = False) -> str:
    """Weekly cash-movement view (P31). Read-only, always available: expected inflows from open
    invoices (read from pipeline/finance/) and dated scheduled rows, outflows from dated cost
    estimates; overdue and undated items totaled separately with gaps, never guessed into a
    week. Movement, not a bank balance. EXPOSURE NOTE: raw output contains real amounts and
    brand names; pass redacted=True (banded amounts, initialed brands) for anything that will
    be quoted outside this machine."""
    sys.path.insert(0, str(HERE))
    import finance as _fin  # type: ignore
    from datetime import date as _date
    try:
        t = _date.fromisoformat(today) if today else None
        result = _fin.cashflow(None, scheduled, estimates, horizon_days, t)
        return json.dumps(_fin.redact(result) if redacted else result,
                          indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def build_calc(calc: str, params: dict | None = None) -> str:
    """Offline residential construction calculation (P34). calc is one of: stair, egress, rvalue,
    box_fill, drain_slope, roof_pitch, board_foot, deck_span. params holds the numeric inputs, e.g.
    stair -> {total_rise_in}; egress -> {width_in, height_in, sill_in, at_grade}; rvalue ->
    {component, climate_zone}; box_fill -> {conductors:[awg...], devices, clamps, grounds};
    drain_slope -> {pipe_dia_in, run_ft}; roof_pitch -> {rise, run}; board_foot -> {thickness_in,
    width_in, length_ft, qty}; deck_span -> {species, nominal, spacing_in}. All math is first
    principles in tools/build_calc.py (no copyrighted tables); every result carries its code section
    and the verify-locally boundary. deck_span is advisory only, never an authoritative span."""
    sys.path.insert(0, str(HERE))
    import build_calc as _bc  # type: ignore
    fns = {
        "stair": _bc.stair, "egress": _bc.egress, "rvalue": _bc.rvalue_zone,
        "box_fill": _bc.box_fill, "drain_slope": _bc.drain_slope, "roof_pitch": _bc.roof_pitch,
        "board_foot": _bc.board_foot, "deck_span": _bc.deck_span_sanity,
    }
    fn = fns.get(calc)
    if fn is None:
        return json.dumps({"error": f"unknown calc '{calc}'; choose one of {sorted(fns)}"})
    try:
        return json.dumps(fn(**(params or {})), indent=2, ensure_ascii=False)
    except TypeError as exc:
        return json.dumps({"error": f"bad params for {calc}: {exc}"})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def payment_reconcile(csv_path: str, window_days: int = 5, amount_tolerance: str = "0.00",
                      redacted: bool = False) -> str:
    """Match a bank/PayPal export to open invoices (P31). PROPOSAL-ONLY: confidence-tiered
    matches for human confirmation; nothing is marked paid here (mark-paid is a gated CLI step
    after an explicit yes per invoice). STRUCTURAL BOUNDARY: an in-repo CSV is refused unless
    its filename carries .local. (bank exports live at pipeline/finance/<name>.local.csv,
    gitignored, or outside the repo). EXPOSURE NOTE: raw output contains real amounts and
    descriptions; pass redacted=True for anything quoted off this machine."""
    sys.path.insert(0, str(HERE))
    import finance as _fin  # type: ignore
    try:
        result = _fin.reconcile(csv_path, None, window_days, amount_tolerance)
        return json.dumps(_fin.redact(result) if redacted else result,
                          indent=2, ensure_ascii=False)
    except PermissionError as exc:
        return json.dumps({"error": str(exc), "refused": True})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def import_finance(today: str | None = None) -> str:
    """Fan the AR scan out to the existing join points (P30), mirroring import_obligations:
    chase send-by dates for the content calendar and production tasks, deposit and payment due
    dates for deal-resourcing. Read-only; a human confirms before any calendar or chase action."""
    sys.path.insert(0, str(HERE))
    import finance as _fin  # type: ignore
    from datetime import date as _date
    try:
        t = _date.fromisoformat(today) if today else None
        scan = _fin.ar_scan(None, t)
        return json.dumps({
            "as_of": scan["as_of"],
            "join_points": {
                "calendar_chase_dates": [
                    {"invoice_id": r["invoice_id"], "brand_name": r.get("brand_name"),
                     "chase_send_by": r.get("chase_send_by"), "urgency_band": r.get("urgency_band")}
                    for r in scan["action_queue"]
                ],
                "production_payment_dates": [
                    {"invoice_id": r["invoice_id"], "payment_due_date": r.get("payment_due_date")}
                    for bucket in scan["buckets"].values() for r in bucket
                ],
                "disputed_for_review": scan["disputed"],
            },
            "total_outstanding": scan["total_outstanding"],
            "computed_by": scan["computed_by"],
            "human_review_required": True,
            "note": "Deterministic AR view from tools/finance.py; map chase dates onto content-calendar and production-task. A human confirms before any chase or calendar action; nothing is sent.",
        }, indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def contact_lookup(query: str, person: str | None = None, redacted: bool = False) -> str:
    """Resolve a fuzzy brand phrase to one account and read its contact(s) (P32). Read-only,
    always available. The brand is resolved via the tiered account resolver (exact, alias,
    substring, fuzzy, brand-category); if it does not resolve to ONE account, no contacts are
    read and the resolver candidates are surfaced. A person hint that matches nobody returns a
    gap naming the known contacts, never the wrong person. EXPOSURE NOTE: contacts are real
    names and emails read from pipeline/accounts/*.local.json; the raw result is for the human
    operator on this machine. Pass redacted=True (initials, masked emails) for anything quoted
    off this machine."""
    sys.path.insert(0, str(HERE))
    import accounts as _acct  # type: ignore
    try:
        result = _acct.contacts(query, person=person)
        return json.dumps(_acct.redact(result) if redacted else result,
                          indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def deal_status(query: str | None = None, deal_id: str | None = None,
                redacted: bool = False) -> str:
    """Report a deal's lifecycle status verbatim (P32). Read-only, always available: stage, the
    latest stage_history event, payment_due_date, and the denormalized invoice.status, quoted
    from pipeline/deals/*.local.json. Give a brand phrase (resolved to the account, then its
    deals are listed) or an explicit deal_id. NO money math (aging, penalties, totals are
    finance_scan) and NO stage transition (that is the evidence-gated deal-pipeline flow).
    EXPOSURE NOTE: brand names are real; pass redacted=True for anything quoted off this
    machine."""
    sys.path.insert(0, str(HERE))
    import accounts as _acct  # type: ignore
    try:
        result = _acct.deal_status(query=query, deal_id=deal_id)
        return json.dumps(_acct.redact(result) if redacted else result,
                          indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Task tracker (P35): tasks, scheduling, coverage, shipments, milestones
# ---------------------------------------------------------------------------

@mcp.tool()
def task_scan(register_path: str | None = None, today: str | None = None) -> str:
    """Read-only outstanding-task view (P35): the waiting-on-counterparty vs I-owe split plus due-soon,
    overdue, and status counts, each item cited. Offline, always available. Nothing is sent."""
    sys.path.insert(0, str(HERE))
    import tasks as _t  # type: ignore
    from datetime import date as _date
    try:
        reg = _t.load_register("local_fs", register_path)
        d = _t._ob._parse_date(today) or _date.today()
        return json.dumps(_t.scan(reg, d), indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def task_plan(tasks: list, events: dict | None = None, deadline_task: str | None = None,
              deadline: str | None = None) -> str:
    """Schedule a project's tasks (P35): forward from trigger events, or, with deadline_task + deadline, a
    backward reverse-plan plus a negative-slack feasibility check. Offline business-day math; unresolved
    triggers are null and flagged, never guessed."""
    sys.path.insert(0, str(HERE))
    import tasks as _t  # type: ignore
    try:
        if deadline_task and deadline:
            return json.dumps(_t.feasibility(tasks, events or {}, deadline_task, deadline), indent=2, ensure_ascii=False)
        return json.dumps(_t.forward_schedule(tasks, events or {}), indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def task_transition(task: dict, to_status: str, by: str = "user:creator", at: str | None = None,
                    note: str | None = None) -> str:
    """Apply one governed task state change (P35) through the single choke point: validates the allowed
    transition, appends the audit event, and re-folds. Illegal transitions are refused, not forced. The
    register write itself is human-confirmed."""
    sys.path.insert(0, str(HERE))
    import tasks as _t  # type: ignore
    from datetime import date as _date
    try:
        return json.dumps(_t.transition(task, to_status, by, at or _date.today().isoformat(), note),
                          indent=2, ensure_ascii=False)
    except ValueError as exc:
        return json.dumps({"error": str(exc), "refused": True})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def task_ics_export(register_path: str | None = None) -> str:
    """Export tracked task due dates (and payment milestones) as a portable RFC 5545 .ics calendar (P35) that
    imports into any calendar app. Skips closed tasks; stable UIDs so re-export updates rather than duplicates."""
    sys.path.insert(0, str(HERE))
    import tasks as _t  # type: ignore
    try:
        reg = _t.load_register("local_fs", register_path)
        return _t.register_to_ics(reg)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def coverage_verify(canonical_or_sources: dict, required_points: list) -> str:
    """Verify a deliverable covered its required points (P35). Pass {"texts": [...]} to reconcile multiple
    transcripts to a canonical truth first, or {"canonical_text": "..."}. Returns per-point verdicts with an
    extractive supporting quote, abstaining when unsure; input conflicts flow into a minority report. Not
    compliance advice."""
    sys.path.insert(0, str(HERE))
    import coverage_verify as _cv  # type: ignore
    try:
        rec = None
        if canonical_or_sources.get("texts"):
            srcs = [{"id": f"src{i}", "text": t} for i, t in enumerate(canonical_or_sources["texts"])]
            rec = _cv.reconcile(srcs)
            canonical = rec.get("canonical_text", "")
        else:
            canonical = canonical_or_sources.get("canonical_text", "")
        return json.dumps(_cv.verify_coverage(canonical, required_points, reconciliation=rec), indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def shipment_track(tracking_number: str | None = None, carrier: str | None = None,
                   provider: str = "easypost", manual: dict | None = None) -> str:
    """Record a product shipment (P35): a live carrier poll (flag-gated, API key from env only) or a manual
    entry, normalized to the canonical status enum, returning the delivered_at planning anchor. No key means
    manual entry, never a guessed status."""
    sys.path.insert(0, str(HERE))
    import shipments as _sh  # type: ignore
    try:
        if manual:
            ship = _sh.manual_shipment(**manual)
            return json.dumps({"shipment": ship, "anchor": _sh.planning_anchor(ship)}, indent=2, ensure_ascii=False)
        res = _sh.fetch(tracking_number, carrier, provider)
        if res.get("shipment"):
            res["anchor"] = _sh.planning_anchor(res["shipment"])
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@mcp.tool()
def milestone_status(schedule: dict, deliverable_id: str | None = None, event: str | None = None) -> str:
    """Payment-milestone billable readiness (P35). With deliverable_id + event, flips the matching milestones
    to billable and returns citation-carrying invoice-draft tasks for the finance lane; otherwise reports
    which milestones are already ready to bill. Nothing is invoiced or sent here."""
    sys.path.insert(0, str(HERE))
    import tasks as _t  # type: ignore
    from datetime import date as _date
    try:
        if deliverable_id and event:
            fired = _t.apply_deliverable_event(schedule, deliverable_id, event, _date.today().isoformat())
            return json.dumps({"newly_billable": fired, "human_review_required": True}, indent=2, ensure_ascii=False)
        return json.dumps(_t.billable_scan(schedule), indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
#
# Transport (P35 cross-surface / cross-AI):
#   default (no args)  -> stdio, for a local Claude Desktop MCP server (claude_desktop_config.json).
#   --serve-remote     -> a remote streamable-HTTP MCP endpoint. Behind an HTTPS reverse proxy with OAuth,
#                         this becomes ONE "custom connector" that works on claude.ai web + mobile AND, since
#                         both vendors speak MCP, ChatGPT (apps/dev-mode) and Gemini (CLI / Agent Platform).
#                         We ship the transport option and this runbook; we do not host a server. Deploy
#                         runbook: docs/TASK-TRACKER.md. The same task tools serve every surface unchanged.

if __name__ == "__main__":
    import argparse as _argparse
    _ap = _argparse.ArgumentParser(description="Creator OS MCP server")
    _ap.add_argument("--serve-remote", action="store_true",
                     help="run as a remote streamable-HTTP MCP endpoint (one connector for web/mobile + other AIs)")
    _ap.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default=None)
    _ap.add_argument("--host", default="127.0.0.1")
    _ap.add_argument("--port", type=int, default=8080)
    _args, _ = _ap.parse_known_args()
    _transport = _args.transport or ("streamable-http" if _args.serve_remote else "stdio")
    if _transport != "stdio":
        try:
            mcp.settings.host = _args.host
            mcp.settings.port = _args.port
        except Exception:  # noqa: BLE001  (older FastMCP: host/port come from env or defaults)
            pass
        mcp.run(transport=_transport)
    else:
        mcp.run()
