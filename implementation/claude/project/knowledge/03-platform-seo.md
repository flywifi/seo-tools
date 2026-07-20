---
file: shared/platform-engine.md
role: Source of truth for per-platform specs, what each algorithm rewards, and metric definitions.
  Read by video-development, shortform-repurposing, seo-keywords, analytics-insights, and
  document-studio (for deliverable specs). Specs current as of mid-2026; re-verify before relying
  on exact limits, since platforms change them often.
load: when the request involves a specific platform, formatting, repurposing, or metric interpretation
---

_Data freshness: as of 2026-07-20 (Creator OS baseline 802ca2be). Live updates come from your own store; see docs/FRESHNESS.md. Source and updates: github.com/flywifi/seo-tools._

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

---

---
file: shared/seo-intelligence-engine.md
role: Canonical SEO algorithm knowledge, topical authority model, entity SEO, long-tail expansion
  methodology, SERP feature map, and seasonal lead times. Loaded by seo-keywords, competitor-analysis,
  and the four SEO atoms (topical-authority-map, long-tail-expand, entity-extract, serp-feature-check).
load: when any SEO research or keyword task is underway
---

# SEO Intelligence Engine

All data in this engine is sourced from the entries in `canonical-sources/source-registry.json`
and checked on the schedules defined in `canonical-sources/traversal-config.json` (default: weekly).
When a section contradicts a more recently verified source, the verified source wins — update this
file via the source currency process and note the source id.

---

## YouTube algorithm signals

Ranked by current impact on discovery. Source: youtube-help-recommendations, youtube-creator-blog
(verify weekly; algorithm weights shift without public announcement).

1. **Click-through rate (CTR)** — The primary Browse and Home feed signal. YouTube tests a video
   against a small audience first; strong CTR earns wider distribution. Target range: 4 to 10% for
   established channels. For a new channel in a competitive niche, anything above 5% is strong.
   Thumbnail and title are the only levers. Test both; never change both at once.

2. **Absolute watch time** — Total minutes watched per video (not completion percentage). YouTube
   is a session-time business; a 20-minute video watched 50% generates more signal than a 5-minute
   video watched 100%. This is why long-form content compounds over time even at lower completion
   rates.

3. **Average view duration (AVD) and retention curve shape** — The shape of the curve matters more
   than the final percentage. A flat retention line at 40% signals consistent value. A sharp drop
   in the first 30 seconds signals a misleading thumbnail or slow hook. A bump in the middle signals
   a high-value moment — note it and front-load similar content in the next video.

4. **Engagement velocity in first 24 to 48 hours** — Likes, comments, saves, and shares in the
   first two days are the strongest signal that a video should be promoted further. Early
   engagement velocity drives Suggested placement, which drives the majority of views for most
   channels. Prioritize publishing at the time when the audience is most active.

5. **Session starts** — Videos that open a YouTube session get a discovery bonus. High-CTR content
   (thumbnails that stop scrolling) is more likely to be a session starter. New channels can
   disproportionately benefit from this signal by investing in thumbnail quality early.

6. **End screen click-through and subscribe rate** — Signals satisfaction and intent to continue
   watching. Low end-screen CTR with high retention suggests content quality is fine but calls
   to action are weak. Strong subscribe rate from a video signals audience-fit and can earn the
   video ongoing recommendation on returning subscriber feeds.

---

## YouTube Shorts algorithm

The Shorts algorithm is entirely separate from the long-form YouTube algorithm. Behavioral signals
dominate — metadata matters far less than on long-form. Source: youtube-creator-blog,
youtube-help-recommendations (verify weekly; Shorts signals shifted materially in 2025).

**As of 2025 to 2026, the signal stack from highest to lowest weight:**

1. **Session contribution (PRIMARY — 2025 shift)** — Whether a Short keeps the viewer in the
   Shorts feed after it ends. A Short that holds a viewer in the feed for two or more subsequent
   Shorts earns outsized distribution. This is why loop design matters: end the Short cleanly
   so the viewer does not leave the feed to search for more.

