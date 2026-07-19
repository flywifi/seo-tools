#!/usr/bin/env python3
"""parse_competitor_meta.py — extract structured metadata from saved competitor HTML files.

Reads raw.html (or rendered.html as fallback) saved by acquire.py and extracts:

YouTube (ytInitialPlayerResponse + ytInitialData):
  - video_tags: full hidden keyword list (competitor SEO strategy not visible in YouTube UI)
  - category: human-readable video category string
  - publish_date, upload_date: ISO 8601
  - is_shorts_eligible: boolean
  - available_countries: country code list
  - chapter_markers: [{timestamp_ms, title}] from player overlay (structured)
  - hashtags: #tags from description text (distinct from video_tags)
  - meta_keywords: <meta name="keywords"> content (simpler fallback for tags)

TikTok (SIGI_STATE):
  - hashtags: [{name, id}] from textExtra
  - sound_name, sound_is_original: audio metadata
  - challenges: editorial category/challenge labels
  - engagement stats: plays, likes, shares, comments

Pinterest:
  - OG tags only (full extraction requires Playwright + network interception)

All platforms:
  - og_title, og_description, og_image: Open Graph meta tags
  - json_ld: raw JSON-LD VideoObject/Article block (if present)
  - schema_types: schema.org @type values found
  - canonical_url: <link rel="canonical">
  - content_hash: sha256 of raw HTML (for change detection)

Returns a flat dict suitable for insertion into the competitor_pages SQLite table.
Never fabricates values — absent fields are returned as None.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


# ---- YouTube extraction from ytInitialPlayerResponse -------------------------

def _try_get(obj: Any, *keys) -> Any:
    """Safe nested dict access; returns None on any KeyError/TypeError."""
    for k in keys:
        try:
            obj = obj[k]
        except (KeyError, TypeError, IndexError):
            return None
    return obj


def _extract_yt_player_response(html: str) -> dict:
    """Extract ytInitialPlayerResponse from raw HTML. Primary source for video tags."""
    match = re.search(r"var ytInitialPlayerResponse\s*=\s*(\{.+?\});\s*(?:var|</script>)",
                      html, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except Exception:
        return {}


def _extract_yt_initial_data(html: str) -> dict:
    """Extract ytInitialData from raw HTML. Secondary source for chapter markers, hashtag chips."""
    match = re.search(r"var ytInitialData\s*=\s*(\{.+?\});\s*(?:var|</script>)",
                      html, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except Exception:
        return {}


def _find_in_dict(obj: Any, target_key: str, results: list, max_depth: int = 20) -> None:
    """Recursively find all values for a given key in a nested dict/list structure."""
    if max_depth <= 0:
        return
    if isinstance(obj, dict):
        if target_key in obj:
            results.append(obj[target_key])
        for v in obj.values():
            _find_in_dict(v, target_key, results, max_depth - 1)
    elif isinstance(obj, list):
        for item in obj:
            _find_in_dict(item, target_key, results, max_depth - 1)


def parse_youtube(html: str) -> dict:
    """Extract YouTube competitive metadata from raw HTML."""
    out: dict = {
        "platform": "youtube",
        "video_tags": None,
        "category": None,
        "publish_date": None,
        "upload_date": None,
        "is_shorts_eligible": None,
        "available_countries": None,
        "chapter_markers": None,
        "hashtags": None,
        "meta_keywords": None,
        "confidence": "low",
    }

    # Primary: ytInitialPlayerResponse
    pr = _extract_yt_player_response(html)
    if pr:
        video_details = pr.get("videoDetails", {})
        microformat = _try_get(pr, "microformat", "playerMicroformatRenderer") or {}

        # Video tags (the hidden keyword strategy)
        tags = video_details.get("keywords")
        if isinstance(tags, list) and tags:
            out["video_tags"] = json.dumps(tags)
            out["confidence"] = "high"

        out["category"] = microformat.get("category")
        out["publish_date"] = microformat.get("publishDate")
        out["upload_date"] = microformat.get("uploadDate")
        out["is_shorts_eligible"] = microformat.get("isShortsEligible")
        countries = microformat.get("availableCountries")
        if isinstance(countries, list):
            out["available_countries"] = json.dumps(countries)

        # Description hashtags
        description = (video_details.get("shortDescription") or
                       (microformat.get("description") or {}).get("simpleText", ""))
        if description:
            raw_hashtags = re.findall(r"(?:^|\s)#(\w+)", description)
            if raw_hashtags:
                out["hashtags"] = json.dumps(raw_hashtags)

    # Fallback for tags: <meta name="keywords">
    meta_match = re.search(r'<meta\s+name=["\']keywords["\'][^>]*content=["\']([^"\']+)["\']',
                           html, re.I)
    if not meta_match:
        meta_match = re.search(r'<meta\s+content=["\']([^"\']+)["\'][^>]*name=["\']keywords["\']',
                               html, re.I)
    if meta_match:
        out["meta_keywords"] = meta_match.group(1)
        if not out["video_tags"]:
            # Use meta keywords as fallback for tags
            tags_list = [t.strip() for t in meta_match.group(1).split(",") if t.strip()]
            if tags_list:
                out["video_tags"] = json.dumps(tags_list)
                out["confidence"] = "medium"

    # Secondary: ytInitialData for chapter markers
    initial_data = _extract_yt_initial_data(html)
    if initial_data:
        out["confidence"] = max(out["confidence"], "medium",
                                key=lambda x: {"low": 0, "medium": 1, "high": 2}[x])
        # Chapter markers — try player overlay path first
        chapters_found = []
        _find_in_dict(initial_data, "chapteredPlayerBarRenderer", chapters_found)
        if chapters_found:
            raw_chapters = _try_get(chapters_found[0], "chapters") or []
            parsed = []
            for ch in raw_chapters:
                renderer = _try_get(ch, "chapterRenderer") or {}
                title_obj = renderer.get("title") or {}
                title = title_obj.get("simpleText") or ""
                ts_ms = renderer.get("timeRangeStartMillis")
                if title or ts_ms is not None:
                    parsed.append({"timestamp_ms": ts_ms, "title": title})
            if parsed:
                out["chapter_markers"] = json.dumps(parsed)
        # Description-based chapters as fallback
        if not out["chapter_markers"]:
            desc_chapters = []
            _find_in_dict(initial_data, "expandableVideoDescriptionBodyRenderer", desc_chapters)
            desc_text = ""
            if desc_chapters:
                _find_in_dict(desc_chapters[0], "simpleText", [desc_text])
            if not desc_text:
                desc_blocks = []
                _find_in_dict(initial_data, "videoDescriptionBodyRenderer", desc_blocks)
                if desc_blocks:
                    _find_in_dict(desc_blocks[0], "simpleText", [desc_text])
            if desc_text:
                ts_lines = re.findall(r"^(\d+:\d+(?::\d+)?)\s+(.+)$", desc_text, re.MULTILINE)
                if ts_lines:
                    out["chapter_markers"] = json.dumps(
                        [{"timestamp": t, "title": title} for t, title in ts_lines]
                    )

    return out


# ---- TikTok extraction from SIGI_STATE ---------------------------------------

def parse_tiktok(html: str) -> dict:
    """Extract TikTok competitive metadata from SIGI_STATE script tag."""
    out: dict = {
        "platform": "tiktok",
        "hashtags": None,
        "sound_name": None,
        "sound_is_original": None,
        "challenges": None,
        "play_count": None,
        "digg_count": None,
        "share_count": None,
        "comment_count": None,
        "confidence": "low",
    }

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        script_tag = soup.find("script", {"id": "SIGI_STATE"})
        if not script_tag or not script_tag.string:
            return out
        data = json.loads(script_tag.string)
    except Exception:
        # Fallback: regex extraction
        match = re.search(r'<script[^>]+id=["\']SIGI_STATE["\'][^>]*>(.+?)</script>',
                          html, re.DOTALL)
        if not match:
            return out
        try:
            data = json.loads(match.group(1))
        except Exception:
            return out

    # Primary path
    item_struct = _try_get(data, "__DEFAULT_SCOPE__", "webapp.video-detail", "itemInfo", "itemStruct")
    if item_struct is None:
        # Fallback: ItemModule (older format)
        item_module = data.get("ItemModule", {})
        if item_module:
            item_struct = next(iter(item_module.values()), None)
    if not item_struct:
        return out

    out["confidence"] = "high"
    text_extra = item_struct.get("textExtra", [])
    hashtags = [t["hashtagName"] for t in text_extra if t.get("hashtagName")]
    if hashtags:
        out["hashtags"] = json.dumps(hashtags)

    music = item_struct.get("music", {})
    out["sound_name"] = music.get("title")
    out["sound_is_original"] = music.get("original")

    challenges = [c.get("title") for c in item_struct.get("challenges", []) if c.get("title")]
    if challenges:
        out["challenges"] = json.dumps(challenges)

    stats = item_struct.get("stats", {})
    out["play_count"] = stats.get("playCount")
    out["digg_count"] = stats.get("diggCount")
    out["share_count"] = stats.get("shareCount")
    out["comment_count"] = stats.get("commentCount")

    return out


# ---- Pinterest extraction (OG tags only without Playwright) ------------------

def parse_pinterest(html: str) -> dict:
    """Extract Pinterest metadata. Without Playwright, only OG tags are reliably available.
    Full pin classification (auto_alt_text, saves, tags) requires Playwright rendering
    and network interception."""
    return {
        "platform": "pinterest",
        "confidence": "low",
        "note": "Pinterest requires Playwright for structured metadata (auto_alt_text, saves, tags). "
                "OG tags extracted from raw HTML only.",
    }


# ---- Shared / cross-platform extraction --------------------------------------

def _extract_og_tags(html: str) -> dict:
    og: dict = {}
    for prop, key in [("og:title", "og_title"), ("og:description", "og_description"),
                      ("og:image", "og_image"), ("og:url", "og_url"),
                      ("og:type", "og_type"), ("og:video:tag", "og_video_tags_raw")]:
        m = re.search(rf'<meta[^>]+property=["\'{prop}["\'][^>]*content=["\']([^"\']+)["\']',
                      html, re.I)
        if not m:
            m = re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\'{prop}["\']',
                          html, re.I)
        if m:
            og[key] = m.group(1)
    return og


def _extract_json_ld(html: str) -> tuple[str | None, list[str]]:
    """Return first JSON-LD block as string + list of @type values found."""
    blocks = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.+?)</script>',
                        html, re.DOTALL | re.I)
    schema_types = []
    first_block = None
    for block in blocks:
        try:
            obj = json.loads(block)
            if first_block is None:
                first_block = block.strip()
            t = obj.get("@type")
            if isinstance(t, str):
                schema_types.append(t)
            elif isinstance(t, list):
                schema_types.extend(t)
        except Exception:
            pass
    return first_block, schema_types


def _extract_canonical(html: str) -> str | None:
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', html, re.I)
    if not m:
        m = re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']', html, re.I)
    return m.group(1) if m else None


def _detect_platform(url: str, html: str) -> str:
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "tiktok.com" in u:
        return "tiktok"
    if "pinterest.com" in u or "pin.it" in u:
        return "pinterest"
    if "instagram.com" in u:
        return "instagram"
    # Fallback: detect from HTML markers
    if "ytInitialPlayerResponse" in html or "ytInitialData" in html:
        return "youtube"
    if "SIGI_STATE" in html:
        return "tiktok"
    return "unknown"


def parse(html_path: Path, url: str = "", competitor_id: str = "") -> dict:
    """Parse a saved HTML file and return a flat dict for SQLite storage.

    Args:
        html_path: path to raw.html (or rendered.html)
        url: original URL (used for platform detection and canonical URL fallback)
        competitor_id: identifier for the competitor entry in source-registry.json
    """
    html = html_path.read_text(encoding="utf-8", errors="replace")
    content_hash = hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()

    platform = _detect_platform(url, html)

    # Platform-specific extraction
    if platform == "youtube":
        platform_data = parse_youtube(html)
    elif platform == "tiktok":
        platform_data = parse_tiktok(html)
    elif platform == "pinterest":
        platform_data = parse_pinterest(html)
    else:
        platform_data = {"platform": platform, "confidence": "low"}

    # Cross-platform extraction
    og = _extract_og_tags(html)
    json_ld_text, schema_types = _extract_json_ld(html)
    canonical = _extract_canonical(html) or og.get("og_url") or url

    result = {
        "competitor_id": competitor_id,
        "platform": platform,
        "url": url,
        "snapshot_path": str(html_path),
        "snapshot_date": None,  # filled by competitor_snapshot.py from manifest.json
        "title": og.get("og_title"),
        "og_title": og.get("og_title"),
        "og_description": og.get("og_description"),
        "og_image": og.get("og_image"),
        "meta_keywords": platform_data.get("meta_keywords"),
        "video_tags": platform_data.get("video_tags"),
        "hashtags": platform_data.get("hashtags"),
        "chapter_markers": platform_data.get("chapter_markers"),
        "category": platform_data.get("category"),
        "publish_date": platform_data.get("publish_date"),
        "upload_date": platform_data.get("upload_date"),
        "is_shorts_eligible": platform_data.get("is_shorts_eligible"),
        "available_countries": platform_data.get("available_countries"),
        # TikTok fields
        "sound_name": platform_data.get("sound_name"),
        "sound_is_original": platform_data.get("sound_is_original"),
        "challenges": platform_data.get("challenges"),
        # JSON-LD
        "json_ld": json_ld_text,
        "schema_types": json.dumps(schema_types) if schema_types else None,
        "canonical_url": canonical,
        "content_hash": content_hash,
        "confidence": platform_data.get("confidence", "low"),
        "parse_notes": platform_data.get("note"),
    }

    return result


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html_file", help="path to raw.html or rendered.html")
    ap.add_argument("--url", default="", help="original URL (for platform detection)")
    ap.add_argument("--id", default="", dest="competitor_id", help="competitor ID")
    a = ap.parse_args(argv)
    result = parse(Path(a.html_file), url=a.url, competitor_id=a.competitor_id)
    print(json.dumps(result, indent=2, default=str))
    return 0


def main(argv=None) -> int:
    """Thin CLI boundary (P66): an unhandled filesystem error from a user-supplied path (for
    example a >255-byte component raising ENAMETOOLONG, which Path.exists() does not suppress)
    becomes the clean {"error","next_step"} envelope instead of a raw traceback."""
    try:
        return _main(argv)
    except OSError as exc:
        print(json.dumps({"error": str(exc),
                          "next_step": "pass a readable file path (this one could not be opened)"}))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
