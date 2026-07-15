#!/usr/bin/env python3
"""
tools/traversal_engine.py

Recursive citation-graph traversal engine for Creator OS.
Walks seed sources in canonical-sources/source-registry.json,
extracts outlinks that pass the authority filter, and proposes
candidate new sources for operator approval. No source is ever
auto-added to the registry -- every candidate requires explicit
--accept confirmation.

Reads intervals and configuration from
canonical-sources/traversal-config.json (default: weekly).

IMPORTANT: This tool does not make HTTP requests directly. It
outputs instructions for what to fetch via web-intel-engine,
and reads operator-provided retrieval results from stdin or a
file. The actual fetching follows web-intel-engine.md conventions.

Usage:
  python3 tools/traversal_engine.py --traverse --source=<id> [--depth=<n>] [--force]
  python3 tools/traversal_engine.py --traverse-all [--depth=<n>] [--category=<cat>] [--force]
  python3 tools/traversal_engine.py --set-interval --category=<cat> <days>
  python3 tools/traversal_engine.py --accept <candidate-url> [--id=<custom-id>] [--category=<cat>] [--tier=<tier>]
  python3 tools/traversal_engine.py --prune-orphans
"""

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_FILE = ROOT / "canonical-sources" / "source-registry.json"
CONFIG_FILE = ROOT / "canonical-sources" / "traversal-config.json"
CANDIDATES_FILE = ROOT / "traversal-candidates.json"
VISITED_FILE = ROOT / "traversal-visited.json"

# Categories that are NOT web pages with followable outlinks: competitor pages (snapshotted
# offline by competitor_snapshot.py) and dependency/MCP-server entries (version-checked by
# dependency_currency.py against PyPI/GitHub, never crawled). traverse-all skips these so it
# never emits a link-crawl instruction for a PyPI or releases page.
NON_TRAVERSABLE_CATEGORIES = {"competitor-page", "software-dependency", "mcp-server"}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_config() -> dict:
    raw = load_json(CONFIG_FILE)
    return raw


# The registry has one write implementation, shared with source_currency.py, so both sanctioned
# writers (source_currency.py and this file's `accept`) produce byte-identical output.
from registry_io import load_registry, save_registry  # noqa: E402


def get_interval(config: dict, category: str, field: str) -> int:
    overrides = config.get("per_category_overrides", {})
    if category in overrides and field in overrides[category]:
        return overrides[category][field]
    if field == "check_interval_days":
        return config.get("default_traversal_interval_days", 7)
    if field == "staleness_threshold_days":
        return config.get("default_staleness_threshold_days", 7)
    if field == "traversal_depth":
        return config.get("default_traversal_depth", 2)
    return 7


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    # Strip UTM and tracking parameters
    query = "&".join(
        p for p in (parsed.query or "").split("&")
        if not p.startswith(("utm_", "ref=", "source=", "fbclid=", "gclid="))
    )
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower().rstrip("/"),
        path=parsed.path.rstrip("/") or "/",
        query=query,
        fragment=""
    )
    return urlunparse(normalized)


def is_authority_domain(url: str, allowlist: list) -> bool:
    try:
        domain = urlparse(url).netloc.lower()
        for allowed in allowlist:
            if domain == allowed or domain.endswith("." + allowed):
                return True
    except Exception:
        pass
    return False


def score_niche_relevance(surrounding_context: str, niche_terms: list) -> int:
    if not surrounding_context:
        return 0
    context_lower = surrounding_context.lower()
    score = sum(1 for term in niche_terms if term.lower() in context_lower)
    return min(score, 5)


def load_visited() -> set:
    data = load_json(VISITED_FILE)
    return set(data.get("visited", []))


def save_visited(visited: set) -> None:
    save_json(VISITED_FILE, {"visited": sorted(visited), "last_updated": date.today().isoformat()})


def load_candidates() -> list:
    data = load_json(CANDIDATES_FILE)
    return data.get("candidates", [])


def save_candidates(candidates: list) -> None:
    save_json(CANDIDATES_FILE, {
        "as_of": date.today().isoformat(),
        "_comment": "Proposed new sources from traversal. Review each entry and run --accept <url> to add to registry. Run --prune-orphans to see sources eligible for removal.",
        "candidates": candidates
    })


