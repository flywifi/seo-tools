"""YouTube publishing client (STUB — feature-flagged off).

When live publishing is implemented, this module will perform a YouTube Data API
v3 resumable upload:
  1. POST https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable
     &part=snippet,status  with Authorization: Bearer {oauth_access_token}
     (obtained via the wizard's /oauth/youtube/callback code-for-token exchange;
     requires the youtube.upload scope and a stored refresh_token).
  2. PUT the video bytes to the returned upload URL.
  3. Set status.publishAt (RFC 3339) for native scheduling, or publish immediately.

Required credential fields (api-credentials.local.json -> "youtube"):
  client_id, client_secret, refresh_token (or a live access_token).
Returns {post_id, permalink, status} on success once implemented.
"""
from __future__ import annotations


def publish(entry: dict, creds: dict) -> dict:
    raise NotImplementedError(
        "YouTube live publishing is not enabled. Set live_publishing_enabled: true "
        "and implement the Data API v3 resumable upload here (see module docstring)."
    )
