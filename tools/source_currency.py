#!/usr/bin/env python3
"""
source_currency.py -- Creator OS source registry staleness tool.

Reads canonical-sources/source-registry.json to report source freshness,
flag stale entries, mark sources as checked, and seed partner entries from
the deal pipeline. Writes to the registry are the only permitted mutations;
all other canonical data is read-only from this tool.

Usage:
  python3 tools/source_currency.py report [--category=<cat>]
  python3 tools/source_currency.py check [--category=<cat>]
  python3 tools/source_currency.py mark-checked <id> [--changed]
  python3 tools/source_currency.py seed-partners
  python3 tools/source_currency.py seed-sources <file.json>

Modes:
  report        Read-only. Prints a staleness report as JSON.
  check         Like report but includes a refetch_queue for web-intel-engine.
  mark-checked  Updates last_checked for a source; --changed also flags content change.
  seed-partners Scans pipeline/deals/ for active deals and upserts partner sites.
  seed-sources  Upserts depth-0 seed source entries from a JSON array file. Skips ids
                that already exist. Used to add new canonical sources without hand-editing.
"""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "canonical-sources" / "source-registry.json"
TRAVERSAL_CONFIG_PATH = ROOT / "canonical-sources" / "traversal-config.json"
DEALS_DIR = ROOT / "pipeline" / "deals"

ACTIVE_DEAL_STAGES = {
    "in-discussion",
    "contract-negotiating",
    "signed",
    "in-production",
    "delivered",
    "invoiced",
}


