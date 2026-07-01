"""Creator OS real-publishing seam (feature-flagged OFF by default).

This package is the drop-in point for actual platform API publishing. Today it is
DARK: every client's publish() raises NotImplementedError, and no caller invokes
it while the `live_publishing_enabled` capability flag is False (the default).

The Scheduling Dashboard and the background scheduler check
`publishing_compliance.live_publishing_enabled(config)` before ever reaching a
publish() call, so the honest scaffold (compliance checks + queue status only, no
network) is the shipped behavior. When a future phase enables live publishing,
implement the four clients below and the wiring is already in place.

Human confirmation remains mandatory: dispatch(...) must only be called for an
entry the human has explicitly confirmed (status set by the dashboard confirm
click), never speculatively.
"""
from __future__ import annotations

from . import instagram, pinterest, tiktok, youtube

_CLIENTS = {
    "youtube": youtube,
    "instagram": instagram,
    "tiktok": tiktok,
    "pinterest": pinterest,
}


def dispatch(platform: str, entry: dict, creds: dict) -> dict:
    """Route a human-confirmed queue entry to its platform client's publish().

    Raises NotImplementedError while the clients are stubs. Callers MUST gate this
    behind publishing_compliance.live_publishing_enabled(config) and an explicit
    human-confirmation status; this function does not re-check either.
    """
    client = _CLIENTS.get((platform or "").strip().lower())
    if client is None:
        raise ValueError(f"No publishing client for platform '{platform}'")
    return client.publish(entry, creds)