def source_is_due(source: dict, config: dict, force: bool) -> bool:
    if force:
        return True
    last_checked = source.get("last_checked")
    if not last_checked:
        return True
    category = source.get("category", "")
    interval = get_interval(config, category, "check_interval_days")
    try:
        last_date = date.fromisoformat(last_checked)
        return (date.today() - last_date).days >= interval
    except ValueError:
        return True


def infer_category(url: str, context: str) -> str:
    url_lower = url.lower()
    context_lower = (context or "").lower()
    if any(x in url_lower for x in ["api", "changelog", "revision", "release-notes"]):
        return "api-changelog"
    if any(x in url_lower for x in ["specs", "formats", "help", "support", "creator-portal"]):
        return "platform-spec"
    if any(x in url_lower for x in ["blog", "seo", "algorithm", "search", "ranking"]):
        return "seo-authority"
    if any(x in url_lower for x in ["benchmark", "report", "rate", "salary", "pricing"]):
        return "rate-benchmark"
    if any(x in url_lower for x in ["mcp", "claude", "anthropic", "openai", "model"]):
        return "tool-mcp"
    if any(x in context_lower for x in ["decor", "diy", "interior", "vintage", "thrift"]):
        return "niche-authority"
    return "seo-authority"


def cmd_traverse(args, registry: dict, config: dict) -> None:
    """Emit traversal instructions for one source or all sources."""
    sources = registry.get("sources", [])
    visited = load_visited()
    existing_urls = {normalize_url(s["url"]) for s in sources}
    existing_ids = {s["id"] for s in sources}
    allowlist = config.get("authority_domain_allowlist", [])
    niche_terms = config.get("niche_relevance_terms", [])
    depth_limit = min(
        args.depth if args.depth else config.get("default_traversal_depth", 2),
        config.get("traversal_max_depth", 2)
    )

    if args.source:
        targets = [s for s in sources if s.get("id") == args.source]
        if not targets:
            print(f"ERROR: source id '{args.source}' not found in registry.", file=sys.stderr)
            sys.exit(1)
    else:
        category_filter = getattr(args, "category", None)
        targets = [
            s for s in sources
            if s.get("depth", 0) == 0
            and s.get("category") not in NON_TRAVERSABLE_CATEGORIES
            and (not category_filter or s.get("category") == category_filter)
        ]

    due_targets = [s for s in targets if source_is_due(s, config, getattr(args, "force", False))]

    if not due_targets:
        print(json.dumps({
            "status": "all_current",
            "message": f"All {len(targets)} targeted sources were checked within their configured intervals. Run with --force to override.",
            "next_check_by": min(
                (s.get("last_checked", "never") for s in targets), default="unknown"
            )
        }, indent=2))
        return

    instructions = []
    for source in due_targets:
        source_depth = source.get("depth", 0)
        if source_depth >= depth_limit:
            continue
        instructions.append({
            "source_id": source["id"],
            "source_name": source["name"],
            "url": source["url"],
            "current_depth": source_depth,
            "traverse_to_depth": depth_limit,
            "extraction_hint": source.get("extraction_hint", ""),
            "web_intel_instruction": (
                f"Fetch {source['url']} using web-intel-engine Level 3 (polite HTTP crawl, "
                f"respect robots.txt). Extract: (1) all outlinks in the page body (not nav/footer), "
                f"(2) the surrounding 100 characters of text for each outlink, "
                f"(3) a change summary compared to the extraction_hint. "
                f"Return the outlinks as a JSON list of {{url, surrounding_context}}. "
                f"If robots.txt disallows crawl, set traversal_status=blocked and record retrieval gap."
            ),
            "authority_filter": f"Keep only outlinks whose domain is in the authority allowlist: {allowlist[:5]}... (full list in traversal-config.json)",
            "already_indexed_urls": list(existing_urls)[:5]  # truncated for readability
        })

    print(json.dumps({
        "as_of": date.today().isoformat(),
        "status": "traversal_instructions_ready",
        "sources_due": len(due_targets),
        "sources_skipped_current": len(targets) - len(due_targets),
        "depth_limit": depth_limit,
        "instructions": instructions,
        "next_steps": [
            "1. Run each web_intel_instruction through web-intel-engine to retrieve outlinks.",
            "2. For each outlink: check domain is in authority allowlist, URL not already in registry, niche_relevance_score >= 2.",
            "3. Call: python3 tools/traversal_engine.py --accept <url> [--id=<id>] [--category=<cat>] [--tier=<tier>]",
            "4. Call: python3 tools/source_currency.py --mark-checked <source_id> [--changed] for each source processed."
        ]
    }, indent=2))