2. **Average view duration thresholds** — Behavioral gate before broader distribution.
   Approximate thresholds: ~65% AVD for sub-30-second Shorts; ~50% for 30 to 60 second Shorts.
   A Short that clears its threshold gets seeded to a wider pool (see three-phase model below).

3. **Loop rate / replay rate** — A rewatch within 2 seconds of video end is counted as a
   partial new view. Loopable Shorts — where the last frame flows naturally back to the first —
   score measurably higher. Design the ending to be a natural loop point whenever the content
   permits.

4. **Comments (outrank likes, 2025)** — As of 2025, comments carry more weight than raw likes
   as a ranking signal. A Short that provokes a reply in the comments section is a stronger
   quality signal than one that collects passive likes.

5. **User satisfaction / post-watch behavior (2025 shift)** — What the viewer does after the
   Short ends: do they subscribe, click to the channel, continue watching Shorts, or leave
   YouTube? Positive post-watch behavior is weighted over raw watch time.

6. **Shares** — Content propagation signal. Weighted alongside replays.

7. **Swipe-vs-watch ratio (first 1 to 3 seconds)** — Now a SECONDARY signal (was primary
   before 2025). The critical hook window is still important, but behavioral signals from
   viewers who stay have more weight than the number who swiped away.

8. **Original audio bonus (March 2026)** — For accounts under 50,000 subscribers, Shorts
   with original voiceovers outperform Shorts using trending audio in recommendation
   distribution. Trending audio may still be useful for discoverability within TikTok-style
   discovery; on Shorts, original voice wins.

9. **Series and repeat viewing (2025)** — A consistent series format earns algorithmic
   preference. Repeat viewing from the same creator is rewarded — a viewer who watches a
   second Short from the same creator in one session signals strong audience-fit.

10. **Metadata and keywords (lower weight)** — Shorts algorithm weights metadata far less than
    long-form YouTube. Title keywords and descriptions still affect discoverability in search,
    but behavioral signals are 80%+ of the distribution decision.

**Three-phase Shorts distribution model:**

Phase 1 — Cold seeding: 50 to 500 viewer test pool (approximately 70% non-subscribers). The
Short is evaluated against AVD and swipe-through thresholds. Shorts that clear the threshold
advance; those that do not are suppressed for wider distribution (but may persist in search).

Phase 2 — Watch time gate: if retention thresholds are met, the Short is distributed to a
broader audience in the same topic cluster. Comments, saves, and shares are measured here to
determine the ceiling for Phase 3.

Phase 3 — Topic clustering: long-tail distribution to high-intent topic audiences. A top-performing
Short in the home decor topic cluster can extend its distribution window for 3 to 6 weeks, unlike
feed-based platforms where content typically decays in 24 to 72 hours.

**Shorts monetization thresholds (current as of 2026):**

The Shorts path to YouTube Partner Program is separate from long-form:
- YPP Shorts path: 1,000 subscribers + 10 million valid Shorts views in the prior 90 days
  (vs. 1,000 subscribers + 4,000 watch hours for long-form)
- Shorts watch hours do NOT count toward the 4,000-hour long-form threshold
- Revenue share: 45% to creator (vs. 55% for long-form ad revenue)

**Shorts content freshness:** Shorts have a documented freshness decay curve of approximately
28 to 30 days (YouTube, September 2025). Unlike long-form evergreen content that accumulates
views for months, Shorts peak and decline. Plan publishing cadence accordingly — 3 to 5 Shorts
per week sustains discovery across the decay window.

**YouTube Data API note for Shorts:** There is no dedicated Shorts API endpoint in YouTube
Data API v3. Short identification is heuristic: `contentDetails.duration` of 60 seconds or less,
combined with `#Shorts` in the title or description, and 9:16 aspect ratio detected from
`fileDetails`. No separate quota system applies to Shorts.

---

## TikTok algorithm signals

