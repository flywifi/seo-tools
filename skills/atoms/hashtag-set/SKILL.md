---
file: skills/atoms/hashtag-set/SKILL.md
name: hashtag-set
description: generate a tiered hashtag set (broad, niche, micro) for a single home decor or DIY social post on Instagram, TikTok, or Pinterest. Use when caption-write, shortform-repurposing, or any spoke needs a ready-to-paste hashtag block. Do NOT use for YouTube (hashtags work differently there), for non-home-decor content, or for batch generation across multiple posts in one call.
load:
  - shared/platform-engine.md
---

# hashtag-set

Generate a single tiered hashtag set tuned for home decor and DIY content on Instagram, TikTok, or Pinterest. Output is grouped into three tiers and also returned as a paste-ready string.

## Purpose

Produce one hashtag set per call, organized into three tiers based on relative audience size. Broad tags reach the widest audience; niche tags target the core home decor and DIY community; micro tags reach the tightest hyper-specific audience and typically drive the highest conversion rate among viewers already searching that aesthetic or method.

Hashtag follower counts and post volumes shift constantly. This atom does not state reach numbers or follower counts as facts. The output always includes a `note` field reminding the publisher to verify tag performance in-app before posting. See `protocols/no-fabrication.md`.

Platform conventions from `shared/platform-engine.md` govern tag formatting, placement, and volume recommendations per platform.

## Inputs

```json
{
  "topic": "string (the content topic or working title, required)",
  "platform": "instagram | tiktok | pinterest",
  "pillar": "optional string (content pillar, e.g. DIY tutorial, room transformation, thrift flip)",
  "aesthetic": "optional string (e.g. moody-vintage, cottagecore, dark academia, maximalist, japandi)"
}
```

Field notes:
- `topic` is required. Pass the working title or a plain description of the content (for example, "painting a thrifted dresser in dark green velvet finish").
- `platform` is required. It controls tag volume targets and formatting conventions.
- `pillar` is optional. When provided it steers the niche tier toward the correct content category.
- `aesthetic` is optional. When provided it anchors the micro tier to the specific visual style. Accepted values include but are not limited to: moody-vintage, cottagecore, dark academia, grandmillennial, maximalist, japandi, hygge. Pass whatever aesthetic label applies to the post.

## Output

```json
{
  "tool": "hashtag-set",
  "platform": "instagram | tiktok | pinterest",
  "topic": "string (echoed from input)",
  "broad_tags": [
    "list of 3 to 5 large/broad tags (high-volume, general audience)"
  ],
  "niche_tags": [
    "list of 5 to 8 mid-size niche tags (home decor and DIY community)"
  ],
  "micro_tags": [
    "list of 3 to 5 micro/hyper-niche tags (tight aesthetic or method)"
  ],
  "all_tags_combined": "string of all tags space-separated, ready to paste into the post",
  "note": "Hashtag reach and follower counts change frequently. Verify tag performance in-app before publishing. Remove any tags that are banned or restricted on the target platform."
}
```

### Tier definitions

| Tier | Field | Count | Audience scope |
|---|---|---|---|
| Broad | `broad_tags` | 3 to 5 | General lifestyle, home, and DIY audiences |
| Niche | `niche_tags` | 5 to 8 | Home decor and DIY enthusiasts actively following the category |
| Micro | `micro_tags` | 3 to 5 | Hyper-specific aesthetic or method; smallest audience, highest intent |

### Platform tag conventions (from shared/platform-engine.md)

| Platform | Formatting | Placement | Volume guidance |
|---|---|---|---|
| Instagram | `#tag` lowercase, no spaces | Caption or first comment | 11 to 18 total tags is a common working range; verify current best practice in-app |
| TikTok | `#tag` lowercase, no spaces | Caption inline | 3 to 6 focused tags; platform indexes caption text broadly so fewer specific tags often outperform large sets |
| Pinterest | `#tag` lowercase, no spaces | Description field | 2 to 5 tags; keyword-forward descriptions carry more weight than tag volume on this platform |

The `all_tags_combined` string must respect the total count appropriate to the platform. If the combined tier count exceeds the platform guidance ceiling, trim from the broad tier first and note the trim in the `note` field.

## Do NOT use for

- YouTube hashtag generation. YouTube hashtag behavior, placement rules, and volume limits differ significantly from short-form platforms. Use the appropriate YouTube-specific atom or spoke.
- Non-home-decor or non-DIY content. This atom is tuned for Alex's niche; tag selection for other verticals (fitness, food, travel) will be off-target.
- Batch generation across multiple posts in one call. Call once per post so tier selection stays scoped to the specific topic and platform.
- Stating tag reach or follower counts as verified facts. Output the tags and the `note` only; never fabricate or invent usage statistics. See `protocols/no-fabrication.md`.
- Replacing caption copy or keyword research. This atom outputs hashtags only. For caption copy use caption-write; for keyword clusters use keyword-cluster.

## Pipeline note

Platform tag conventions, character limits, and placement rules come from `shared/platform-engine.md`. Aesthetic vocabulary and content pillar labels come from `shared/brand-engine.md`. This atom does not fabricate engagement metrics, reach numbers, or tag follower counts; all such figures change and must be verified in-app before publishing.
