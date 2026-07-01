"""Pinterest publishing client (STUB — feature-flagged off).

When live publishing is implemented, this module will create a Pin via the
Pinterest API v5:
  - Image pin:  POST /v5/pins  with board_id, media_source (image_url), title,
    description, link.
  - Video pin:  POST /v5/media (register) -> upload to the returned AWS S3 target
    -> POST /v5/pins with the media_id.
  Auth: Authorization: Bearer {access_token}; scopes pins:write, boards:write;
  write rate limit 100/min.

Required credential fields (api-credentials.local.json -> "pinterest"):
  access_token. The target board is taken from the queue entry (board_name/board_id).
Returns {post_id, permalink, status} on success once implemented.
"""
from __future__ import annotations


def publish(entry: dict, creds: dict) -> dict:
    raise NotImplementedError(
        "Pinterest live publishing is not enabled. Set live_publishing_enabled: true "
        "and implement the API v5 create-pin flow here (see module docstring)."
    )