Source: tiktok-newsroom (official transparency blog), tiktok-fyp-guide, tiktok-api-changelog
(verify weekly; TikTok has made material signal changes in 2025 and 2026).

**The 15 documented signals, ranked:**

1. **Rewatch / replay rate** — As of 2025, TikTok's highest-weighted single signal. A video
   rewatched even once in the same session signals strong entertainment or utility value.
   Design content with a natural re-watch hook: a reveal that improves on second viewing, a
   detail that rewards closer attention. This signal has overtaken video completion rate.
   Source: tiktok-newsroom (official).

2. **Shares** — Cross-platform DM shares and in-app shares. The second-strongest signal.
   Content designed to be shared (humor, transformation reveals, "show this to someone" moments)
   compounds quickly because shares pull new users into the session from outside the app.
   Source: tiktok-newsroom (official).

3. **Comments** — Strong positive signal. Content that provokes questions or opinions performs
   best. The first hour of comments is weighted most heavily.

4. **Video completion rate** — Still a primary signal but no longer the single most important
   one. A completion rate above 80% is strong. Roughly 70% is acceptable. Below 60% for videos
   under 30 seconds signals swipe-through and suppresses distribution.

5. **Watch time (quantified threshold: 15 to 20 second AVD earns 3x distribution)** — Confirmed
   by multiple independent analyses of TikTok's distribution patterns. For longer videos
   (1 to 3+ minutes), proportionally high completion earns compounding reward as TikTok expands
   its long-form emphasis.

6. **Saves / Favorites** — Strong signal. `favorites_count` field was added to the TikTok
   Research API in May 2026 (see `canonical-sources/keyword-library/tiktok-api-registry.json`).
   Content designed to be saved (tutorials, reference guides, before-and-after) earns saves.

7. **Longer video completion bonus (2026)** — Videos of 1 to 3+ minutes that achieve high
   completion receive outsized distribution reward as TikTok's algorithm shifts to reward
   long-form watch time alongside short-form.

8. **TikTok SEO / search-driven discovery (2025 to 2026 expansion)** — Approximately 84% of
   TikTok searches are exploration-phase (users discovering new creators, not searching for
   specific known content). Keywords in captions, voiceovers, and on-screen text feed FYP
   placement alongside search results. Treat caption keywords as SEO keywords, not just context.

9. **Micro-community clustering (2025)** — A 2025 algorithm change shifted TikTok away from
   pure virality. Niche clusters of 3 or more users with shared preference signals now receive
   relevant niche content, even from small accounts. A home decor account with 500 followers
   can reach 5,000 home-decor-interested viewers through clustering. This reduces the "lottery
   mentality" of chasing mass virality and rewards consistent niche content.

10. **Video information signals (captions, hashtags, sounds, effects)** — Official medium-weight
    signals used for topic classification and audience matching. Captions are now a primary text
    signal. The TikTok 7-second pattern interrupt is documented across multiple creator analyses
    as a retention signal: a visual or audio change within the first 7 seconds re-hooks viewers
    who are about to swipe.

11. **"Not Interested" / Skip signals** — Explicitly negative signal per TikTok's official
    documentation. A viewer who taps "Not Interested" or skips within the first 2 to 3 seconds
    actively suppresses distribution to similar audiences.

12. **Device and account settings** — Official low-weight signals: language, country, device type.
    These are relevance filters, not quality signals. Source: tiktok-newsroom (official).

13. **Content ineligible for FYP** — Official: hate speech, misinformation, fake engagement,
    watermarked content (this includes TikTok watermarks on content repurposed to competitor
    platforms). Ineligible content is distributed only to existing followers, not to the FYP.

14. **Follower count** — EXPLICITLY A NON-FACTOR. TikTok's official documentation states:
    "every video starts from zero." Follower count does not influence FYP distribution.
    A new account's first video competes on the same signal basis as an established creator's.

15. **Prior video performance** — EXPLICITLY A NON-FACTOR. One poor-performing video does not
    suppress future content. Source: tiktok-newsroom (official). This is a meaningful difference
    from YouTube, where channel authority does accumulate over time.

