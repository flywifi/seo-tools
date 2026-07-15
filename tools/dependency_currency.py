#!/usr/bin/env python3
"""dependency_currency.py -- token-free version-drift checker for Creator OS dependencies.

The third currency lane (after web-content freshness in source_currency.py and competitor
snapshots in competitor_snapshot.py). It answers "has a dependency released a newer version than
the one we validated / pinned?" deterministically, with no model tokens: it reads the
`software-dependency` and `mcp-server` entries from canonical-sources/source-registry.json and,
for each, queries the exact upstream it declares:

  upstream_api = "pypi"            -> https://pypi.org/pypi/<pkg>/json      (.info.version + upload date)
  upstream_api = "github_releases" -> https://api.github.com/repos/<o>/<r>/releases/latest (tag + date)
  upstream_api = "binary"|"manual" -> no fetch; advisory (report the pinned/validated baseline + URL)

It then computes drift deterministically (latest vs validated_version and vs the pinned upper
bound), flags a MAJOR bump as breaking, and degrades to advisory when offline or a fetch fails.
Network is stdlib urllib honoring the env proxy + CA bundle; nothing here needs the crawl stack.

The registry is written only through tools/registry_io.py (the shared single implementation).
`--apply` stamps last_checked / latest_seen / latest_seen_date (and last_changed_detected on
drift) for reachable entries so a cron or human runs mundane currency maintenance token-free.

Usage:
  python3 tools/dependency_currency.py report [--offline] [--only <id>]
  python3 tools/dependency_currency.py check  [--offline] [--only <id>]   # report + a mark-checked queue
  python3 tools/dependency_currency.py check --apply [--only <id>]        # + token-free stamping
  python3 tools/dependency_currency.py --selftest                          # pure drift logic, no network
"""
import argparse
import json
import os
import re
import ssl
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import registry_io  # noqa: E402  (the single shared registry writer)

DEP_CATEGORIES = {"software-dependency", "mcp-server"}
TOOL = "tools/dependency_currency.py"
CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") or "/root/.ccr/ca-bundle.crt"


# ── deterministic version logic (pure; the selftest pins this) ───────────────

def parse_version(text):
    """Best-effort (major, minor, patch, ...) tuple from a version/tag string. Strips a leading
    'v'/tag noise and any pre-release suffix. Returns () when no numeric component is found."""
    if not text or not isinstance(text, str):
        return ()
    m = re.search(r"(\d+(?:\.\d+)*)", text)
    if not m:
        return ()
    return tuple(int(p) for p in m.group(1).split("."))


def _cmp(a, b):
    """Compare two version tuples with zero-padding. -1 / 0 / 1."""
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return (a > b) - (a < b)


def pinned_upper_bound(constraint):
    """Return the version tuple of a '<X' / '<=X' upper bound in a pip constraint, or None."""
    if not constraint or not isinstance(constraint, str):
        return None
    m = re.search(r"<=?\s*([0-9][0-9.]*)", constraint)
    return parse_version(m.group(1)) if m else None


def classify_drift(entry, latest, latest_date):
    """Deterministic drift status for one entry given the observed latest version. Returns a dict
    (never raises). `latest`/`latest_date` are None for advisory (unreached) entries."""
    baseline = entry.get("validated_version")
    pin = entry.get("pinned_constraint", "")
    out = {
        "id": entry["id"],
        "category": entry["category"],
        "baseline": baseline,
        "pinned_constraint": pin or None,
        "latest_seen": latest,
        "latest_seen_date": latest_date,
    }
    if latest is None:
        out["status"] = "advisory"
        out["breaking"] = False
        out["note"] = "no programmatic upstream (binary/manual) or unreachable; check the URL by hand"
        return out

    lv = parse_version(latest)
    upper = pinned_upper_bound(pin)
    breaking = False
    # A latest at/above the pinned upper bound is out-of-pin and treated as breaking.
    if upper is not None and lv and _cmp(lv, upper) >= 0:
        breaking = True

    if baseline:
        bv = parse_version(baseline)
        c = _cmp(lv, bv) if (lv and bv) else 0
        if c <= 0:
            out["status"] = "current"
        else:
            # newer than what we validated
            major_bump = bool(lv and bv) and lv[0] > bv[0]
            breaking = breaking or major_bump
            out["status"] = "major-drift" if major_bump else "minor-drift"
    else:
        # no validated baseline: report the observed latest but do not call it drift
        out["status"] = "out-of-pin" if breaking else "no-baseline"
    out["breaking"] = breaking
    return out


# ── network (stdlib; honors env proxy + CA bundle; never raises) ─────────────

def _http_get_json(url, timeout=12):
    ctx = ssl.create_default_context()
    if os.path.exists(CA_BUNDLE):
        try:
            ctx.load_verify_locations(CA_BUNDLE)
        except Exception:  # noqa: BLE001
            pass
    headers = {"User-Agent": "creator-os-dependency-currency", "Accept": "application/json"}
    if "api.github.com" in url:
        headers["Accept"] = "application/vnd.github+json"
        # Use a token when present (CI has GITHUB_TOKEN) to lift the 60/hr unauthenticated limit.
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode("utf-8")), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {str(exc)[:160]}"


