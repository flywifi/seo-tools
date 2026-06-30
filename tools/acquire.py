#!/usr/bin/env python3
"""acquire.py — all-in redundant acquisition for ONE public URL (token-free, max-success).

Ported from educator-tools-k12-public/tools/acquire.py for use in Creator OS competitive
intelligence. Gathers (each independent — one failing never stops the others):
  1. browser_headers   full-browser-header GET                 -> raw.html
  2. render            REAL Chromium: runs JS/WASM/SPA          -> rendered.html
                       captures the page's OWN xhr/fetch data    + network/*
  3. screenshot        full-page screenshot                    -> page.png
  4. mirror            download linked FILES found in the HTML  -> files/*
  5. wayback           closest Internet Archive snapshot        -> wayback.html

All artifacts land in an out folder + a manifest.json. Robots respected unless --ignore-robots
(maintainer override for authorized public data).

After acquisition, call tools/parse_competitor_meta.py to extract structured metadata
(YouTube tags, TikTok hashtags, JSON-LD, OG tags) from the saved HTML files.

USAGE
  python3 tools/acquire.py "https://www.youtube.com/watch?v=VIDEO_ID" --out pipeline/competitor-snapshots/
  python3 tools/acquire.py URL --out pipeline/competitor-snapshots/ --depth 0 --max-files 0
"""
from __future__ import annotations

import argparse
import glob as _glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch_resilient as FR  # noqa
import rate_governor as RG    # noqa
import fetch_diag as FD       # noqa
import fetch_cache as FC      # noqa


def _mac_playwright_chrome() -> list[str]:
    """Return installed Playwright Chromium paths on macOS (arm64 and x86_64)."""
    base = os.path.expanduser("~/Library/Caches/ms-playwright")
    return sorted(
        _glob.glob(f"{base}/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
        reverse=True,  # newest version first
    )


CHROME_CANDIDATES = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",  # remote CI (Linux)
    "/opt/pw-browsers/chromium/chrome-linux/chrome",        # remote CI fallback
    *_mac_playwright_chrome(),                              # macOS (arm64 + x86_64)
]
FILE_EXT = (".pdf", ".xlsx", ".xls", ".docx", ".doc", ".csv", ".zip", ".json", ".xml")


def _links(html_text: str, base: str) -> list[str]:
    out = []
    for href in re.findall(r'href=["\']([^"\']+)["\']', html_text, re.I):
        if href.startswith(("javascript:", "#", "mailto:")):
            continue
        out.append(urllib.parse.urljoin(base, href))
    return out


def _same_domain(a: str, b: str) -> bool:
    return urllib.parse.urlparse(a).netloc.split(":")[0].replace("www.", "") == \
           urllib.parse.urlparse(b).netloc.split(":")[0].replace("www.", "")


DATA_CT = ("application/json", "text/json", "application/ld+json", "application/xml",
           "text/xml", "application/x-ndjson", "text/csv")


def _autoscroll(pg, max_steps: int = 25, pause: int = 600) -> None:
    try:
        last = -1
        for _ in range(max_steps):
            h = pg.evaluate("() => (document.body ? document.body.scrollHeight : 0)")
            if h == last:
                break
            last = h
            pg.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            pg.wait_for_timeout(pause)
    except Exception:  # noqa: BLE001
        pass


