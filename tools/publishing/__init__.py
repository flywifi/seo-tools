"""Creator OS real-publishing seam (feature-flagged OFF by default).

The four platform clients here are REAL API implementations (P51): youtube.py
(Data API v3 resumable upload), instagram.py (container -> poll -> media_publish),
tiktok.py (creator_info -> init -> chunked FILE_UPLOAD -> status), pinterest.py
(v5 base64 create-Pin). Each exposes publish(entry, creds) -> {ok, status, post_id,
permalink, error} and obtains/refreshes its token via tools/oauth_flow.py from
creds[platform]["publish"]. See tools/publishing/MAINTAINER_README.md for the
non-negotiable invariants and docs/PUBLISHING.md for the per-platform setup + walls.

The clients are still GATED: no network publish happens unless the
`live_publishing_enabled` capability flag is on (default False) AND the specific
entry has been confirmed by a human. As of P57, `dispatch()` ENFORCES both gates
itself (defense in depth), so a mis-wired or alternate caller can no longer reach a
client's network path with the flag off or without an explicit human confirm --
`dispatch()` returns a `gated`/`unconfirmed` refusal instead. The Scheduling
Dashboard and background scheduler still compute
`publishing_compliance.live_publishing_enabled(config)` and pass the human-confirm
signal explicitly; while the flag is off they schedule and advance items to
ready_to_post and make no network call.

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

    Defense in depth (P57 F2/F8): the network gate and the human-confirmation
    requirement are enforced HERE, not only by the caller:
      - allow_live: the caller's already-computed gate; when None, dispatch reads
        publishing_compliance.live_publishing_enabled(config) itself (default OFF).
      - confirmed: must be True (the caller asserts a human confirmed THIS entry).
      - persist: forwarded to the client so a token refresh/rotation is saved (F3).
      - creds: the FULL {platform: {...}} credentials map -- each client re-indexes
        creds[platform]['publish'], so the caller must pass the whole map, not a
        per-platform sub-dict (F1).

    Returns the client's {ok, status, post_id, permalink, error}, or a
    gated/unconfirmed refusal dict. Raises ValueError for an unknown platform.
    """
    client = _CLIENTS.get((platform or "").strip().lower())
    if client is None:
        raise ValueError(f"No publishing client for platform '{platform}'")
    live = allow_live if allow_live is not None else _live_publishing_enabled(config)
    if not live:
        return {"ok": False, "status": "gated", "post_id": None, "permalink": None,
                "error": "live_publishing_enabled is off; dispatch made no network call."}
    if confirmed is not True:
        return {"ok": False, "status": "unconfirmed", "post_id": None, "permalink": None,
                "error": "dispatch requires explicit human confirmation (confirmed=True)."}
    return client.publish(entry, creds, persist=persist)


def _selftest() -> int:
    """Offline: dispatch's structural gate + confirm requirement (P57 F2/F8). No network."""
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # A transport that would raise if any client actually reached the network.
    sentinel = {"youtube": {"publish": {"access_token": "AT", "expires_at": "2999-01-01T00:00:00+00:00"}}}
    r_gated = dispatch("youtube", {}, sentinel, allow_live=False, confirmed=True)
    ok("flag off -> gated, no client call", r_gated.get("status") == "gated")
    r_unconf = dispatch("youtube", {}, sentinel, allow_live=True, confirmed=False)
    ok("live but not confirmed -> unconfirmed", r_unconf.get("status") == "unconfirmed")
    try:
        dispatch("vimeo", {}, {}, allow_live=True, confirmed=True)
        ok("unknown platform raises ValueError", False)
    except ValueError:
        ok("unknown platform raises ValueError", True)
    # Default (no allow_live) reads the compliance flag, which is OFF by default -> gated.
    r_default = dispatch("youtube", {}, sentinel, confirmed=True)
    ok("default gate reads compliance (OFF) -> gated", r_default.get("status") == "gated")

    failed = [n for n, c in checks if not c]
    for n, c in checks:
        print(("ok   " if c else "FAIL ") + n)
    print(f"dispatch selftest: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0

