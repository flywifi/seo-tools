#!/usr/bin/env python3
"""parse_competitor_meta.py: extract structured metadata from saved competitor HTML files.

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
Never fabricates values; absent fields are returned as None.
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import re
from pathlib import Path
from typing import Any

# P75: the parser's own version, stored on every row it produces.
#
# `content_hash` answers "is this the same page?". Nothing answered "is this the same READING of
# the page?", so when P74-0 fixed the OG extractor, re-parsing skipped every existing row as
# "unchanged" -- the HTML had not moved, only the parser had -- and the corrupted rows survived a
# fix that was supposed to repair them.
#
# BUMP THIS whenever extraction behaviour changes. competitor_snapshot.py compares it against the
# stored value and supersedes rows parsed by an older version, so a future extractor fix repairs
# its own historical rows instead of silently leaving them wrong.
PARSER_VERSION = "2026-10-11.1"

# The selftest's reading of its own fixture pages under PARSER_VERSION: the sha256 of the JSON it
# builds from them (selftest, _fixture_reading). A change to what the parser extracts changes the
# sha256, so the selftest fails until PARSER_VERSION is bumped and both values below are recorded
# again. It cannot tell a re-recorded sha256 under the old version from a bump; review does.
_READING = {"version": "2026-10-11.1",
            "sha256": "f02d5624be48de88844f8c68f77f39e21ae2022a221054fe8bde7bbc7fffc030"}

# An HTML attribute value in double or single quotes. The other quote may appear inside it: a title
# such as Kid's Room in a double-quoted attribute is read whole, not cut at the apostrophe.
_QV = r'''(?:"([^"]*)"|'([^']*)')'''


def _qv(m) -> str:
    """The attribute value _QV captured: its double-quoted group, else its single-quoted one."""
    return m.group(1) if m.group(1) is not None else m.group(2)


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


def _player_bar_chapters(initial_data: Any) -> list:
    """The chapter list a page keeps under multiMarkersPlayerBarRenderer -> markersMap -> value ->
    chapters: the entry keyed DESCRIPTION_CHAPTERS when its list has chapters, else the first
    entry whose list has chapters (P102). [] when the page has no such list, so the caller falls
    back to chapteredPlayerBarRenderer, which pages also use."""
    bars: list = []
    _find_in_dict(initial_data, "multiMarkersPlayerBarRenderer", bars)
    for bar in bars:
        entries = bar.get("markersMap") if isinstance(bar, dict) else None
        if not isinstance(entries, list):
            continue
        with_chapters = [e for e in entries if isinstance(e, dict)
                         and isinstance(_try_get(e, "value", "chapters"), list)
                         and _try_get(e, "value", "chapters")]
        preferred = [e for e in with_chapters if e.get("key") == "DESCRIPTION_CHAPTERS"]
        for entry in preferred or with_chapters:
            return _try_get(entry, "value", "chapters") or []
    return []


def _chapter_rows(raw_chapters: list) -> list:
    """[{timestamp_ms, title}] from chapterRenderer entries; an entry with neither is dropped, and
    a renderer or title that is not an object reads as absent."""
    parsed = []
    for ch in raw_chapters or []:
        renderer = _try_get(ch, "chapterRenderer")
        if not isinstance(renderer, dict):
            continue
        title_obj = renderer.get("title")
        title = (title_obj.get("simpleText") if isinstance(title_obj, dict) else None) or ""
        ts_ms = renderer.get("timeRangeStartMillis")
        if title or ts_ms is not None:
            parsed.append({"timestamp_ms": ts_ms, "title": title})
    return parsed


# A double-quoted phrase, or a run of characters that are neither whitespace nor a double quote.
# Only the double quote groups words: an apostrophe (kid's) and a backslash are ordinary
# characters, and a double quote that never closes is skipped, so the words after it are kept.
_KW_WORD = re.compile(r'"([^"]*)"|([^\s"]+)')
# The pieces of a comma list: a double-quoted phrase, a run with no comma or double quote, a lone
# double quote, or a comma.
_KW_PIECE = re.compile(r'"[^"]*"|[^,"]+|"|,')


def _split_keywords(text: str) -> list:
    """Keywords from a <meta name="keywords"> value, in one pass with no recursion (P102). A value
    with a comma outside its double-quoted phrases is a comma list: it splits at those commas, a
    part written as one quoted phrase loses its quotes, and a quote that never closes is dropped.
    Otherwise words split on whitespace and each double-quoted phrase is kept whole."""
    if "," in re.sub(r'"[^"]*"', "", text):
        parts, buf = [], []
        for piece in _KW_PIECE.findall(text):
            if piece == ",":
                parts.append("".join(buf))
                buf = []
            elif piece != '"':
                buf.append(piece)
        parts.append("".join(buf))
        out = []
        for part in (x.strip() for x in parts):
            whole = re.fullmatch(r'"([^"]*)"', part)
            out.append(whole.group(1).strip() if whole else part)
        return [x for x in out if x]
    return [w for w in ((a or b).strip() for a, b in _KW_WORD.findall(text)) if w]


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
    meta_match = re.search(r'<meta\s+name=["\']keywords["\'][^>]*content=' + _QV, html, re.I)
    if not meta_match:
        meta_match = re.search(r'<meta\s+content=' + _QV + r'[^>]*name=["\']keywords["\']',
                               html, re.I)
    if meta_match and _qv(meta_match).strip():
        out["meta_keywords"] = _html.unescape(_qv(meta_match))
        if not out["video_tags"]:
            # Use meta keywords as fallback for tags. A channel page writes them space-separated
            # with quoted phrases and escaped quotes ("diy &quot;how to&quot; ..."), so unescape
            # first and split quoted phrases whole; a comma list still splits on commas (P102).
            tags_list = _split_keywords(out["meta_keywords"])
            if tags_list:
                out["video_tags"] = json.dumps(tags_list)
                out["confidence"] = "medium"

    # Secondary: ytInitialData for chapter markers
    initial_data = _extract_yt_initial_data(html)
    if initial_data:
        out["confidence"] = max(out["confidence"], "medium",
                                key=lambda x: {"low": 0, "medium": 1, "high": 2}[x])
        # Chapter markers — try player overlay path first
        raw_chapters = _player_bar_chapters(initial_data)
        if not raw_chapters:
            chapters_found = []
            _find_in_dict(initial_data, "chapteredPlayerBarRenderer", chapters_found)
            if chapters_found:
                raw_chapters = _try_get(chapters_found[0], "chapters") or []
        parsed = _chapter_rows(raw_chapters)
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
        # P74-0: the quote group MUST close before the property name. The previous spelling was
        # ["\'{prop}["\'] -- one unterminated character class that swallowed the property name, so
        # it matched a SINGLE character and every og_* key received the first meta tag's content
        # (og_image held the title, and so on, straight into the competitor snapshot DB).
        # re.escape because og:video:tag and any future property must be matched literally.
        p = re.escape(prop)
        m = re.search(rf'<meta[^>]+property=["\']{p}["\'][^>]*content=' + _QV, html, re.I)
        if not m:
            m = re.search(r'<meta[^>]+content=' + _QV + rf'[^>]*property=["\']{p}["\']',
                          html, re.I)
        if m and _qv(m).strip():
            og[key] = _html.unescape(_qv(m))  # "A &amp; B" -> "A & B", once (P102)
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
    """The canonical link's href, unescaped once like the og values ("?a=1&amp;b=2" -> "?a=1&b=2")."""
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*href=' + _QV, html, re.I)
    if not m:
        m = re.search(r'<link[^>]+href=' + _QV + r'[^>]*rel=["\']canonical["\']', html, re.I)
    return _html.unescape(_qv(m)) if m and _qv(m).strip() else None


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
        "parser_version": PARSER_VERSION,
    }

    return result


