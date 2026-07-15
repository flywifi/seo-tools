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
import freshness_overlay as _fo  # P36: per-user overlay; runtime writes here, never the repo registry
from fetch_diag import classify_block  # P49 WS9: tell a bot-block apart from a genuinely-gone page


def is_currently_blocked(source):
    """True when the most recent signal on this source is a bot-block, not a successful check.
    P49 WS9: a blocked-but-valid source must NOT be aged into stale/SLA-error on last_checked math.
    A source is 'currently blocked' when last_block_detected is set and is at least as recent as
    last_checked (a later successful check clears the block)."""
    lbd = source.get("last_block_detected")
    if not lbd:
        return False
    last = source.get("last_checked")
    if not last:
        return True
    try:
        # A successful check on/after the block clears it (>, so a same-day check counts as recovered).
        return datetime.fromisoformat(lbd).date() > datetime.fromisoformat(last).date()
    except ValueError:
        return True


def blocked_sources(sources, category=None):
    """The currently-blocked sources, shaped for the report. Each is inconclusive (not gone/stale)
    and carries a human-verification hint (P49 WS9)."""
    out = []
    for s in sources:
        if category and s.get("category") != category:
            continue
        if not is_currently_blocked(s):
            continue
        out.append({
            "id": s["id"], "name": s["name"], "url": s.get("url", ""),
            "category": s.get("category", ""),
            "block_kind": s.get("block_kind"), "block_vendor": s.get("block_vendor"),
            "last_block_detected": s.get("last_block_detected"),
            "last_verified": s.get("last_checked"),
            "used_by": s.get("used_by", []),
            "note": "the automated fetch was blocked (not gone); open the URL in a browser and paste "
                    "the text, or run 'python3 tools/fetch_resilient.py <url>' to retry. See "
                    "docs/PASTE-SAFETY.md.",
        })
    return out