---

## Instagram Reels algorithm

Source: Adam Mosseri (official Instagram head) statements January 2025; Meta Graph API
documentation v25.0 (February 2026). Reels signals are distinct from both TikTok and YouTube
Shorts. Verify monthly — Meta makes frequent undocumented algorithm adjustments.

**The Reels signal stack (Mosseri official, January 2025):**

1. **Watch time and completion rate** — Primary gate. A 15-second Reel watched 3 times
   outranks a 60-second Reel watched once. The 3-second mark is a critical engagement gate:
   `skip_rate` (the percentage of viewers who skip within 3 seconds) was added as an official
   metric in December 2025. Keep the first 3 seconds visually compelling and audio-on-assumption.

2. **Sends per reach (DM shares)** — THIS IS THE UNIQUE PRIMARY SIGNAL FOR REELS. Approximately
   694,000 Reels are shared per DM per minute (Meta, 2025). The ratio of DM shares to total
   reach is weighted 3 to 5 times more than likes. Content that makes a viewer want to send it
   directly to a specific friend or group performs dramatically better on Reels than on TikTok.
   For home decor content, this means before-and-after reveals, useful thrift finds, and
   "show this to your partner who says no to dark walls" moments.

3. **Likes per reach** — Ratio to total views, not raw count. Weighted differently for
   connected reach (followers) vs. non-follower reach. A Reel shown to followers that gets
   high likes per reach earns continued feed distribution to followers. A Reel shown to
   non-followers that gets high likes per reach earns Explore and Reels tab distribution.

4. **Saves** — Classified as a "heavy" interaction. Benchmark: 50 saves plus 20 shares
   outperforms 200 likes plus 0 shares for distribution purposes. Tutorial content, reference
   guides, and step-by-step processes earn saves.

5. **Two-way conversation (March 2026)** — DMs, comment replies, and Story reactions between
   two accounts now signal genuine relationship and influence feed distribution. Content that
   prompts actual conversations in DMs earns a distribution bonus beyond the DM-share metric.

6. **Originality** — Critical threshold: accounts with 10 or more reposts in a 30-day period
   are excluded from Recommendations entirely (December 31, 2025 Mosseri memo). Original
   content receives 40 to 60% more distribution than re-shared content. Do not repost TikToks
   with watermarks — this violates both the originality requirement and Meta's duplicate
   content detection.

7. **Topic consistency** — The last 9 to 12 posts determine the account's topic categorization
   in Instagram's recommendation engine. Off-topic content (posting a food reel on a home decor
   account) reduces distribution to the home decor interest cluster. Maintain pillar consistency
   across the most recent 9 to 12 posts.

8. **Audio track** — Video understanding including audio is classified as a ranking signal.
   Original audio is preferred for recommendation matching. Trending audio still provides
   discoverability via the audio page but does not boost algorithmic recommendation.

9. **Captions** — Used for content categorization and recommendation matching. Keyword-rich
   captions improve topic classification accuracy.

**Instagram hashtag mechanics (2025 to 2026):**

- Hashtag follow feature removed December 2024
- 5-hashtag cap imposed December 2025 (previously 30 was common advice)
- Hashtags now function as classification signals for Meta's recommendation system, NOT as
  traffic sources
- 3 to 5 highly specific niche hashtags (e.g. `#moodyhomedecor`, `#vintageinterior`) are
  more effective than 10 generic hashtags
- Keywords in captions now drive discovery more strongly than hashtags

**Meta Graph API v25.0 — key publishing endpoints (current as of February 2026):**

Publishing flow (two-step):
1. `POST /{ig-user-id}/media` with `media_type=REELS`, `video_url`, optional `trial_params`
2. `POST /{ig-user-id}/media_publish` with `creation_id` from step 1
3. `GET /{ig-container-id}?fields=status_code` to poll processing