def selftest() -> int:
    """Offline proof over synthetic HTML. No network, no files, no repo mutation.

    Exists because P74-0 shipped: _extract_og_tags copied ONE meta tag's content into all six
    og_* keys for an unknown number of phases, and those keys are persisted by
    competitor_snapshot.py and surfaced by the deep-competitor-scan atom. Nothing executed this
    module's logic, so nothing caught it. The first two cases are that regression.
    """
    failures = []

    def ok(name, cond):
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    html = ('<meta property="og:title" content="REAL TITLE">'
            '<meta property="og:image" content="https://example.com/img.jpg">'
            '<meta property="og:type" content="video.other">')
    og = _extract_og_tags(html)
    ok("og properties map to their OWN content (P74-0 regression)",
       og.get("og_title") == "REAL TITLE" and og.get("og_image") == "https://example.com/img.jpg"
       and og.get("og_type") == "video.other")
    ok("an absent og property stays absent, never copied from a sibling (P74-0 regression)",
       "og_title" not in _extract_og_tags('<meta property="og:image" content="i.jpg">'))
    ok("reversed attribute order still matches",
       _extract_og_tags('<meta content="Rev" property="og:title">').get("og_title") == "Rev")
    ok("a colon-heavy property matches literally",
       _extract_og_tags('<meta property="og:video:tag" content="diy">').get("og_video_tags_raw") == "diy")
    ok("empty html yields no tags and never raises", _extract_og_tags("") == {})

    ok("canonical link extracted",
       _extract_canonical('<link rel="canonical" href="https://example.com/a">') == "https://example.com/a")
    _, types = _extract_json_ld('<script type="application/ld+json">'
                                '{"@type":"VideoObject","name":"n"}</script>')
    ok("json-ld @type surfaced", "VideoObject" in types)
    ok("truncated json-ld degrades to a tuple, never a crash",
       isinstance(_extract_json_ld('<script type="application/ld+json">{"@ty'), tuple))

    ok("absent ytInitialPlayerResponse -> {} (not None, not an exception)",
       _extract_yt_player_response("<html></html>") == {})
    pr = _extract_yt_player_response(
        '<html>var ytInitialPlayerResponse = {"videoDetails":{"keywords":["a","b"]}};</script>')
    ok("ytInitialPlayerResponse parsed when terminated by </script>",
       isinstance(pr, dict) and pr.get("videoDetails", {}).get("keywords") == ["a", "b"])

    found = []
    _find_in_dict({"a": [{"t": 1}, {"b": {"t": 2}}]}, "t", found)
    ok("_find_in_dict recurses lists and nested dicts", found == [1, 2])
    shallow = []
    _find_in_dict({"a": [{"t": 1}]}, "t", shallow, 1)
    ok("_find_in_dict honours its depth bound (untrusted JSON cannot force unbounded recursion)",
       shallow == [])
    ok("_try_get returns None on a bad path", _try_get({"a": {"b": 1}}, "a", "zz") is None)
    ok("platform detected from url", _detect_platform("https://www.youtube.com/watch?v=1", "") == "youtube")

    # P102: chapters under multiMarkersPlayerBarRenderer or chapteredPlayerBarRenderer; channel
    # keywords with quoted phrases; og, keyword and canonical values with entities and quotes.
    def initial(data):
        return '<html><script>var ytInitialData = ' + json.dumps(data) + ';</script></html>'

    def chapter(title, ms):
        return {"chapterRenderer": {"title": {"simpleText": title}, "timeRangeStartMillis": ms}}

    def markers(*entries):
        return {"playerOverlays": {"playerBar": {"multiMarkersPlayerBarRenderer": {
            "markersMap": [{"key": k, "value": {"chapters": c}} for k, c in entries]}}}}

    bar = markers(("AUTO_CHAPTERS", [chapter("auto", 0)]),
                  ("DESCRIPTION_CHAPTERS", [chapter("Plan", 0), chapter("Paint & prep", 100000),
                                            {"chapterRenderer": {}}]))
    rows = _chapter_rows(_player_bar_chapters(bar))
    ok("chapters read from multiMarkersPlayerBarRenderer, the DESCRIPTION_CHAPTERS entry preferred",
       rows == [{"timestamp_ms": 0, "title": "Plan"}, {"timestamp_ms": 100000, "title": "Paint & prep"}])
    ok("a page without that player bar yields [] from _player_bar_chapters",
       _player_bar_chapters({"a": {"chapteredPlayerBarRenderer": {}}}) == [])
    yt = parse_youtube(initial(bar))
    ok("parse_youtube stores the player-bar chapters",
       json.loads(yt["chapter_markers"] or "[]") == rows)
    older = parse_youtube(initial({"playerOverlays": {"playerBar": {"chapteredPlayerBarRenderer": {
        "chapters": [chapter("Intro", 0), chapter("Sand", 42000)]}}}}))
    ok("a page with only chapteredPlayerBarRenderer has its chapters read from there",
       json.loads(older["chapter_markers"] or "[]")
       == [{"timestamp_ms": 0, "title": "Intro"}, {"timestamp_ms": 42000, "title": "Sand"}])
    heat = markers(("HEATSEEKER", None), ("AUTO_CHAPTERS", [chapter("Auto one", 0)]))
    heat["playerOverlays"]["playerBar"]["multiMarkersPlayerBarRenderer"]["markersMap"][0]["value"] = {
        "heatMarkers": [{"heatMarkerRenderer": {}}]}
    ok("without DESCRIPTION_CHAPTERS the first entry that has chapters is read",
       _chapter_rows(_player_bar_chapters(heat)) == [{"timestamp_ms": 0, "title": "Auto one"}])
    ok("an empty DESCRIPTION_CHAPTERS list gives way to an entry that has chapters",
       _chapter_rows(_player_bar_chapters(markers(("DESCRIPTION_CHAPTERS", []),
                                                  ("AUTO_CHAPTERS", [chapter("Auto", 0)]))))
       == [{"timestamp_ms": 0, "title": "Auto"}])
    ok("a chapter renderer or title that is not an object reads as absent, never raises",
       _chapter_rows([{"chapterRenderer": "x"}, {"chapterRenderer": {"title": "Intro",
                                                                      "timeRangeStartMillis": 5}}])
       == [{"timestamp_ms": 5, "title": ""}])

    kw_cases = [
        ('diy "how to" makeover "room makeover"', ["diy", "how to", "makeover", "room makeover"]),
        ("a, b c, d", ["a", "b c", "d"]),
        ('diy "how to" "room make', ["diy", "how to", "room", "make"]),
        ("diy \"how to\" kid's room", ["diy", "how to", "kid's", "room"]),
        ("kid's mom's room", ["kid's", "mom's", "room"]),
        ('"rock, paper" scissors', ["rock, paper", "scissors"]),
        ("C\\D drive", ["C\\D", "drive"]),
        ('a, "b, c", d', ["a", "b, c", "d"]),
        ('a, "b, c', ["a", "b", "c"]),
        ('"" x', ["x"]),
    ]
    for text, want in kw_cases:
        ok(f"keywords {text!r} split as {want!r}", _split_keywords(text) == want)
    many = _split_keywords("kid's " + ' "w x"' * 3000)
    ok("an apostrophe before 3000 quoted phrases splits in one pass",
       len(many) == 3001 and many[:2] == ["kid's", "w x"])
    ch = parse_youtube('<meta name="keywords" content="diy &quot;how to&quot; makeover">')
    ok("the keywords fallback unescapes before splitting",
       json.loads(ch["video_tags"]) == ["diy", "how to", "makeover"] and ch["meta_keywords"] == 'diy "how to" makeover')
    raw = parse_youtube('<meta name="keywords" content="diy &quot;kid\'s room&quot; decor">')
    ok("an apostrophe inside a double-quoted keywords attribute is read whole",
       json.loads(raw["video_tags"]) == ["diy", "kid's room", "decor"])
    ok("og values are unescaped once",
       _extract_og_tags('<meta property="og:title" content="SMALL &amp; AWKWARD &quot;entryway&quot;">').get("og_title")
       == 'SMALL & AWKWARD "entryway"'
       and _extract_og_tags('<meta property="og:title" content="Tom &amp;amp; Jerry">').get("og_title")
       == "Tom &amp; Jerry")
    ok("an og value keeps an apostrophe in a double-quoted attribute and a double quote in a single-quoted one",
       _extract_og_tags('<meta property="og:title" content="Kid\'s Room">').get("og_title") == "Kid's Room"
       and _extract_og_tags("<meta content='Say \"hi\"' property='og:title'>").get("og_title") == 'Say "hi"')
    ok("an empty og value stays absent", "og_title" not in _extract_og_tags('<meta property="og:title" content="">'))
    ok("the canonical href is unescaped once, like og_url",
       _extract_canonical('<link rel="canonical" href="https://example.com/w?a=1&amp;b=2">')
       == "https://example.com/w?a=1&b=2")

    reading = _fixture_reading()
    ok(f"the fixture pages read as _READING records (sha256 {reading}); a change to what the parser "
       f"extracts needs a PARSER_VERSION bump and both values recorded again",
       _READING == {"version": PARSER_VERSION, "sha256": reading})

    print(f"parse_competitor_meta selftest: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 1 if failures else 0


def _fixture_reading() -> str:
    """sha256 of what the parser extracts from a fixed set of fixture pages, for the _READING pin
    (test code: selftest calls it)."""
    def chapter(title, ms):
        return {"chapterRenderer": {"title": {"simpleText": title}, "timeRangeStartMillis": ms}}

    data_new = {"playerOverlays": {"playerBar": {"multiMarkersPlayerBarRenderer": {"markersMap": [
        {"key": "AUTO_CHAPTERS", "value": {"chapters": [chapter("auto", 0)]}},
        {"key": "DESCRIPTION_CHAPTERS", "value": {"chapters": [chapter("Plan", 0),
                                                                chapter("Paint & prep", 100000)]}}]}}}}
    data_old = {"playerOverlays": {"playerBar": {"chapteredPlayerBarRenderer": {
        "chapters": [chapter("Intro", 0), chapter("Sand", 42000)]}}}}
    player = {"videoDetails": {"keywords": ["diy", "entryway"], "shortDescription": "Paint #diy now"},
              "microformat": {"playerMicroformatRenderer": {"category": "Howto & Style",
                                                            "publishDate": "2026-10-01"}}}
    pages = [
        '<meta property="og:title" content="Kid\'s Room &amp;amp; More">'
        '<meta content="https://example.com/i.jpg" property="og:image">'
        '<link rel="canonical" href="https://example.com/w?a=1&amp;b=2">'
        '<script>var ytInitialPlayerResponse = ' + json.dumps(player) + ';</script>'
        '<script>var ytInitialData = ' + json.dumps(data_new) + ';</script>',
        '<meta name="keywords" content="diy &quot;how to&quot; kid&#39;s room, &quot;rock, paper&quot;">'
        '<script>var ytInitialData = ' + json.dumps(data_old) + ';</script>',
        "<meta name='keywords' content='diy \"how to\" \"room make'>"
        '<script type="application/ld+json">{"@type":"VideoObject","name":"n"}</script>',
    ]
    reading = [[parse_youtube(h), _extract_og_tags(h), _extract_canonical(h), _extract_json_ld(h)]
               for h in pages]
    blob = json.dumps(reading, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true", help="offline proof over synthetic HTML")
    ap.add_argument("html_file", nargs="?", help="path to raw.html or rendered.html")
    ap.add_argument("--url", default="", help="original URL (for platform detection)")
    ap.add_argument("--id", default="", dest="competitor_id", help="competitor ID")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.html_file:
        ap.error("html_file is required (or pass --selftest)")
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
