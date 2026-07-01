---
name: content-distributor
description: "Orchestrates multi-platform content scheduling and distribution — takes finalized content (or produces captions and hashtags on demand) and queues or schedules posts across up to 4 platforms via the active publishing connector, with human confirmation required before every post. Do NOT use to create content from scratch — run video-development or shortform-repurposing first; do NOT use for analytics on previously published posts — use analytics-insights."
---

# content-distributor

## When to use this spoke

Trigger phrases: "schedule my content," "post this across platforms," "distribute this week's content," "queue everything up," "get this live on Instagram and TikTok," "schedule my short-form package," "post to all platforms," "set up my publishing queue."

Use when: the creator has finalized content (from a prior shortform-repurposing or video-development run, or by pasting captions directly) and wants to schedule or queue it to multiple platforms.

Do NOT use for:
- Creating captions or video concepts from scratch — use shortform-repurposing or video-development first, then return here to distribute.
- Reviewing analytics on previously published posts — use analytics-insights.
- Formatting content for manual copy-paste to a single platform without queuing — use publish-draft directly.
- Checking status of already-queued posts — use post-status directly.

## Inputs

The spoke accepts content in two modes:

**Mode A — Content already produced (typical path from shortform-repurposing):**
- `captions` (object): keyed by platform — `{ "instagram": "...", "tiktok": "...", "pinterest": "...", "youtube": "..." }`
- `hashtags` (object): keyed by platform — can be null per platform (atom will generate if absent)
- `platform_targets` (array): platforms to distribute to (default: all platforms with content provided)

**Mode B — Content not yet produced (spoke writes captions):**
- `content_brief` (string): the source content (title, concept, or short-form hook)
- `platform_targets` (array): which platforms to produce and distribute to

Both modes accept:
- `scheduled_datetimes` (object): keyed by platform — ISO 8601 or null (post ASAP)
- `ftc_disclosures` (object): keyed by platform — `#ad | #gifted | #affiliate | null` per platform
- `is_aigc` (boolean): if true, AIGC flag is set for TikTok posts
- `board_names` (object): Pinterest board names keyed by board platform (for Pinterest)
- `media_urls` (object): keyed by platform — required for direct API tier, optional for Postiz/Buffer

## Core procedure

Follow `shared/method.md`.

### Step 1: Connector resolution
Check `get_publishing_plan` (via integrations-engine.md) to determine which publishing tier is available per platform. Show the creator a publishing plan before proceeding:
- Which platforms have an active connector and at what tier (hosted_mcp / direct_api / manual)
- Which platforms will fall back to manual mode (no connector)

### Step 2: Caption and hashtag preparation (skip if Mode A and all captions provided)
- If any platform lacks a caption, invoke caption-write for that platform.
- If any platform lacks hashtags, invoke hashtag-set for that platform.
- Steps 1 and 2 are skipped when the spoke receives pre-written captions from shortform-repurposing. The spoke checks whether captions are provided before running caption-write.

### Step 3: Schedule posts (per platform, repeat)
For each platform in `platform_targets`:
1. Invoke schedule-post with the finalized caption, hashtags, media_url, scheduled_datetime, ftc_disclosure, is_aigc, and board_name for that platform.
2. schedule-post runs the FTC/AIGC compliance check and returns a confirmation summary.
3. Human confirmation required before schedule-post sends to any connector. Present the full confirmation table to the creator before proceeding.
4. After confirmation, schedule-post queues to the connector and returns post_id, status, and permalink (or manual_required if no connector is active).

### Step 4: Status check (optional, post-confirmation)
After all posts are queued, offer to run post-status for any post_id where the connector returned `status: processing`. Remind the creator to check back after processing completes.

### Step 5: Govern artifact
Run govern-artifact with gates: integrity (FTC disclosures verified, AIGC flags applied), safety (no prohibited content patterns), brand_alignment (captions match voice and platform conventions).

## Output contract

```json
{
  "distribution_summary": {
    "total_platforms": "number",
    "queued": "number",
    "manual_required": "number",
    "failed": "number"
  },
  "posts": [
    {
      "platform": "string",
      "post_id": "string or null",
      "status": "queued | scheduled | manual_required | failed",
      "scheduled_datetime": "ISO 8601 or null",
      "permalink": "string or null",
      "publishing_tier": "hosted_mcp | direct_api | manual",
      "ftc_disclosure": "string or null",
      "is_aigc": "boolean",
      "human_review_required": true,
      "error": "string or null"
    }
  ],
  "manual_posting_packages": [
    {
      "platform": "string",
      "formatted_caption": "string",
      "hashtag_block": "string",
      "posting_checklist": ["string"],
      "media_specs": {}
    }
  ],
  "next_steps": ["string"],
  "govern_artifact_result": {}
}
```

`human_review_required: true` on every post entry. `manual_posting_packages` is populated for every platform that returned `status: manual_required`.

## Engines and protocols loaded

- `shared/platform-engine.md` — per-platform specs, character limits, hashtag caps
- `shared/integrations-engine.md` — connector resolution and publishing endpoint specs
- `shared/brand-engine.md` — caption voice validation (when caption-write is invoked in Step 2)
- `protocols/safety.md` — FTC/AIGC compliance
- `protocols/no-fabrication.md` — never invent post_id or permalink
- `protocols/formatting-metadata.md` — no em dashes in any caption output

## Atoms used

Workflow atoms (invoked by spoke steps):
- `caption-write` (Step 2, conditional — only if captions not provided)
- `hashtag-set` (Step 2, conditional — only if hashtags not provided)
- `schedule-post` (Step 3, per platform)
- `post-status` (Step 4, optional)
- `govern-artifact` (Step 5)

Shortcut atoms (callable directly, bypassing full workflow):
- `schedule-post` — queue a single post to one platform
- `publish-draft` — format content for manual copy-paste to one platform
- `post-status` — check status of a previously queued post

## Standalone usability

When no connector is active, produces a full manual posting package (via publish-draft fallback) for every platform — paste-ready captions, hashtag blocks, numbered checklists, and media spec reminders — with no API credentials or infrastructure required.

## Failure modes

- **No connector active for any platform**: every post returns `status: manual_required`; full manual_posting_packages generated for all platforms. Distribution continues; nothing blocks.
- **Partial connector failure**: some platforms queue successfully, others fail. The distribution_summary shows the breakdown; the creator sees exactly which platforms need manual action.
- **Caption generation failure (Step 2)**: if caption-write cannot produce a caption for a platform, that platform is skipped and noted in `next_steps`.
- **FTC disclosure missing**: schedule-post prepends the disclosure and flags it; govern-artifact verifies before completing.
- **Govern-artifact gate failure**: if a post fails the integrity or safety gate, the post is not queued and the creator is shown the gate failure reason.
