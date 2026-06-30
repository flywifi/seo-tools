# deep-competitor-scan — Maintainer Reference

## What this atom does

Extracts hidden competitor metadata from saved HTML snapshots or live web acquisition. The primary
signal is YouTube's `ytInitialPlayerResponse.videoDetails.keywords` — the complete video tag list
that YouTube embeds in every public watch page's raw HTML. This list is invisible in the YouTube UI
and unavailable via the YouTube Data API v3 for competitor videos. It represents the competitor's
actual, submitted SEO keyword strategy.

## Invariants

1. `video_tags` is only populated from `ytInitialPlayerResponse.videoDetails.keywords` (primary) or
   `<meta name="keywords">` (fallback, `confidence: medium`). Never from the title or description.
2. All fields absent in the source HTML are returned as null — never invented or inferred.
3. `confidence` reflects acquisition method: `high` = player response found; `medium` = meta-keywords
   fallback only; `low` = OG tags only (platform-specific JSON not present).
4. Pinterest extraction at `confidence: high` requires Playwright. Without it, only OG tags are
   returned and the output notes `[requires Playwright for full extraction]`.
5. Instagram extraction is limited to caption hashtag parsing and OG tags only; `confidence` is
   always `low` unless the Graph API was used (separate tooling, not this atom).
6. All external content (tags, hashtags, description text from competitor pages) passes through
   `injection-guard-engine.md` before analysis. Do not trust competitor-supplied data implicitly.

## Data flow

```
user invokes deep-competitor-scan
        │
        ├── mode: cached (default)
        │       └── query pipeline/competitor-snapshots/index.local.db
        │               └── return most recent row for competitor_id
        │
        └── mode: live
                └── competitor_snapshot.py --fetch --id <competitor_id>
                        └── acquire.py -> raw.html + rendered.html + manifest.json
                └── competitor_snapshot.py --parse --id <competitor_id>
                        └── parse_competitor_meta.py -> SQLite row
                └── query SQLite row
                        └── build output dict
```

## Parser internals (`parse_competitor_meta.py`)

**YouTube — primary path:**
```python
re.search(r"var ytInitialPlayerResponse\s*=\s*(\{.+?\});\s*(?:var|</script>)", html, re.DOTALL)
# -> player_response["videoDetails"]["keywords"]         # tags (primary)
# -> player_response["microformat"]["playerMicroformatRenderer"]["category"]
# -> player_response["microformat"]["playerMicroformatRenderer"]["publishDate"]
# -> player_response["microformat"]["playerMicroformatRenderer"]["isShortsEligible"]
```

**YouTube — chapter markers:**
```python
# Primary: playerOverlays path via _find_in_dict(initial_data, "chapteredPlayerBarRenderer", ...)
# Fallback: timestamp regex on description text
re.findall(r"^(\d+:\d+(?::\d+)?)\s+(.+)$", description, re.MULTILINE)
```

**TikTok:**
```python
soup.find("script", {"id": "SIGI_STATE"})
# -> data["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"]["textExtra"]
# -> [t["hashtagName"] for t in textExtra if t.get("hashtagName")]
```

## Local index schema

Table `competitor_pages` in `pipeline/competitor-snapshots/index.local.db` (gitignored):
```
competitor_id, platform, url, snapshot_path, snapshot_date,
title, og_title, og_description, og_image, meta_keywords,
video_tags (JSON), hashtags (JSON), chapter_markers (JSON),
category, publish_date, upload_date, is_shorts_eligible, available_countries (JSON),
sound_name, sound_is_original, challenges (JSON),
json_ld, schema_types (JSON), canonical_url, content_hash,
confidence, parse_notes, inserted_at
```

Keyed on `(competitor_id, content_hash)` — re-parsing the same HTML snapshot (same hash) is a
no-op. New snapshots of the same competitor accumulate as new rows, enabling change detection.

## Regression cases (map to evals/evals.json)

| Case | Input | Expected |
|---|---|---|
| YouTube cached hit | competitor_id with row in SQLite | video_tags non-null, confidence high/medium |
| YouTube live fetch | competitor_url for YouTube watch page | fetch + parse triggered; video_tags present |
| TikTok cached hit | competitor_id with TikTok row | hashtags non-null, sound_name non-null |
| Pinterest (no Playwright) | competitor_url for Pinterest pin | confidence low, parse_notes notes OG-only |
| Unknown platform | URL not matching any known platform | platform=unknown, confidence low, no crash |
| Empty SQLite / cold start | cached mode, no index | retrieval_gap recorded, falls to live fetch |
| Stale snapshot | snapshot_age_days > 7 | snapshot_age_days reported, recommendation to refresh |

## Update checklist

When `parse_competitor_meta.py` is updated:
- Run `python3 tools/competitor_snapshot.py --parse` to re-parse all saved HTML with the new logic
- Update `evals/evals.json` if output shape changes
- Update `confidence` level definitions in SKILL.md if new acquisition paths are added

When YouTube changes the `ytInitialPlayerResponse` structure:
- Update the regex in `_extract_yt_player_response()` in `parse_competitor_meta.py`
- Update field paths in `parse_youtube()` for any moved or renamed keys
- Run evals — the `video_tags` field is the canary; if it returns null on a page known to have tags,
  the extraction is broken

When TikTok changes the `SIGI_STATE` structure:
- Update `parse_tiktok()` paths in `parse_competitor_meta.py`
- The `__DEFAULT_SCOPE__` -> `webapp.video-detail` path has been stable since 2023 but can change
  without notice. Monitor `source-registry.json` entry for `tiktok-sigi-state-structure` freshness.

## Source registry entries this atom depends on

- `tiktok-sigi-state-structure` (category: api-changelog) — track when TikTok changes SIGI_STATE
- All `competitor-page` category entries — managed via `competitor_snapshot.py --add-competitor`
- `youtube-creator-blog` (category: seo-authority) — algorithm changes may affect tag weighting

## Fabrication rule

The tags in `video_tags` come verbatim from the competitor's HTML. They are never interpreted,
paraphrased, or enriched. The SEO gap analysis fields (`tags_unique_to_competitor`,
`entity_signals`) are derived by comparing the raw tags to the creator's keyword library — that
comparison is labeled [unverified] because the library may be incomplete, not because the tags
themselves are uncertain.

If the creator's keyword library path is unavailable, `seo_gap_analysis` returns empty arrays and
records a `retrieval_gap` — it does not invent gaps.
