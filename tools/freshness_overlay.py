#!/usr/bin/env python3
"""freshness_overlay.py -- the per-user freshness overlay for Creator OS (P36).

The repo's canonical-sources/source-registry.json is a READ-ONLY baseline. A deployed user's
freshness state (last_checked, content hashes, change flags, refreshed values) lives in an OVERLAY
that the user controls -- a local JSON file, or (via the P35 store adapter) Google Drive / remote
MCP. The runtime NEVER writes the repo registry and NEVER touches GitHub; it writes only the
overlay, and union-merges baseline + overlay at read time. There is no upstream path, no sharing,
and no "an update is available" nag -- each user's freshness stays entirely in the store they
control.

Design (mirrors the P35 task register):
- Append-only: each overlay source keeps a history[] of freshness events; the current freshness
  fields are a fold over that history. Two overlays (e.g. two devices editing one Drive file)
  union-merge by event id without last-writer-wins clobber.
- Every refreshed VALUE carries an {as_of, source_citation, publish_date} envelope so a stale value
  ages and flags rather than being silently trusted (no-fabrication).
- Pure stdlib. All network is injected (getter) so the selftest runs offline.

This module holds no CLI of its own beyond --selftest; source_currency.py wires it into report /
check --detect-changes via an --overlay path.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

BOUNDARY = ("Personal freshness overlay. Writes only to the user's own store; never GitHub, never "
            "shared. The repo registry is a read-only baseline.")

# Freshness fields the overlay may carry for a source (folded from history).
FRESHNESS_FIELDS = (
    "last_checked", "content_sha256", "content_etag", "content_last_modified",
    "last_changed_detected", "latest_seen", "latest_seen_date", "min_recheck_at",
    "link_status", "replacement_url",
)


# -- envelope (every refreshed value keeps its provenance) --------------------
def envelope(value, source_citation, publish_date=None, as_of=None):
    """Wrap a refreshed value with the provenance needed to age it. A value with a stale publish_date
    can be flagged rather than silently trusted."""
    return {
        "value": value,
        "as_of": as_of or date.today().isoformat(),
        "source_citation": source_citation,
        "publish_date": publish_date,
    }


# -- append-only event log + fold --------------------------------------------
def _event_id(source_id, seq, at, kind):
    return f"{source_id}:{seq}:{at}:{kind}"


def record_event(overlay, source_id, kind, at, actor="user:local", **fields):
    """Append one freshness event to a source's history. Returns the event."""
    entries = overlay.setdefault("entries", {})
    entry = entries.setdefault(source_id, {"id": source_id, "history": []})
    seq = len(entry["history"])
    ev = {"event_id": _event_id(source_id, seq, at, kind), "kind": kind, "at": at,
          "actor": actor, "fields": {k: v for k, v in fields.items() if v is not None}}
    entry["history"].append(ev)
    return ev


def fold_entry(entry):
    """Fold a source's history into current freshness fields (last write per field wins WITHIN one
    entry's ordered history; across merged overlays the union of events is refolded deterministically
    by (at, event_id) order, so it is not a blind file-level last-writer-wins)."""
    folded = {"id": entry.get("id")}
    for ev in sorted(entry.get("history", []), key=lambda e: (e.get("at", ""), e.get("event_id", ""))):
        for k, v in (ev.get("fields") or {}).items():
            folded[k] = v
    return folded


def stamp(overlay, source_id, at, actor="user:local", kind="detect", **fields):
    """Record a freshness event and return the folded entry."""
    record_event(overlay, source_id, kind, at, actor=actor, **fields)
    return fold_entry(overlay["entries"][source_id])


