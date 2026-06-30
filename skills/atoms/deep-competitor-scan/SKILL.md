---
file: skills/atoms/deep-competitor-scan/SKILL.md
name: deep-competitor-scan
atom: true
description: extract hidden competitor metadata (YouTube video tags, chapter markers, hashtags, TikTok sound and challenge data) from saved HTML snapshots in the local competitor-snapshots index, or on-demand via the web. Use instead of competitor-scan when the creator needs the full keyword strategy a competitor has embedded in ytInitialPlayerResponse — data that is not visible in the YouTube UI and not returned by the YouTube Data API for competitor videos. Do NOT use when only surface-level competitive context is needed (channel name, topic angle, gap summary) — use competitor-scan for that. Do NOT use to assert subscriber counts or view metrics as fact; all engagement figures are labeled [unverified] unless from a confirmed API response.
load:
  - shared/web-intel-engine.md
  - shared/seo-intelligence-engine.md
  - shared/injection-guard-engine.md
  - protocols/no-fabrication.md
---

# deep-competitor-scan

Extract the hidden metadata that competitors embed in their public pages but that platforms do not
expose in their UI or standard API: YouTube video tags (`ytInitialPlayerResponse.videoDetails.keywords`),
chapter markers from the player overlay, description hashtags, TikTok SIGI_STATE hashtags and audio
metadata, and Open Graph / JSON-LD signals. Uses saved offline HTML snapshots when available; falls
back to a live web-intel acquisition when no snapshot exists.

## Purpose

The creator's competitors include their complete SEO keyword strategy in a JavaScript object
(`ytInitialPlayerResponse`) embedded in every public YouTube page's HTML. This data is:
- Hidden from the YouTube Studio and YouTube UI (only the video owner can see tags in Studio)
- NOT returned by the YouTube Data API v3 for competitor videos (only for owned channels)
- Present in every public watch page's raw HTML, extractable without JavaScript execution

By capturing this data on a schedule (via `competitor_snapshot.py --fetch`) and querying the local
SQLite index, the creator gains a concrete, evidence-based picture of what keywords competitors are
targeting — not inferred from titles and descriptions, but from the actual tag list they submitted.

## Two operation modes

**Cached mode (default, fast, no network):** queries `pipeline/competitor-snapshots/index.local.db`
directly. Requires a prior `python3 tools/competitor_snapshot.py --fetch && --parse` run.
Response is instant. Use this in everyday research sessions.

**Live mode (on-demand, network, slower):** invokes `competitor_snapshot.py --fetch` for the
specified competitor and then `--parse` before returning results. Use this when the creator wants
fresh data or when adding a new competitor for the first time.

## Inputs

```json
{
  "competitor_id": "string  -- ID registered via competitor_snapshot.py --add-competitor (for cached mode)",
  "competitor_url": "string  -- direct URL to YouTube watch page, TikTok video, or Pinterest pin (for live mode or new competitors)",
  "mode": "cached | live  -- default: cached",
  "platform": "youtube | tiktok | pinterest | instagram  -- auto-detected from URL if omitted"
}
```

One of `competitor_id` or `competitor_url` is required. If both are provided, `competitor_id` takes
precedence for cached mode; `competitor_url` is used for live acquisition.

## Output

