#!/usr/bin/env python3
"""Drop-folder scan + approve for the Drive hub Inbox (P60).

The offline half of the inbox-routing atom: scan lists what is NEW in Inbox/ (sha256-diffed
against the ledger), classifies each file by FORMAT (shared/docintel/classify.py), and proposes a
route only for categories the rules table marks category_source 'format' (transcripts, media,
platform export bundles). Document types that need their CONTENT read (contracts, pitches,
invoices) are listed as needs_review for a Claude session running the inbox-routing atom with the
injection guard; this tool never pretends to have read them. approve is the only writer: it moves
approved files to Inbox/Processed/<date>/ and records the routing in the gitignored inbox ledger.
Nothing is written or moved by scan.

Usage:
  python3 tools/handoff/inbox.py scan --hub PATH [--json]
  python3 tools/handoff/inbox.py approve --hub PATH --proposal FILE.json
  python3 tools/handoff/inbox.py --selftest
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

from shared.docintel import classify as _classify  # noqa: E402

RULES_PATH = ROOT / "shared" / "docintel" / "inbox_rules.json"
LEDGER_PATH = ROOT / "pipeline" / "inbox" / "inbox-ledger.local.json"

# family/ext -> the format-assignable content_category (everything else needs content review).
_FORMAT_CATEGORY = {
    "transcript": "transcript",
    "video": "video_media",
    "audio": "audio_media",
}
_EXPORT_HINTS = ("takeout", "studio", "dyi", "export")


def load_rules(path=RULES_PATH) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get("rules", {})
    except (OSError, ValueError):
        return {}


def load_ledger(path=LEDGER_PATH) -> dict:
    """{sha256: entry}. Missing/unreadable -> empty (the scan says so; approve still refuses to
    double-write a file already in Processed)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return {e["sha256"]: e for e in data.get("entries", []) if e.get("sha256")}
    except (OSError, ValueError):
        return {}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _format_category(info: dict, name: str) -> str | None:
    fam = info.get("family")
    if fam in _FORMAT_CATEGORY:
        return _FORMAT_CATEGORY[fam]
    if fam == "archive" and any(h in name.lower() for h in _EXPORT_HINTS):
        return "platform_export"
    return None


def scan(hub_root, rules=None, ledger=None) -> dict:
    """Read-only: the proposal skeleton for everything new in Inbox/ (excluding Processed/)."""
    rules = rules if rules is not None else load_rules()
    ledger = ledger if ledger is not None else load_ledger()
    inbox = Path(hub_root) / "Inbox"
    out = {"proposals": [], "needs_review": [], "unknown": [],
           "already_handled": 0, "human_review_required": True,
           "ledger_note": None if ledger or LEDGER_PATH.exists() else
           "ledger missing; treating every file as new"}
    if not inbox.is_dir():
        out["error"] = f"no Inbox folder under {hub_root} (create it on the wizard /drive-hub screen)"
        return out
    for p in sorted(inbox.iterdir()):
        if not p.is_file() or p.name.startswith("."):
            continue
        digest = _sha256(p)
        if digest in ledger:
            out["already_handled"] += 1
            continue
        info = _classify.classify(str(p))
        entry = {"file": f"Inbox/{p.name}", "sha256": digest,
                 "format_family": info.get("family"), "ext": info.get("ext")}
        cat = _format_category(info, p.name)
        rule = rules.get(cat) if cat else None
        if cat and rule and rule.get("category_source") == "format":
            entry.update({"classified_as": cat, "category_source": "format",
                          "route_to": {"handler": rule.get("handler"), "store": rule.get("store")},
                          "after_approval": "handler runs; file moves to Inbox/Processed/<date>/"})
            out["proposals"].append(entry)
        elif info.get("family") in ("document", "pdf", "spreadsheet", "presentation", "data", "image"):
            entry.update({"classified_as": None, "category_source": "content_pending",
                          "note": "needs a Claude session (inbox-routing atom) to read the content "
                                  "and run the injection guard before a route is proposed"})
            out["needs_review"].append(entry)
        else:
            entry.update({"classified_as": "unknown",
                          "note": "unclassifiable from format; left in place"})
            out["unknown"].append(entry)
    return out