def load_traversal_config():
    """Load traversal-config.json for interval defaults. Returns empty dict on missing file."""
    if not TRAVERSAL_CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(TRAVERSAL_CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def get_threshold_for_source(source, traversal_config):
    """
    Return staleness threshold in days for a source.
    Priority: traversal-config per_category_overrides > source-registry field > config default > 30.
    """
    category = source.get("category", "")
    overrides = traversal_config.get("per_category_overrides", {})
    if category in overrides:
        cat_override = overrides[category]
        return cat_override.get("staleness_threshold_days", cat_override.get("check_interval_days", 30))
    # Fall back to the source-registry entry's own field, then the config global default
    global_default = traversal_config.get("default_staleness_threshold_days", 30)
    return source.get("staleness_threshold_days", source.get("check_interval_days", global_default))


from registry_io import load_registry, save_registry  # single sanctioned writer (shared)


def today_str():
    return date.today().isoformat()


def days_since(date_str):
    if not date_str:
        return None
    try:
        then = datetime.fromisoformat(date_str).date()
        return (date.today() - then).days
    except ValueError:
        return None


def compute_staleness(sources, category=None, traversal_config=None):
    stale = []
    never_checked = []
    up_to_date = []
    if traversal_config is None:
        traversal_config = {}

    for s in sources:
        if category and s.get("category") != category:
            continue

        last = s.get("last_checked")
        threshold = get_threshold_for_source(s, traversal_config)

        if not last:
            never_checked.append({
                "id": s["id"],
                "name": s["name"],
                "url": s.get("url", ""),
                "category": s.get("category", ""),
                "used_by": s.get("used_by", []),
            })
        else:
            age = days_since(last)
            if age is not None and age > threshold:
                stale.append({
                    "id": s["id"],
                    "name": s["name"],
                    "url": s.get("url", ""),
                    "category": s.get("category", ""),
                    "days_since_checked": age,
                    "days_overdue": age - threshold,
                    "used_by": s.get("used_by", []),
                })
            else:
                up_to_date.append({
                    "id": s["id"],
                    "name": s["name"],
                    "last_checked": last,
                    "category": s.get("category", ""),
                })

    return stale, never_checked, up_to_date


def build_recommended_actions(stale, never_checked):
    actions = []
    for s in never_checked:
        cats = s.get("category", "unknown")
        actions.append(
            f"Never checked [{cats}]: {s['name']} -- run web-intel currency-check"
        )
    for s in sorted(stale, key=lambda x: x.get("days_overdue", 0), reverse=True):
        affected = ", ".join(s.get("used_by", [])) or "no atoms registered"
        actions.append(
            f"{s['days_overdue']}d overdue [{s.get('category', '?')}]: "
            f"{s['name']} -- affects: {affected}"
        )
    return actions


def build_report(sources, category=None, include_refetch=False, traversal_config=None):
    stale, never_checked, up_to_date = compute_staleness(sources, category, traversal_config)
    actions = build_recommended_actions(stale, never_checked)

    report = {
        "as_of": today_str(),
        "summary": {
            "total_sources": len(sources) if not category else len(stale) + len(never_checked) + len(up_to_date),
            "stale": len(stale),
            "never_checked": len(never_checked),
            "up_to_date": len(up_to_date),
        },
        "stale": stale,
        "never_checked": never_checked,
        "up_to_date": up_to_date,
        "recommended_actions": actions,
    }

    if include_refetch:
        refetch_queue = []
        for s in stale + never_checked:
            src = next(
                (x for x in sources if x["id"] == s["id"]), {}
            )
            refetch_queue.append({
                "id": s["id"],
                "name": s["name"],
                "url": s.get("url", ""),
                "tier": src.get("tier", ""),
                "extraction_hint": src.get("extraction_hint", ""),
                "used_by": s.get("used_by", []),
                "action": "source-verify via web-intel-engine currency-check mode",
            })
        report["refetch_queue"] = refetch_queue
        report["web_intel_instruction"] = (
            "For each entry in refetch_queue: call web-intel-engine in currency-check mode "
            "using the url and extraction_hint. After verification, call "
            "'python3 tools/source_currency.py mark-checked <id> [--changed]'."
        )

    return report


def cmd_report(args, registry, traversal_config):
    category = getattr(args, "category", None)
    report = build_report(registry["sources"], category=category, traversal_config=traversal_config)
    print(json.dumps(report, indent=2))


def cmd_check(args, registry, traversal_config):
    category = getattr(args, "category", None)
    report = build_report(registry["sources"], category=category, include_refetch=True, traversal_config=traversal_config)
    print(json.dumps(report, indent=2))


def cmd_mark_checked(args, registry, traversal_config=None):
    source_id = args.id
    changed = getattr(args, "changed", False)

    found = False
    affected = []
    source_name = source_id

    for s in registry["sources"]:
        if s["id"] == source_id:
            s["last_checked"] = today_str()
            source_name = s.get("name", source_id)
            if changed:
                s["last_changed_detected"] = today_str()
                affected = s.get("used_by", [])
            found = True
            break

    if not found:
        print(
            f"ERROR: source id {source_id!r} not found in registry. "
            "Run 'report' to see available ids.",
            file=sys.stderr,
        )
        sys.exit(1)

    save_registry(registry)

    result = {
        "marked_checked": source_id,
        "name": source_name,
        "date": today_str(),
        "content_changed": changed,
    }
    if changed and affected:
        result["affected_atoms_and_engines"] = affected
        result["recommended_action"] = (
            f"Review canonical data for: {', '.join(affected)}. "
            "Update the relevant file in canonical-sources/ if spec or rate data changed."
        )
    elif changed:
        result["note"] = "Changed flagged but no used_by registered for this source."

    print(json.dumps(result, indent=2))


def cmd_seed_sources(args, registry, traversal_config=None):
    """
    Upsert depth-0 seed source entries from a JSON file.
    Input file must be a JSON array of source objects conforming to the source-registry schema.
    Required fields per entry: id, name, url, category, tier. All others optional (get defaults).
    Adds entries whose id does not already exist. For an id that already exists, does not clobber
    its url/category/tier/intervals; it only unions any new used_by references into the existing
    entry (so a source can be shared by more atoms without a second registry writer).
    """
    seeds_path = Path(args.file)
    if not seeds_path.exists():
        print(f"ERROR: seeds file not found: {seeds_path}", file=sys.stderr)
        sys.exit(1)

    try:
        new_entries = json.loads(seeds_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: could not parse seeds file: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(new_entries, list):
        print("ERROR: seeds file must be a JSON array of source objects.", file=sys.stderr)
        sys.exit(1)

    existing_ids = {s["id"] for s in registry["sources"]}
    id_to_entry = {s["id"]: s for s in registry["sources"]}
    upserted = []
    skipped = []
    used_by_extended = []

    for entry in new_entries:
        if not all(k in entry for k in ("id", "name", "url", "category", "tier")):
            print(
                f"WARNING: skipping entry missing required fields: {entry.get('id', '<no id>')}",
                file=sys.stderr,
            )
            skipped.append(entry.get("id", "<no id>"))
            continue

        if entry["id"] in existing_ids:
            # Do not clobber an existing entry's url, category, tier, or intervals.
            # Only union in any new used_by references so a source can be shared by
            # additional atoms without a second registry writer. This keeps
            # source_currency.py the sole writer while allowing used_by growth.
            existing = id_to_entry.get(entry["id"])
            incoming_used_by = entry.get("used_by", []) or []
            if existing is not None and incoming_used_by:
                current = existing.get("used_by", []) or []
                added = [u for u in incoming_used_by if u not in current]
                if added:
                    existing["used_by"] = current + added
                    used_by_extended.append(entry["id"])
                else:
                    skipped.append(entry["id"])
            else:
                skipped.append(entry["id"])
            continue

        category = entry["category"]
        overrides = (traversal_config or {}).get("per_category_overrides", {}).get(category, {})
        check_days = overrides.get("check_interval_days", entry.get("check_interval_days", 14))
        stale_days = overrides.get("staleness_threshold_days", entry.get("staleness_threshold_days", check_days))

        seeded = {
            "id": entry["id"],
            "name": entry["name"],
            "url": entry["url"],
            "category": category,
            "tier": entry["tier"],
            "check_interval_days": check_days,
            "staleness_threshold_days": stale_days,
            "last_checked": entry.get("last_checked", None),
            "last_changed_detected": entry.get("last_changed_detected", None),
            "extraction_hint": entry.get("extraction_hint", ""),
            "used_by": entry.get("used_by", []),
            "depth": entry.get("depth", 0),
            "parent_source_id": entry.get("parent_source_id", None),
            "traversal_status": entry.get("traversal_status", "pending"),
            "child_source_ids": entry.get("child_source_ids", []),
        }
        registry["sources"].append(seeded)
        existing_ids.add(entry["id"])
        upserted.append(entry["id"])

    if upserted or used_by_extended:
        registry["last_registry_update"] = today_str()
        save_registry(registry)

    print(json.dumps({
        "upserted": len(upserted),
        "skipped_already_exist": len(skipped),
        "used_by_extended": used_by_extended,
        "new_ids": upserted,
        "skipped_ids": skipped,
    }))


def cmd_seed_partners(args, registry, traversal_config=None):
    if not DEALS_DIR.exists():
        print(json.dumps({
            "upserted": 0,
            "updated": 0,
            "note": "pipeline/deals/ directory not found",
        }))
        return

    existing = {s["id"]: s for s in registry["sources"]}
    upserted = []
    updated = []

    for deal_file in sorted(DEALS_DIR.glob("*.json")):
        try:
            deal = json.loads(deal_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        stage = deal.get("stage", "")
        if stage not in ACTIVE_DEAL_STAGES:
            continue

        url = deal.get("partner_website_url") or deal.get("partner_website")
        if not url:
            continue

        deal_id = deal.get("deal_id") or deal_file.stem
        brand = deal.get("brand_name") or deal_id
        source_id = f"partner-{deal_id}"

        if source_id in existing:
            if existing[source_id].get("url") != url:
                existing[source_id]["url"] = url
                updated.append(source_id)
        else:
            partner_override = (traversal_config or {}).get("per_category_overrides", {}).get("partner-site", {})
            check_days = partner_override.get("check_interval_days", 7)
            stale_days = partner_override.get("staleness_threshold_days", check_days)
            entry = {
                "id": source_id,
                "name": f"{brand} website",
                "url": url,
                "category": "partner-site",
                "tier": "T2",
                "check_interval_days": check_days,
                "staleness_threshold_days": stale_days,
                "last_checked": None,
                "last_changed_detected": None,
                "extraction_hint": (
                    f"Check {brand} for new product launches, active campaigns, "
                    "brand messaging updates, and recent press relevant to home decor, "
                    "DIY, or vintage aesthetics."
                ),
                "used_by": ["pitch-paragraph", "mediakit-section", "web-intel-engine"],
            }
            registry["sources"].append(entry)
            existing[source_id] = entry
            upserted.append(source_id)

    if upserted or updated:
        save_registry(registry)

    print(json.dumps({
        "upserted": len(upserted),
        "updated": len(updated),
        "new_ids": upserted,
        "updated_ids": updated,
    }))


def cmd_update_source(args, registry):
    """Correct fields on an existing source in place (URL fix, recategorization, name/tier, hint,
    used_by union). Intended for corrections that seed-sources cannot make (it never clobbers an
    existing id). Keeps source_currency.py the single hand-driven writer for these edits."""
    sources = registry.get("sources", [])
    entry = next((s for s in sources if s.get("id") == args.id), None)
    if entry is None:
        print(f"[error] source '{args.id}' not found in registry.", file=sys.stderr)
        sys.exit(1)
    changed = []
    for field, val in (("url", args.url), ("category", args.category),
                       ("name", args.name), ("tier", args.tier),
                       ("extraction_hint", args.extraction_hint)):
        if val is not None and entry.get(field) != val:
            entry[field] = val
            changed.append(field)
    if args.add_used_by:
        additions = [u.strip() for u in args.add_used_by.split(",") if u.strip()]
        existing = entry.setdefault("used_by", [])
        for u in additions:
            if u not in existing:
                existing.append(u)
                changed.append(f"used_by+{u}")
    if not changed:
        print(json.dumps({"id": args.id, "changed": [], "note": "no field differed; nothing written"}))
        return
    registry["last_registry_update"] = today_str()
    save_registry(registry)
    print(json.dumps({"id": args.id, "changed": changed, "written": True}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Creator OS source registry staleness tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    p_report = sub.add_parser("report", help="Print staleness report (read-only)")
    p_report.add_argument("--category", help="Filter by category (seo-authority, platform-spec, api-changelog, rate-benchmark, tool-mcp, partner-site)")

    p_check = sub.add_parser("check", help="Report + include refetch queue for web-intel-engine")
    p_check.add_argument("--category", help="Filter by category")

    p_mark = sub.add_parser("mark-checked", help="Mark a source as checked today")
    p_mark.add_argument("id", help="Source id (from source-registry.json)")
    p_mark.add_argument("--changed", action="store_true", help="Flag that content changed; emits affected atom list")

    sub.add_parser("seed-partners", help="Upsert partner sites from pipeline/deals/ active records")

    p_seed = sub.add_parser("seed-sources", help="Upsert depth-0 seed sources from a JSON file")
    p_seed.add_argument("file", help="Path to JSON file containing array of source objects")

    p_rm = sub.add_parser("remove-source", help="Remove a source entry by ID")
    p_rm.add_argument("id", help="Source id to remove from the registry")

    p_upd = sub.add_parser("update-source", help="Correct fields on an existing source (url, category, name, tier)")
    p_upd.add_argument("id", help="Source id to update")
    p_upd.add_argument("--url", help="Corrected URL")
    p_upd.add_argument("--category", help="Corrected category")
    p_upd.add_argument("--name", help="Corrected human-readable name")
    p_upd.add_argument("--tier", help="Corrected tier (T1|T2|T3)")
    p_upd.add_argument("--extraction-hint", dest="extraction_hint", help="Corrected extraction hint")
    p_upd.add_argument("--add-used-by", dest="add_used_by", help="Comma-separated atoms/engines to union into used_by")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    registry = load_registry()
    traversal_config = load_traversal_config()

    if args.command == "report":
        cmd_report(args, registry, traversal_config)
    elif args.command == "check":
        cmd_check(args, registry, traversal_config)
    elif args.command == "mark-checked":
        cmd_mark_checked(args, registry, traversal_config)
    elif args.command == "seed-partners":
        cmd_seed_partners(args, registry, traversal_config)
    elif args.command == "seed-sources":
        cmd_seed_sources(args, registry, traversal_config)
    elif args.command == "remove-source":
        sources = registry.get("sources", [])
        before = len(sources)
        registry["sources"] = [s for s in sources if s.get("id") != args.id]
        after = len(registry["sources"])
        if before == after:
            print(f"[warn] source '{args.id}' not found in registry.")
        else:
            registry["last_registry_update"] = today_str()
            save_registry(registry)
            print(f"[ok] removed source '{args.id}' from registry.")
    elif args.command == "update-source":
        cmd_update_source(args, registry)


if __name__ == "__main__":
    main()