def _apply_overlay_if_any(registry, overlay_path):
    """When an --overlay path is given, union-merge the user's freshness overlay onto the read-only
    baseline sources and return (sources, overlay). Otherwise return the baseline sources as-is."""
    if not overlay_path:
        return registry.get("sources", []), None
    overlay = _fo.load_overlay(overlay_path)
    return _fo.apply_overlay(registry.get("sources", []), overlay), overlay


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
        if is_currently_blocked(s):
            continue  # P49 WS9: a blocked source is inconclusive, never stale/never-checked

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
    blocked = blocked_sources(sources, category)  # P49 WS9: inconclusive, not stale
    actions = build_recommended_actions(stale, never_checked)

    report = {
        "as_of": today_str(),
        "summary": {
            "total_sources": len(sources) if not category else
                             len(stale) + len(never_checked) + len(up_to_date) + len(blocked),
            "stale": len(stale),
            "never_checked": len(never_checked),
            "up_to_date": len(up_to_date),
            "blocked": len(blocked),
        },
        "stale": stale,
        "never_checked": never_checked,
        "up_to_date": up_to_date,
        "blocked": blocked,
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


def _sla_counts(sources, traversal_config):
    """Two-tier freshness SLA (dbt warn_after/error_after) over the sources: ok/warn/error counts,
    using the per-source threshold as warn_after and 3x as error_after (a stale source becomes an
    error once it is badly overdue). Read-only."""
    counts = {"ok": 0, "warn": 0, "error": 0, "blocked": 0}
    for s in sources:
        if is_currently_blocked(s):
            counts["blocked"] += 1  # P49 WS9: excluded from ok/warn/error; a block is not an SLA miss
            continue
        warn_after = get_threshold_for_source(s, traversal_config or {})
        error_after = warn_after * 3 if warn_after else None
        age = days_since(s.get("last_checked"))
        counts[_fo.sla_status(age, warn_after, error_after)] += 1
    return counts


def cmd_report(args, registry, traversal_config):
    category = getattr(args, "category", None)
    sources, _ = _apply_overlay_if_any(registry, getattr(args, "overlay", None))
    report = build_report(sources, category=category, traversal_config=traversal_config)
    report["sla"] = _sla_counts(sources if not category else
                                [s for s in sources if s.get("category") == category], traversal_config)
    print(json.dumps(report, indent=2))


def cmd_check(args, registry, traversal_config):
    category = getattr(args, "category", None)
    sources, _ = _apply_overlay_if_any(registry, getattr(args, "overlay", None))
    report = build_report(sources, category=category, include_refetch=True, traversal_config=traversal_config)
    report["sla"] = _sla_counts(sources if not category else
                                [s for s in sources if s.get("category") == category], traversal_config)
    print(json.dumps(report, indent=2))


def cmd_dashboard(args, registry, traversal_config):
    """Render the personal Currency Dashboard (a single local view; never sent, pushed, or shared).
    With --out, write it to the user's store path; otherwise print it."""
    sources, _ = _apply_overlay_if_any(registry, getattr(args, "overlay", None))
    report = build_report(sources, category=getattr(args, "category", None), traversal_config=traversal_config)
    md = _fo.dashboard_markdown(report)
    out = getattr(args, "out", None)
    if out:
        Path(out).write_text(md + "\n", encoding="utf-8")
        print(json.dumps({"written": out, "as_of": report["as_of"],
                          "boundary": "local view only; nothing sent or pushed"}))
    else:
        print(md)


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
                    "_why", "_static", "_no_upstream", "source_ids", "_license",
                    "content_selector", "_signal"):
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
            # P49 WS9: keep the response headers so a 200-served challenge page can be detected.
            return {"status": r.status, "body": body, "headers": dict(rh.items()),
                    "etag": rh.get("ETag"), "last_modified": rh.get("Last-Modified"),
                    "cache_control": rh.get("Cache-Control"), "error": None}
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return {"status": 304, "body": None, "headers": {}, "etag": etag,
                    "last_modified": last_modified, "cache_control": None, "error": None}
        # P49 WS9: DO NOT discard the error body/headers -- classify_block needs them to tell a
        # bot-block (403/429/challenge) apart from a genuinely-gone page (404/410).
        try:
            err_body = exc.read()
        except Exception:  # noqa: BLE001
            err_body = b""
        try:
            err_headers = dict(exc.headers.items()) if exc.headers else {}
        except Exception:  # noqa: BLE001
            err_headers = {}
        return {"status": exc.code, "body": err_body, "headers": err_headers, "etag": None,
                "last_modified": None, "cache_control": None, "error": f"HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001
        return {"status": None, "body": None, "headers": {}, "etag": None, "last_modified": None,
                "cache_control": None, "error": f"{type(exc).__name__}: {str(exc)[:140]}"}


def _resp_block(resp):
    """Run the anti-bot classifier over a fetch response (P49 WS9). Decodes the body defensively."""
    body = resp.get("body")
    try:
        body_text = body.decode("utf-8", "ignore") if isinstance(body, (bytes, bytearray)) else (body or "")
    except Exception:  # noqa: BLE001
        body_text = ""
    return classify_block(resp.get("status"), resp.get("headers"), body_text)


def classify_content_change(entry, resp):
    """Deterministic change status for one source given a fetch response. Returns
    (status, new_sha) where status is unchanged|first_seen|changed|unreachable|blocked. When the entry
    carries a `content_selector`, only the text inside that region is hashed (nav/ads/timestamps outside
    it do not create false 'changed' events).

    P49 WS9 -- a bot-block is NOT evidence a source is gone or changed:
      * a real anti-bot wall / throttle / CAPTCHA (403/429/challenge), OR a challenge interstitial served
        at HTTP 200, returns 'blocked' and preserves the last-known-good sha (never hashed as 'changed');
      * a genuinely-absent page (404/410) or a transient error/timeout returns 'unreachable';
      * only a 2xx, non-challenge body is hashed for change detection."""
    prior = entry.get("content_sha256")
    status = resp.get("status")
    if status == 304:
        return "unchanged", prior
    body = resp.get("body")
    block = _resp_block(resp)
    if block.get("blocked"):
        # Bot-block or challenge (incl. a 200 interstitial): inconclusive. Keep the prior sha.
        return "blocked", prior
    if status is None or status >= 400 or body is None:
        return "unreachable", None  # genuinely gone (404/410) or transient; do not hash an error body
    new_sha = _fo.content_hash(body, entry.get("content_selector"))
    if not prior:
        return "first_seen", new_sha
    return ("unchanged" if new_sha == prior else "changed"), new_sha


def cmd_detect_changes(args, registry, traversal_config, getter=_http_get_content):
    """Fetch each web-content source, detect change by sha256, and (with --apply) stamp last_checked
    token-free. Changed pages are flagged and queued for the user to interpret. With --overlay PATH,
    stamps are written to the USER'S OWN overlay store (never the repo registry, never GitHub); the
    baseline+overlay are union-merged so prior stamps are honored. RFC 9111 max-age, when present, is
    recorded as a min_recheck_at hint so the origin's own policy can lengthen the re-check cadence."""
    overlay_path = getattr(args, "overlay", None)
    sources, overlay = _apply_overlay_if_any(registry, overlay_path)
    if overlay is None:
        overlay = _fo.empty_overlay()  # not persisted unless overlay_path is set
    detectable = [
        s for s in sources
        if str(s.get("url", "")).startswith("http") and s.get("category") not in NON_WEB_CATEGORIES
        and (not getattr(args, "category", None) or s.get("category") == args.category)
        and (not getattr(args, "only", None) or s.get("id") == args.only)
    ]
    today = today_str()
    buckets = {"unchanged": [], "first_seen": [], "changed": [], "unreachable": [], "blocked": []}
    changed_queue = []
    needs_human_verification = []  # P49 WS9: blocked-but-valid sources awaiting a human/browser check
    stamped = []
    apply = getattr(args, "apply", False)
    for e in detectable:
        resp = getter(e.get("url"), e.get("content_etag"), e.get("content_last_modified"))
        status, new_sha = classify_content_change(e, resp)
        buckets[status].append(e["id"])
        if status == "changed":
            changed_queue.append({
                "id": e["id"], "url": e.get("url"), "used_by": e.get("used_by", []),
                "note": "content changed; review the page and update YOUR OWN copy of the data it feeds",
            })
        if status == "blocked":
            # P49 WS9: never stamp last_checked, never flag changed, never remove. Record a durable
            # block state (so staleness/SLA/orphan math skips it) and offer a human-verification handoff.
            blk = _resp_block(resp)
            needs_human_verification.append({
                "id": e["id"], "url": e.get("url"), "used_by": e.get("used_by", []),
                "block_kind": blk.get("kind"), "block_vendor": blk.get("vendor"),
                "retry_worthwhile": blk.get("retry_worthwhile"),
                "note": "the automated fetch was BLOCKED, not gone. Open the URL in your browser and "
                        "paste the text (or upload a screenshot), or run "
                        "'python3 tools/fetch_resilient.py <url>' to retry with a real browser + Wayback. "
                        "See docs/PASTE-SAFETY.md before pasting into a third-party chat.",
            })
            if apply:
                bf = {"last_block_detected": today, "block_kind": blk.get("kind"),
                      "block_vendor": blk.get("vendor")}
                if overlay_path:
                    _fo.stamp(overlay, e["id"], today, kind="block", **bf)
                else:
                    for k, v in bf.items():
                        e[k] = v
                stamped.append(e["id"])
            continue
        if apply and status in ("unchanged", "first_seen", "changed"):
            fields = {"last_checked": today}
            if new_sha:
                fields["content_sha256"] = new_sha
            if resp.get("etag"):
                fields["content_etag"] = resp["etag"]
            if resp.get("last_modified"):
                fields["content_last_modified"] = resp["last_modified"]
            max_age = _fo.max_age_seconds(resp.get("cache_control"))
            if max_age:
                fields["min_recheck_at"] = (date.today().toordinal() + max_age // 86400)
            if status == "changed":
                fields["last_changed_detected"] = today
            # P49 WS9: a successful check clears any prior block state (source recovered).
            if e.get("last_block_detected"):
                fields.update({"last_block_detected": None, "block_kind": None, "block_vendor": None})
            if overlay_path:
                _fo.stamp(overlay, e["id"], today, kind="detect", **fields)
            else:
                # owner/dev mode (no overlay): stamp the working-copy registry as before
                for k, v in fields.items():
                    e[k] = v
            stamped.append(e["id"])
    if apply and stamped:
        if overlay_path:
            _fo.save_overlay(overlay, overlay_path)
        else:
            registry["last_registry_update"] = today
            save_registry(registry)
    print(json.dumps({
        "as_of": today,
        "computed_by": "tools/source_currency.py.classify_content_change",
        "wrote_to": ("overlay:" + overlay_path) if (apply and overlay_path) else
                    ("registry" if apply else "nothing (read-only)"),
        "summary": {k: len(v) for k, v in buckets.items()},
        "changed_queue": changed_queue,
        "needs_human_verification": needs_human_verification,
        "stamped": stamped if apply else [],
        "note": "unchanged/first_seen stamped token-free; changed entries need interpretation of the diff. "
                "BLOCKED entries are inconclusive (bot-block, not gone): never stamped stale, never flagged "
                "changed; resolve them via the human/browser handoff in needs_human_verification. "
                "With --overlay, all writes go to your own store; nothing touches the repo or GitHub.",
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

    # P49 WS9: a bot-block is inconclusive, never 'changed'/'unreachable-as-gone'.
    ok("403 -> blocked, prior sha preserved (not stale/gone)",
       classify_content_change({"content_sha256": "keepme"},
                               {"status": 403, "body": b"denied", "headers": {}}) == ("blocked", "keepme"))
    ok("200 Cloudflare interstitial -> blocked, NOT changed",
       classify_content_change({"content_sha256": "keepme"},
                               {"status": 200, "body": b"<html>Just a moment...</html>",
                                "headers": {"cf-ray": "abc123"}})[0] == "blocked")
    ok("429 throttle -> blocked",
       classify_content_change({}, {"status": 429, "body": b"slow down", "headers": {}})[0] == "blocked")
    ok("genuine 404 -> unreachable (gone), not blocked",
       classify_content_change({}, {"status": 404, "body": b"Not Found", "headers": {}})[0] == "unreachable")

    # P49 WS9: a currently-blocked source is excluded from staleness (would otherwise be 'stale').
    blocked_src = {"id": "s-blk", "name": "Blocked Co", "url": "https://x.example/z",
                   "category": "seo-authority", "last_checked": "2000-01-01",
                   "last_block_detected": today_str(), "block_kind": "challenge", "used_by": []}
    st, nv, up = compute_staleness([blocked_src])
    ok("blocked source not counted stale", "s-blk" not in [x["id"] for x in st])
    ok("blocked source surfaced in blocked_sources", "s-blk" in [x["id"] for x in blocked_sources([blocked_src])])
    ok("blocked excluded from SLA error", _sla_counts([blocked_src], {})["blocked"] == 1)
    recovered = dict(blocked_src, last_checked=today_str())  # a later check clears the block
    ok("recovered source (last_checked >= block) no longer blocked", not is_currently_blocked(recovered))

    # P49 WS9 apply-path: a 403 records a durable block, does NOT stamp last_checked, and asks for a human.
    class BArgs:
        category = None
        only = None
        apply = True
        overlay = None
    breg = {"sources": [{"id": "b1", "url": "https://x.example/blocked", "category": "seo-authority",
                         "content_sha256": "orig", "used_by": ["trend-check"]}]}

    def blocking_getter(url, etag=None, last_modified=None):
        return {"status": 403, "body": b"<html>cf-error</html>",
                "headers": {"cf-ray": "z"}, "etag": None, "last_modified": None, "error": None}

    def ok_getter(url, etag=None, last_modified=None):
        return {"status": 200, "body": b"real content now", "headers": {}, "etag": None,
                "last_modified": None, "error": None}
    import io as _io2
    import contextlib as _cl2
    # apply=True triggers save_registry() on the working-copy registry; neutralize it so the test's
    # fake registry never touches the real canonical-sources/source-registry.json file.
    _saved_writer = globals().get("save_registry")
    globals()["save_registry"] = lambda *a, **k: None
    try:
        b2 = _io2.StringIO()
        with _cl2.redirect_stdout(b2):
            cmd_detect_changes(BArgs(), breg, {}, getter=blocking_getter)
        bout = json.loads(b2.getvalue())
        e_b1 = breg["sources"][0]
        ok("blocked apply records last_block_detected", e_b1.get("last_block_detected") == today_str())
        ok("blocked apply does NOT stamp last_checked", "last_checked" not in e_b1)
        ok("blocked apply preserves prior content sha", e_b1.get("content_sha256") == "orig")
        ok("blocked surfaced for human verification", "b1" in [q["id"] for q in bout["needs_human_verification"]])
        ok("blocked not in changed_queue", "b1" not in [q["id"] for q in bout["changed_queue"]])

        b3 = _io2.StringIO()
        with _cl2.redirect_stdout(b3):
            cmd_detect_changes(BArgs(), breg, {}, getter=ok_getter)
        ok("recovery clears the block state", e_b1.get("last_block_detected") is None)
        ok("recovery stamps last_checked", e_b1.get("last_checked") == today_str())
    finally:
        globals()["save_registry"] = _saved_writer

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
    p_report.add_argument("--overlay", metavar="PATH", help="Union-merge your personal freshness overlay onto the read-only baseline")

    p_check = sub.add_parser("check", help="Report + include refetch queue for web-intel-engine")
    p_check.add_argument("--category", help="Filter by category")
    p_check.add_argument("--overlay", metavar="PATH", help="Your personal freshness overlay (read + write target for --apply)")
    p_check.add_argument("--detect-changes", dest="detect_changes", action="store_true",
                         help="Token-free: conditional-GET + sha256 per web source; unchanged stamped, changed queued")
    p_check.add_argument("--apply", action="store_true",
                         help="(with --detect-changes) stamp freshness; writes to --overlay if given, else the working-copy registry")
    p_check.add_argument("--only", metavar="ID", help="Restrict --detect-changes to one source id")

    p_dash = sub.add_parser("dashboard", help="Render your personal Currency Dashboard (local view; never sent)")
    p_dash.add_argument("--category", help="Filter by category")
    p_dash.add_argument("--overlay", metavar="PATH", help="Your personal freshness overlay")
    p_dash.add_argument("--out", metavar="PATH", help="Write the dashboard markdown to your store (default: print)")

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
    elif args.command == "dashboard":
        cmd_dashboard(args, registry, traversal_config)
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