def merge_overlays(a, b):
    """Union two overlays by event_id (append-only, no clobber) and refold. Idempotent:
    merge(x, x) == x. Deterministic regardless of argument order."""
    out = {"_boundary": BOUNDARY, "schema_version": "0.1.0", "entries": {}}
    seen = {}
    for ov in (a, b):
        for sid, entry in (ov.get("entries") or {}).items():
            bucket = seen.setdefault(sid, {})
            for ev in entry.get("history", []):
                bucket[ev.get("event_id")] = ev
    for sid, evmap in seen.items():
        hist = sorted(evmap.values(), key=lambda e: (e.get("at", ""), e.get("event_id", "")))
        out["entries"][sid] = {"id": sid, "history": hist}
    return out


def apply_overlay(baseline_sources, overlay):
    """Union-merge the overlay's folded freshness onto the read-only baseline sources. The overlay
    only supplies freshness fields; it never removes or rewrites a baseline source's identity. Returns
    a NEW list; the baseline is not mutated (so the repo registry object is never changed)."""
    folded = {sid: fold_entry(e) for sid, e in (overlay.get("entries") or {}).items()}
    merged = []
    for s in baseline_sources:
        f = folded.get(s.get("id"))
        if not f:
            merged.append(dict(s))
            continue
        m = dict(s)
        for k in FRESHNESS_FIELDS:
            if k in f and f[k] is not None:
                m[k] = f[k]
        merged.append(m)
    return merged


# -- content hashing (optionally scoped to a CSS-ish selector) ----------------
class _TextExtractor(HTMLParser):
    """Extract visible text, optionally only inside the first element matching an id or tag. Stdlib
    only; a lightweight stand-in for CSS-selector-scoped hashing (id=, tag). Kills false-positive
    'changed' events from nav/ads/timestamps outside the watched region."""

    def __init__(self, want_tag=None, want_id=None):
        super().__init__()
        self.want_tag = want_tag
        self.want_id = want_id
        self.depth = 0
        self.capturing = self.want_tag is None and self.want_id is None
        self._enter_depth = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        self.depth += 1
        if not self.capturing:
            ad = dict(attrs)
            if (self.want_id and ad.get("id") == self.want_id) or \
               (self.want_tag and tag == self.want_tag and not self.want_id):
                self.capturing = True
                self._enter_depth = self.depth

    def handle_endtag(self, tag):
        if self.capturing and self._enter_depth is not None and self.depth == self._enter_depth:
            self.capturing = False
            self._enter_depth = None
        self.depth -= 1

    def handle_data(self, data):
        if self.capturing:
            t = data.strip()
            if t:
                self.parts.append(t)


def _parse_selector(selector):
    """Tiny selector parser: '#id' -> id; 'tag' -> tag; 'tag#id' -> id. Returns (tag, id)."""
    if not selector:
        return None, None
    m = re.match(r"^([a-zA-Z0-9]*)(?:#([\w\-]+))?$", selector.strip())
    if not m:
        return None, None
    tag, _id = m.group(1) or None, m.group(2)
    return tag, _id


def content_hash(body, selector=None):
    """sha256 of the whole body, or of the normalized text inside `selector` when given. `body` may be
    bytes or str."""
    if selector:
        text = body.decode("utf-8", "ignore") if isinstance(body, (bytes, bytearray)) else body
        tag, _id = _parse_selector(selector)
        ex = _TextExtractor(want_tag=tag, want_id=_id)
        try:
            ex.feed(text)
        except Exception:  # noqa: BLE001 -- malformed HTML degrades to whole-body hash
            ex.parts = []
        scoped = " ".join(ex.parts).strip()
        if scoped:
            return hashlib.sha256(scoped.encode("utf-8")).hexdigest()
        # selector matched nothing -> fall through to whole-body hash (never silently "unchanged")
    raw = body.encode("utf-8") if isinstance(body, str) else body
    return hashlib.sha256(raw).hexdigest()