def render_and_shot(url: str, outdir: Path, timeout: float = 45.0,
                    scroll: bool = True, capture_network: bool = True) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return {"render": False, "screenshot": False, "network": 0, "frames": 0,
                "note": "playwright not installed"}
    res = {"render": False, "screenshot": False, "network": 0, "frames": 0, "note": ""}
    captured: list = []

    def _on_response(resp):
        if len(captured) >= 150:
            return
        try:
            ct = (resp.headers or {}).get("content-type", "").lower()
            u = resp.url
            if any(t in ct for t in DATA_CT) or u.split("?")[0].lower().endswith(
                    (".json", ".xml", ".geojson", ".csv", ".ndjson")):
                body = resp.body()
                if body and len(body) <= 12_000_000:
                    captured.append((u, ct, body))
        except Exception:  # noqa: BLE001
            pass

    try:
        with sync_playwright() as p:
            kw = {}
            for c in CHROME_CANDIDATES:
                if Path(c).exists():
                    kw["executable_path"] = c
                    break
            b = p.chromium.launch(headless=True, **kw)
            ctx = b.new_context(user_agent=FR.BROWSER_HEADERS["User-Agent"],
                                viewport={"width": 1366, "height": 1000})
            pg = ctx.new_page()
            if capture_network:
                pg.on("response", _on_response)
            pg.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            try:
                pg.wait_for_load_state("networkidle", timeout=timeout * 1000)
            except Exception:  # noqa: BLE001
                pass
            if scroll:
                _autoscroll(pg)
            pg.wait_for_timeout(1200)
            (outdir / "rendered.html").write_text(pg.content(), encoding="utf-8")
            res["render"] = True
            for i, fr in enumerate(f for f in pg.frames if f is not pg.main_frame):
                try:
                    fh = fr.content()
                    if fh and len(fh) > 200:
                        (outdir / f"frame_{i}.html").write_text(fh, encoding="utf-8")
                        res["frames"] += 1
                except Exception:  # noqa: BLE001
                    pass
            try:
                pg.screenshot(path=str(outdir / "page.png"), full_page=True)
                res["screenshot"] = True
            except Exception as e:  # noqa: BLE001
                res["note"] = f"screenshot failed: {e.__class__.__name__}"
            if captured:
                ndir = outdir / "network"; ndir.mkdir(exist_ok=True)
                used = set()
                for u, ct, body in captured:
                    stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", u.split("?")[0].rsplit("/", 1)[-1] or "resp")[:60]
                    ext = ".json" if "json" in ct or u.lower().split("?")[0].endswith(".json") else \
                          ".xml" if "xml" in ct else ".csv" if "csv" in ct else ".txt"
                    name = stem if stem.lower().endswith(ext) else stem + ext
                    k = 0
                    while name in used:
                        k += 1; name = f"{k}_{stem}{ext}"
                    used.add(name)
                    try:
                        (ndir / name).write_bytes(body); res["network"] += 1
                    except Exception:  # noqa: BLE001
                        pass
            b.close()
    except Exception as e:  # noqa: BLE001
        res["note"] = f"render failed: {e.__class__.__name__}"
    return res


def _governed_get(gov: "RG.RateGovernor", url: str, timeout: float, cap: int,
                  cache: "FC.FetchCache" = None):
    ok, why = gov.can_request(url)
    if not ok:
        return None, why
    for attempt in range(3):
        gov.wait(url)
        try:
            headers = dict(FR.BROWSER_HEADERS)
            if cache:
                headers.update(cache.validators(url))
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read(cap)
                hdrs = dict(r.headers)
            gov.note(url, getattr(r, "status", 200), hdrs)
            if cache and not cache.update(url, hdrs, raw):
                return b"", {"unchanged": True}
            return raw, hdrs
        except urllib.error.HTTPError as e:
            if e.code == 304:
                gov.note(url, 304, {})
                if cache:
                    cache.note_unchanged(url)
                return b"", {"unchanged": True}
            hdrs = dict(getattr(e, "headers", {}) or {})
            wait = gov.note(url, e.code, hdrs)
            if wait is not None and attempt < 2:
                time.sleep(wait)
                continue
            return None, f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            gov.note(url, 0, {})
            return None, e.__class__.__name__
    return None, "retries exhausted"


def mirror(seed_html: str, base_url: str, outdir: Path, depth: int, max_files: int,
           max_pages: int, ignore_robots: bool, gov: "RG.RateGovernor" = None,
           cache: "FC.FetchCache" = None) -> dict:
    if gov is None:
        gov = RG.RateGovernor(FR.BROWSER_HEADERS["User-Agent"], respect_robots=not ignore_robots)
    files_dir = outdir / "files"; files_dir.mkdir(exist_ok=True)
    got_files, got_pages, unchanged, seen = [], [], 0, {base_url}
    queue = [(base_url, seed_html, 0)]
    while queue:
        cur_url, cur_html, d = queue.pop(0)
        for link in _links(cur_html, cur_url):
            low = link.lower().split("?")[0]
            if low.endswith(FILE_EXT) and link not in seen and len(got_files) < max_files:
                seen.add(link)
                data, info = _governed_get(gov, link, 25, 30_000_000, cache)
                if data is None:
                    continue
                if isinstance(info, dict) and info.get("unchanged"):
                    unchanged += 1; got_files.append(link); continue
                name = re.sub(r"[^a-zA-Z0-9._-]+", "_", urllib.parse.urlparse(link).path.split("/")[-1] or "file")[:80]
                (files_dir / name).write_bytes(data)
                got_files.append(link)
            elif d < depth and _same_domain(link, base_url) and link not in seen and len(got_pages) < max_pages:
                seen.add(link)
                raw, info = _governed_get(gov, link, 20, 10_000_000, cache)
                if raw is None:
                    continue
                if isinstance(info, dict) and info.get("unchanged"):
                    unchanged += 1; got_pages.append(link); continue
                enc = (info.get("Content-Encoding") or "").lower() if isinstance(info, dict) else ""
                sub = _decode(raw, enc)
                pname = re.sub(r"[^a-zA-Z0-9]+", "_", link)[:70] + ".html"
                (outdir / pname).write_text(sub, encoding="utf-8")
                got_pages.append(link); queue.append((link, sub, d + 1))
    return {"files": got_files, "pages": got_pages, "unchanged": unchanged}


