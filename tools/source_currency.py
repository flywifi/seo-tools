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
import hashlib
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "canonical-sources" / "source-registry.json"
TRAVERSAL_CONFIG_PATH = ROOT / "canonical-sources" / "traversal-config.json"
DEALS_DIR = ROOT / "pipeline" / "deals"
CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") or "/root/.ccr/ca-bundle.crt"

# Categories that are not fetchable web pages (checked by dependency_currency.py / competitor
# snapshots instead), so --detect-changes skips them.
NON_WEB_CATEGORIES = {"software-dependency", "mcp-server", "competitor-page"}

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
        # Carry through optional dependency / marker fields when present (P33 schema extension):
        # dependency drift is checked by tools/dependency_currency.py against these fields, and
        # _static / _no_upstream / _why are documentation markers. Absent fields are simply omitted
        # so existing web-content entries are unchanged.
        for opt in ("package", "upstream_api", "check_url", "pinned_constraint",
                    "validated_version", "latest_seen", "latest_seen_date",
                    "_why", "_static", "_no_upstream", "source_ids"):
            if opt in entry:
                seeded[opt] = entry[opt]
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


# ── token-free content-change detection (P33) ────────────────────────────────
# The mundane question "did this source page change since we last looked?" is answered
# deterministically by a conditional GET + sha256 (the tools/fetch_cache.py pattern), with the
# authoritative hash stored on the registry entry so the baseline travels with the repo. Unchanged
# and first-seen pages are stamped last_checked token-free; changed pages are stamped AND flagged
# (last_changed_detected) and surfaced in a queue so the model interprets the diff and updates the
# canonical data file the source feeds. No model tokens are spent on the unchanged majority.

