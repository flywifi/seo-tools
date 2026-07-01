"""TikTok publishing client (STUB — feature-flagged off).

When live publishing is implemented, this module will perform a TikTok Content
Posting API direct post:
  1. POST https://open.tiktokapis.com/v2/post/publish/video/init/
     with post_info (caption, privacy, disclosure), source_info, and
     post_info.is_aigc set from the queue entry's AIGC flag.
  2. PUT the video bytes to the returned upload_url (open-upload.tiktokapis.com).
  3. Poll publish status until the post completes.
  Auth: Authorization: Bearer {access_token}; scope video.publish;
  rate limit 6 req/min per user token. TikTok has NO native scheduled_at, so the
  dashboard's background scheduler dispatches at the scheduled time.

Required credential fields (api-credentials.local.json -> "tiktok"):
  client_key, client_secret, access_token.
Returns {post_id, permalink, status} on success once implemented.
"""
from __future__ import annotations


def publish(entry: dict, creds: dict) -> dict:
    raise NotImplementedError(
        "TikTok live publishing is not enabled. Set live_publishing_enabled: true "
        "and implement the Content Posting init->upload->publish flow here "
        "(see module docstring). Honor post_info.is_aigc for AI-generated content."
    )
