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
   images perform well in the home decor niche — consistent with the moody-vintage aesthetic.

---

## Topical authority model

A single video on "dark fall mantel" competes against every other video on that exact keyword.
A cluster of related videos signals to both YouTube and Google that the channel has authority
on the subject, which earns better recommendation placement for all videos in the cluster.

**Hub-and-cluster pattern:**
- One hub video: comprehensive, long-form, targets the broadest version of the keyword
  ("Complete Dark Moody Fall Mantel Guide")
- Three to five satellite videos: specific angles, shorter, target long-tail variations
  ("How to layer candlesticks for a moody fall look," "The one thrift store find that transformed
  my fall mantel," "Dark fall mantel on a $30 budget")

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
- Name specific places when relevant. "Goodwill Orlando" or "Habitat for Humanity ReStore" is
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
"fall mantel ideas" but can rank on "moody dark fall mantel on a budget" or "thrift store finds
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
velvet curtains, moody vintage wall art) surfaces keyword variants used by buyers. Buyer
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
