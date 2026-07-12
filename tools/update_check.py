#!/usr/bin/env python3
"""update_check.py -- token-free self-update check for the Creator OS ecosystem itself.

The fourth currency lane. dependency_currency.py watches third-party deps; source_currency.py
watches web sources; competitor_snapshot.py watches competitors. This one answers the question no
existing checker covers: "has a NEWER Creator OS release been published upstream than the copy I
have installed?" It is a read-only poll of the repo's own GitHub releases (stdlib urllib, honoring
the env proxy + CA bundle, never raises), compared against the locally installed VERSION.

It NEVER pulls, never writes code, and contacts only the public releases API. Applying an update
stays the user's explicit `python3 tools/update.py` run (git pull + drift guard + cache rebuild),
which by design never touches *.local.json data. The optional `check --apply` only stamps
last_checked / latest_seen on the registry's own `creator-os-release` currency entry (token-free
maintenance), through the shared registry_io writer.

Design rules honored (P44):
  R2  check is decoupled from apply: this tool only checks and proposes; it never applies.
  R5  nothing leaves the machine: outbound is a single GET to the public releases API; no upload.

Reuse (not reinvented): dependency_currency._http_get_json / fetch_latest / parse_version / _cmp;
version.read_versions; registry_io.save_registry (the sole registry writer).

Usage:
  python3 tools/update_check.py report                 # read-only: poll releases, compare, print JSON
  python3 tools/update_check.py check                  # report + a one-line apply hint
  python3 tools/update_check.py check --apply           # + token-free stamp of the release entry
  python3 tools/update_check.py report --offline         # skip network; status 'unknown' (no nag)
  python3 tools/update_check.py --selftest               # pure compare logic + injected fetcher, no network
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import registry_io  # noqa: E402  (the single shared registry writer)
import version as version_mod  # noqa: E402
from dependency_currency import _cmp, _http_get_json, fetch_latest, parse_version  # noqa: E402

TOOL = "tools/update_check.py"
# The upstream the installed copy tracks. Overridable so a fork / self-host can point elsewhere and
# so the selftest never depends on a real slug.
REPO = os.environ.get("CREATOR_OS_UPDATE_REPO", "flywifi/seo-tools")
# The registry currency entry this tool stamps (seeded via source_currency.py seed-sources, P44-1).
RELEASE_ENTRY_ID = "creator-os-release"


def release_url(repo=None):
    return f"https://api.github.com/repos/{repo or REPO}/releases/latest"


# ── deterministic compare (pure; the selftest pins this) ─────────────────────

def compare_versions(local, latest):
    """Compare installed vs upstream. Returns current | behind | ahead | unknown.
    'behind' is the only state that means an update is available."""
    lv, av = parse_version(local), parse_version(latest)
    if not lv or not av:
        return "unknown"
    c = _cmp(av, lv)  # latest vs local
    if c > 0:
        return "behind"
    if c < 0:
        return "ahead"
    return "current"


# ── report (a proposal; never applies) ───────────────────────────────────────

def local_version():
    """The installed ecosystem version (VERSION file, mirrored in versions.json/plugin.json)."""
    return version_mod.read_versions()[0]


def build_report(local, offline=False, getter=_http_get_json, repo=None):
    """Poll the repo's latest release and classify. `local` is the installed version string;
    `getter` is injectable so the selftest never hits the network. Never raises."""
    repo = repo or REPO
    entry = {"upstream_api": "github_releases", "check_url": release_url(repo)}
    if offline:
        latest, latest_date, err = None, None, "offline"
    else:
        latest, latest_date, err = fetch_latest(entry, getter=getter)

    if latest is None:
        if offline:
            status, note = "unknown", "Offline: no check performed. No update state is implied."
        elif err and "404" in err:
            status, note = "no_release", "No published release upstream yet; nothing to compare against."
        else:
            status, note = "unreachable", "Could not reach the releases API; try again later."
        update_available = False
    else:
        status = compare_versions(local, latest)
        note = {
            "current": "You are on the latest published release.",
            "behind": "A newer Creator OS release is available upstream.",
            "ahead": "Your installed version is newer than the latest published release (development copy).",
            "unknown": "Versions could not be compared.",
        }[status]
        update_available = status == "behind"

    report = {
        "as_of": date.today().isoformat(),
        "computed_by": f"{TOOL}.compare_versions",
        "repo": repo,
        "local_version": local,
        "latest_seen": latest,
        "latest_seen_date": latest_date,
        "status": status,
        "update_available": update_available,
        "note": note,
        "apply": {
            "how": "python3 tools/update.py",
            "note": ("Applying is your explicit choice. It pulls new code and rebuilds the cache. "
                     "It never touches your .local data files (rate card, deals, contracts, templates)."),
        },
        "boundary": ("Read-only version check. This tool never pulls, never writes code, and contacts "
                     "only the public releases API. Nothing about your data leaves this machine."),
        "human_review_required": True,
    }
    if err:
        report["fetch_error"] = err
    return report


# ── token-free stamp of the release currency entry (via the shared writer) ────

def apply_stamp(registry, report, saver=registry_io.save_registry):
    """Stamp last_checked / latest_seen on the registry's creator-os-release entry. Reachable
    results only. `saver` is injectable so the selftest never writes the real registry."""
    if report.get("latest_seen") is None:
        return {"stamped": [], "note": "no latest_seen observed; nothing to stamp"}
    by_id = {s["id"]: s for s in registry.get("sources", [])}
    entry = by_id.get(RELEASE_ENTRY_ID)
    if not entry:
        return {"stamped": [],
                "note": f"{RELEASE_ENTRY_ID} not in registry; run: python3 tools/source_currency.py seed-sources <file>"}
    today = date.today().isoformat()
    entry["last_checked"] = today
    entry["latest_seen"] = report["latest_seen"]
    entry["latest_seen_date"] = report.get("latest_seen_date")
    drift = report["status"] == "behind"
    if drift:
        entry["last_changed_detected"] = today
    registry["last_registry_update"] = today
    saver(registry)
    return {"stamped": [RELEASE_ENTRY_ID], "drift_flagged": [RELEASE_ENTRY_ID] if drift else []}


# ── selftest (pure logic + injected fetcher; no network) ─────────────────────

def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    ok("compare behind", compare_versions("0.1.0", "0.2.0") == "behind")
    ok("compare current", compare_versions("0.1.0", "v0.1.0") == "current")
    ok("compare ahead", compare_versions("0.2.0", "0.1.0") == "ahead")
    ok("compare tag prefix", compare_versions("1.0.0", "v1.0.0") == "current")
    ok("compare padded", compare_versions("1.2", "1.2.0") == "current")
    ok("compare unknown when unparseable", compare_versions("0.1.0", "") == "unknown")

    def getter_behind(url):
        return {"tag_name": "v0.2.0", "published_at": "2026-07-10T00:00:00Z"}, None

    def getter_current(url):
        return {"tag_name": "v0.1.0", "published_at": "2026-06-01T00:00:00Z"}, None

    def getter_404(url):
        return None, "HTTPError: HTTP Error 404: Not Found"

    def getter_down(url):
        return None, "URLError: <urlopen error timed out>"

    r = build_report("0.1.0", getter=getter_behind, repo="o/r")
    ok("behind -> update_available", r["status"] == "behind" and r["update_available"] is True)
    ok("behind carries latest", r["latest_seen"] == "v0.2.0" and r["latest_seen_date"] == "2026-07-10")
    ok("report always proposes apply", r["apply"]["how"] == "python3 tools/update.py")
    ok("report never auto-applies (human_review_required)", r["human_review_required"] is True)

    r2 = build_report("0.1.0", getter=getter_current, repo="o/r")
    ok("current -> no update", r2["status"] == "current" and r2["update_available"] is False)

    r3 = build_report("0.1.0", getter=getter_404, repo="o/r")
    ok("404 -> no_release, no nag", r3["status"] == "no_release" and r3["update_available"] is False)

    r4 = build_report("0.1.0", getter=getter_down, repo="o/r")
    ok("unreachable -> no update state implied", r4["status"] == "unreachable" and r4["update_available"] is False)

    r5 = build_report("0.1.0", offline=True, getter=getter_behind, repo="o/r")
    ok("offline -> unknown, no network implied", r5["status"] == "unknown" and r5["update_available"] is False)

    # apply-stamp: writes once, only the release entry, only when reachable
    writes = []
    reg = {"sources": [{"id": RELEASE_ENTRY_ID, "category": "creator-os-release"}]}
    res = apply_stamp(reg, r, saver=writes.append)
    ok("apply stamps the release entry", res["stamped"] == [RELEASE_ENTRY_ID])
    ok("apply flags drift when behind", res.get("drift_flagged") == [RELEASE_ENTRY_ID])
    ok("apply wrote once", len(writes) == 1)
    ok("stamp recorded latest_seen", reg["sources"][0]["latest_seen"] == "v0.2.0")

    # apply is a no-op when the entry is missing (never invents it)
    writes2 = []
    res2 = apply_stamp({"sources": []}, r, saver=writes2.append)
    ok("apply no-ops without the entry", res2["stamped"] == [] and len(writes2) == 0)

    # apply is a no-op when nothing was observed
    writes3 = []
    res3 = apply_stamp(reg, r3, saver=writes3.append)
    ok("apply no-ops when latest_seen is None", res3["stamped"] == [] and len(writes3) == 0)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv):
    ap = argparse.ArgumentParser(description="Token-free self-update check for the Creator OS ecosystem.")
    ap.add_argument("command", nargs="?", choices=["report", "check"], help="report (read-only) or check (+apply hint)")
    ap.add_argument("--offline", action="store_true", help="skip the network; status 'unknown' (no update implied)")
    ap.add_argument("--apply", action="store_true", help="(check) stamp last_checked/latest_seen on the release entry")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.command:
        ap.print_help()
        return 2

    report = build_report(local_version(), offline=args.offline)

    if args.command == "check":
        report["apply_hint"] = (
            "python3 tools/update.py" if report["update_available"]
            else "up to date; nothing to apply" if report["status"] == "current"
            else "no action")
        if args.apply:
            registry = registry_io.load_registry()
            report["applied"] = apply_stamp(registry, report)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
