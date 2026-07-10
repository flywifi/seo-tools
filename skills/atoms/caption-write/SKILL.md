---
file: skills/atoms/caption-write/SKILL.md
name: caption-write
description: write ONE platform-appropriate social media caption (hook line, body, CTA) in the creator's warm published-to-audience voice for an Instagram Reel, TikTok, YouTube Short, or Pinterest Pin. Use when shortform-repurposing, content-calendar, or any spoke needs a ready-to-post caption. Do NOT use to write a full video script, a long-form YouTube description, or a title card.
load:
  - shared/brand-engine.md
  - shared/platform-engine.md
  - shared/voice-engine.md
  - protocols/safety.md
---

# caption-write

Write a single social caption ready for publishing: hook line, body, and CTA. Voice is published-to-audience mode (warm, specific, draws the viewer in). Character count is enforced per platform.

## Purpose

Produce one caption per call, scoped to the target platform. The caption must open with the hook line, flow naturally through a brief body, and close with a CTA. If the post is sponsored, gifted, or affiliate, the output flags that an FTC disclosure line is required before publishing and returns the correct disclosure tag.

## Inputs

```json
{
  "topic": "string (the content topic or working title)",
  "platform": "instagram-reel | tiktok | shorts | pinterest",
  "hook_angle": "optional string (angle or emotion to lead with)",
  "persona": "optional string (persona this post serves, from shared/brand-engine.md)",
  "sponsored": "optional bool (default false)",
  "gifted": "optional bool (default false)",
  "affiliate": "optional bool (default false)"
}
```

Field notes:
- `topic` is required. Pass the working title or a plain description of the content.
- `platform` is required. It controls character limits and tone calibration.
- `hook_angle`, `persona`, `sponsored`, `gifted`, and `affiliate` are optional; omit any you do not have.
- More than one of `sponsored`, `gifted`, `affiliate` may be true at once.

## Output

```json
{
  "tool": "caption-write",
  "platform": "instagram-reel | tiktok | shorts | pinterest",
  "hook_line": "string (opening line used inside caption)",
  "caption": "string (full caption: hook line + body + CTA, within platform character limit)",
  "cta": "string (the call-to-action line, also embedded in caption)",
  "ftc_disclosure_line": "#ad | #gifted | #affiliate | null",
  "character_count": 0,
  "notes": "string or null (flags, suggestions, or truncation warnings)"
}
```

### Character limits (enforced)

| Platform | Limit | Notes |
|---|---|---|
| instagram-reel | 2200 chars | Full caption; only the first 125 chars show before "more" |
| tiktok | 2200 chars | Full caption; front-load the hook |
| shorts | 100 chars | Only the first ~100 chars are visible without expanding; keep the full caption within this limit |
| pinterest | 500 chars | Description field; keyword-forward, no hashtag clutter |

If the draft exceeds the platform limit, trim body copy first, preserve the hook line and CTA, and set `notes` to explain what was shortened.

### FTC disclosure logic

- If `sponsored` is true: `ftc_disclosure_line` returns `"#ad"`.
- If `gifted` is true and `sponsored` is false: `ftc_disclosure_line` returns `"#gifted"`.
- If `affiliate` is true (and neither sponsored nor gifted): `ftc_disclosure_line` returns `"#affiliate"`.
- If more than one flag is true, use the strictest applicable tag (`#ad` outranks the others) and note the others in `notes`.
- If all three are false or omitted: `ftc_disclosure_line` returns `null`.

The disclosure line must appear in the final published caption before it goes live. This atom flags the requirement and returns the tag; the human is responsible for placement. See `protocols/safety.md`.

## Do NOT use for

- Full YouTube video descriptions (use the description-write atom or the relevant spoke).
- Video titles or thumbnail text (use title-generate or thumbnail-concept).
- Scripts or spoken voiceover copy (use hook-write or script-writer).
- Batch caption generation across multiple posts in one call; call once per post.
- Any caption where brand voice, persona, or platform specs have not been loaded; always load `shared/brand-engine.md` and `shared/platform-engine.md` before writing.

## Pipeline note

Voice and persona guidance come from `shared/brand-engine.md` (published-to-audience mode: warm, specific, draws the viewer in; no corporate tone, no em dashes). Platform character limits, hashtag conventions, and opening-window rules come from `shared/platform-engine.md`. Sponsored-content disclosure requirements come from `protocols/safety.md`. This atom does not fabricate engagement metrics, brand names, or product claims; see `protocols/no-fabrication.md`.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