def fetch_latest(entry, getter=_http_get_json):
    """Return (latest_version, latest_date, error). getter is injectable for the selftest.
    Advisory (binary/manual) entries return (None, None, None) without a fetch."""
    api = entry.get("upstream_api")
    url = entry.get("check_url")
    if api not in ("pypi", "github_releases") or not url:
        return None, None, None
    data, err = getter(url)
    if data is None:
        return None, None, err
    try:
        if api == "pypi":
            latest = data["info"]["version"]
            files = data.get("releases", {}).get(latest) or []
            latest_date = (files[0].get("upload_time_iso_8601") or files[0].get("upload_time") or "")[:10] if files else None
            return latest, (latest_date or None), None
        # github_releases
        latest = data.get("tag_name")
        latest_date = (data.get("published_at") or "")[:10] or None
        return (latest or None), latest_date, (None if latest else "no tag_name in release payload")
    except Exception as exc:  # noqa: BLE001
        return None, None, f"parse: {type(exc).__name__}: {str(exc)[:120]}"


# ── orchestration ────────────────────────────────────────────────────────────

def check_entries(entries, offline=False, getter=_http_get_json):
    results = []
    for e in entries:
        if offline:
            latest, ldate, err = None, None, "offline"
        else:
            latest, ldate, err = fetch_latest(e, getter)
        res = classify_drift(e, latest, ldate)
        if err:
            res["fetch_error"] = err
            # P49 WS9: a rate-limit/block on a REAL upstream is not "no upstream" -- drift is UNKNOWN,
            # not current. Distinguish it so a GitHub 403 isn't read as an absent/binary source.
            if e.get("upstream_api") in ("pypi", "github_releases") and \
                    any(tok in err for tok in ("403", "429", "rate limit", "RateLimit", "rate_limit")):
                res["blocked"] = True
                res["note"] = ("upstream fetch was rate-limited or blocked (NOT absent); set GITHUB_TOKEN "
                               "and retry, or check the URL by hand. Version drift is unknown, not current.")
        res["url"] = e.get("check_url") or e.get("url")
        res["used_by"] = e.get("used_by", [])
        results.append(res)
    return results


def build_report(registry, offline=False, only=None, getter=_http_get_json):
    entries = [s for s in registry.get("sources", []) if s.get("category") in DEP_CATEGORIES]
    if only:
        entries = [s for s in entries if s["id"] == only]
    results = check_entries(entries, offline=offline, getter=getter)
    drifted = [r for r in results if r["status"] in ("minor-drift", "major-drift", "out-of-pin")]
    breaking = [r for r in results if r.get("breaking")]
    advisory = [r for r in results if r["status"] == "advisory"]
    current = [r for r in results if r["status"] in ("current", "no-baseline")]
    return {
        "as_of": date.today().isoformat(),
        "computed_by": f"{TOOL}.classify_drift",
        "summary": {
            "total": len(results), "current": len(current), "drifted": len(drifted),
            "breaking": len(breaking), "advisory": len(advisory),
        },
        "drifted": drifted,
        "breaking": [r["id"] for r in breaking],
        "advisory": [r["id"] for r in advisory],
        "results": results,
    }


def apply_stamps(registry, results, saver=registry_io.save_registry):
    """Token-free registry maintenance: stamp last_checked / latest_seen for every reachable
    entry, and last_changed_detected when drift was observed. Advisory (unreached) entries are
    NOT stamped (we could not confirm them). `saver` is injectable so the selftest never writes
    the real registry; the CLI passes the shared registry_io single writer."""
    by_id = {s["id"]: s for s in registry.get("sources", [])}
    today = date.today().isoformat()
    stamped, drift_flagged = [], []
    for r in results:
        if r["status"] == "advisory" or r.get("latest_seen") is None:
            continue
        entry = by_id.get(r["id"])
        if not entry:
            continue
        entry["last_checked"] = today
        entry["latest_seen"] = r["latest_seen"]
        entry["latest_seen_date"] = r.get("latest_seen_date")
        stamped.append(r["id"])
        if r["status"] in ("minor-drift", "major-drift", "out-of-pin"):
            entry["last_changed_detected"] = today
            drift_flagged.append(r["id"])
    if stamped:
        registry["last_registry_update"] = today
        saver(registry)
    return {"stamped": stamped, "drift_flagged": drift_flagged}


# ── selftest (pure logic + injected fetcher; no network) ─────────────────────