def cmd_set_interval(args, config: dict) -> None:
    """Update a category's check interval in traversal-config.json."""
    category = args.category
    if not args.days or not args.days.isdigit():
        print("ERROR: provide a positive integer number of days.", file=sys.stderr)
        sys.exit(1)
    days = int(args.days)
    if days < 1:
        print("ERROR: interval must be at least 1 day.", file=sys.stderr)
        sys.exit(1)

    if "per_category_overrides" not in config:
        config["per_category_overrides"] = {}
    if category not in config["per_category_overrides"]:
        config["per_category_overrides"][category] = {}
    config["per_category_overrides"][category]["check_interval_days"] = days
    config["per_category_overrides"][category]["staleness_threshold_days"] = days
    save_json(CONFIG_FILE, config)
    print(json.dumps({
        "status": "updated",
        "category": category,
        "check_interval_days": days,
        "staleness_threshold_days": days,
        "message": f"Interval for '{category}' set to {days} days. Takes effect on next tool run."
    }, indent=2))


def cmd_accept(args, registry: dict, config: dict) -> None:
    """Operator approves a candidate URL — upsert into source-registry.json."""
    url = args.url
    norm_url = normalize_url(url)
    sources = registry.get("sources", [])
    existing_urls = {normalize_url(s["url"]): s["id"] for s in sources}

    if norm_url in existing_urls:
        print(json.dumps({
            "status": "already_indexed",
            "existing_id": existing_urls[norm_url],
            "url": url
        }, indent=2))
        return

    # Find parent source from candidates file
    candidates = load_candidates()
    matched_candidate = next(
        (c for c in candidates if normalize_url(c.get("url", "")) == norm_url), None
    )

    custom_id = getattr(args, "id", None)
    if not custom_id:
        # Generate an id from the domain + path slug
        parsed = urlparse(url)
        slug = re.sub(r"[^a-z0-9]+", "-", (parsed.netloc + parsed.path).lower()).strip("-")
        custom_id = slug[:60]

    category = getattr(args, "category", None)
    if not category:
        category = matched_candidate.get("category") if matched_candidate else infer_category(url, "")

    tier = getattr(args, "tier", None) or (matched_candidate.get("tier") if matched_candidate else "T2")
    parent_id = matched_candidate.get("parent_source_id") if matched_candidate else None
    depth = (matched_candidate.get("depth_would_be") if matched_candidate else 1) or 1
    check_interval = get_interval(config, category, "check_interval_days")
    staleness = get_interval(config, category, "staleness_threshold_days")

    new_entry = {
        "id": custom_id,
        "name": getattr(args, "name", None) or url,
        "url": url,
        "category": category,
        "tier": tier,
        "check_interval_days": check_interval,
        "staleness_threshold_days": staleness,
        "last_checked": None,
        "last_changed_detected": None,
        "extraction_hint": matched_candidate.get("extraction_hint", "Set extraction_hint after first review.") if matched_candidate else "Set extraction_hint after first review.",
        "used_by": [],
        "depth": depth,
        "parent_source_id": parent_id,
        "traversal_status": "pending",
        "child_source_ids": []
    }

    # Update parent's child_source_ids if parent exists
    if parent_id:
        for source in sources:
            if source.get("id") == parent_id:
                if "child_source_ids" not in source:
                    source["child_source_ids"] = []
                if custom_id not in source["child_source_ids"]:
                    source["child_source_ids"].append(custom_id)
                source["traversal_status"] = "complete"
                break

    sources.append(new_entry)
    registry["sources"] = sources
    registry["last_registry_update"] = date.today().isoformat()
    save_registry(registry)

    # Update visited set
    visited = load_visited()
    visited.add(norm_url)
    save_visited(visited)

    print(json.dumps({
        "status": "accepted",
        "id": custom_id,
        "url": url,
        "category": category,
        "tier": tier,
        "depth": depth,
        "parent_source_id": parent_id,
        "next_steps": [
            f"python3 tools/source_currency.py --mark-checked {custom_id}",
            "Edit 'name' and 'extraction_hint' in source-registry.json for this entry (the only manual edit permitted after --accept).",
            "Add this source to the 'used_by' list of any atoms or engines that depend on it."
        ]
    }, indent=2))


