#!/usr/bin/env python3
"""fetch_diag.py — diagnose a fetch: WHY was it blocked, and is there a cleaner structured source?

Two honest, token-free diagnostics for the local acquirer:

1. classify_block(status, headers, body)  -> which anti-bot vendor + challenge type, from STATIC HTTP
   signatures. Used defensively: feed the result to the rate governor so a detected hard block trips
   the per-host breaker BEFORE repeated hits earn a real lockout.

2. find_data_sources(html, base_url)       -> structured sources already on the page (JSON-LD,
   __NEXT_DATA__/__NUXT__ state, RSS/Atom feeds, /api/ endpoints, sitemap hint) PLUS platform-specific
   embedded JSON blobs (YouTube ytInitialPlayerResponse/ytInitialData, TikTok SIGI_STATE,
   Pinterest __PWS_DATA__). Detects what is available so the caller can prefer structured parsing
   over scraping rendered HTML.
"""
from __future__ import annotations

import re
import urllib.parse

_VENDORS = [
    ("Cloudflare", {
        "headers": ["cf-ray", "cf-mitigated", "cf-chl-bypass", "cf-cache-status"],
        "server": ["cloudflare"],
        "cookies": ["__cf_bm", "cf_clearance"],
        "body": ["just a moment", "/cdn-cgi/challenge-platform", "attention required",
                 "cf-challenge", "checking if the site connection is secure", "window._cf_chl_opt"],
    }),
    ("DataDome", {
        "headers": ["x-datadome", "x-dd-b"],
        "server": [],
        "cookies": ["datadome"],
        "body": ["geo.captcha-delivery.com", "captcha-delivery.com", "js.datadome.co", "datadome"],
    }),
    ("PerimeterX/HUMAN", {
        "headers": ["x-px"],
        "server": [],
        "cookies": ["_px", "_pxhd", "_pxvid", "_px2", "_px3", "pxcts"],
        "body": ["px-captcha", "client.perimeterx.net", "window._pxappid", "perimeterx", "/api/v1/px/"],
    }),
    ("Akamai Bot Manager", {
        "headers": ["x-akamai", "akamai-"],
        "server": ["akamaighost", "akamai"],
        "cookies": ["_abck", "ak_bmsc", "bm_sz", "bm_sv", "bm_mi", "bm_so"],
        "body": [],
    }),
    ("Imperva/Incapsula", {
        "headers": ["x-iinfo", "x-cdn"],
        "server": ["incapsula"],
        "cookies": ["incap_ses", "visid_incap", "nlbi_", "reese84"],
        "body": ["_incapsula_resource", "incapsula incident", "request unsuccessful"],
    }),
    ("AWS WAF", {
        "headers": ["x-amzn-waf-action"],
        "server": ["awselb"],
        "cookies": ["aws-waf-token"],
        "body": ["token.awswaf.com", "captcha.awswaf.com", "awswaf"],
    }),
    ("Kasada", {
        "headers": ["x-kpsdk"],
        "server": [],
        "cookies": [],
        "body": ["/ips.js", "kpsdk", "kasada"],
    }),
]

# P82-9: real challenge interstitials are small; genuine pages that merely EMBED a captcha
# widget are large. Measured 2026-09-12: nine false-positive pages ran 85 KB to 1.1 MB; a
# Cloudflare interstitial is under ~16 KB. 30 KB separates the populations with wide margin.
_CHALLENGE_BODY_MAX = 30_000

_CAPTCHAS = [
    ("hCaptcha", ["hcaptcha.com", "h-captcha", "hcaptcha"]),
    ("reCAPTCHA", ["recaptcha", "g-recaptcha", "google.com/recaptcha"]),
    ("Turnstile", ["cf-turnstile", "challenges.cloudflare.com/turnstile"]),
]


def _blob(headers: dict | None) -> str:
    if not headers:
        return ""
    parts = []
    for k, v in headers.items():
        parts.append(f"{str(k).lower()}: {str(v).lower()}")
    return "\n".join(parts)


