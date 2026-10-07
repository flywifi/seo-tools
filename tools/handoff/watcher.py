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
import atomic_io  # noqa: E402  (the one atomic writer, P81)
import env_paths  # noqa: E402  (utf8_stdio: a redirected log on Windows, P102)

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


def _windows_drives() -> list:
    """The drive roots on this Windows computer: os.listdrives() (Python 3.12 and later), else each
    letter whose root exists."""
    lister = getattr(os, "listdrives", None)
    try:
        if lister is not None:
            return list(lister())
    except OSError:
        return []
    import string
    return [f"{c}:\\" for c in string.ascii_uppercase if os.path.exists(f"{c}:\\")]


def detect_mirror_candidates(home=None, folder_name="Creator OS", osname=None, drives=None,
                             isdir=None) -> list:
    """Where Google Drive for desktop usually puts the hub: on macOS the File Provider mount under
    ~/Library/CloudStorage/GoogleDrive-*/My Drive/<folder>; on Windows <letter>:\\My Drive\\<folder>
    on the drive letter Drive for desktop mounts (P102; each drive in `drives`, default
    _windows_drives()). Returns existing candidates only; detection is a convenience for the wizard,
    never an authority (the user confirms the path)."""
    import ntpath
    isdir = os.path.isdir if isdir is None else isdir
    home = Path(home or os.path.expanduser("~"))
    pattern = str(home / "Library" / "CloudStorage" / "GoogleDrive-*" / "My Drive" / folder_name)
    found = [p for p in glob.glob(pattern) if isdir(p)]
    if (os.name if osname is None else osname) == "nt":
        for drive in (_windows_drives() if drives is None else drives):
            cand = ntpath.join(drive, "My Drive", folder_name)
            if isdir(cand):
                found.append(cand)
    return sorted(found)


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
            try:
                results = once(hub_root)
            except Exception as exc:  # noqa: BLE001 - one failed pass must not end the watcher (P102)
                print(f"handoff watcher: pass failed, retrying next interval: {type(exc).__name__}: {exc}")
                results = []
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
    # P102: on Windows each drive's My Drive\Creator OS is offered when it exists.
    _dirs = {"G:\\My Drive\\Creator OS", "H:\\My Drive"}
    _win = detect_mirror_candidates(home=tempfile.mkdtemp(), osname="nt", drives=["C:\\", "G:\\", "H:\\"],
                                    isdir=lambda p: p in _dirs)
    ok("on Windows the drive whose My Drive holds the hub folder is offered, and no other",
       _win == ["G:\\My Drive\\Creator OS"])
    ok("off Windows the drive letters are not looked at",
       detect_mirror_candidates(home=tempfile.mkdtemp(), osname="posix", drives=["G:\\"],
                                isdir=lambda p: p in _dirs) == [])

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

    # P102: a pass that raises (a ticket locked on a Drive hub) is reported and the loop goes on;
    # Ctrl+C still stops it.
    import contextlib
    import io
    passes, naps = [], []

    def flaky_once(hub_root):
        passes.append(hub_root)
        if len(passes) == 1:
            raise PermissionError(32, "The process cannot access the file because it is being used by "
                                      "another process")
        return [{"status": "done"}]

    def two_naps(seconds):
        naps.append(seconds)
        if len(naps) == 2:
            raise KeyboardInterrupt
    real_once, real_sleep = globals()["once"], time.sleep
    globals()["once"], time.sleep = flaky_once, two_naps
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            watch(hub, interval=30)
        stopped = True
    except BaseException:  # noqa: BLE001 - a Ctrl+C that escapes watch is a failed check here
        stopped = False
    finally:
        globals()["once"], time.sleep = real_once, real_sleep
    ok("a failed pass is reported and the watcher runs the next one; Ctrl+C still stops it",
       stopped and len(passes) == 2 and "pass failed, retrying next interval: PermissionError" in out.getvalue()
       and '"status": "done"' in out.getvalue() and "handoff watcher: stopped" in out.getvalue())

    # P102: Ctrl+C during a pass stops the watcher too, and a pass that raises something other than
    # OSError (a ticket that trips a bug) is reported like a locked one.
    passes_k, naps_k = [], []

    def interrupted_once(hub_root):
        passes_k.append(hub_root)
        if len(passes_k) == 1:
            raise ValueError("an unexpected ticket shape")
        if len(passes_k) == 2:
            raise TypeError("a ticket field of the wrong type")
        raise KeyboardInterrupt

    def bounded_nap(seconds):
        naps_k.append(seconds)
        if len(naps_k) >= 4:  # a watcher that swallowed the Ctrl+C is stopped here, after extra passes
            raise KeyboardInterrupt
    globals()["once"], time.sleep = interrupted_once, bounded_nap
    out_k = io.StringIO()
    try:
        with contextlib.redirect_stdout(out_k):
            watch(hub, interval=30)
        stopped_k = True
    except BaseException:  # noqa: BLE001
        stopped_k = False
    finally:
        globals()["once"], time.sleep = real_once, real_sleep
    ok("passes that raise ValueError and TypeError are reported, and Ctrl+C during the next pass stops "
       "the watcher",
       stopped_k and len(passes_k) == 3 and "pass failed, retrying next interval: ValueError" in out_k.getvalue()
       and "pass failed, retrying next interval: TypeError" in out_k.getvalue()
       and "handoff watcher: stopped" in out_k.getvalue())

    # P102: with stdout redirected to a cp1252 file (a Windows log), main writes a failed pass that
    # names a file with an emoji as UTF-8 instead of ending on UnicodeEncodeError.
    import tempfile as _tf_w
    locked_name = "G:/My Drive/Creator OS/Inbox/Vlog \U0001f3ac.mp4"

    def emoji_once(hub_root):
        raise PermissionError(32, "The process cannot access the file", locked_name)

    def stop_nap(seconds):
        raise KeyboardInterrupt
    real_streams = sys.stdout, sys.stderr
    raw_out, raw_err = io.BytesIO(), io.BytesIO()
    with _tf_w.TemporaryDirectory() as hub_w:
        globals()["once"], time.sleep = emoji_once, stop_nap
        wrapped = (io.TextIOWrapper(raw_out, encoding="cp1252", write_through=True),
                   io.TextIOWrapper(raw_err, encoding="cp1252", write_through=True))
        sys.stdout, sys.stderr = wrapped
        try:
            rc_w = main(["--watch", "--hub", hub_w])
        except BaseException as exc:  # noqa: BLE001
            rc_w = repr(exc)
        finally:
            sys.stdout, sys.stderr = real_streams
            globals()["once"], time.sleep = real_once, real_sleep
            for stream in wrapped:
                stream.flush()
            log_w = raw_out.getvalue().decode("utf-8", errors="replace")
            for stream in wrapped:
                stream.detach()  # leave the buffers open; the wrapper is done
    ok("main logs a failed pass naming an emoji file as UTF-8 when stdout is a cp1252 file",
       rc_w == 0 and locked_name in log_w and "handoff watcher: stopped" in log_w)

    failed = [n for n, c in checks if not c]
    for n, c in checks:
        print(("ok   " if c else "FAIL ") + n)
    print(f"handoff.watcher selftest: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0


def _persist_publish_creds(platform, updated) -> None:
    """Deep-merge a refreshed token into creds[platform]['publish'] in the gitignored credential
    store (the dashboard's _save_publish_creds model, kept local so the watcher never imports the
    wizard)."""
    creds_path = ROOT / "pipeline" / "user-context" / "api-credentials.local.json"
    try:
        with atomic_io.locked(creds_path):
            existed = creds_path.exists()
            current = json.loads(creds_path.read_text(encoding="utf-8")) if existed else {}
            if not isinstance(current, dict):
                current = {}
            plat = current.setdefault(platform, {})
            pub = plat.get("publish")
            if isinstance(pub, dict):
                pub.update(updated)
            else:
                plat["publish"] = dict(updated)
            creds_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_io.atomic_write_text(creds_path, json.dumps(current, indent=2) + "\n")
            if not existed:
                os.chmod(creds_path, 0o600)  # tokens at rest: the wizard's convention for this file
    except (OSError, ValueError) as exc:
        # background path: must not raise, but must not be silent either (P81)
        print(f"[watcher] WARNING: could not persist refreshed {platform} token to "
              f"{creds_path.name}: {exc}", file=sys.stderr)


def api_once() -> dict:
    """Transport B: one Drive API polling pass. Doubly gated (drive_api_polling AND the master
    compute gate, which run_pass re-checks); returns an honest dict, never raises."""
    if not runner.capability_enabled("drive_api_polling"):
        return {"ok": False, "error": "drive_api_polling is off (the default); turn it on at the "
                                      "wizard /drive-hub screen or use the Drive for desktop transport"}
    import oauth_flow
    from handoff import drive_api
    creds_path = ROOT / "pipeline" / "user-context" / "api-credentials.local.json"
    try:
        creds = json.loads(creds_path.read_text(encoding="utf-8")) if creds_path.exists() else {}
    except (OSError, ValueError):
        creds = {}
    pub = (creds.get("google_drive") or {}).get("publish") or {}
    if not pub:
        return {"ok": False, "error": "no Google Drive credential is connected; use the wizard "
                                      "/drive-hub screen to connect one"}
    try:
        token, updated = oauth_flow.get_valid_access_token("google_drive", pub)
        if updated:
            _persist_publish_creds("google_drive", updated)
    except oauth_flow.OAuthError as exc:
        return {"ok": False, "error": f"Drive credential problem: {exc}"}
    staging = ROOT / "pipeline" / "inbox" / "api-staging-hub"
    folder = load_hub_config().get("folder_name", "Creator OS")
    return drive_api.poll_once(str(staging), token, folder)


def main(argv) -> int:
    """The CLI. stdout and stderr write UTF-8 when redirected (env_paths.utf8_stdio, P102), so a
    failed pass that names a file with an emoji is logged instead of ending the watcher."""
    if "--selftest" in argv:
        return selftest()
    env_paths.utf8_stdio()
    if "--transport" in argv and argv[argv.index("--transport") + 1] == "api":
        print(json.dumps(api_once(), indent=2, default=str))
        return 0
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