def approve(hub_root, proposal, ledger_path=LEDGER_PATH, now=None) -> dict:
    """The ONLY writer: move each approved entry to Inbox/Processed/<date>/ and record it in the
    ledger. Approves exactly what it is given (the human already reviewed); refuses entries whose
    file vanished or whose sha no longer matches (the file changed since the scan)."""
    hub = Path(hub_root)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    processed = hub / "Inbox" / "Processed" / stamp
    results = {"moved": [], "refused": []}
    try:
        data = json.loads(Path(ledger_path).read_text(encoding="utf-8")) if Path(ledger_path).exists() \
            else {"schema_version": "0.1.0", "entries": []}
    except (OSError, ValueError):
        data = {"schema_version": "0.1.0", "entries": []}
    entries = [e for e in data.get("entries", []) if e.get("sha256")]
    known = {e["sha256"] for e in entries}
    for item in proposal.get("proposals", []):
        src = hub / item.get("file", "")
        if not src.is_file():
            results["refused"].append({"file": item.get("file"), "why": "file no longer present"})
            continue
        if _sha256(src) != item.get("sha256"):
            results["refused"].append({"file": item.get("file"),
                                       "why": "file changed since the scan; re-scan first"})
            continue
        if item["sha256"] in known:
            results["refused"].append({"file": item.get("file"), "why": "already in the ledger"})
            continue
        processed.mkdir(parents=True, exist_ok=True)
        target = processed / src.name
        os.replace(src, target)
        entries.append({
            "sha256": item["sha256"], "file_name": src.name,
            "first_seen": item.get("first_seen") or stamp,
            "classified_as": item.get("classified_as"),
            "injection_scan_result": item.get("injection_scan_result"),
            "routed_to": item.get("route_to"),
            "status": "approved",
            "approved_at": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "notes": item.get("note"),
        })
        known.add(item["sha256"])
        results["moved"].append(item["file"])
    data["entries"] = entries
    Path(ledger_path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(ledger_path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, ledger_path)
    return results


def selftest() -> int:
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    hub = Path(tempfile.mkdtemp())
    (hub / "Inbox").mkdir()
    ledger_path = Path(tempfile.mkdtemp()) / "ledger.json"
    (hub / "Inbox" / "talk.srt").write_text("1\n00:00:00,000 --> 00:00:02,000\nhi\n", encoding="utf-8")
    (hub / "Inbox" / "clip.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42fakevideo")
    (hub / "Inbox" / "contract.pdf").write_bytes(b"%PDF-1.4 fake")
    (hub / "Inbox" / "mystery.xyz").write_bytes(b"\x01\x02\x03")

    res = scan(hub, ledger=load_ledger(ledger_path))
    ok("srt routes by format to transcript-import",
       any(p["classified_as"] == "transcript" and p["route_to"]["handler"] == "transcript-import"
           for p in res["proposals"]))
    ok("mp4 routes by format to library-complete",
       any(p["classified_as"] == "video_media" for p in res["proposals"]))
    ok("pdf waits for a content review, never guessed",
       any(e["file"].endswith("contract.pdf") for e in res["needs_review"]) and
       not any(p["file"].endswith("contract.pdf") for p in res["proposals"]))
    ok("unknown binary flagged in place",
       any(e["file"].endswith("mystery.xyz") for e in res["unknown"]))
    ok("scan wrote and moved nothing",
       sorted(f.name for f in (hub / "Inbox").iterdir()) ==
       ["clip.mp4", "contract.pdf", "mystery.xyz", "talk.srt"] and not ledger_path.exists())

    out = approve(hub, res, ledger_path=ledger_path)
    ok("approve moves exactly the proposed files", sorted(out["moved"]) == ["Inbox/clip.mp4", "Inbox/talk.srt"])
    ok("approved files landed in Processed",
       any((hub / "Inbox" / "Processed").rglob("talk.srt")))
    res2 = scan(hub, ledger=load_ledger(ledger_path))
    ok("re-scan proposes nothing for handled files (idempotent)",
       res2["proposals"] == [] and res2["already_handled"] == 0)

    # A stale proposal (file changed after scan) is refused, not silently routed.
    (hub / "Inbox" / "late.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n", encoding="utf-8")
    res3 = scan(hub, ledger=load_ledger(ledger_path))
    (hub / "Inbox" / "late.srt").write_text("EDITED AFTER SCAN", encoding="utf-8")
    out = approve(hub, res3, ledger_path=ledger_path)
    ok("changed-since-scan file refused", out["refused"] and "changed" in out["refused"][0]["why"])

    res4 = scan(Path(tempfile.mkdtemp()), ledger={})
    ok("missing Inbox is a plain error", "error" in res4 and "no Inbox folder" in res4["error"])

    failed = [n for n, c in checks if not c]
    for n, c in checks:
        print(("ok   " if c else "FAIL ") + n)
    print(f"handoff.inbox selftest: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0


def main(argv) -> int:
    if "--selftest" in argv:
        return selftest()
    if "scan" in argv and "--hub" in argv:
        hub = argv[argv.index("--hub") + 1]
        print(json.dumps(scan(hub), indent=2))
        return 0
    if "approve" in argv and "--hub" in argv and "--proposal" in argv:
        hub = argv[argv.index("--hub") + 1]
        prop_path = argv[argv.index("--proposal") + 1]
        try:
            proposal = json.loads(Path(prop_path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(json.dumps({"error": f"unreadable proposal: {exc}"}))
            return 1
        print(json.dumps(approve(hub, proposal), indent=2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