def classify_block(status: int | None, headers: dict | None = None, body: str = "") -> dict:
    """Classify a (possibly blocked) response by anti-bot vendor + challenge kind."""
    hdr = _blob(headers)
    low = (body or "").lower()[:200_000]
    signals: list[str] = []
    vendor = None

    for name, sig in _VENDORS:
        hits = []
        for h in sig["headers"]:
            if re.search(rf"(?:^|\n){re.escape(h)}", hdr):
                hits.append(f"header {h}")
        for s in sig["server"]:
            if re.search(rf"server:.*{re.escape(s)}", hdr):
                hits.append(f"server {s}")
        for c in sig["cookies"]:
            if c in hdr:
                hits.append(f"cookie {c}")
        for b in sig["body"]:
            if b in low:
                hits.append(f"body '{b}'")
        if hits:
            vendor = name
            signals = hits
            break

    captcha = None
    for name, marks in _CAPTCHAS:
        if any(m in low for m in marks):
            captcha = name
            signals.append(f"captcha {name}")
            break

    is_4xx_block = status in (401, 403, 406, 451)
    is_throttle = status in (429, 503)
    is_success = status is not None and 200 <= status < 300
    challenge_body = any(s.startswith("body") for s in signals)
    # P82-9: on a SUCCESS response, a captcha asset or a bare vendor fingerprint is not a wall.
    # Genuine pages embed reCAPTCHA for their own forms (Google's blog carries 'recaptcha' five
    # times on a 623 KB page of real content), and every site behind a CDN carries that CDN's
    # header/cookie fingerprint (Akamai has NO body markers, so its 200-verdicts were always
    # fingerprint-only). A real challenge interstitial is small (Cloudflare's is under ~16 KB)
    # or carries a challenge-specific body marker. Requiring that evidence on a 2xx ended nine
    # false "permanently blocked" verdicts on healthy seo-authority sources (2026-09-12).
    # Non-2xx logic is unchanged: a 403/429/503 is still a block/throttle on status alone.
    if captcha and is_success and not challenge_body and len(body or "") > _CHALLENGE_BODY_MAX:
        signals = [s for s in signals if not s.startswith("captcha ")]
        captcha = None
    if vendor and is_success and not challenge_body and not captcha:
        vendor = None  # a CDN serving real content, not a CDN refusing us
    challenge_markers = challenge_body or captcha
    blocked = bool(vendor or captcha or is_4xx_block or is_throttle)

    if captcha:
        kind, retry = "captcha", False
    elif is_throttle:
        kind, retry = "rate_limit", True
    elif vendor and challenge_markers:
        kind, retry = "challenge", False
    elif vendor or is_4xx_block:
        kind, retry = "ip_block", False
    else:
        kind, retry = "none", True

    confidence = "high" if (vendor and challenge_markers) or captcha else \
                 "medium" if vendor or is_4xx_block or is_throttle else "low"

    advice = _advice(vendor, kind, captcha)
    return {"blocked": blocked, "vendor": vendor or captcha, "kind": kind,
            "confidence": confidence, "signals": signals[:8], "advice": advice,
            "retry_worthwhile": retry, "status": status}


def _advice(vendor, kind, captcha) -> str:
    if kind == "rate_limit":
        return ("Server is rate-limiting (honor Retry-After; the governor backs off). Slow down.")
    if kind == "captcha" or captcha:
        return (f"Interactive {captcha or 'CAPTCHA'} challenge — prefer the site's official data "
                "file / API, or a Wayback snapshot.")
    if kind == "challenge":
        return (f"{vendor} managed challenge — a plain GET won't pass. The real-browser render "
                "prong may legitimately load it; otherwise prefer official API or Wayback.")
    if kind == "ip_block":
        return (f"{vendor or 'Server'} is refusing automated requests. Back off (breaker), use "
                "the official data source / API or Wayback.")
    return "No anti-bot block detected."


