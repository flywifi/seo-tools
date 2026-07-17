#!/usr/bin/env python3
"""Transport frontends for the compute hand-off queue (P60).

Transport A (default, this module's --once/--watch): the Drive hub folder is synced to the local
disk by Google Drive for desktop, so watching Drive is just reading a normal directory on a
schedule. No Drive API, no OAuth, no server. The schedule follows the repo's scheduler convention
(tools/freshness-scheduler.example): a cron/launchd job runs `--once`, or `--watch` loops in the
foreground with an interval. Transport B (--transport api, opt-in via the drive_api_polling
capability) ships in a later phase and is refused honestly until then.

The hub root resolves in this order: --hub argument, then the drive_hub.local_mirror setting
(creator-os-config.local.json over creator-os-config.json). Everything execution-side (gate,
allowlist, idempotency, confinement, timeouts) lives in runner.run_pass — the watcher only decides
WHERE the queue directory is and WHEN to look.

Usage:
  python3 tools/handoff/watcher.py --once [--hub PATH]
  python3 tools/handoff/watcher.py --watch [--interval SECONDS] [--hub PATH]
  python3 tools/handoff/watcher.py --status [--hub PATH]
  python3 tools/handoff/watcher.py --selftest
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from handoff import queue as q  # noqa: E402
from handoff import runner  # noqa: E402

DEFAULT_INTERVAL = 300  # seconds; latency is sync + this, so 5 minutes is a sane floor


def load_hub_config() -> dict:
    """The drive_hub section, local overrides winning (the update-channel precedence model)."""
    merged = {}
    for name in ("creator-os-config.json", "creator-os-config.local.json"):
        p = ROOT / name
        if p.exists():
            try:
                merged.update(json.loads(p.read_text(encoding="utf-8")).get("drive_hub", {}))
            except (OSError, ValueError):
                pass
    return merged


def detect_mirror_candidates(home=None, folder_name="Creator OS") -> list:
    """Where Google Drive for desktop usually puts the hub on macOS: the File Provider mount under
    ~/Library/CloudStorage/GoogleDrive-*/My Drive/<folder>. Returns existing candidates only;
    detection is a convenience for the wizard, never an authority (the user confirms the path)."""
    home = Path(home or os.path.expanduser("~"))
    pattern = str(home / "Library" / "CloudStorage" / "GoogleDrive-*" / "My Drive" / folder_name)
    return sorted(p for p in glob.glob(pattern) if os.path.isdir(p))


def resolve_hub(arg_hub=None) -> tuple:
    """Returns (hub_path|None, note). --hub wins; else drive_hub.local_mirror; else unresolved."""
    if arg_hub:
        return (arg_hub, "from --hub") if os.path.isdir(arg_hub) else (None, f"--hub path does not exist: {arg_hub}")
    cfg = load_hub_config()
    mirror = cfg.get("local_mirror")
    if mirror and os.path.isdir(os.path.expanduser(mirror)):
        return os.path.expanduser(mirror), "from drive_hub.local_mirror"
    if mirror:
        return None, f"drive_hub.local_mirror is set but missing on disk: {mirror}"
    return None, ("no hub configured; set it on the wizard /drive-hub screen or pass --hub "
                  "(is Google Drive for desktop installed and syncing the hub folder?)")


def status(hub_root) -> dict:
    """Read-only queue snapshot for the wizard screen and --status."""
    paths = q.hub_paths(hub_root)
    def _count(p):
        return sum(1 for f in p.iterdir() if f.suffix == ".json" and not f.name.endswith(".tmp")) if p.exists() else 0
    return {
        "hub": str(hub_root),
        "pending": _count(paths["queue"]),
        "results": _count(paths["results"]),
        "archived": _count(paths["archive"]),
        "enabled": runner.handoff_enabled(),
    }


def once(hub_root) -> list:
    return runner.run_pass(hub_root)


def watch(hub_root, interval=DEFAULT_INTERVAL) -> None:
    print(f"handoff watcher: hub={hub_root} interval={interval}s (Ctrl+C to stop)")
    try:
        while True:
            results = once(hub_root)
            acted = [r for r in results if r.get("status") not in ("gated",)]
            if acted:
                print(json.dumps(acted, default=str))
            time.sleep(max(30, int(interval)))
    except KeyboardInterrupt:
        print("\nhandoff watcher: stopped")


def selftest() -> int:
    import tempfile
    import types
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # Hub resolution precedence and honest failures.
    hub = tempfile.mkdtemp()
    got, note = resolve_hub(hub)
    ok("--hub wins when it exists", got == hub and note == "from --hub")
    got, note = resolve_hub(os.path.join(hub, "missing"))
    ok("missing --hub refused with a plain note", got is None and "does not exist" in note)
    got, note = resolve_hub(None) if load_hub_config().get("local_mirror") else (None, "no hub configured; ...")
    ok("unconfigured hub yields guidance, not a crash", got is None or os.path.isdir(got))

    # Mirror detection on a simulated CloudStorage tree (no real Drive needed).
    fakehome = Path(tempfile.mkdtemp())
    target = fakehome / "Library" / "CloudStorage" / "GoogleDrive-someone@example.com" / "My Drive" / "Creator OS"
    target.mkdir(parents=True)
    found = detect_mirror_candidates(home=fakehome)
    ok("detects the CloudStorage mirror path", found == [str(target)])
    ok("no candidates on an empty home", detect_mirror_candidates(home=tempfile.mkdtemp()) == [])

    # Status snapshot over a temp hub.
    q.ensure_hub_dirs(hub)
    q.submit(hub, "library_analyze")
    st = status(hub)
    ok("status counts one pending job", st["pending"] == 1 and st["results"] == 0)

    # The production once() path honors the master gate (off by default in this repo).
    res = once(hub)
    ok("once() with the gate off stays gated and leaves the queue alone",
       res and res[0]["status"] == "gated" and status(hub)["pending"] == 1)

    # And a gated-open pass drains it (runner already covers execution; this pins the wiring).
    calls = []
    def fake_spawn(argv, **kw):
        calls.append(argv)
        return types.SimpleNamespace(returncode=0, stdout="{}", stderr="")
    res = runner.run_pass(hub, spawn=fake_spawn, allow=True)
    ok("wired pass drains the queue", res[0]["status"] == "done" and status(hub)["pending"] == 0)

    failed = [n for n, c in checks if not c]
    for n, c in checks:
        print(("ok   " if c else "FAIL ") + n)
    print(f"handoff.watcher selftest: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0


def main(argv) -> int:
    if "--selftest" in argv:
        return selftest()
    if "--transport" in argv and argv[argv.index("--transport") + 1] == "api":
        print(json.dumps({"error": "the Drive API transport (drive_api_polling) is not wired in "
                                   "this version; use the Drive for desktop sync transport"}))
        return 1
    arg_hub = argv[argv.index("--hub") + 1] if "--hub" in argv else None
    hub, note = resolve_hub(arg_hub)
    if hub is None:
        print(json.dumps({"error": note}))
        return 1
    if "--status" in argv:
        print(json.dumps(status(hub), indent=2))
        return 0
    if "--once" in argv:
        print(json.dumps(once(hub), indent=2, default=str))
        return 0
    if "--watch" in argv:
        interval = int(argv[argv.index("--interval") + 1]) if "--interval" in argv else DEFAULT_INTERVAL
        watch(hub, interval)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
