---
file: shared/platform-engine.md
role: Source of truth for per-platform specs, what each algorithm rewards, and metric definitions.
  Read by video-development, shortform-repurposing, seo-keywords, analytics-insights, and
  document-studio (for deliverable specs). Specs current as of mid-2026; re-verify before relying
  on exact limits, since platforms change them often.
load: when the request involves a specific platform, formatting, repurposing, or metric interpretation
---

# Platform Engine

## Cross-platform rule
A single 1080x1920 (9:16) export serves YouTube Shorts, Instagram Reels, and TikTok. Design inside
the tightest safe zone (YouTube's top UI is the most restrictive) and keep key content in the
central area, away from each app's top bar, right-side action column, and bottom caption block.
Pinterest is the exception: its native shape is 2:3, not 9:16.

## YouTube (long-form)
- Specs: 16:9, 1920x1080 (1080p standard; 4K only for evergreen hero builds). MP4, H.264.
- Thumbnail: 1280x720 (16:9). High contrast, one clear subject, expressive face filling roughly
  40 to 60% when a face is used, readable at small size, text inside a 10 to 15% edge margin.
  Thumbnail and title must align (no overpromising).
- Title: roughly 80 to 100 characters for search and how-to content; front-load the primary
  keyword; balance curiosity with clarity.
- Hook: the first 15 to 30 seconds decide retention. State the promise or payoff fast; cut long intros.
- Length: match viewer intent. Detailed makeovers and tutorials can run long because this audience
  wants the how and why; test runtime against AVD rather than guessing.
- Structure: hook, before, process and key decisions, reveal and payoff, recap. Use chapters, an end
  screen, and a pinned comment linking the related project or playlist.
- Key metrics: CTR (good 4% to 10%; search traffic 8 to 15%, browse 3 to 7%), AVD and average
  percentage viewed (target above 50%), the retention curve (a near-flat line is ideal), watch time,
  traffic source (Search signals an SEO cluster to expand; Suggested signals a follow-up or series;
  Browse is packaging-led), and subscribers gained. In 2026 "Quality CTR" applies: high CTR with weak
  first-30-second retention is demoted.
- Cadence: 1 to 2 long-form per week.

## YouTube Shorts
- Specs: 9:16, 1080x1920, MP4 H.264, 30 or 60 fps. Up to 3 minutes (since Oct 15, 2024), but 15 to
  60 seconds performs best. Keep key content centered, away from UI. Optional custom thumbnail at
  1280x720 for non-feed surfaces.
- Algorithm rewards: replay rate, swipe-through ("how many chose to view"), completion or average
  percentage viewed (70%+ healthy, above 100% means replays), like-to-view ratio, and shares.
  Watch time matters far less than for long-form.
- Use: discovery and repurposing. Pull the best moments from a long-form build; point viewers to the
  full video.
- Cadence: 3 to 5 per week.

## Instagram Reels
- Specs: 9:16, 1080x1920, MP4 H.264 + AAC, 30 fps. Up to 3 minutes in-app. Caption up to 2,200
  characters. The feed crops Reels to 4:5 and the profile grid previews at 3:4, so keep faces, text,
  and the cover's focal point inside the central 1:1 to 4:5 safe area.
- Algorithm rewards: completion, saves, shares, and sends. Saves and shares are strong distribution
  signals for this niche.
- Metrics: reach, plays, watch time, completion rate, saves, shares, follows from the post.

## Instagram feed and carousels
- Feed image: 4:5 (1080x1350) is the engagement default; 3:4 (1080x1440) avoids grid cropping;
  1:1 (1080x1080) for a uniform grid. The profile grid previews at 3:4, so keep faces, text, and
  logos inside that zone.
- Carousels: up to 20 slides; the first slide locks the aspect ratio and every slide should match
  (4:5 or 3:4 recommended). Slides can be reordered or replaced after publishing. Carousels are one
  of the highest-performing formats for step-by-step tutorials, before-and-after sequences, and
  source lists, and they drive high dwell time and saves.
- Files: JPG or PNG; keep under about 10 MB.

## TikTok
- Specs: 9:16, 1080x1920, MP4 or MOV, H.264 + AAC, 30 fps (60 for high motion). Length 3 seconds to
  10 minutes (up to 60 via web upload). Optimal 15 to 35 seconds; the algorithm favors roughly 21 to
  34 seconds; completion rate is the dominant signal. Design audio-first, since the large majority of
  users watch with sound on. Safe zones: avoid the top bar, the right action column, and the bottom
  caption block. Photo Mode carousel supports up to 35 images.
- Metrics: completion rate, watch time, rewatches, shares, saves, and For You reach.

## Pinterest
- Nature: a visual search engine, not a social feed. Pins compound and can drive traffic for months
  to years after posting, which suits evergreen DIY and decor.
- Specs: standard Pin 2:3 at 1000x1500 (the highest-engagement shape; vertical claims more space in
  the masonry feed). Do not exceed 1:2.1 or the feed crops the bottom. Video Pin 2:3 or 9:16
  (1080x1920). PNG for pins with text overlays, JPG for photos; keep under about 5 MB. Idea Pins were
  merged into one unified Pin format in 2023; there is no separate Idea Pin to create.
- SEO: keyword-rich Pin titles, descriptions, board names, alt text, and clean file names drive
  discovery. Lean on these more than hashtags.
- Metrics: impressions, saves (repins), pin clicks, and outbound clicks; track top boards and topics.

## Metric glossary (what each signal means)
- CTR: share of impressions that clicked. Packaging quality (title and thumbnail).
- Impressions and reach: how many were shown the content.
- AVD / average percentage viewed / retention: how long viewers stay; content and pacing quality.
- Completion rate: finished the video; the core short-form quality signal.
- Swipe-through / "chose to view": short-form feed equivalent of CTR.
- Saves: reference and depth value. Shares: spreadability. Comments: resonance.
  Follows or subscribers from a piece: growth power.
- Traffic source (YouTube): Search means an SEO topic to build a cluster around; Suggested means a
  good candidate for follow-ups and series; Browse is driven by packaging.