Trial Reels (new December 2025): `trial_params.graduation_strategy` set to `MANUAL` or
`SS_PERFORMANCE` tests the Reel with non-followers only before committing to full distribution.

Key insights metrics (current): `views`, `reach`, `saved`, `shares`, `skip_rate`,
`avg_watch_time`, `repost_count`. Deprecated (April 21, 2025, v22.0+): `impressions`,
`plays`, `clips_replays_count`.

**Critical deprecation (December 4, 2024):** Instagram Basic Display API was shut down entirely.
All integrations must use the Instagram Graph API via a Facebook App, not the Basic Display API.
Any system built on Basic Display API stopped working in December 2024.

See `canonical-sources/keyword-library/instagram-reels-signals.json` for the full signal
catalog and `shared/integrations-engine.md` for the complete API endpoint reference.

---

## Pinterest algorithm signals

Source: pinterest-creator-hub-seo, pinterest-business-specs (verify weekly).

1. **Keyword placement** — Pinterest is a visual search engine first. Keyword-rich Pin title
   (first 40 characters weighted most), Pin description (first 100 characters weighted most),
   board name, board description, and profile bio all feed the search index. Treat every field
   as a keyword field, not a copywriting field.

2. **Save rate (repins)** — A saved pin propagates through the follower graph of the saver. Saves
   compound over months to years as the pin resurfaces in search results and related pins.
   Prioritize content designed to be saved: reference guides, before-and-after transformations,
   step-by-step tutorials, and seasonal inspiration boards.

3. **Fresh content signal** — Pinterest boosts new pins from consistently active accounts.
   Pinning daily (5 to 10 pins, mixing fresh original content with curated topic-relevant repins)
   maintains the freshness signal. Scheduling tools (Later, Tailwind) are explicitly sanctioned
   by Pinterest for this purpose.

4. **Link domain quality** — Pins that link to fast, trustworthy domains rank better. A YouTube
   video URL is a strong link destination because YouTube has high domain authority and fast load
   times.

5. **Image quality signals** — Tall 2:3 format (1000x1500) consistently outperforms square and
   landscape. Text overlay on the image improves CTR in search results. High-contrast, warm-toned
   images perform well in the home decor niche — consistent with the home decor aesthetic.

6. **Entity recognition (2026)** — Pinterest's algorithm added entity recognition in 2026.
   Named entities in pin titles and descriptions (specific brands, furniture terms, techniques)
   now influence recommendation matching alongside keyword signals. Use entity-rich descriptions:
   "Rust-Oleum Chalked Paint in Linen White on a vintage dresser" is processed differently from
   "painted vintage furniture."

7. **Real-time engagement processing (2026)** — Interaction on one pin now immediately surfaces
   similar content from that account to the engaged user. This means a viewer who saves a "dark
   seasonal decor" pin will see the account's other dark or fall pins surfaced within the same
   session. Series and thematically consistent content compounds faster than it did before this
   change.

8. **Longevity advantage** — Unlike TikTok (24 to 72 hour peak) and Instagram Reels (3 to 7 day
   peak), Pinterest pins can rank and drive traffic for months to years. A well-optimized seasonal
   pin republished or refreshed annually compounds across years. This makes Pinterest uniquely
   valuable for evergreen DIY and decor content — the investment does not expire.

---

## Topical authority model

A single video on "seasonal home decor" competes against every other video on that exact keyword.
A cluster of related videos signals to both YouTube and Google that the channel has authority
on the subject, which earns better recommendation placement for all videos in the cluster.

**Hub-and-cluster pattern:**
- One hub video: comprehensive, long-form, targets the broadest version of the keyword
  ("Complete Seasonal Home Decor Guide")