# -- RFC 9111 max-age -> minimum re-check interval ----------------------------
def max_age_seconds(cache_control):
    """Parse max-age from a Cache-Control header; returns int seconds or None. Lets the origin's own
    freshness policy lengthen (never shorten) our re-check cadence."""
    if not cache_control:
        return None
    m = re.search(r"(?:^|[,\s])max-age\s*=\s*(\d+)", cache_control, re.I)
    if not m:
        return None
    if re.search(r"(?:^|[,\s])(?:no-store|no-cache)\b", cache_control, re.I):
        return 0
    return int(m.group(1))


# -- two-tier freshness SLA (dbt warn_after / error_after) --------------------
def sla_status(age_days, warn_after, error_after):
    """ok | warn | error. `age_days` None (never checked) -> warn. error dominates."""
    if error_after is not None and age_days is not None and age_days > error_after:
        return "error"
    if age_days is None:
        return "warn"
    if warn_after is not None and age_days > warn_after:
        return "warn"
    return "ok"


# -- link-rot: Wayback Availability API (getter injected for offline test) ----
def wayback_lookup(url, getter):
    """Return {available, archived_url, timestamp} for the closest Wayback snapshot. `getter(url)`
    returns parsed JSON (injected so the selftest is offline). Never raises."""
    api = "https://archive.org/wayback/available?url=" + url
    try:
        data = getter(api) or {}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    snap = ((data.get("archived_snapshots") or {}).get("closest") or {})
    if snap.get("available") and snap.get("url"):
        return {"available": True, "archived_url": snap["url"], "timestamp": snap.get("timestamp")}
    return {"available": False}


# -- local_fs load/save (google_drive / remote_mcp reuse the P35 adapter) -----
def empty_overlay():
    return {"_boundary": BOUNDARY, "schema_version": "0.1.0", "entries": {}}


def load_overlay(path):
    p = Path(path)
    if not p.exists():
        return empty_overlay()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_overlay()
    data.setdefault("entries", {})
    return data