def _http_get_content(url, etag=None, last_modified=None, timeout=12):
    """Conditional GET. Returns {status, body, etag, last_modified, error}. Never raises.
    status 304 => unchanged (no body). Honors the env proxy + CA bundle."""
    ctx = ssl.create_default_context()
    if os.path.exists(CA_BUNDLE):
        try:
            ctx.load_verify_locations(CA_BUNDLE)
        except Exception:  # noqa: BLE001
            pass
    headers = {"User-Agent": "creator-os-source-currency", "Accept": "*/*"}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            body = r.read()
            rh = r.headers
            return {"status": r.status, "body": body,
                    "etag": rh.get("ETag"), "last_modified": rh.get("Last-Modified"), "error": None}
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return {"status": 304, "body": None, "etag": etag, "last_modified": last_modified, "error": None}
        return {"status": exc.code, "body": None, "etag": None, "last_modified": None,
                "error": f"HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001
        return {"status": None, "body": None, "etag": None, "last_modified": None,
                "error": f"{type(exc).__name__}: {str(exc)[:140]}"}


def classify_content_change(entry, resp):
    """Deterministic change status for one source given a fetch response. Returns
    (status, new_sha) where status is unchanged|first_seen|changed|unreachable."""
    prior = entry.get("content_sha256")
    if resp.get("status") == 304:
        return "unchanged", prior
    body = resp.get("body")
    if body is None:
        return "unreachable", None
    new_sha = hashlib.sha256(body).hexdigest()
    if not prior:
        return "first_seen", new_sha
    return ("unchanged" if new_sha == prior else "changed"), new_sha


def cmd_detect_changes(args, registry, traversal_config, getter=_http_get_content):
    """Fetch each web-content source, detect change by sha256, and (with --apply) stamp
    last_checked token-free. Changed pages are flagged and queued for model interpretation."""
    sources = registry.get("sources", [])
    detectable = [
        s for s in sources
        if str(s.get("url", "")).startswith("http") and s.get("category") not in NON_WEB_CATEGORIES
        and (not getattr(args, "category", None) or s.get("category") == args.category)
        and (not getattr(args, "only", None) or s.get("id") == args.only)
    ]
    today = today_str()
    buckets = {"unchanged": [], "first_seen": [], "changed": [], "unreachable": []}
    changed_queue = []
    stamped = []
    for e in detectable:
        resp = getter(e.get("url"), e.get("content_etag"), e.get("content_last_modified"))
        status, new_sha = classify_content_change(e, resp)
        buckets[status].append(e["id"])
        if status == "changed":
            changed_queue.append({
                "id": e["id"], "url": e.get("url"), "used_by": e.get("used_by", []),
                "note": "content changed; review the page and update the canonical data it feeds",
            })
        if getattr(args, "apply", False) and status in ("unchanged", "first_seen", "changed"):
            e["last_checked"] = today
            if new_sha:
                e["content_sha256"] = new_sha
            if resp.get("etag"):
                e["content_etag"] = resp["etag"]
            if resp.get("last_modified"):
                e["content_last_modified"] = resp["last_modified"]
            if status == "changed":
                e["last_changed_detected"] = today
            stamped.append(e["id"])
    if getattr(args, "apply", False) and stamped:
        registry["last_registry_update"] = today
        save_registry(registry)
    print(json.dumps({
        "as_of": today,
        "computed_by": "tools/source_currency.py.classify_content_change",
        "summary": {k: len(v) for k, v in buckets.items()},
        "changed_queue": changed_queue,
        "stamped": stamped if getattr(args, "apply", False) else [],
        "note": "unchanged/first_seen stamped token-free; changed entries need model interpretation of the diff",
    }, indent=2, ensure_ascii=False))


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


def selftest_detect():
    """Pure-logic checks for the content-change detector (no network, no real registry write)."""
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    import hashlib as _h
    body = b"hello world"
    sha = _h.sha256(body).hexdigest()
    ok("first_seen when no prior hash",
       classify_content_change({}, {"status": 200, "body": body}) == ("first_seen", sha))
    ok("unchanged when hash matches",
       classify_content_change({"content_sha256": sha}, {"status": 200, "body": body}) == ("unchanged", sha))
    ok("changed when hash differs",
       classify_content_change({"content_sha256": "deadbeef"}, {"status": 200, "body": body})[0] == "changed")
    ok("unchanged on 304",
       classify_content_change({"content_sha256": sha}, {"status": 304, "body": None}) == ("unchanged", sha))
    ok("unreachable when body None and not 304",
       classify_content_change({}, {"status": None, "body": None})[0] == "unreachable")

    # end-to-end with an injected getter and a fake registry; apply=False must not write
    class Args:
        category = None
        only = None
        apply = False
    reg = {"sources": [
        {"id": "s-changed", "url": "https://x.example/a", "category": "seo-authority",
         "content_sha256": "old", "used_by": ["trend-check"]},
        {"id": "s-first", "url": "https://x.example/b", "category": "legal-authority"},
        {"id": "dep-skip", "url": "https://pypi.org/pypi/x/json", "category": "software-dependency"},
    ]}

    def fake_getter(url, etag=None, last_modified=None):
        return {"status": 200, "body": b"NEW-" + url.encode(), "etag": None, "last_modified": None, "error": None}

    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_detect_changes(Args(), reg, {}, getter=fake_getter)
    out = json.loads(buf.getvalue())
    ok("dep category skipped by detect", "dep-skip" not in json.dumps(out["summary"]) or out["summary"]["changed"] >= 1)
    ok("changed source detected", "s-changed" in [q["id"] for q in out["changed_queue"]])
    ok("first_seen counted", out["summary"]["first_seen"] == 1)
    ok("apply=false writes nothing (stamped empty)", out["stamped"] == [])
    ok("dependency entry not fetched (only 2 web sources touched)",
       out["summary"]["changed"] + out["summary"]["first_seen"] + out["summary"]["unchanged"] + out["summary"]["unreachable"] == 2)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


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
    p_check.add_argument("--detect-changes", dest="detect_changes", action="store_true",
                         help="Token-free: conditional-GET + sha256 per web source; unchanged stamped, changed queued")
    p_check.add_argument("--apply", action="store_true",
                         help="(with --detect-changes) stamp last_checked/content_sha256 token-free")
    p_check.add_argument("--only", metavar="ID", help="Restrict --detect-changes to one source id")

    p_mark = sub.add_parser("mark-checked", help="Mark a source as checked today")
    p_mark.add_argument("id", help="Source id (from source-registry.json)")
    p_mark.add_argument("--changed", action="store_true", help="Flag that content changed; emits affected atom list")

    sub.add_parser("seed-partners", help="Upsert partner sites from pipeline/deals/ active records")

    p_seed = sub.add_parser("seed-sources", help="Upsert depth-0 seed sources from a JSON file")
    p_seed.add_argument("file", help="Path to JSON file containing array of source objects")

    p_rm = sub.add_parser("remove-source", help="Remove a source entry by ID")
    p_rm.add_argument("id", help="Source id to remove from the registry")

    sub.add_parser("selftest", help="Run the content-change detector selftest (no network)")

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

    if args.command == "selftest":
        sys.exit(selftest_detect())

    registry = load_registry()
    traversal_config = load_traversal_config()

    if args.command == "report":
        cmd_report(args, registry, traversal_config)
    elif args.command == "check":
        if getattr(args, "detect_changes", False):
            cmd_detect_changes(args, registry, traversal_config)
        else:
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
