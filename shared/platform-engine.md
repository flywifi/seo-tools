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
  60 seconds performs best for Phase 1 distribution. Keep key content centered, away from UI.
  Optional custom thumbnail at 1280x720 for non-feed surfaces.
- Algorithm rewards (2025 shift, ranked): session contribution (PRIMARY — does the Short keep the
  viewer in the Shorts feed?), AVD threshold (~65% for sub-30s; ~50% for 30 to 60s), loop rate
  (rewatches within 2 seconds of video end count as partial views), comments (outrank likes since
  2025), user satisfaction / post-watch behavior, shares, original audio bonus for accounts under
  50K subscribers (March 2026).
- Swipe-through rate is now SECONDARY (was primary before 2025). Design the first frame for visual
  impact but prioritize session contribution over first-impression hook.
- Three-phase distribution model: cold seeding (50 to 500 viewers, ~70% non-subscribers) → watch
  time gate (clears on AVD threshold) → topic clustering (3 to 6 week distribution window).
  Freshness decay: ~28 to 30 days. Shorts are not evergreen — plan cadence to sustain presence.
- No dedicated Shorts API endpoint in YouTube Data API v3. Identification is heuristic:
  contentDetails.duration ≤ 60s + #Shorts in title/description + 9:16 aspect ratio.
- YPP Shorts path: 1,000 subscribers + 10M valid Shorts views in 90 days. Revenue share: 45%
  (vs. 55% for long-form). Shorts watch hours do NOT count toward 4,000-hour long-form threshold.
- Use: discovery via behavioral distribution and niche clustering. Pull best moments from long-form;
  point viewers to the full video. Original audio preferred over trending audio for recommendation.
- Cadence: 3 to 5 per week. See `shared/seo-intelligence-engine.md` for the full Shorts algorithm
  and `canonical-sources/keyword-library/youtube-algorithm-signals.json` for the signal registry.

## Instagram Reels
- Specs: 9:16, 1080x1920, MP4 H.264 + AAC, 30 fps. 5 to 90 seconds for Reels tab; up to 15 minutes
  via the Graph API. Caption up to 2,200 characters. The feed crops Reels to 4:5 and the profile
  grid previews at 3:4, so keep faces, text, and the cover's focal point inside the central safe area.
- Algorithm rewards (Mosseri official, January 2025): completion rate (15s watched 3x outranks 60s
  watched once), sends per reach (DM shares — 3 to 5x weight of likes, UNIQUE PRIMARY SIGNAL for
  Reels), saves ("heavy" interaction), likes per reach, originality (10+ reposts in 30 days =
  excluded from Recommendations), topic consistency (last 9 to 12 posts determine category).
- Critical threshold: the 3-second gate. `skip_rate` (added December 2025) measures viewers who
  leave in the first 3 seconds. Design the opening for sound-on assumption; text overlay for
  sound-off viewers.
- Hashtags: 5-hashtag cap since December 2025. Hashtag follow was removed December 2024. Use 3
  to 5 specific niche hashtags as classification signals, not as traffic drivers. Keywords in
  captions now drive discovery more strongly than hashtags.
- Do not repost TikTok-watermarked content — Meta detects watermarks and suppresses distribution.
  Accounts with 10+ reposts in 30 days are excluded from Recommendations entirely.
- Metrics: reach, views (note: "impressions" deprecated April 2025 — use "views"), avg_watch_time,
  completion rate, saves, shares, skip_rate (new December 2025), follows from post.
- Graph API: v25.0 (February 18, 2026). Basic Display API shut down December 4, 2024 — use Graph
  API via Facebook App for all integrations. See `shared/integrations-engine.md`.

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
  10 minutes (up to 60 via web upload). Optimal 15 to 60 seconds for completion rate; 1 to 3+ minutes
  now rewarded with a long-form completion bonus (2026). Design audio-first. Safe zones: avoid the top
  bar, the right action column, and the bottom caption block. Photo Mode carousel supports up to 35 images.
  AIGC disclosure: set `is_aigc: true` on any Content Posting API upload that uses AI-generated script
  or AI-generated visuals (required by TikTok; FTC disclosure also required verbally and in captions).
- Algorithm rewards (2025 to 2026, ranked): rewatch rate (NOW #1 signal, surpasses completion rate),
  shares (2nd strongest), comments, video completion rate, watch time (15 to 20s AVD = 3x distribution
  multiplier), saves/favorites, micro-community clustering (2025 — niche cluster of 3+ users with
  shared preferences receives relevant content from small accounts), TikTok SEO / search keywords in
  captions (84% of TikTok searches are exploration-phase). Explicit non-factors: follower count and
  prior video performance (every video starts from zero).
- Rewatch design is the highest-leverage single change: design a reveal, detail, or transformation
  that rewards a second viewing. The 7-second pattern interrupt (visual or audio change within first 7
  seconds) is a documented retention signal across multiple creator analyses.
- Captions as SEO: treat as keyword fields, not just context. TikTok search is now a primary
  discovery surface alongside the FYP. Keywords in captions influence both FYP placement and search.
- Do not watermark: never repost a TikTok-watermarked video to other platforms. TikTok detects
  watermarked reposts from competitor platforms and suppresses FYP distribution.
- Metrics: completion rate, rewatch count, shares, saves (favorites_count added to Research API May
  2026), comments, For You reach.
- Content Posting API: `POST https://open.tiktokapis.com/v2/post/publish/video/init/`. See
  `shared/integrations-engine.md` and `canonical-sources/keyword-library/tiktok-api-registry.json`.

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
