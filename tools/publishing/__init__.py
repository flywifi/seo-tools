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
entry has been confirmed by a human. The clients do NOT self-check either gate --
callers must. The Scheduling Dashboard and the background scheduler check
`publishing_compliance.live_publishing_enabled(config)` (and the per-post human
confirm) before ever reaching dispatch(); while the flag is off they schedule and
advance items to ready_to_post and make no network call.

Human confirmation remains mandatory: dispatch(...) must only be called for an
entry the human has explicitly confirmed, never speculatively.
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

    Returns the client's {ok, status, post_id, permalink, error} result. Callers MUST
    gate this behind publishing_compliance.live_publishing_enabled(config) and an
    explicit human-confirmation status; this function does not re-check either.
    """
    client = _CLIENTS.get((platform or "").strip().lower())
    if client is None:
        raise ValueError(f"No publishing client for platform '{platform}'")
    return client.publish(entry, creds)