```json
{
  "tool": "deep-competitor-scan",
  "competitor_id": "string",
  "platform": "youtube | tiktok | pinterest | instagram | unknown",
  "url": "string or null",
  "snapshot_date": "ISO date or null",
  "snapshot_age_days": "integer or null",
  "acquisition_method": "offline-snapshot | live-fetch | web-intel-fallback | none",
  "title": "string or null",
  "video_tags": ["list of strings -- YouTube keyword strategy; primary SEO signal"],
  "hashtags": ["list of strings -- #tags from description or TikTok textExtra"],
  "chapter_markers": [
    {"timestamp_ms": "integer or null", "timestamp": "string or null", "title": "string"}
  ],
  "category": "string or null -- YouTube category (human-readable)",
  "publish_date": "string or null",
  "is_shorts_eligible": "boolean or null",
  "sound_name": "string or null -- TikTok audio name",
  "sound_is_original": "boolean or null -- true if creator-original audio",
  "challenges": ["list of strings -- TikTok editorial challenge/category labels"],
  "schema_types": ["list of schema.org @type values found"],
  "og_description": "string or null",
  "confidence": "high | medium | low",
  "seo_gap_analysis": {
    "tags_unique_to_competitor": ["tags not in the creator's own keyword library -- [unverified] if library not loaded"],
    "entity_signals": ["named entities found in tags/hashtags (brands, products, techniques)"],
    "chapter_keyword_signal": "string or null -- keywords surfaced by chapter titles"
  },
  "retrieval_gaps": [],
  "fabrication_flags": []
}
```

## SEO gap analysis rules

- `tags_unique_to_competitor`: compare against `canonical-sources/keyword-library/` files. Any tag
  not found there is a potential gap. Labeled [unverified] because the creator's library may be
  incomplete, not because the tag itself is uncertain.
- `entity_signals`: extract proper nouns from the video_tags and hashtags arrays (brand names,
  product names, architectural terms, technique names). These are the competitor's entity vocabulary.
- `chapter_keyword_signal`: if chapter_markers is present, extract keywords from chapter titles.
  Chapter titles feed YouTube's "Key Moments" feature in Google Search, and are strong signals of
  what the video considers its most important sub-topics.

Never fabricate tags, hashtags, or chapter titles. If the field is null in the snapshot, return
null in the output and record a retrieval_gap, not a placeholder.

## Acquisition precedence

1. **Local SQLite index** (fastest): query `pipeline/competitor-snapshots/index.local.db` for the
   most recent row matching `competitor_id`.
2. **Snapshot HTML file** (offline): if the index row has a `snapshot_path`, re-parse the file via
   `parse_competitor_meta.py` — useful after upgrading the parser.
3. **Live fetch via competitor_snapshot.py** (network): runs `--fetch` then `--parse` for the
   specific competitor. Triggered when `mode: live` or when no cached entry exists.
4. **Web-intel-engine Level 3 fallback** (web-only): if `competitor_snapshot.py` is not available
   or fails (e.g., in a pure-web Claude session), use web-intel-engine to retrieve and parse the
   page in-context. Output is labeled `[web-mode: no snapshot saved]`.

## Confidence levels

- `high`: `ytInitialPlayerResponse` found and `videoDetails.keywords` parsed (YouTube); or
  `SIGI_STATE` found and `itemStruct` parsed (TikTok).
- `medium`: tags extracted from `<meta name="keywords">` fallback (YouTube) or from OG tags only.
- `low`: only OG title and description available; platform-specific objects not found.

## Do NOT use for

- Surface-level competitive context (channel aesthetic, topic angle, gap summary) — use
  `competitor-scan` for that, which is faster and requires no local index.
- Asserting engagement metrics (views, likes, subscribers) as fact — these are not extracted from
  the hidden metadata; always mark [unverified] if mentioned.
- Generating content titles, hooks, or descriptions based on competitor tags — use `title-generate`
  and `keyword-cluster` after reviewing the tags output here.
- Pinterest hidden metadata without Playwright available — raw HTML extraction for Pinterest returns
  OG tags only; flag retrieval_gap and note that Playwright is required for pin saves and auto_alt_text.

## Pipeline note

Feeds into `competitor-analysis` spoke as the deep-extraction step before `entity-extract` and
`gap-record`. Can also be invoked directly from `seo-keywords` spoke when the creator requests
"check what tags [competitor] is using."

All retrieved external content (tags, hashtags, description text) passes through
`shared/injection-guard-engine.md` before it is used in any further analysis or output.