def _decode(raw: bytes, content_encoding: str) -> str:
    import gzip
    import zlib
    try:
        if "gzip" in content_encoding:
            raw = gzip.decompress(raw)
        elif "deflate" in content_encoding:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
    except Exception:  # noqa: BLE001
        pass
    return raw.decode("utf-8", "replace")


def acquire(url: str, outdir: Path, ignore_robots: bool = False, depth: int = 0,
            max_files: int = 0, max_pages: int = 0, do_ocr: bool = False,
            gov: "RG.RateGovernor" = None, per_host_budget: int = RG.DEFAULT_BUDGET,
            min_interval: float = RG.DEFAULT_MIN_INTERVAL) -> dict:
    """Fetch a URL with all available prongs. Defaults tuned for competitor page snapshots:
    depth=0 (no link following), max_files=0 (no file download), do_ocr=False (no OCR).
    Adjust for broader acquisitions."""
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = {"url": url, "artifacts": {}, "ok_any": False}
    if gov is None:
        gov = RG.RateGovernor(FR.BROWSER_HEADERS["User-Agent"], per_host_budget=per_host_budget,
                              min_interval=min_interval, respect_robots=not ignore_robots)
    ok, why = gov.can_request(url)
    if not ok:
        manifest["note"] = f"skipped: {why}"
        (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        gov.save()
        return manifest

    cache = FC.FetchCache()
    seed_html = ""
    gov.wait(url)
    r1 = FR.prong_browser_headers(url)
    gov.note(url, r1.get("status"), None)
    static_body = r1["content"].decode("utf-8", "replace") if r1.get("content") else ""
    if r1.get("ok") and r1.get("content"):
        seed_html = static_body
        (outdir / "raw.html").write_text(seed_html, encoding="utf-8")
        manifest["artifacts"]["raw_html"] = True; manifest["ok_any"] = True
    block = FD.classify_block(r1.get("status"), None, static_body)
    manifest["block"] = block
    if block["blocked"] and not block["retry_worthwhile"] and block["confidence"] != "low":
        gov.cooldown(url, reason=f"{block['vendor'] or block['kind']} block")
    if gov.can_request(url)[0]:
        gov.wait(url)
        rs = render_and_shot(url, outdir)
    else:
        rs = {"render": False, "screenshot": False, "network": 0, "frames": 0,
              "note": "skipped (breaker/budget)"}
    manifest["artifacts"].update({"rendered_html": rs["render"], "screenshot": rs["screenshot"],
                                  "iframes": rs.get("frames", 0),
                                  "network_responses": rs.get("network", 0)})
    if rs["render"]:
        manifest["ok_any"] = True
        rendered = (outdir / "rendered.html").read_text(encoding="utf-8", errors="replace")
        if len(rendered) > len(seed_html):
            seed_html = rendered
    rw = FR.prong_wayback(url)
    if rw.get("ok") and rw.get("content"):
        (outdir / "wayback.html").write_text(rw["content"].decode("utf-8", "replace"), encoding="utf-8")
        manifest["artifacts"]["wayback_html"] = True; manifest["ok_any"] = True
        if not seed_html:
            seed_html = rw["content"].decode("utf-8", "replace")
    manifest["data_sources"] = FD.find_data_sources(seed_html, url)
    if seed_html and (depth > 0 or max_files > 0):
        m = mirror(seed_html, url, outdir, depth, max_files, max_pages, ignore_robots, gov, cache)
        manifest["artifacts"]["mirrored_files"] = len(m["files"])
        manifest["artifacts"]["mirrored_pages"] = len(m["pages"])
        manifest["artifacts"]["unchanged_skipped"] = m["unchanged"]
        if m["files"] or m["pages"]:
            manifest["ok_any"] = True

    manifest["rate"] = gov.summary()
    manifest["incremental"] = cache.summary()
    manifest["diag"] = FD.summarize(block, manifest["data_sources"])
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    gov.save()
    cache.save()
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--out", default="pipeline/competitor-snapshots")
    ap.add_argument("--ignore-robots", action="store_true")
    ap.add_argument("--depth", type=int, default=0)
    ap.add_argument("--max-files", type=int, default=0)
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--per-host-budget", type=int, default=RG.DEFAULT_BUDGET)
    ap.add_argument("--min-interval", type=float, default=RG.DEFAULT_MIN_INTERVAL)
    a = ap.parse_args(argv)
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", a.url)[:70]
    out = Path(a.out) / slug
    m = acquire(a.url, out, a.ignore_robots, a.depth, a.max_files, a.max_pages, not a.no_ocr,
                per_host_budget=a.per_host_budget, min_interval=a.min_interval)
    print(json.dumps(m, indent=2))
    print(f"\n{'RECOVERED' if m['ok_any'] else 'FAILED (all methods)'} -> {out}")
    return 0 if m["ok_any"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
