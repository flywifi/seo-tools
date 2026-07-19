---
file: skills/atoms/schedule-post/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for schedule-post so it stays stable under iteration.
---

# schedule-post: Maintainer README

## Purpose
This atom queues or schedules a single piece of finalized content to one social platform via the active publishing connector. It resolves the correct connector tier (direct platform API > manual fallback), runs FTC/AIGC compliance checks, presents a confirmation summary to the creator, and only then sends to the connector. Its job ends at the moment the post is queued — post-status handles follow-up status checks.

## Non-negotiable invariants
- `human_review_required: true` must be present in every output. The creator must confirm before any connector call. This is unconditional.
- FTC disclosure: if `ftc_disclosure` is non-null, the disclosure must appear in the caption. Prepend if missing; flag in `notes`.
- AIGC flag: if `is_aigc: true` and `platform: tiktok`, set `post_info.is_aigc` in the TikTok payload. Log in output.
- Connector resolution order is fixed: per-platform direct API first, manual last.
- `post_id` and `permalink` must be null when `publishing_tier: manual`.
- Never fabricate post_id, permalink, or status.
- No retry logic in the atom — on connector error, return `status: failed` and surface to creator.

## Known failure modes
- Missing media_url when direct API path is active: return `status: failed`.
- TikTok rate limit (6 req/min): connector rejects; return `status: failed` with rate limit message.
- Instagram container+publish flow: if the container is accepted but publish step fails, the container_id is in the error message for retry.
- AIGC flag not passed by caller: atom cannot auto-detect AI-generated content; flag is omitted; `notes` warns.

## Fragile fallbacks that must not become defaults
- Manual fallback (`publishing_tier: manual`) is acceptable only when no content_publishing connector is active. Never silently use manual mode when a connector is configured but temporarily unavailable — return `status: failed` and expose the connector error.
- FTC prepending is a correction, not a feature. If disclosure is consistently missing from captions, the calling workflow should be fixed upstream (caption-write atom).

## Regression cases to preserve (mapped to evals/evals.json)
1. Happy path: direct API active, all fields present → `status: queued`, `publishing_tier: direct_api`
2. Manual fallback: no connector active → `status: manual_required`, `publishing_tier: manual`, null post_id and permalink
3. FTC disclosure absent: `ftc_disclosure: "#ad"`, not in caption → disclosure prepended, `notes` flags it
4. AIGC flag on TikTok: `is_aigc: true`, `platform: tiktok` → `aigc_flag_set: true`
5. Connector error: rate limit response → `status: failed`, error field populated
6. Pinterest: `board_name` required → board_name included in connector payload
7. `human_review_required` always present → true in every output variant

## Approval-gated changes
- Changes to the connector resolution order (any reordering of tiers requires explicit review)
- Any change to the `human_review_required` handling
- New platform added to `platform` enum
- Changes to FTC or AIGC compliance logic

## Minority-report policy
When the connector returns ambiguous status (e.g., partial acceptance), the atom returns the conservative interpretation (failed) and surfaces the raw connector message in `error`.

## Update checklist
1. Run `python3 tools/sync_check.py` — all 55 invariants must pass.
2. Verify all path references in this file and SKILL.md resolve to real files on disk.
3. After any platform API rate limit or endpoint change, update `shared/integrations-engine.md` first, then update the Failure modes section here.
4. After any connector registry change, confirm `shared/connectors/connectors.py` CAPABILITY_TO_CONNECTOR is up to date.
5. Update `evals/evals.json` if output schema changes.