_FEED_RE = re.compile(
    r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*href=["\']([^"\']+)["\']', re.I)
_FEED_RE2 = re.compile(
    r'<link[^>]+href=["\']([^"\']+)["\'][^>]*type=["\']application/(?:rss|atom)\+xml["\']', re.I)
_JSONLD_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>', re.I)
_HREF_RE = re.compile(r'(?:href|src|action)=["\']([^"\']+)["\']', re.I)


# Platform-specific embedded JSON detection markers
_PLATFORM_MARKERS = [
    # YouTube — primary machine-readable metadata object (video tags, category, dates)
    ("ytInitialPlayerResponse", "YouTube ytInitialPlayerResponse (video tags, category, microformat)"),
    # YouTube — UI-rendered data (chapter markers, hashtag chips, engagement panels)
    ("ytInitialData", "YouTube ytInitialData (UI data, chapter markers, hashtag chips)"),
    # TikTok — structured video metadata (hashtags, sound, challenges, stats)
    ("SIGI_STATE", "TikTok SIGI_STATE (hashtags, sound metadata, challenges, engagement stats)"),
    # Pinterest — client-side state (requires Playwright; partial data in raw HTML)
    ("__PWS_DATA__", "Pinterest __PWS_DATA__ (board/pin state; requires Playwright for full extraction)"),
    ("__PWS_INITIAL_PROPS__", "Pinterest __PWS_INITIAL_PROPS__ (requires Playwright)"),
    # Instagram — (these patterns have been patched as of 2024; included for detection only)
    ("window.__initialData", "Instagram __initialData (patched as of 2024; low reliability)"),
    # Generic SPA frameworks
    ("__NEXT_DATA__", "Next.js __NEXT_DATA__"),
    ("__NUXT__", "Nuxt __NUXT__"),
    ("window.__INITIAL_STATE__", "__INITIAL_STATE__"),
    ("__APOLLO_STATE__", "Apollo cache"),
]


def find_data_sources(html: str, base_url: str) -> dict:
    """Spot structured/data sources already exposed by the page, including platform-specific
    embedded JSON blobs that carry competitive metadata (video tags, hashtags, chapters).
    Nothing fetched here — detection only."""
    out = {"json_ld": 0, "embedded_state": [], "platform_blobs": [],
           "feeds": [], "api_endpoints": [], "sitemap": None}
    if not html:
        return out
    out["json_ld"] = len(_JSONLD_RE.findall(html))

    for marker, label in _PLATFORM_MARKERS:
        if marker in html:
            if any(p in label for p in ("YouTube", "TikTok", "Pinterest", "Instagram")):
                out["platform_blobs"].append(label)
            else:
                out["embedded_state"].append(label)

    feeds = set(_FEED_RE.findall(html)) | set(_FEED_RE2.findall(html))
    out["feeds"] = sorted(urllib.parse.urljoin(base_url, f) for f in feeds)

    eps = set()
    for href in _HREF_RE.findall(html):
        low = href.lower().split("?")[0]
        if any(seg in low for seg in ("/api/", "/wp-json/", "/rest/", "/graphql", "/odata")) \
                or low.endswith((".json", ".geojson")):
            eps.add(urllib.parse.urljoin(base_url, href))
        if low.endswith("/sitemap.xml") or low.endswith("/sitemap_index.xml"):
            out["sitemap"] = urllib.parse.urljoin(base_url, href)
    out["api_endpoints"] = sorted(eps)[:25]
    return out


def summarize(block: dict, sources: dict) -> str:
    bits = []
    if block.get("blocked"):
        bits.append(f"block={block['vendor'] or block['kind']}({block['confidence']})")
    s = []
    if sources.get("json_ld"):
        s.append(f"{sources['json_ld']} JSON-LD")
    if sources.get("platform_blobs"):
        s.append("platform:" + "+".join(b.split(" ")[0] for b in sources["platform_blobs"]))
    if sources.get("embedded_state"):
        s.append("+".join(sources["embedded_state"]))
    if sources.get("feeds"):
        s.append(f"{len(sources['feeds'])} feed(s)")
    if sources.get("api_endpoints"):
        s.append(f"{len(sources['api_endpoints'])} api-ish link(s)")
    if sources.get("sitemap"):
        s.append("sitemap")
    if s:
        bits.append("structured: " + ", ".join(s))
    return "; ".join(bits) or "no block, no structured-source hints"


def selftest() -> int:
    """Offline proof of the anti-bot classifier over synthetic responses. No network (P74 WP4).

    classify_block takes the body as str, not bytes. Both directions matter: calling a live page
    blocked wastes the acquire budget, and calling a block "fine" makes the caller trust an
    error page as content."""
    failures = []

    def ok(name, cond):
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    cf = classify_block(403, {"server": "cloudflare", "cf-ray": "abc"},
                        "Attention Required! | Cloudflare")
    ok("a Cloudflare challenge is identified by vendor", cf.get("vendor") == "Cloudflare")
    ok("a challenge is marked blocked and not worth a naive retry",
       cf.get("blocked") is True and cf.get("retry_worthwhile") is False)
    ok("the classification cites the signals it used, never a bare verdict",
       bool(cf.get("signals")))

    clean = classify_block(200, {"server": "nginx"}, "<html>ok</html>")
    ok("an ordinary 200 is NOT called a block",
       clean.get("blocked") is False and clean.get("vendor") is None)
    ok("an unblocked response is worth retrying", clean.get("retry_worthwhile") is True)

    widget = classify_block(200, {"server": "cloudflare"},
                            "<html><title>Real article</title>" + "x" * 40_000 +
                            "<script src='https://www.google.com/recaptcha/api.js'></script></html>")
    ok("a genuine 200 page embedding a captcha widget is NOT a block (P82-9)",
       widget.get("blocked") is False)
    cdn = classify_block(200, {"server": "cloudflare", "cf-ray": "abc"},
                         "<html>plain healthy page" + "y" * 40_000 + "</html>")
    ok("a CDN fingerprint on a healthy 200 is NOT a block (P82-9)",
       cdn.get("blocked") is False and cdn.get("vendor") is None)
    interstitial = classify_block(200, {"server": "cloudflare"},
                                  "<html>Just a moment... /cdn-cgi/challenge-platform</html>")
    ok("a 200-served challenge interstitial IS still a block",
       interstitial.get("blocked") is True)
    small_captcha = classify_block(200, {}, "<html>verify: g-recaptcha challenge</html>")
    ok("a small 200 body with a captcha marker IS still a block",
       small_captcha.get("blocked") is True)
    hard403 = classify_block(403, {"server": "cloudflare", "cf-ray": "abc"},
                             "Attention Required! | Cloudflare")
    ok("non-2xx classification is unchanged by P82-9",
       hard403.get("blocked") is True and hard403.get("retry_worthwhile") is False)

    src = find_data_sources(
        '<link rel="alternate" type="application/rss+xml" href="/feed.xml">', "https://example.com")
    ok("a feed is surfaced as an absolute URL",
       "https://example.com/feed.xml" in (src.get("feeds") or []))
    empty = find_data_sources("<html></html>", "https://example.com")
    ok("a page with no structured sources yields empty lists, not invented ones",
       not any(empty.get(k) for k in ("feeds", "api_endpoints", "platform_blobs")))
    ok("summarize renders a human line for the no-block case",
       isinstance(summarize(clean, empty), str) and summarize(clean, empty).strip() != "")

    print(f"fetch_diag selftest: {'PASS' if not failures else 'FAIL'} ({len(failures)} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    print("fetch_diag is a library; run with --selftest to verify its classifiers.")