def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    ok("parse_version basic", parse_version("2.2.1") == (2, 2, 1))
    ok("parse_version tag prefix", parse_version("v0.36.0") == (0, 36, 0))
    ok("parse_version four parts", parse_version("5.0.0.93") == (5, 0, 0, 93))
    ok("parse_version empty", parse_version("") == ())
    ok("cmp pads zeros", _cmp((2,), (2, 0, 0)) == 0)
    ok("cmp less", _cmp((0, 7), (0, 8)) == -1)
    ok("pinned upper bound <3", pinned_upper_bound(">=2,<3") == (3,))
    ok("pinned upper bound <0.8", pinned_upper_bound(">=0.7,<0.8") == (0, 8))
    ok("pinned upper bound none", pinned_upper_bound("") is None)

    # current: latest == validated, within pin
    r = classify_drift({"id": "d", "category": "software-dependency",
                        "validated_version": "0.7", "pinned_constraint": ">=0.7,<0.8"}, "0.7", "2026-01-01")
    ok("current when latest==validated", r["status"] == "current" and not r["breaking"])

    # minor-drift: newer minor, still under pin
    r = classify_drift({"id": "d", "category": "software-dependency",
                        "validated_version": "2.2.1", "pinned_constraint": ">=2,<3"}, "2.4.0", "2026-06-01")
    ok("minor-drift under pin", r["status"] == "minor-drift" and not r["breaking"])

    # major-drift / out-of-pin: latest crosses the pinned upper bound
    r = classify_drift({"id": "d", "category": "software-dependency",
                        "validated_version": "2.2.1", "pinned_constraint": ">=2,<3"}, "3.0.0", "2026-07-01")
    ok("major bump is breaking", r["status"] == "major-drift" and r["breaking"])

    # out-of-pin without a baseline
    r = classify_drift({"id": "d", "category": "software-dependency",
                        "validated_version": None, "pinned_constraint": ">=0.7,<0.8"}, "0.8.0", "2026-07-01")
    ok("out-of-pin without baseline flagged breaking", r["breaking"] and r["status"] == "out-of-pin")

    # advisory: no latest observed
    r = classify_drift({"id": "d", "category": "software-dependency",
                        "validated_version": None, "pinned_constraint": "system"}, None, None)
    ok("advisory when unreached", r["status"] == "advisory" and not r["breaking"])

    # injected fetcher end-to-end (pypi + github shapes), no network
    def fake_getter(url):
        if "pypi.org" in url:
            return {"info": {"version": "0.7"},
                    "releases": {"0.7": [{"upload_time_iso_8601": "2026-03-01T00:00:00Z"}]}}, None
        if "api.github.com" in url:
            return {"tag_name": "v9.9.9", "published_at": "2026-07-01T00:00:00Z"}, None
        return None, "unmocked"
    pypi_entry = {"id": "dep-x", "category": "software-dependency", "upstream_api": "pypi",
                  "check_url": "https://pypi.org/pypi/x/json", "validated_version": "0.7",
                  "pinned_constraint": ">=0.7,<0.8"}
    gh_entry = {"id": "mcp-y", "category": "mcp-server", "upstream_api": "github_releases",
                "check_url": "https://api.github.com/repos/o/r/releases/latest",
                "validated_version": None, "pinned_constraint": ""}
    reg = {"sources": [pypi_entry, gh_entry]}
    rep = build_report(reg, getter=fake_getter)
    ok("report totals", rep["summary"]["total"] == 2)
    ok("pypi entry current via fetch", any(r["id"] == "dep-x" and r["status"] == "current" for r in rep["results"]))
    ok("github latest parsed", any(r["id"] == "mcp-y" and r["latest_seen"] == "v9.9.9" for r in rep["results"]))
    writes = []  # capture-saver so the selftest never touches the real registry
    ok("apply stamps reachable only", apply_stamps({"sources": [dict(pypi_entry)]},
        [r for r in rep["results"] if r["id"] == "dep-x"],
        saver=writes.append)["stamped"] == ["dep-x"])
    ok("apply actually wrote once", len(writes) == 1)
    # advisory entries are never stamped (and no write happens)
    adv = classify_drift({"id": "dep-ffmpeg", "category": "software-dependency",
                          "validated_version": "7.0.2-static", "pinned_constraint": "system"}, None, None)
    writes2 = []
    ok("advisory not stamped", apply_stamps({"sources": [{"id": "dep-ffmpeg"}]}, [adv],
        saver=writes2.append)["stamped"] == [])
    ok("no write when nothing stamped", len(writes2) == 0)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv):
    ap = argparse.ArgumentParser(description="Token-free dependency version-drift checker.")
    ap.add_argument("command", nargs="?", choices=["report", "check"], help="report (read-only) or check (+queue)")
    ap.add_argument("--offline", action="store_true", help="skip all network; everything degrades to advisory")
    ap.add_argument("--only", metavar="ID", help="check a single entry by id")
    ap.add_argument("--apply", action="store_true", help="(check) stamp last_checked/latest_seen token-free")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.command:
        ap.print_help()
        return 2

    registry = registry_io.load_registry()
    report = build_report(registry, offline=args.offline, only=args.only)

    if args.command == "check":
        report["mark_checked_queue"] = [
            {"id": r["id"], "status": r["status"], "latest_seen": r["latest_seen"],
             "action": f"python3 tools/source_currency.py mark-checked {r['id']}"
                       + (" --changed" if r["status"] in ('minor-drift', 'major-drift', 'out-of-pin') else "")}
            for r in report["results"] if r["status"] != "advisory"
        ]
        if args.apply:
            report["applied"] = apply_stamps(registry, report["results"])

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