- Three to five satellite videos: specific angles, shorter, target long-tail variations
  ("How to layer candlesticks for a moody fall look," "The one thrift store find that transformed
  my seasonal decor," "Seasonal decor on a $30 budget")

Each satellite video mentions and links to the hub in the description. The hub links to each
satellite in cards and the description. YouTube's Suggested algorithm rewards the resulting
watch-time chain — a viewer who watches the hub is likely to continue to satellites, increasing
session time and deepening the channel's authority signal.

**Pillar-to-cluster mapping:**
Apply this pattern at the pillar level. Each of the five content pillars gets its own cluster
architecture. The cluster content also reinforces Pinterest topical authority when the same
keyword phrases appear across multiple pin descriptions on the same board.

**Build order matters:** publish the hub video first, then the satellites over subsequent weeks.
Each satellite should reference the hub explicitly in the first 60 seconds and in the description.

---

## Entity SEO

Named entities (brand names, product names, places, techniques) in titles, descriptions, captions,
and spoken transcripts help YouTube's Knowledge Graph understand what a video is about and surface
it alongside related content searches.

**Rules for entity inclusion:**

- Name specific items. "Rust-Oleum Chalked Paint in Linen White" is more indexable than
  "white chalk paint."
- Name specific places when relevant. "local thrift store" or "Habitat for Humanity ReStore" is
  more indexable than "the thrift store."
- Spell out entity names in full. Avoid acronyms, shorthand, and nicknames that differ from the
  common search term.
- Repeat key entity names in the spoken audio. YouTube ASR (automatic speech recognition) feeds
  the entity model, so an entity named in the title that also appears in the spoken content
  receives stronger signal than one that only appears in the description.
- Use the brand-standard product name as it appears on the manufacturer's own marketing, not
  common abbreviations. ("Annie Sloan Chalk Paint" not "ASCP")

**Entity types relevant to this niche:**
See `canonical-sources/keyword-library/entity-keywords.json` for the full seeded list. Categories:
brands, furniture terms, architectural elements, lighting, textiles, decorative objects, techniques.

---

## Long-tail expansion methodology

Long-tail keywords (3 to 6 words, lower competition, clearer intent) drive the majority of
search traffic for new channels. A new channel cannot out-compete established channels on
"seasonal decor ideas" but can rank on "seasonal home decor on a budget" or "thrift store finds
for fall mantel decor."

**Five-method expansion sequence — traverse 2 levels from each seed:**

**1. YouTube autocomplete traversal**
Type the seed keyword into YouTube search and capture every autocomplete suggestion. Then
systematically append letters A through Z after the seed to surface additional suggestions
(a common keyword research technique). Each suggestion is a real query with real search demand.
Depth 1 from seed. Depth 2: treat the top 5 suggestions as new seeds and run autocomplete on each.

**2. Google "People Also Ask" tree**
Search the seed keyword on Google. Extract the first 5 PAA questions. Click each to expand
nested PAA — each click reveals 4 more questions. This is a recursive PAA tree; traverse
2 levels deep (seed PAA → first-level expansion → second-level expansion). Each question is
a real searcher intent that can become a video title, chapter heading, or description section.

**3. Related searches (Google SERP bottom)**
The 8 related searches at the bottom of any Google SERP are algorithmically derived from
co-search behavior. Each is a semantic neighbor of the seed. Treat each as a depth-1 long-tail
candidate. Running related searches on the top 3 related terms gives depth-2 candidates.

**4. Forum and community mining**
Reddit home decor subreddits (r/malelivingspace, r/femalelivingspace, r/DIY, r/HomeDecorating),
Pinterest comment sections, and YouTube comment sections under competitor videos surface questions
phrased in natural language that closely matches how people search. These are rarely indexed by
autocomplete tools but convert well because they reflect real intent.

**5. Product search adjacency**
Searching Etsy and Amazon for niche-adjacent products (antique brass candlesticks, dark green
velvet curtains, stylized home decor) surfaces keyword variants used by buyers. Buyer
language and searcher language have substantial overlap for decorating content.

**Depth rule:** traverse exactly 2 levels from each seed keyword. Beyond 2 levels the queries
become either too niche (near zero volume) or too generic (out of niche territory) to be useful.

**Volume labeling rule:** all volume estimates returned by long-tail-expand must be labeled
`[estimated, unverified]`. No tool in this system has direct API access to Ahrefs or SEMrush
volume data. Volume inferences from Google Trends signals are acceptable with that label.

---

## SERP feature map

Different query types trigger different SERP features. Matching content format to the dominant
feature for a keyword type is more efficient than optimizing for organic blue-link ranking.

Source: google-video-best-practices, google-structured-data-video, google-eeeat-guidelines
(verify monthly; SERP feature mix shifts with algorithm updates).

| Query type | Dominant SERP feature | Best content format | Key optimization |
|---|---|---|---|
| How-to / tutorial | Video carousel (YouTube) | Long-form YouTube video | Timestamps, chapter markers, keyword in title |
| Inspiration / aesthetic | Image pack (Google Images) | Pinterest pin, Instagram Reel cover | Keyword-rich alt text and pin description |
| "Best of" / list | Featured snippet (ordered list) | YouTube video or blog with numbered steps | Numbered steps in description and transcript |
| Style / trend | Video carousel + image pack | YouTube video + Pinterest pin | Same keyword on both platforms |
| Product / purchase | Shopping ads + product carousel | Not directly applicable; use affiliate links with product entity names | |
| Local (thrift stores, markets) | Google Maps pack | Not directly applicable; mention specific named locations for entity context | |
| Recipe / DIY steps | How-to rich result (structured data) | Web content with HowTo schema; YouTube chapter markers approximate this | |

**For video content:** the video carousel in Google SERP requires a YouTube video with:
- `name` (title matching the keyword), `description`, `thumbnailUrl`, and `uploadDate` — these
  are set by YouTube automatically from the video metadata
- Chapter markers in the description (format: `00:00 Title`) to enable key moments in SERP
- The VideoObject schema is populated by YouTube; no additional markup is needed for YouTube-hosted videos

---

## GEO and AEO optimization

GEO (Generative Engine Optimization) and AEO (AI Engine Optimization) are an emerging parallel
SEO channel alongside traditional search. When users ask AI assistants (Claude, ChatGPT, Perplexity,
Google AI Overviews) about home decor topics, those systems cite YouTube videos and web content.
Optimizing for AI citation is now a distinct SEO objective.

**Why this matters for video-first creators:** AI systems summarize content by pulling from
transcripts, chapter text, and structured data. A YouTube video with strong chapter markers,
a published transcript, and VideoObject schema is indexable by AI systems at the segment level,
not just the video level. This means an AI asking "what color makes a mantel look moody" can
cite a specific chapter of a specific video, not just say "I found a video about mantels."

**Bridge tactics: YouTube SEO to AI citation**

1. **Chapter markers as AI citation anchors** — Chapter markers in YouTube descriptions (format:
   `00:00 Title`, `01:30 Title`) create chapter-level structure that both YouTube "Key Moments"
   in Google Search and AI citation systems can reference. A chapter titled "How to layer moody
   textures on a budget mantel" creates a citable, findable content unit independent of the full
   video title.

2. **Companion blog posts with YouTube embeds** — A blog post that embeds the YouTube video,
   uses the same primary keyword in the title, and provides a written summary or transcript
   creates dual-ranking opportunity: the video ranks in YouTube Search and the blog post ranks
   in Google Search. BrightEdge (2025) documented a 53% improvement in Google ranking for blog
   posts that embed a corresponding YouTube video. The blog post is also the primary surface
   that AI search systems cite, because they prefer indexable text over video transcripts.

3. **VideoObject structured data** — YouTube automatically applies VideoObject schema to hosted
   videos. Creator-controlled fields: `name` (title), `description` (first 300 characters are
   most weighted), `thumbnailUrl`, `uploadDate`. The `hasPart` and `SeekToAction` markup in the
   description creates chapter links that both Google SERP and AI systems can use to surface
   specific segments.

4. **Transcript density** — AI citation systems pull from transcripts. Speak entity names
   explicitly in the video (see Entity SEO section). A video where "Rust-Oleum Chalked Paint
   in Linen White" is spoken aloud is more citable on that entity than one where only on-screen
   text shows it.

5. **SERP-URL-overlap clustering (GEO-relevant)** — When multiple videos from the same channel
   appear in the top-10 results for semantically related queries, AI systems are more likely
   to cite that channel as an authority rather than a one-off result. Building topical clusters
   (see Topical authority model section) is therefore both a traditional SEO strategy and an
   AI citation authority-building strategy.

**Dual-ranking strategy:**

For each hub video in a topical cluster, consider publishing a companion blog post that:
- Embeds the YouTube video
- Uses the primary keyword in the H1 title
- Includes a written version of the key steps (or a chapter-by-chapter outline)
- Cites the entity names from the video
- Links to related cluster videos with keyword-rich anchor text

This approach captures three separate distribution surfaces: YouTube Search, Google Video
Carousel, and Google Text Results — while building AI citation authority across all three.

**Tools for tracking AI citations (monitor at source_currency weekly check):**
Goodie AI, HubSpot AI Search Grader, and Otterly AI track whether content is being cited
by AI search systems. Monitoring these provides a signal for whether the entity and transcript
strategy is working.

---

## Seasonal SEO lead times

**Publish-by dates for peak search.** Source: pinterest-creator-hub-seo, youtube-creator-blog,
google-search-status. Pinterest and Google search interest peaks 2 to 6 weeks before YouTube
video peak interest for the same seasonal topic.

| Seasonal window | Search peak period | YouTube publish by | Pinterest pin by |
|---|---|---|---|
| Fall / Halloween | Sept 15 to Oct 20 | September 1 | August 15 |
| Thanksgiving / late fall | Nov 1 to Nov 25 | October 25 | October 10 |
| Christmas / holiday | Nov 20 to Dec 15 | November 10 | October 31 |
| New Year organizing | Dec 26 to Jan 15 | December 20 | December 10 |
| Valentine / cozy Feb | Feb 1 to Feb 14 | January 28 | January 15 |
| Spring refresh | Mar 1 to Apr 15 | February 20 | February 10 |
| Summer outdoor | May 1 to Jun 30 | April 25 | April 10 |
| Back-to-school / fall prep | Aug 1 to Aug 25 | July 25 | July 10 |

**Evergreen content** has no publish-by date but still benefits from keyword optimization and
entity richness at the time of publishing, as YouTube continues to index and recommend evergreen
content for months to years.

**Shorts and the seasonal calendar:** YouTube Shorts do not benefit from the same advance-publish
window as long-form content because Shorts distribution is driven by behavioral signals, not
by date-indexed search. Publish Shorts on or close to the date the topic is peak-relevant. A
Shorts series during the peak season (for example, daily fall mantel Shorts in late September)
compounds the session-contribution signal as viewers in the topic cluster discover the series.
TikTok and Instagram Reels follow the same pattern — behavioral distribution is real-time,
not advance-indexed.

---

## Source traversal and citation tracking

This engine's data is only as current as the sources it is derived from. The traversal pipeline:

1. `canonical-sources/source-registry.json` tracks each source with `last_checked`,
   `traversal_status`, and `child_source_ids`.
2. `tools/source_currency.py --report` identifies stale sources (overdue for check).
3. `tools/source_currency.py --check` queues stale sources for re-fetch via web-intel-engine.
4. `tools/traversal_engine.py --traverse-all` walks seed sources (depth 0), extracts outlinks,
   proposes candidates for operator approval. Approved candidates become depth-1 nodes in the
   registry and are themselves traversed on the next weekly run.
5. When a source's content changes (`--mark-checked --changed`), the `used_by` field identifies
   which atoms and engines need a human review pass to update their canonical data.

Default check schedule: weekly for seo-authority and partner-site; bi-weekly for platform-spec,
api-changelog, and tool-mcp; quarterly for rate-benchmark. Edit
`canonical-sources/traversal-config.json` to change any interval.
