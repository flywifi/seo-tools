"""Creator OS real-publishing seam (feature-flagged OFF by default).

The four platform clients here are REAL API implementations: youtube.py
(Data API v3 resumable upload), instagram.py (container -> poll -> media_publish),
tiktok.py (creator_info -> init -> chunked FILE_UPLOAD -> status), pinterest.py
(v5 base64 create-Pin). Each exposes publish(entry, creds) -> {ok, status, post_id,
permalink, error} and obtains/refreshes its token via tools/oauth_flow.py from
creds[platform]["publish"]. See tools/publishing/MAINTAINER_README.md for the
non-negotiable invariants and docs/PUBLISHING.md for the per-platform setup + walls.

The clients are still GATED: no network publish happens unless the
`live_publishing_enabled` capability flag is on (default False) AND the specific
entry has been confirmed by a human. `dispatch()` enforces both gates itself
(defense in depth): it reads the flag from the config it is given, `allow_live`
can only veto (False refuses; True cannot open a gate the flag keeps shut), and an
entry not passed `confirmed=True` is refused. Each refusal is a `gated` or
`unconfirmed` result returned before any client code runs. The Scheduling
Dashboard's background scheduler computes the same gate, passes allow_live=None
and the human-confirm signal, and while the flag is off advances due items to
ready_to_post with no network call.

Human confirmation remains mandatory: dispatch(...) is called with confirmed=True
only for an entry the human has explicitly confirmed, never speculatively.
"""
from __future__ import annotations

import pathlib
import sys

from . import instagram, pinterest, tiktok, youtube

_HERE = pathlib.Path(__file__).resolve().parent
_TOOLS = _HERE.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_CLIENTS = {
    "youtube": youtube,
    "instagram": instagram,
    "tiktok": tiktok,
    "pinterest": pinterest,
}


def _live_publishing_enabled(config):
    """Read the master gate. Lazy import (publishing_compliance imports nothing from
    this package, so there is no cycle). Default OFF when config is None."""
    import publishing_compliance
    return publishing_compliance.live_publishing_enabled(config)


def dispatch(platform: str, entry: dict, creds: dict, *, config=None,
             allow_live=None, confirmed: bool = False, persist=None) -> dict:
    """Route a human-confirmed queue entry to its platform client's publish().

    Defense in depth: the network gate and the human-confirmation requirement are
    enforced HERE, not only by the caller:
      - config: the gate is publishing_compliance.live_publishing_enabled(config),
        read on every call (default OFF; config=None reads the committed config plus
        the gitignored local override).
      - allow_live: a veto only. False refuses even with the flag on; None or True
        defer to the flag, so a caller cannot open a gate the flag keeps shut.
      - confirmed: must be True (the caller asserts a human confirmed THIS entry).
      - persist: forwarded to the client so a token refresh/rotation is saved.
      - creds: the FULL {platform: {...}} credentials map -- each client re-indexes
        creds[platform]['publish'], so the caller must pass the whole map, not a
        per-platform sub-dict.

    Returns the client's {ok, status, post_id, permalink, error}, or a
    gated/unconfirmed refusal dict. Raises ValueError for an unknown platform.
    """
    client = _CLIENTS.get((platform or "").strip().lower())
    if client is None:
        raise ValueError(f"No publishing client for platform '{platform}'")
    live = _live_publishing_enabled(config) and allow_live is not False
    if not live:
        return {"ok": False, "status": "gated", "post_id": None, "permalink": None,
                "error": "live_publishing_enabled is off; dispatch made no network call."}
    if confirmed is not True:
        return {"ok": False, "status": "unconfirmed", "post_id": None, "permalink": None,
                "error": "dispatch requires explicit human confirmation (confirmed=True)."}
    return client.publish(entry, creds, persist=persist)