def cmd_prune_orphans(registry: dict, config: dict) -> None:
    """Report sources eligible for removal."""
    sources = registry.get("sources", [])
    orphan_candidates = []
    today = date.today()

    for source in sources:
        used_by = source.get("used_by", [])
        traversal_status = source.get("traversal_status", "pending")
        last_checked = source.get("last_checked")
        days_since_check = None

        if last_checked:
            try:
                days_since_check = (today - date.fromisoformat(last_checked)).days
            except ValueError:
                pass

        # P49 WS9: a blocked source (robots/bot-block) is inconclusive, not gone -- it must NOT be
        # orphan-eligible just because the crawler could not verify it. Only deliberately-skipped,
        # unused, long-unchecked sources are orphan candidates; a durable fetch-block also protects it.
        is_orphan = (
            not used_by
            and traversal_status == "skipped"
            and not source.get("last_block_detected")
            and (days_since_check is None or days_since_check > 180)
        )

        if is_orphan:
            orphan_candidates.append({
                "id": source["id"],
                "name": source["name"],
                "url": source["url"],
                "category": source.get("category"),
                "tier": source.get("tier"),
                "depth": source.get("depth", 0),
                "used_by": used_by,
                "traversal_status": traversal_status,
                "last_checked": last_checked,
                "days_since_check": days_since_check,
                "reason": "no used_by entries, traversal deliberately skipped (not blocked), checked more than 180 days ago"
            })

    print(json.dumps({
        "as_of": today.isoformat(),
        "total_sources": len(sources),
        "orphan_candidates": len(orphan_candidates),
        "orphans": orphan_candidates,
        "note": "These sources are candidates for removal. No source is auto-removed. Review and delete manually from source-registry.json if confirmed unnecessary.",
        "recommended_action": "For each orphan: either (a) add to used_by of an atom that should depend on it, (b) delete the entry manually, or (c) run --traverse to retry."
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Creator OS source traversal and citation graph tool"
    )
    subparsers = parser.add_subparsers(dest="command")

    # --traverse
    traverse_p = subparsers.add_parser("traverse", help="Emit traversal instructions for one or all sources")
    traverse_p.add_argument("--source", help="Source id to traverse (omit for --traverse-all behavior)")
    traverse_p.add_argument("--depth", type=int, help="Max traversal depth (default from config)")
    traverse_p.add_argument("--category", help="Filter sources by category (with --traverse-all)")
    traverse_p.add_argument("--force", action="store_true", help="Ignore interval check, always emit instructions")

    # --traverse-all (alias: same as traverse without --source)
    traverse_all_p = subparsers.add_parser("traverse-all", help="Traverse all depth-0 sources")
    traverse_all_p.add_argument("--depth", type=int)
    traverse_all_p.add_argument("--category")
    traverse_all_p.add_argument("--force", action="store_true")

    # --set-interval
    set_p = subparsers.add_parser("set-interval", help="Set check interval for a category")
    set_p.add_argument("--category", required=True)
    set_p.add_argument("days", nargs="?")

    # --accept
    accept_p = subparsers.add_parser("accept", help="Accept a candidate URL into the registry")
    accept_p.add_argument("url")
    accept_p.add_argument("--id", help="Custom registry id (auto-generated if omitted)")
    accept_p.add_argument("--category", help="Override inferred category")
    accept_p.add_argument("--tier", help="T1, T2, or T3 (default T2)")
    accept_p.add_argument("--name", help="Human-readable name for the entry")

    # --prune-orphans
    subparsers.add_parser("prune-orphans", help="List sources eligible for removal")

    # Support both subcommand style and legacy flag style
    if len(sys.argv) > 1 and sys.argv[1].startswith("--"):
        # Rewrite legacy --traverse, --traverse-all, etc. to subcommands
        sys.argv[1] = sys.argv[1].lstrip("-")

    args = parser.parse_args()

    config = load_config()
    registry = load_registry()

    if args.command in ("traverse", "traverse-all"):
        cmd_traverse(args, registry, config)
    elif args.command == "set-interval":
        cmd_set_interval(args, config)
    elif args.command == "accept":
        cmd_accept(args, registry, config)
    elif args.command == "prune-orphans":
        cmd_prune_orphans(registry, config)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
