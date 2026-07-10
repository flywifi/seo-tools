---
file: skills/shortform-repurposing/SKILL.md
name: shortform-repurposing
description: "converts a long-form YouTube video project into a short-form package: 3 to 5 Shorts/Reels, per-platform captions, hashtag sets, and Pinterest Pins; does NOT generate the original long-form content."
load: always
---

# shortform-repurposing

## Purpose

Maintains the Creator OS ecosystem ratio of 1 long-form video + 3 to 5 Shorts/Reels + 1 to 3 Pins per project. This spoke handles everything after the long-form video exists: it extracts clips, writes per-platform captions, builds hashtag sets, drafts Pinterest Pins, slots drops onto the calendar, and runs the quality gate before output is returned.

## Inputs

| Field | Type | Required | Notes |
|---|---|---|---|
| `long_form_title` | string | required (or `project_brief`) | Title of the published or in-progress long-form video |
| `project_brief` | string | required (or `long_form_title`) | Free-text brief if the video is not yet titled |
| `source_transcript` | string | optional | Full or partial transcript; improves clip extraction fidelity |
| `video_url` | string | optional | YouTube or internal URL used to extract clips when no transcript is supplied |
| `platform_targets` | list of strings | optional | Defaults to `[youtube-shorts, instagram-reels, tiktok, pinterest]` |
| `persona` | string | optional | Overrides the default audience persona from `shared/audience-engine.md` |

## Primary Outputs

Returns a single `short_form_package` object with the following keys:

- **clips** (list, 3 to 5 items) - produced by `short-extract`. Each clip contains a hook line, a transcript excerpt or timecode range, and a recommended duration.
- **captions** (list) - produced by `caption-write` (repeated once per clip per platform). Each caption is platform-spec-compliant in length, tone, and CTA style.
- **hashtag_sets** (map: platform to list) - produced by `hashtag-set` (repeated once per platform). Each set is deduplicated and ordered by tier (niche first, broad last).
- **pins** (list, 1 to 3 items) - produced by `pin-write`. Each Pin includes a title, description, and board suggestion aligned to the seasonal aesthetic in `canonical-sources/`.
- **drop_schedule** (object) - produced by `calendar-slot`. Maps each clip and Pin to a recommended publish date and time window.
- **quality_gate_result** (object) - produced by `govern-artifact`. Passes or blocks the package; surfaces any formatting, safety, or brand violations before delivery.

## Atoms Composed

Atoms are invoked in the order listed. `caption-write` and `hashtag-set` run once per target platform per clip.

1. `short-extract` - identifies and structures 3 to 5 clip candidates from the source material
2. `caption-write` (repeat: per_platform) - writes a caption for each clip tailored to the target platform
3. `hashtag-set` (repeat: per_platform) - builds a ranked hashtag set for each platform
4. `pin-write` - drafts 1 to 3 Pinterest Pins from the strongest visual moments
5. `calendar-slot` - assigns publish windows for each clip and Pin
6. `govern-artifact` - runs the full quality gate and returns a pass or block result

## Engines Required

- `shared/platform-engine.md` - character limits, aspect ratios, caption styles, hashtag ceilings, and scheduling windows for each platform
- `shared/brand-engine.md` - voice, tone, visual style, and niche identity constraints

## References

- `shared/platform-engine.md`
- `protocols/formatting-metadata.md`
- `protocols/safety.md` (FTC disclosure rules apply when content is sponsored)
- `protocols/quality-gates.md`

## Do NOT use for

- **Generating the original long-form video** - use the `video-development` spoke. This spoke assumes the long-form project already exists.
- **SEO keyword strategy** - use the `seo-keywords` spoke. This spoke consumes keywords; it does not generate them.
- **Caption file transcription** (SRT/VTT/ASS output) - use `document-studio`. This spoke writes social captions, not caption files.

## Cross-modality
Class: C.
Runs on: Claude Desktop/Code (native, MCP + the tool module); claude.ai via a hosted remote-MCP connector; Custom GPT / Gemini only when the tool is hosted behind a remote MCP or an Action; Gems: no.
Mechanism: Reasoning over the transcript plus scoop-cached platform specs (cache_query / shared/platform-engine.md) for clips, captions, hashtags, Pins, and calendar slots; local COMPUTE only through the shorts-reframe shortcut atom's MCP tool reframe_shorts (tools/videoedit/reframe.py 9:16 crop geometry + ffmpeg filter string, flag-gated CLI render) and mediaprobe-backed silence_scan / scene_scan for clip-point probing.
Fallback: Without the MCP runtime, run the full 6-step package as B/A work: reason over the user-supplied transcript and platform specs for clips, captions, hashtags, Pins, and schedule; skip shorts-reframe crop geometry and media probing, flag cut points/durations as unverified, and never fabricate timecodes it cannot probe.
See `shared/cross-modality-engine.md`.