def _selftest() -> int:
    """Offline: dispatch's structural gate + confirm requirement. No network, and every call
    passes its config explicitly, so no local config file changes the result."""
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # Every dispatch call passes its config explicitly, so the result never depends on the
    # gitignored creator-os-config.local.json of the machine running it. A tripwire stands in for
    # load_config() for the whole run, and a final pin fails if any call reached it.
    import publishing_compliance
    OFF = {"capabilities": {}}
    ON = {"capabilities": {"live_publishing_enabled": True}}
    config_reads = []
    real_load_config = publishing_compliance.load_config

    def _load_config_tripwire():
        config_reads.append(1)
        return {}

    publishing_compliance.load_config = _load_config_tripwire
    sentinel = {"youtube": {"publish": {"access_token": "AT", "expires_at": 4102444800}}}
    r_gated = dispatch("youtube", {}, sentinel, config=OFF, allow_live=False, confirmed=True)
    ok("flag off -> gated, no client call", r_gated.get("status") == "gated")
    r_unconf = dispatch("youtube", {}, sentinel, config=ON, allow_live=True, confirmed=False)
    ok("live but not confirmed -> unconfirmed", r_unconf.get("status") == "unconfirmed")
    try:
        dispatch("vimeo", {}, {}, config=ON, allow_live=True, confirmed=True)
        ok("unknown platform raises ValueError", False)
    except ValueError:
        ok("unknown platform raises ValueError", True)
    # No allow_live: dispatch reads the flag from the config it is given (off) -> gated.
    r_default = dispatch("youtube", {}, sentinel, config=OFF, confirmed=True)
    ok("no allow_live: dispatch reads the flag from the config it is given (off) -> gated",
       r_default.get("status") == "gated")

    # The property, not the status string: a recording client stands in for the real
    # one, so "no network call while the flag is off" is observed rather than inferred from the
    # refusal; the flag-on control proves the probe can see a call at all.
    calls = []

    class _Recorder:
        @staticmethod
        def publish(*args, **kwargs):
            calls.append(args)
            return {"ok": True, "status": "published", "post_id": "X", "permalink": None,
                    "error": None}

    # The property, observed at the network: outbound calls are recorded at urllib.request.urlopen
    # and socket.create_connection (and refused), with credentials and entries complete enough
    # that a client that is reached really would connect.
    import os
    import socket
    import urllib.request
    media = os.path.abspath(__file__)
    full = {p: {"publish": {"access_token": "AT", "expires_at": 4102444800}} for p in _CLIENTS}
    full["instagram"]["ig_user_id"] = "1"
    entry = {"media_path": media, "image_path": media, "board_id": "board1",
             "image_url": "https://example.invalid/x.jpg"}
    net = []

    def _urlopen(req, *args, **kwargs):
        net.append(getattr(req, "full_url", req))
        raise OSError("selftest: network refused")

    def _connect(address, *args, **kwargs):
        net.append(address)
        raise OSError("selftest: network refused")

    def _status(platform, **kwargs):
        try:
            return dispatch(platform, dict(entry), full, confirmed=True, **kwargs).get("status")
        except Exception as exc:  # noqa: BLE001 - a refused connection surfaces as an error
            return "raised " + type(exc).__name__

    saved = (urllib.request.urlopen, socket.create_connection)
    urllib.request.urlopen, socket.create_connection = _urlopen, _connect
    try:
        gated = [_status(p, config={"capabilities": {}}, allow_live=a)
                 for p in sorted(_CLIENTS) for a in (False, None)]
        ok("flag off: no network call on any platform, observed at urlopen and socket",
           net == [] and gated == ["gated"] * 8)
        _status("youtube", allow_live=True, config={"capabilities": {"live_publishing_enabled": True}})
        ok("flag on and confirmed: the network recorder sees the upload attempt (the probe sees calls)",
           len(net) >= 1)
    finally:
        urllib.request.urlopen, socket.create_connection = saved

    real = _CLIENTS["youtube"]
    _CLIENTS["youtube"] = _Recorder
    try:
        dispatch("youtube", {}, sentinel, config=OFF, allow_live=False, confirmed=True)
        ok("flag off: the platform client is never called, so no network call is made",
           calls == [])
        dispatch("youtube", {}, sentinel, config={"capabilities": {}}, allow_live=True, confirmed=True)
        ok("allow_live=True cannot open the gate while the flag is off", calls == [])
        dispatch("youtube", {}, sentinel, config={"capabilities": {"live_publishing_enabled": True}},
                 allow_live=False, confirmed=True)
        ok("allow_live=False vetoes a flag that is on -> gated", calls == [])
        dispatch("youtube", {}, sentinel, config=ON, allow_live=True, confirmed=True)
        ok("flag on and confirmed: the recording client is reached (the probe sees calls)",
           len(calls) == 1)
    finally:
        _CLIENTS["youtube"] = real

    publishing_compliance.load_config = real_load_config
    ok("the dispatch selftest reads no local config: every call passes its config explicitly",
       config_reads == [])

    failed = [n for n, c in checks if not c]
    for n, c in checks:
        print(("ok   " if c else "FAIL ") + n)
    print(f"dispatch selftest: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0

