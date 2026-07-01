---
name: post-status
atom: true
description: "Checks the current status of a scheduled or published post via the active publishing connector and returns the platform status, permalink, and an engagement snapshot if available. Falls back to a manual check prompt when no publishing connector is active. Do NOT use to schedule or queue a new post — use schedule-post; do NOT use for historical analytics over a time range — use analytics-insights."
engines_required:
  - shared/integrations-engine.md
protocols:
  - protocols/no-fabrication.md
---

# post-status

## When to use this atom

Trigger phrases: "did my posts go live," "check if it published," "what's the status of my TikTok post," "is the pin live," "show me the post link," "check my scheduled video," "did the Instagram reel go up."

Use when: the creator wants to verify whether a previously scheduled post has published successfully and optionally see an early engagement snapshot.

Do NOT use for:
- Scheduling a new post — use schedule-post.
- Deep analytics over a time range (views, retention, revenue) — use analytics-insights.
- Bulk status checks across many posts at once — call this atom once per post_id.

## Inputs

Required:
- `platform` (string): `instagram | tiktok | pinterest | youtube`
- `post_id` (string): the post_id returned by schedule-post when the post was queued

Optional:
- `include_engagement_snapshot` (boolean): if true and the connector supports it, return current views/likes/saves/shares. Defaults false to avoid unnecessary API calls.

Retrieved automatically:
- Active connector for the platform (via integrations-engine.md)

## Core procedure

### Step 1: Connector resolution
Determine which connector handles the given platform:
1. Direct platform API — call the platform's status endpoint:
   - Instagram: `GET /{ig-container-id}?fields=status_code` then `GET /{ig-media-id}?fields=permalink`
   - TikTok: check via Display API or Content Posting API status poll
   - Pinterest: `GET /v5/pins/{pin_id}?fields=id,link,created_at`
   - YouTube: `GET /youtube/v3/videos?part=status,statistics&id={video_id}`
2. No connector: return `status: unknown` with manual check instructions

### Step 2: Status fetch
Call the resolved connector. Map platform-native status codes to the Creator OS status vocabulary:
- `published` — post is live and publicly accessible
- `scheduled` — post is queued for a future datetime
- `processing` — upload or render is in progress (common for video on YouTube and Instagram)
- `failed` — connector or platform returned an error
- `draft` — saved but not yet submitted for publishing
- `unknown` — no connector active or post_id not found

### Step 3: Engagement snapshot (if requested)
If `include_engagement_snapshot: true` and the connector supports read access, retrieve:
- Instagram: `GET /{ig-media-id}/insights?metric=views,reach,saved,shares`
- TikTok: video stats from Research API or Display API (if available; Research API is institution-only)
- Pinterest: pin saves (strongest Pinterest signal) and click-throughs
- YouTube: `GET /youtube/v3/videos?part=statistics` (viewCount, likeCount, commentCount)

Never fabricate engagement numbers. If data is unavailable, return `engagement_snapshot: null` with a note.

### Step 4: Permalink assembly
If `status: published`, return the direct link to the post:
- Instagram: `https://www.instagram.com/p/{shortcode}/`
- TikTok: `https://www.tiktok.com/@{username}/video/{video_id}`
- Pinterest: `https://www.pinterest.com/pin/{pin_id}/`
- YouTube: `https://www.youtube.com/watch?v={video_id}`

If the permalink is not yet available (processing), return null and note that the link will be available once processing completes.

## Output contract

```json
{
  "platform": "instagram | tiktok | pinterest | youtube",
  "post_id": "string",
  "status": "published | scheduled | processing | failed | draft | unknown",
  "permalink": "string or null",
  "published_at": "ISO 8601 or null",
  "scheduled_for": "ISO 8601 or null",
  "engagement_snapshot": {
    "views": "number or null",
    "likes": "number or null",
    "saves": "number or null",
    "shares": "number or null",
    "comments": "number or null"
  },
  "connector_used": "direct_api | none",
  "error": "string or null",
  "notes": "string or null"
}
```

`engagement_snapshot` is `null` when `include_engagement_snapshot` is false or data is unavailable. Counts are `null` individually when the connector does not expose that metric — never zero-filled.

## Engines and protocols loaded

- `shared/integrations-engine.md` — platform status endpoints, connector resolution, API field paths
- `protocols/no-fabrication.md` — never invent status, permalink, or engagement numbers

## Standalone usability

When no connector is active, returns `status: unknown` and a platform-specific manual check URL pattern so the creator can verify the post themselves.

## Failure modes

- **No connector active**: returns `status: unknown`, includes a note with the direct URL pattern to check on the platform natively.
- **post_id not found**: returns `status: unknown` with the connector's not-found message. The post_id may be from a different connector session or may have been deleted.
- **Processing timeout**: YouTube videos and Instagram Reels can take minutes to hours to process. If `status: processing` is returned, advise the creator to check again in 5 to 30 minutes.
- **Engagement data unavailable**: TikTok Research API is restricted to academic institutions. If the direct connector is not active, `engagement_snapshot` is null. Never substituted with estimates.
- **Platform API deprecation**: Instagram deprecated `clips_replays_count` and `impressions` in API v22.0+ (April 2025). If the connector returns a deprecation error for a metric, that metric is null in the snapshot and the deprecation is noted.
