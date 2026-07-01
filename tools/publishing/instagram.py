"""Instagram publishing client (STUB — feature-flagged off).

When live publishing is implemented, this module will perform the Instagram Graph
API v25.0 two-step Reels publish:
  1. POST /{ig-user-id}/media  with media_type=REELS, video_url, caption
     -> returns a creation_id (container).
  2. Poll GET /{ig-container-id}?fields=status_code until FINISHED.
  3. POST /{ig-user-id}/media_publish  with creation_id=<container>.
  Auth: Authorization via a long-lived access_token; rate limit 100 posts/24h.

Required credential fields (api-credentials.local.json -> "instagram"):
  access_token, account_id (the IG Business user id).
Returns {post_id, permalink, status} on success once implemented.
"""
from __future__ import annotations


def publish(entry: dict, creds: dict) -> dict:
    raise NotImplementedError(
        "Instagram live publishing is not enabled. Set live_publishing_enabled: true "
        "and implement the Graph API container->publish flow here (see module docstring)."
    )
