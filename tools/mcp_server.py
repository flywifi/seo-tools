#!/usr/bin/env python3
"""Creator OS MCP Server — exposes Python tools to Claude Desktop as MCP tool calls.

Ten tools:
  cache_query        Query the offline FTS5 keyword/entity cache.
  competitor_scan    Return parsed metadata for a stored competitor snapshot.
  source_staleness   Report which canonical sources are stale or never checked.
  drift_check        Run sync_check.py and return the result.
  quality_score      Score an artifact against the 9-dimension quality gates.
  add_competitor     Add a competitor URL to the tracking registry.
  get_capabilities   Return which Creator OS capabilities are enabled.
  get_connectors     Return the full connector evidence plan for this deployment.
  get_stats_tools    Return which statistical MCP servers are currently enabled.
  configure_tool     Enable or disable a capability flag in creator-os-config.local.json.

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
        query: Full-text search query (e.g. "moody fall mantel" or "entity armoire").
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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
