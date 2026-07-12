#!/usr/bin/env python3
"""update_notify.py -- consent-gated, never-nag notifier for a newer Creator OS release (P44).

The CHECK (update_check.py) is read-only and privacy-safe (R5: it contacts only the public releases
API and uploads nothing). This module governs WHETHER the automated/background check runs and turns
its result into a single passive notice. It mirrors the geo_consent gate contract:

  capabilities.background_update_check
      absent / {"enabled": false}  -> OFF (the shipped default): no check, no network, no notice
      {"enabled": true}            -> ON:  the read-only check may run; a passive one-line notice is
                                            produced ONLY when a newer version exists

Enabling the flag IS the standing consent for the background check (the wizard offers a one-click
enable). Applying an update is NEVER automatic; the notice only points at `python3 tools/update.py`,
which the user runs when they choose.

Design rules honored (P44):
  R2  check is decoupled from apply: this only checks and produces a notice; it never applies.
  R4  one passive notice, never a nag: notice_line returns None when there is nothing to say.
  R5  nothing leaves the machine: with the flag OFF, no network call is made at all.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obligations  # noqa: E402
import update_check as uc  # noqa: E402

FEATURE = "background_update_check"


def enabled(config):
    """True when the user has opted in to the background update check."""
    return obligations.flag_enabled(config, FEATURE)


def gate(config):
    """feature_off (no check, no network) | ok (read-only check permitted). Enabling the flag is the
    standing consent; the poll is read-only and privacy-safe, so there is no per-run ask."""
    if not enabled(config):
        return {"proceed": False, "code": "feature_off",
                "reason": (f"{FEATURE} is off; enable it (wizard or config) to let Creator OS quietly "
                           "check for a newer version. Nothing is ever applied automatically.")}
    return {"proceed": True, "code": "ok",
            "reason": "background update check is enabled; the poll is read-only and uploads nothing"}


def notice_line(report):
    """A single passive line, or None when there is nothing to say (R4: never a nag)."""
    if not report or not report.get("update_available"):
        return None
    return (f"A newer Creator OS version ({report['latest_seen']}) is available; you are on "
            f"{report['local_version']}. Update when you choose: python3 tools/update.py "
            "(it never touches your saved data).")


def check(config, offline=False, getter=None):
    """Gate, then (only if enabled) run the read-only check and attach a passive notice. Never
    applies. With the flag OFF this returns before any network call is made."""
    g = gate(config)
    if not g["proceed"]:
        return {"gate": g, "checked": False, "notice": None}
    report = uc.build_report(uc.local_version(), offline=offline, getter=getter or uc._http_get_json)
    return {"gate": g, "checked": True, "report": report, "notice": notice_line(report)}


# ---- selftest ----------------------------------------------------------------

def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    ON = {"capabilities": {"background_update_check": {"enabled": True}}}
    OFF = {"capabilities": {"background_update_check": {"enabled": False}}}
    ABSENT = {"capabilities": {}}

    ok("flag enabled reads dict form", enabled(ON) is True)
    ok("flag disabled reads dict form", enabled(OFF) is False)
    ok("flag absent -> off (opt-in default)", enabled(ABSENT) is False)

    def raising_getter(url):
        raise AssertionError("no network call may happen when the flag is off")

    r_off = check(OFF, getter=raising_getter)
    ok("flag off -> not checked, no notice", r_off["checked"] is False and r_off["notice"] is None)
    ok("flag off -> gate feature_off", r_off["gate"]["code"] == "feature_off")

    # pin the installed version so the selftest does not depend on VERSION on disk
    real_local = uc.local_version
    uc.local_version = lambda: "0.1.0"
    try:
        def getter_behind(url):
            return {"tag_name": "v0.2.0", "published_at": "2026-07-10T00:00:00Z"}, None

        def getter_current(url):
            return {"tag_name": "v0.1.0", "published_at": "2026-06-01T00:00:00Z"}, None

        r_new = check(ON, getter=getter_behind)
        ok("flag on + behind -> checked", r_new["checked"] is True)
        ok("behind -> a passive notice is produced", isinstance(r_new["notice"], str) and "0.2.0" in r_new["notice"])
        ok("notice points at explicit apply, not auto-apply", "tools/update.py" in r_new["notice"])
        ok("notice has no em dash", "—" not in r_new["notice"])

        r_cur = check(ON, getter=getter_current)
        ok("flag on + current -> no notice (never a nag)", r_cur["checked"] is True and r_cur["notice"] is None)

        ok("notice_line None when no report", notice_line(None) is None)
        ok("notice_line None when not available",
           notice_line({"update_available": False, "latest_seen": "v0.1.0", "local_version": "0.1.0"}) is None)
    finally:
        uc.local_version = real_local

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


def main(argv):
    ap = argparse.ArgumentParser(description="Consent-gated, never-nag notifier for a newer Creator OS release.")
    ap.add_argument("--offline", action="store_true", help="skip the network; status 'unknown' (no notice)")
    ap.add_argument("--json", action="store_true", help="print the full gate+report JSON instead of just the notice")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    config = obligations.load_config()
    result = check(config, offline=args.offline)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if result["notice"]:
        print(result["notice"])
    elif not result["checked"]:
        print(f"(background update check is off; enable {FEATURE} to turn it on)")
    else:
        print("(up to date; no notice)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
