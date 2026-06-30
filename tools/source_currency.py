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

Modes:
  report        Read-only. Prints a staleness report as JSON.
  check         Like report but includes a refetch_queue for web-intel-engine.
  mark-checked  Updates last_checked for a source; --changed also flags content change.
  seed-partners Scans pipeline/deals/ for active deals and upserts partner sites.
"""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "canonical-sources" / "source-registry.json"
DEALS_DIR = ROOT / "pipeline" / "deals"

ACTIVE_DEAL_STAGES = {
    "in-discussion",
    "contract-negotiating",
    "signed",
    "in-production",
    "delivered",
    "invoiced",
}


def load_registry():
    if not REGISTRY_PATH.exists():
        return {"sources": []}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def save_registry(data):
    REGISTRY_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


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


def compute_staleness(sources, category=None):
    stale = []
    never_checked = []
    up_to_date = []

    for s in sources:
        if category and s.get("category") != category:
            continue

        last = s.get("last_checked")
        threshold = s.get("staleness_threshold_days", s.get("check_interval_days", 30))

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


def build_report(sources, category=None, include_refetch=False):
    stale, never_checked, up_to_date = compute_staleness(sources, category)
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


def cmd_report(args, registry):
    category = getattr(args, "category", None)
    report = build_report(registry["sources"], category=category)
    print(json.dumps(report, indent=2))


def cmd_check(args, registry):
    category = getattr(args, "category", None)
    report = build_report(registry["sources"], category=category, include_refetch=True)
    print(json.dumps(report, indent=2))


def cmd_mark_checked(args, registry):
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


def cmd_seed_partners(args, registry):
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
            entry = {
                "id": source_id,
                "name": f"{brand} website",
                "url": url,
                "category": "partner-site",
                "tier": "T2",
                "check_interval_days": 7,
                "staleness_threshold_days": 14,
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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    registry = load_registry()

    if args.command == "report":
        cmd_report(args, registry)
    elif args.command == "check":
        cmd_check(args, registry)
    elif args.command == "mark-checked":
        cmd_mark_checked(args, registry)
    elif args.command == "seed-partners":
        cmd_seed_partners(args, registry)


if __name__ == "__main__":
    main()