def save_overlay(overlay, path):
    overlay.setdefault("_boundary", BOUNDARY)
    Path(path).write_text(json.dumps(overlay, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# -- dashboard (a personal, local view; never sent anywhere) ------------------
def dashboard_markdown(report, as_of=None):
    """Render a staleness report as a single local 'Currency Dashboard' markdown -- one view, not
    notification spam (the Renovate pattern). For the user's eyes only."""
    as_of = as_of or (report.get("as_of") or date.today().isoformat())
    lines = [f"# Personal Currency Dashboard (as of {as_of})", "",
             "_Local view of your own sources. Nothing here is sent, pushed, or shared._", ""]
    summ = report.get("summary", {})
    lines.append(f"- up to date: {summ.get('up_to_date', 0)}  |  stale: {summ.get('stale', 0)}  |  "
                 f"never checked: {summ.get('never_checked', 0)}")
    lines.append("")
    stale = report.get("stale", [])
    if stale:
        lines.append("## Stale (review at your discretion)")
        for s in sorted(stale, key=lambda x: x.get("days_overdue", 0), reverse=True):
            lines.append(f"- [ ] **{s.get('name')}** ({s.get('category')}) -- "
                         f"{s.get('days_overdue', '?')}d overdue")
        lines.append("")
    never = report.get("never_checked", [])
    if never:
        lines.append("## Never checked")
        for s in never:
            lines.append(f"- [ ] {s.get('name')} ({s.get('category')})")
        lines.append("")
    return "\n".join(lines)


# -- selftest -----------------------------------------------------------------
def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # envelope
    e = envelope(1200, "https://x.example/report", publish_date="2026-05-04", as_of="2026-07-05")
    ok("envelope carries provenance", e["value"] == 1200 and e["source_citation"].endswith("report")
       and e["publish_date"] == "2026-05-04")

    # append-only fold: last write per field wins within ordered history
    ov = empty_overlay()
    stamp(ov, "s1", "2026-07-01", last_checked="2026-07-01", content_sha256="aaa")
    folded = stamp(ov, "s1", "2026-07-05", last_checked="2026-07-05", content_sha256="bbb")
    ok("fold takes latest by (at, event_id)", folded["last_checked"] == "2026-07-05"
       and folded["content_sha256"] == "bbb")
    ok("history is append-only", len(ov["entries"]["s1"]["history"]) == 2)

    # merge idempotence + union + order-independence
    m_self = merge_overlays(ov, ov)
    ok("merge(x,x) idempotent (no duplicate events)",
       len(m_self["entries"]["s1"]["history"]) == 2)
    ov2 = empty_overlay()
    stamp(ov2, "s1", "2026-07-06", last_checked="2026-07-06")
    stamp(ov2, "s2", "2026-07-06", last_checked="2026-07-06")
    m_ab = merge_overlays(ov, ov2)
    m_ba = merge_overlays(ov2, ov)
    ok("merge unions sources", set(m_ab["entries"]) == {"s1", "s2"})
    ok("merge is order-independent", fold_entry(m_ab["entries"]["s1"]) == fold_entry(m_ba["entries"]["s1"]))
    ok("merged fold takes newest event", fold_entry(m_ab["entries"]["s1"])["last_checked"] == "2026-07-06")

    # apply_overlay does not mutate baseline and merges freshness
    baseline = [{"id": "s1", "name": "Src 1", "category": "seo-authority", "used_by": ["x"]},
                {"id": "s3", "name": "Src 3", "category": "platform-spec"}]
    merged = apply_overlay(baseline, ov)
    ok("apply_overlay merges freshness onto baseline",
       next(x for x in merged if x["id"] == "s1").get("last_checked") == "2026-07-05")
    ok("apply_overlay leaves un-overlaid sources alone",
       next(x for x in merged if x["id"] == "s3").get("last_checked") is None)
    ok("apply_overlay does not mutate the baseline object", "last_checked" not in baseline[0])

    # content hashing + selector scoping
    html = "<html><nav>ads 12:03</nav><div id='spec'>Reels 9:16 1080x1920</div></html>"
    html2 = "<html><nav>ads 19:44</nav><div id='spec'>Reels 9:16 1080x1920</div></html>"
    ok("whole-body hash changes when nav timestamp changes",
       content_hash(html) != content_hash(html2))
    ok("selector-scoped hash ignores nav change",
       content_hash(html, "#spec") == content_hash(html2, "#spec"))
    ok("selector-scoped hash changes when the watched region changes",
       content_hash(html, "#spec") != content_hash(html.replace("9:16", "1:1"), "#spec"))

    # max-age
    ok("max-age parsed", max_age_seconds("public, max-age=86400") == 86400)
    ok("no-store -> 0", max_age_seconds("no-store, max-age=99") == 0)
    ok("no max-age -> None", max_age_seconds("public") is None)

    # SLA
    ok("sla ok", sla_status(3, 7, 30) == "ok")
    ok("sla warn past warn_after", sla_status(10, 7, 30) == "warn")
    ok("sla error past error_after", sla_status(40, 7, 30) == "error")
    ok("sla never-checked warns", sla_status(None, 7, 30) == "warn")

    # wayback (injected getter)
    def wb_getter(url):
        return {"archived_snapshots": {"closest": {"available": True,
                "url": "http://web.archive.org/web/20260101/https://x.example/a", "timestamp": "20260101"}}}
    wb = wayback_lookup("https://x.example/a", wb_getter)
    ok("wayback returns archived url", wb["available"] and "web.archive.org" in wb["archived_url"])
    ok("wayback handles no snapshot", wayback_lookup("x", lambda u: {})["available"] is False)

    # dashboard renders without error
    dash = dashboard_markdown({"as_of": "2026-07-05", "summary": {"stale": 1, "never_checked": 0, "up_to_date": 5},
                               "stale": [{"name": "S", "category": "seo-authority", "days_overdue": 4}],
                               "never_checked": []})
    ok("dashboard renders stale checklist", "S" in dash and "as of 2026-07-05" in dash)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
