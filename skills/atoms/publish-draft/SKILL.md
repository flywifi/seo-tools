---
name: publish-draft
atom: true
description: "Formats finalized content into a paste-ready posting package for a specific platform — formatted caption, hashtag block, platform-specific posting checklist, media specs reminder, and FTC reminder — requiring zero connector infrastructure. Always available as the manual fallback for schedule-post. Do NOT use when a live publishing connector is active and the creator wants to actually queue the post — use schedule-post instead."
engines_required:
  - shared/platform-engine.md
  - shared/brand-engine.md
protocols:
  - protocols/safety.md
  - protocols/formatting-metadata.md
---

# publish-draft

## When to use this atom

Trigger phrases: "format this for posting," "give me the copy to paste," "prepare for manual upload," "format the caption for Instagram," "what do I paste into TikTok," "posting checklist," "help me post this manually."

Use when:
- No publishing connector is active and schedule-post has fallen back to manual mode.
- The creator wants to manually copy-paste content into a platform's native app or web interface.
- The creator wants a pre-flight checklist before uploading themselves.

Do NOT use for:
- Actually queuing or scheduling a post to a platform — use schedule-post.
- Writing the caption from scratch — use caption-write first.
- Checking whether a post went live — use post-status.

## Inputs

Required:
- `platform` (string): `instagram | tiktok | pinterest | youtube`
- `caption` (string): finalized caption text

Optional:
- `hashtags` (array of string): appended to caption if not already present
- `media_notes` (string): description of the media file (format, resolution, length) for the checklist
- `scheduled_datetime` (string): ISO 8601; atom converts to a human-readable "best window" note if a connector is not available to schedule it
- `ftc_disclosure` (string): `#ad | #gifted | #affiliate | null` — included in caption if not already present

Retrieved automatically:
- Platform-specific character limits, hashtag caps, and file format specs (via platform-engine.md)
- Optimal posting time windows for the platform (via platform-engine.md; labeled `[estimated]` when not grounded in the creator's own analytics)
- Creator voice and brand context for caption validation (via brand-engine.md)

## Core procedure

### Step 1: Caption finalization
- Ensure FTC disclosure is present in caption if `ftc_disclosure` is non-null. Prepend if missing.
- Append `hashtags` array to caption if they are not already embedded, respecting platform hashtag caps:
  - Instagram: up to 5 relevant hashtags (cap imposed December 2025)
  - TikTok: 3 to 5 niche hashtags
  - Pinterest: 2 to 5 keyword hashtags in description; hashtags function as classification signals
  - YouTube: hashtags appear in description or above title; 3 to 15 is typical
- Enforce platform character limits: Instagram caption 2,200 chars; TikTok caption 2,200 chars; Pinterest description 500 chars; YouTube description 5,000 chars (first 120 chars are above fold).
- Format caption with line breaks appropriate for the platform (Instagram: two blank lines between sections; TikTok: compact, hook in first line).

### Step 2: Posting checklist generation
Generate a numbered, platform-specific checklist with every manual step the creator must complete. Example for Instagram Reels:
1. Open Instagram app and tap the + icon
2. Select Reel, then choose your video file
3. Trim if needed; confirm aspect ratio is 9:16
4. Paste the caption below
5. Add the hashtags exactly as listed below
6. Set to Share to Feed if you want it on your profile grid
7. Tap Advanced Settings and verify Professional controls are active
8. Schedule via Instagram's native scheduler or post immediately
9. Confirm FTC disclosure is visible in the first 125 characters of the caption

### Step 3: Media specs reminder
Return the platform-specific media requirements for the declared `content_type`. Source: `shared/platform-engine.md`. Do not fabricate specs not found there.

### Step 4: Optimal posting time
Return the current best-practice posting time window for the platform. Label `[estimated — from platform-engine.md defaults]` unless the creator has analytics data grounding the recommendation.

## Output contract

```json
{
  "platform": "instagram | tiktok | pinterest | youtube",
  "formatted_caption": "string — paste-ready, includes disclosure and hashtags",
  "hashtag_block": "string — hashtags as a separate copyable block",
  "posting_checklist": ["string — numbered steps"],
  "media_specs": {
    "format": "string",
    "aspect_ratio": "string",
    "max_duration_seconds": "number or null",
    "max_file_size_mb": "number or null",
    "resolution_minimum": "string or null"
  },
  "optimal_posting_time": "string — labeled [estimated] if not grounded in creator analytics",
  "ftc_reminder": "string or null — null if no disclosure applies",
  "character_count": "number",
  "character_limit": "number",
  "notes": "string or null"
}
```

Every output from this atom is for manual copy-paste. No connector calls are made.

## Engines and protocols loaded

- `shared/platform-engine.md` — character limits, hashtag caps, media specs, posting windows
- `shared/brand-engine.md` — voice validation; ensures caption matches creator voice profile
- `protocols/safety.md` — FTC disclosure check
- `protocols/formatting-metadata.md` — no em dashes in caption output; ranges with "to"

## Standalone usability

Produces a complete manual posting package — paste-ready caption, hashtag block, numbered upload checklist, media spec reminder, and FTC note — with no external dependencies beyond platform-engine.md.

## Failure modes

- **Platform character limit exceeded**: returns the formatted caption with a warning showing how many characters over the limit the caption is. Does not truncate automatically — surfaces the issue for the creator to resolve.
- **FTC disclosure absent and disclosure required**: prepends the disclosure and flags the addition in `notes`. Does not block output.
- **Hashtag cap exceeded**: truncates to the platform cap and notes the dropped hashtags in `notes`.
- **No media_notes provided**: checklist skips the media-specific steps and adds a note that the creator should verify their file meets the platform's specs before uploading.
- **Unknown platform**: returns an error note; does not fabricate specs for an unsupported platform.

## Cross-modality
Inherits its calling spoke's class (the calling spoke's class); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
