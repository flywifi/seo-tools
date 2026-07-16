---
file: skills/atoms/post-status/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for post-status so it stays stable under iteration.
---

# post-status: Maintainer README

## Purpose
This atom checks the current status of a single previously scheduled post via the active publishing connector and returns platform status, permalink, and an optional early engagement snapshot. It is called after schedule-post queues a post when the creator wants to confirm it went live. Its job ends when it returns the current status — it does not reschedule, retry, or modify the post.

## Non-negotiable invariants
- Never fabricate status, permalink, or engagement numbers. If data is unavailable, return null and note.
- `engagement_snapshot` counts must be null (not zero) when the metric is genuinely unavailable. Zero and null have different meanings — null means "did not retrieve," zero means "no engagement recorded."
- `status: unknown` is the correct return when no connector is active. Never guess or infer status from context.
- The status vocabulary is fixed: `published | scheduled | processing | failed | draft | unknown`. No custom values.
- Permalink format must match the platform's canonical URL pattern. Never construct a URL from parts that have not been confirmed by the connector.

## Known failure modes
- No connector active: `status: unknown`; include manual check URL pattern in `notes`.
- post_id not found: `status: unknown` with connector's not-found message.
- Video still processing (YouTube, Instagram): `status: processing`; advise creator to retry in 5 to 30 minutes.
- TikTok engagement data: Research API is institution-only. If no direct connector, `engagement_snapshot` is null.
- Deprecated Instagram metrics (v22.0+): `clips_replays_count`, `impressions` return deprecation errors. These fields are null and the deprecation is noted.

## Fragile fallbacks that must not become defaults
- `status: unknown` with manual check guidance is acceptable when no connector is active. It must never be the return when a connector is configured but returns an unexpected response — surface the actual connector error in `error`.

## Regression cases to preserve (mapped to evals/evals.json)
1. Published post with direct API active → `status: published`, `permalink` populated
2. Scheduled future post → `status: scheduled`, `scheduled_for` populated, `published_at` null
3. Processing video (YouTube) → `status: processing`, `permalink` null, note with retry guidance
4. Failed post → `status: failed`, `error` populated
5. No connector active → `status: unknown`, `notes` includes manual check URL pattern
6. Engagement snapshot requested → `engagement_snapshot` fields populated (or null per metric if unavailable)
7. Deprecated Instagram metric → null in snapshot with deprecation note

## Approval-gated changes
- Changes to the status vocabulary (any new value or rename requires updates to schedule-post and content-distributor spoke)
- Changes to permalink URL patterns per platform (source from platform announcements, not assumptions)
- Any change to `engagement_snapshot` field names

## Minority-report policy
If the connector returns a status that does not map cleanly to the vocabulary (e.g., "pending_review" on TikTok), map to the nearest safe value (`processing`) and include the raw connector status string in `notes`. Never invent a new status value without an approval-gated change.

## Update checklist
1. Run `python3 tools/sync_check.py` — all 51 invariants must pass.
2. Verify path references: `shared/integrations-engine.md`, `protocols/no-fabrication.md`.
3. After any Instagram Graph API version change (e.g., metric deprecations), update the Failure modes section and `shared/integrations-engine.md` first.
4. After any platform permalink URL format change, update the Core procedure Step 4 in SKILL.md.
5. Update `evals/evals.json` if status vocabulary or output schema changes.

## Path references to verify on update
- `shared/integrations-engine.md` (must exist)
- `protocols/no-fabrication.md` (must exist)
- `skills/atoms/schedule-post/SKILL.md` (must exist — upstream atom)
- `.claude/workflows/content-distribution.js` (must reference this atom)
