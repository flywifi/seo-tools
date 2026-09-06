#!/usr/bin/env python3
"""persona_audit.py -- a read-only harness for the wizard's non-technical first-run (P49 WS4).

Renders every wizard GET screen in-process (it imports tools/wizard.py and calls the _screen_* render
functions; no server, no network, no writes) and checks each one the way a non-technical persona ("Alex",
a YouTube creator, not a developer) would experience it:

  * does the screen render and carry a heading?
  * does it offer a clear NEXT ACTION (a link to another screen, or a form/button)?
  * does its VISIBLE text leak an internal token that reads as code (e.g. local_fs, google_drive)?

It also builds the screen-to-screen link graph and flags any ORPHAN route (reachable only by typing the
URL). This is the machine-checkable half of docs/PERSONA-AUDIT.md; the human judgement (jargon walls,
dead-ends, install friction) is recorded in the dated audit log alongside it.

  python3 tools/persona_audit.py             # print the audit report (green / amber / red per screen)
  python3 tools/persona_audit.py --selftest   # exit 1 if any screen fails to render, an orphan exists,
                                              # or a store-token leaks into visible text
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wizard  # noqa: E402  (the module under audit; render functions only, no server)

# Route -> the render function that produces its HTML (all take optional args with safe defaults).
ROUTES = {
    "/": "_screen_welcome",
    "/claude": "_screen_claude",
    "/bring": "_screen_bring",
    "/setup-computer": "_screen_setup_computer",
    "/storage-folder": "_screen_storage_folder",
    "/claudeai": "_screen_claudeai",
    "/desktop": "_screen_desktop",
    "/google": "_screen_google",
    "/microsoft": "_screen_microsoft",
    "/done": "_screen_done",
    "/publishing-setup": "_screen_publishing_setup",
    "/publishing-setup/youtube": "_screen_publishing_youtube",
    "/publishing-setup/instagram": "_screen_publishing_instagram",
    "/publishing-setup/tiktok": "_screen_publishing_tiktok",
    "/publishing-setup/pinterest": "_screen_publishing_pinterest",
    "/freshness-setup": "_screen_freshness",
    "/brand-deals": "_screen_brand_deals",
    "/import": "_screen_import",
    "/doctor": "_screen_doctor",
    "/chatgpt": "_screen_chatgpt",
    "/transitions": "_screen_transitions",
    "/updates": "_screen_updates",
    "/cross-modality": "_screen_cross_modality",
    "/drive-hub": "_screen_drive_hub",
    "/compute": "_screen_compute",
    "/inbox": "_screen_inbox",
}

# Internal store/path tokens that must never surface in VISIBLE user-facing text (they read as code).
STORE_TOKENS = ["local_fs", "google_drive", "cross_platform"]

_TAG_RE = re.compile(r"<[^>]+>")
_HREF_RE = re.compile(r'href=["\'](/[^"\'#?]*)')


def _visible_text(html):
    return _TAG_RE.sub(" ", html)


def render(path):
    fn = getattr(wizard, ROUTES[path])
    return fn()


def audit():
    """Render every screen and return (per_screen, orphans, errors)."""
    per_screen, errors, link_targets = [], [], set()
    htmls = {}
    for path in ROUTES:
        try:
            htmls[path] = render(path)
        except Exception as exc:  # noqa: BLE001
            errors.append({"path": path, "error": f"{type(exc).__name__}: {exc}"})
            continue
    for path, html in htmls.items():
        vis = _visible_text(html)
        targets = {t for t in _HREF_RE.findall(html) if t != path}
        link_targets |= targets
        has_heading = "<h1" in html
        has_next = bool(targets) or "<form" in html or "<button" in html or "<select" in html
        leaks = [t for t in STORE_TOKENS if t in vis]
        verdict = "red" if not (has_heading and has_next) else ("amber" if leaks else "green")
        per_screen.append({"path": path, "verdict": verdict, "has_heading": has_heading,
                           "has_next_action": has_next, "token_leaks": leaks,
                           "links_to": sorted(targets)})
    # an orphan is a real route that nothing links to (the landing page "/" is exempt)
    orphans = sorted(p for p in ROUTES if p != "/" and p not in link_targets)
    return per_screen, orphans, errors


def report():
    per_screen, orphans, errors = audit()
    icon = {"green": "OK ", "amber": "~ ", "red": "XX "}
    print("PERSONA AUDIT -- wizard first-run for a non-technical creator (read-only)\n")
    for s in sorted(per_screen, key=lambda x: x["path"]):
        line = f"  [{icon[s['verdict']]}] {s['path']}"
        notes = []
        if not s["has_heading"]:
            notes.append("no heading")
        if not s["has_next_action"]:
            notes.append("no next action")
        if s["token_leaks"]:
            notes.append("leaks: " + ", ".join(s["token_leaks"]))
        if notes:
            line += "  -- " + "; ".join(notes)
        print(line)
    if errors:
        print("\n  RENDER ERRORS:")
        for e in errors:
            print(f"    {e['path']}: {e['error']}")
    print(f"\n  Orphan routes (reachable only by typing the URL): {orphans or 'none'}")
    reds = [s["path"] for s in per_screen if s["verdict"] == "red"]
    ambers = [s["path"] for s in per_screen if s["verdict"] == "amber"]
    print(f"  Summary: {len(per_screen)} screens, {len(reds)} red, {len(ambers)} amber, "
          f"{len(errors)} render errors, {len(orphans)} orphans")
    return per_screen, orphans, errors


def selftest():
    per_screen, orphans, errors = audit()
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    ok("every screen renders without error", not errors)
    ok("every screen has a heading", all(s["has_heading"] for s in per_screen))
    ok("every screen offers a next action", all(s["has_next_action"] for s in per_screen))
    ok("no orphan routes", not orphans)
    ok("no store token leaks into visible text",
       all(not s["token_leaks"] for s in per_screen))
    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    if errors:
        for e in errors:
            print(f"    render error: {e['path']}: {e['error']}")
    if orphans:
        print(f"    orphans: {orphans}")
    print(f"selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    report()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
