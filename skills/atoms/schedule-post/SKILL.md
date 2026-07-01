---
name: schedule-post
atom: true
description: "Queues or schedules a single piece of content to a social platform via the active publishing connector (direct platform API) and returns the post ID and status. Falls back to publish-draft (manual mode) when no content_publishing connector is active. Do NOT use for content creation — use caption-write or pin-write first; do NOT use to check post status after publishing — use post-status instead."
engines_required:
  - shared/platform-engine.md
  - shared/integrations-engine.md
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# schedule-post

## When to use this atom

Trigger phrases: "schedule this post," "queue to Instagram," "publish to TikTok," "post to Pinterest," "upload to YouTube," "set a publish time," "schedule for Tuesday," "put this in the queue."

Use when: the creator has finalized content (caption, media URL, hashtags) and wants to queue or schedule it to one platform. The calling spoke (content-distributor) invokes this atom once per platform per post.

Do NOT use for:
- Writing captions or hashtags — use caption-write or hashtag-set first.
- Checking whether a post went live after scheduling — use post-status.
- Formatting content for manual copy-paste without a connector — use publish-draft.
- Batch multi-platform scheduling in one call — the content-distributor spoke loops this atom per platform.

## Inputs

Required:
- `platform` (string): `instagram | tiktok | pinterest | youtube`
- `caption` (string): final caption text (must already include FTC disclosure if required)
- `content_type` (string): `reel | short | pin | video | carousel | photo`

Optional:
- `media_url` (string): publicly accessible URL to the media file (required for direct API tier)
- `scheduled_datetime` (string): ISO 8601 datetime; null = post immediately when connector supports it
- `hashtags` (array of string): appended to caption if not already present
- `ftc_disclosure` (string): `#ad | #gifted | #affiliate | null` — if non-null, atom verifies the disclosure appears in caption before queuing
- `is_aigc` (boolean): if true and platform is tiktok, AIGC flag is set on the post
- `board_name` (string): Pinterest board name (required for Pinterest)
- `thumbnail_url` (string): YouTube custom thumbnail URL (optional)

Retrieved automatically:
- Active publishing connector and tier from connector registry (via integrations-engine.md)
- Platform media spec constraints (via platform-engine.md) to validate content_type against platform rules

## Core procedure

### Step 1: Connector resolution
Check which `content_publishing` connectors are active:
1. Per-platform direct API — check the platform-specific publishing flag (`youtube_publishing`, `instagram_publishing`, `tiktok_publishing`, `pinterest_publishing`)
2. Manual fallback — if no connector is active, fall back to publish-draft behavior inline

### Step 2: Compliance check (before any connector call)
- FTC disclosure: if `ftc_disclosure` is non-null, verify the disclosure string is present in `caption`. If absent, prepend it and note the addition in `notes`.
- AIGC flag: if `is_aigc: true` and `platform: tiktok`, set the AIGC flag in the payload. Log in output.
- Cross-platform watermark rule: if `content_type` is `reel` or `short`, flag if the content was sourced from a competing platform (watermarked content is penalized on Instagram and TikTok).

### Step 3: Human confirmation gate
Return a confirmation summary BEFORE queuing. The caller (content-distributor spoke or the creator directly) must confirm before the atom sends to any connector. `human_review_required: true` is always set in output.

### Step 4: Connector call (post-confirmation only)
Call the resolved connector:
- **YouTube direct API**: initiate resumable upload to Data API v3, set `status.publishAt` if scheduled_datetime is provided
- **Instagram direct API**: POST to `/{ig-user-id}/media` (container), poll `status_code`, then POST to `/{ig-user-id}/media_publish`
- **TikTok direct API**: POST to `/v2/post/publish/video/init/`, upload chunk, set `is_aigc` flag if required
- **Pinterest direct API**: POST to `/v5/pins` with `scheduled_at` if scheduled_datetime is provided; include `board_name`
- **Manual fallback**: invoke publish-draft behavior — return formatted caption, hashtag block, posting checklist

### Step 5: Error handling
On connector error: return `status: failed`, populate `error` with the connector message, do NOT retry automatically. Surface to creator for human decision.

## Output contract

```json
{
  "platform": "instagram | tiktok | pinterest | youtube",
  "post_id": "string or null",
  "status": "queued | scheduled | draft | failed | manual_required",
  "scheduled_datetime": "ISO 8601 or null",
  "permalink": "string or null",
  "publishing_tier": "direct_api | manual",
  "connector_used": "youtube_publishing | instagram_publishing | tiktok_publishing | pinterest_publishing | none",
  "ftc_disclosure_verified": "boolean",
  "aigc_flag_set": "boolean",
  "human_review_required": true,
  "error": "string or null",
  "notes": "string or null"
}
```

`human_review_required` is always true. The creator must confirm before the atom sends to any connector.

When `publishing_tier: manual`:
- `status` is `manual_required`
- `post_id` and `permalink` are null
- `notes` contains a brief posting checklist for the platform

## Engines and protocols loaded

- `shared/platform-engine.md` — platform media specs, content type validation, rate limits
- `shared/integrations-engine.md` — publishing endpoint specs, connector resolution, FTC/AIGC rules
- `protocols/safety.md` — FTC disclosure requirements
- `protocols/no-fabrication.md` — never invent post_id or permalink
- `protocols/formatting-metadata.md` — no em dashes in caption output

## Standalone usability

When invoked directly without the content-distributor spoke, accepts caption and platform and returns either a queued post confirmation or a manual posting checklist — useful for one-off scheduling without running the full distribution workflow.

## Failure modes

- **No connector active**: gracefully falls back to manual mode; returns `publishing_tier: manual` and `status: manual_required`. Never fails silently.
- **FTC disclosure missing**: atom adds the disclosure and flags the addition; does not block posting.
- **Media URL missing for direct API tier**: returns `status: failed` with a note that media_url is required for the direct API path.
- **Platform rate limit hit**: returns `status: failed` with the rate limit message from the connector. TikTok Content Posting API rate limit is 6 requests per minute; Pinterest Pins API write limit is 100 per minute.
- **AIGC flag omitted on TikTok for AI-generated content**: atom auto-sets the flag when `is_aigc: true` is passed. If the caller does not pass `is_aigc`, the atom cannot detect AI content and the flag is omitted — document this in `notes`.
