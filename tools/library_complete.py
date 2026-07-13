#!/usr/bin/env python3
"""library_complete.py -- finish what the API/export did NOT send (P45 completion layer).

The importers deliver metadata + stats, but the highest-value fields are exactly the ones every
platform withholds: transcripts (off-YouTube none; YouTube ASR undownloadable), chapters, spoken
keywords, and -- for YouTube -- the MEANING behind the retention curve. The creator already
downloaded the actual video files (Takeout/DYI/data-export). This module runs the on-device stack
over those files to complete each record, entirely local (zero cloud, zero tokens).

Three moving parts:
  match_media(export_dir, records)      -> map each downloaded file to a video_key + what it lacks
  complete(worklist, ...)               -> per item: local STT -> chapters -> keywords (proposal)
  join_retention_transcript(rec, segs)  -> THE PAYOFF: attach the actual words at each retention
                                            peak and the line at the steepest drop

Honesty contract: nothing is fabricated. A missing backend or missing media degrades to a flagged
gap, never a guessed transcript. This module PROPOSES completions; the human saves them via
`tools/video_library.py upsert` (the read-only / human-saves boundary from CLAUDE.md).

Usage:
  python3 tools/library_complete.py match --export-dir DIR            # (reads the local store)
  python3 tools/library_complete.py complete --export-dir DIR [--write]
  python3 tools/library_complete.py --selftest
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CREATOR_OS_ROOT", str(HERE.parent)))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "videoedit"))
sys.path.insert(0, str(HERE.parent / "shared" / "docintel"))
import transcribe as _tr  # noqa: E402
import transcripts as _t  # noqa: E402
import mediaprobe as _mp  # noqa: E402
import video_library as _vl  # noqa: E402

MEDIA_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mp3", ".m4a", ".wav", ".aac", ".flac"}


# ── match downloaded media files to library records ──────────────────────────

def _missing_fields(rec):
    """What a record still lacks that the local stack can fill."""
    missing = []
    if not (rec.get("transcript_text") or rec.get("transcript_ref")):
        missing.append("transcript")
    if not rec.get("chapters"):
        missing.append("chapters")
    return missing


def _media_uri_from_provenance(rec):
    """IG/TikTok DYI records may carry the export's own media path/uri in provenance."""
    prov = rec.get("provenance") or {}
    for key in ("media_uri", "uri", "media_path"):
        v = prov.get(key)
        if v:
            return str(v)
    return None


def match_media(export_dir, records, prober=_mp.probe):
    """Map each downloaded media file under export_dir to a video_key. Match order:
      1. filename contains the platform_video_id
      2. the DYI media uri already recorded in provenance
      3. fallback: title token + duration (via mediaprobe) when ffprobe is present
    Returns {worklist:[{video_key, media_path, missing[]}], unmatched_media:[...], no_media:[...]}.
    Never invents a match; an unmatched file is reported, not force-fit."""
    export = Path(export_dir)
    files = [p for p in export.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXTS]
    by_key = {r["video_key"]: r for r in records}
    # index provenance uris (basename) -> video_key
    uri_index = {}
    for r in records:
        uri = _media_uri_from_provenance(r)
        if uri:
            uri_index[Path(uri).name] = r["video_key"]

    worklist, unmatched, matched_keys = [], [], set()
    for f in files:
        vk = None
        name = f.name
        # 1. platform_video_id substring
        for r in records:
            pvid = str(r.get("platform_video_id") or "")
            if pvid and pvid in name:
                vk = r["video_key"]
                break
        # 2. provenance uri basename
        if vk is None and name in uri_index:
            vk = uri_index[name]
        # 3. duration + title fallback (only if ffprobe is available)
        if vk is None:
            pr = prober(str(f))
            dur = None
            if pr.get("ok"):
                try:
                    dur = float(((pr.get("format") or {}).get("duration")) or 0.0)
                except (TypeError, ValueError):
                    dur = None
            if dur:
                for r in records:
                    rd = r.get("duration_s")
                    title = (r.get("title") or "").lower()
                    token = f.stem.lower()
                    if rd and abs(float(rd) - dur) <= 1.0 and (title and token and (token in title or title.split()[0] in token)):
                        vk = r["video_key"]
                        break
        if vk is None:
            unmatched.append(str(f))
            continue
        matched_keys.add(vk)
        worklist.append({"video_key": vk, "media_path": str(f),
                         "missing": _missing_fields(by_key[vk])})
    no_media = [r["video_key"] for r in records if r["video_key"] not in matched_keys]
    return {"worklist": worklist, "unmatched_media": unmatched, "no_media": no_media}


# ── retention x transcript join: the actual words at the peak / the cliff line ──

def _segment_at(segments, t):
    """The transcript segment covering absolute time t (seconds), else the nearest by start."""
    if not segments:
        return None
    for s in segments:
        if float(s.get("start", 0)) <= t <= float(s.get("end", 0)):
            return s
    return min(segments, key=lambda s: abs(float(s.get("start", 0)) - t))


def join_retention_transcript(record, transcript_segments):
    """Map each YouTube retention peak/cliff to the transcript line at that absolute timestamp
    (elapsed_ratio x duration_s). This is what finally answers 'which parts were most watched'
    with WHAT WAS SAID there. Off-YouTube (no retention) it null-flags retention honestly.
    Returns {most_watched:[...], retention_available:bool, gaps:[...]}. Never fabricates text."""
    retention = record.get("retention")
    duration = record.get("duration_s")
    if not isinstance(retention, list) or not retention:
        return {"most_watched": [], "retention_available": False,
                "gaps": [{"gap_type": "no_retention",
                          "description": "platform provides no per-second retention (YouTube only); "
                                         "transcript and topics still delivered",
                          "impact": "most-watched-parts cannot be located on this platform"}]}
    segs = _vl.derive_most_watched(retention)
    if not duration:
        return {"most_watched": segs, "retention_available": True,
                "gaps": [{"gap_type": "no_duration",
                          "description": "retention present but duration_s is unknown; cannot map "
                                         "ratios to timestamps",
                          "impact": "peaks not tied to transcript lines"}]}
    out = []
    for seg in segs:
        mid = (float(seg["start_ratio"]) + float(seg["end_ratio"])) / 2.0
        t = round(mid * float(duration), 1)
        match = _segment_at(transcript_segments, t) if transcript_segments else None
        enriched = dict(seg)
        enriched["at_seconds"] = t
        enriched["text"] = (match.get("text") if match else None)  # null when no transcript yet
        out.append(enriched)
    gaps = []
    if not transcript_segments:
        gaps.append({"gap_type": "no_transcript",
                     "description": "retention peaks located but no transcript to name them; run "
                                    "the completion layer to attach the spoken words",
                     "impact": "peaks carry timestamps but null text"})
    return {"most_watched": out, "retention_available": True, "gaps": gaps}


# ── complete one worklist item (proposal-only) ───────────────────────────────

def _segments_from_text(text):
    """Parse a stored transcript string into timed segments, mirroring transcripts.parse() dispatch:
    whisper-JSON (with timings) or SRT/VTT. Returns [] for plain/untimed text (no timestamps to join)
    and never raises. This is what lets a pasted whisper-JSON transcript join to the retention curve."""
    if not text:
        return []
    stripped = text.lstrip()
    try:
        if stripped.startswith(("{", "[")):
            return _t.parse_json(text)
        if "-->" in text or stripped.upper().startswith("WEBVTT"):
            return _t.parse_srt_vtt(text)
    except Exception:  # noqa: BLE001
        return []
    return []


def complete_item(item, record, transcriber=None, out_dir=None):
    """Complete one video: local STT (if transcript missing) -> chapters -> retention join.
    `transcriber` is injectable (transcribe.transcribe) so the selftest needs no real backend.
    Returns a PROPOSAL dict (the human saves it); never writes here, never fabricates."""
    transcriber = transcriber or _tr.transcribe
    proposal = {"video_key": item["video_key"], "filled": [], "gaps": [], "provenance": {}}
    segments = None
    transcript_text = record.get("transcript_text")

    if "transcript" in item.get("missing", []):
        res = transcriber(item["media_path"],
                          tags=record.get("tags"), title=record.get("title"),
                          out_dir=out_dir)
        if res.get("transcript_text"):
            transcript_text = res["transcript_text"]
            segments = res.get("segments") or _segments_from_text(transcript_text)
            proposal["transcript_text"] = transcript_text
            proposal["transcript_ref"] = res.get("srt")
            proposal["filled"].append("transcript")
            proposal["provenance"]["transcript"] = {"computed_by": res.get("computed_by"),
                                                    "backend_chain": res.get("backend_chain")}
        else:
            proposal["gaps"].extend(res.get("gaps") or [])
    elif transcript_text:
        # transcript already present -> reparse to segments (JSON/SRT/VTT) for the join + chapters
        segments = _segments_from_text(transcript_text)

    if segments:
        chapters = _t.suggest_chapters(segments)
        if chapters:
            proposal["chapters"] = chapters
            proposal["filled"].append("chapters")

    join = join_retention_transcript(record, segments)
    if join["most_watched"]:
        # A transcript that exists but has no timestamps cannot supply the words at each peak; say so
        # explicitly instead of silently filling most-watched with null text.
        if transcript_text and not segments:
            proposal["gaps"].append({
                "gap_type": "no_timing",
                "description": "the transcript has no timestamps, so the words at each most-watched "
                               "moment cannot be attached",
                "impact": "peaks carry timestamps but null text",
                "recommended_action": "provide a timed transcript (SRT/VTT or whisper JSON)"})
        proposal["most_watched_segments"] = join["most_watched"]
        proposal["filled"].append("most_watched")
    proposal["gaps"].extend(join.get("gaps") or [])
    proposal["retention_available"] = join["retention_available"]
    return proposal


def complete(worklist, records_by_key, transcriber=None, out_dir=None):
    """Run complete_item over a worklist. Proposal-only: returns [proposal]. No store write."""
    out = []
    for item in worklist:
        rec = records_by_key.get(item["video_key"])
        if not rec:
            out.append({"video_key": item["video_key"], "gaps": [{"gap_type": "no_record",
                        "description": "media matched a key with no store record"}]})
            continue
        out.append(complete_item(item, rec, transcriber=transcriber, out_dir=out_dir))
    return out


# ── CLI (reads the real local store; --write applies proposals via video_library) ──

def _load_records(con):
    keys = [r["video_key"] for r in con.execute("SELECT video_key FROM video_records").fetchall()]
    return [_vl.get_record(con, k) for k in keys]


def selftest():
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # A synthetic YouTube record with a retention array + known duration.
    retention = [{"elapsed_ratio": round(i / 100, 2),
                  "watch_ratio": (1.4 if i < 10 else (0.4 if i >= 60 else 0.9))} for i in range(0, 100, 2)]
    rec = _vl.normalize_record({
        "platform_video_id": "vidJoin", "title": "Restoring an armoire", "duration_s": 600,
        "tags": ["armoire", "patina"], "stats": {"views": 9000},
        "retention": retention,
    }, platform="youtube", source_mode="export_bundle")

    # A canned transcript spanning the 600s video (segments every ~60s).
    segments = [{"start": float(i * 60), "end": float(i * 60 + 59), "text": f"line {i} about the armoire step {i}"}
                for i in range(10)]

    join = join_retention_transcript(rec, segments)
    ok("retention available on youtube record", join["retention_available"] is True)
    ok("peak carries an at_seconds timestamp", all("at_seconds" in s for s in join["most_watched"]))
    peak = next((s for s in join["most_watched"] if s["label"] == "peak"), None)
    ok("front peak's words attached from transcript", peak is not None and peak["text"] and "line 0" in peak["text"])
    cliff = next((s for s in join["most_watched"] if s["label"] == "cliff"), None)
    ok("cliff line identified with its text", cliff is not None and cliff["text"] is not None)

    # Off-YouTube record: retention null -> honest gap, no fabrication.
    ig = _vl.normalize_record({"platform_video_id": "reel5", "title": "quick tour", "duration_s": 30,
                               "stats": {"reach": 4000}, "retention": None},
                              platform="instagram", source_mode="direct_connector")
    jig = join_retention_transcript(ig, segments)
    ok("instagram retention null-flagged, not faked", jig["retention_available"] is False and jig["most_watched"] == [])

    # match_media: a file named with the platform_video_id maps to its record.
    tmp = Path(tempfile.mkdtemp(prefix="library_complete_selftest_"))
    try:
        (tmp / "myvideo_vidJoin_final.mp4").write_bytes(b"\x00")
        (tmp / "unrelated.mp4").write_bytes(b"\x00")  # not a media ext -> ignored
        (tmp / "orphan_12345.mov").write_bytes(b"\x00")
        m = match_media(tmp, [rec], prober=lambda p: {"ok": False})
        wl_keys = [w["video_key"] for w in m["worklist"]]
        ok("match_media links id-named file", "youtube:vidJoin" in wl_keys)
        ok("unmatched media reported, not force-fit", any("orphan_12345" in u for u in m["unmatched_media"]))
        ok("worklist item flags missing transcript", m["worklist"][0]["missing"] == ["transcript", "chapters"])

        # complete with an INJECTED transcriber (no real backend) -> proposal carries transcript+join.
        def fake_transcriber(path, tags=None, title=None, out_dir=None):
            return {"transcript_text": " ".join(s["text"] for s in segments),
                    "segments": segments, "srt": str(tmp / "vidJoin.srt"),
                    "computed_by": "faster-whisper:small:cpu",
                    "backend_chain": [{"backend": "faster-whisper"}], "gaps": []}
        proposals = complete(m["worklist"], {"youtube:vidJoin": rec}, transcriber=fake_transcriber, out_dir=tmp)
        p = proposals[0]
        ok("proposal fills transcript", "transcript" in p["filled"] and p.get("transcript_text"))
        ok("proposal fills most_watched with words", "most_watched" in p["filled"] and
           any(seg.get("text") for seg in p.get("most_watched_segments", [])))
        ok("proposal records STT provenance", p["provenance"]["transcript"]["computed_by"].startswith("faster-whisper"))

        # complete when the transcriber has no backend -> gap, nothing fabricated.
        def gap_transcriber(path, tags=None, title=None, out_dir=None):
            return {"transcript_text": None, "segments": [], "srt": None, "computed_by": None,
                    "backend_chain": [], "gaps": [{"gap_type": "no_backend",
                    "recommended_action": "run_local_stt", "install": "brew install whisper-cpp ffmpeg"}]}
        p2 = complete(m["worklist"], {"youtube:vidJoin": rec}, transcriber=gap_transcriber, out_dir=tmp)[0]
        ok("no-backend completion proposes no transcript", "transcript" not in p2["filled"])
        ok("no-backend completion surfaces run_local_stt gap",
           any(g.get("recommended_action") == "run_local_stt" for g in p2["gaps"]))

        # P46 fix 8: a whisper-JSON transcript already on the record joins to retention (words attached).
        import json as _json
        json_rec = _vl.normalize_record({
            "platform_video_id": "vidJSON", "title": "json transcript", "duration_s": 600,
            "stats": {"views": 1}, "retention": retention,
            "transcript_text": _json.dumps({"segments": segments}),
        }, platform="youtube", source_mode="export_bundle")
        pj = complete_item({"video_key": "youtube:vidJSON", "media_path": "/x.mp4", "missing": ["chapters"]}, json_rec)
        ok("JSON transcript joins to retention (words attached)",
           "most_watched" in pj["filled"] and any(s.get("text") for s in pj.get("most_watched_segments", [])))
        ok("JSON transcript join has no no_timing gap", not any(g.get("gap_type") == "no_timing" for g in pj["gaps"]))

        # P46 fix 8: a plain-text (untimed) transcript cannot join -> explicit no_timing gap, not silent null words.
        plain_rec = _vl.normalize_record({
            "platform_video_id": "vidPlain", "title": "plain transcript", "duration_s": 600,
            "stats": {"views": 1}, "retention": retention,
            "transcript_text": "this is a plain transcript with no timestamps whatsoever",
        }, platform="youtube", source_mode="export_bundle")
        pp = complete_item({"video_key": "youtube:vidPlain", "media_path": "/x.mp4", "missing": ["chapters"]}, plain_rec)
        ok("untimed transcript surfaces a no_timing gap", any(g.get("gap_type") == "no_timing" for g in pp["gaps"]))
        ok("untimed transcript peaks carry null words (not fabricated)",
           all(s.get("text") is None for s in pp.get("most_watched_segments", [])))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    print(f"selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


def main(argv):
    ap = argparse.ArgumentParser(description="Complete the library from downloaded media (local, zero-token).")
    sub = ap.add_subparsers(dest="cmd")
    for name in ("match", "complete"):
        p = sub.add_parser(name)
        p.add_argument("--export-dir", required=True)
        p.add_argument("--out-dir")
        if name == "complete":
            p.add_argument("--write", action="store_true", help="apply proposals to the store")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.cmd:
        ap.print_help()
        return 2

    con = _vl._open_db()
    records = _load_records(con)
    if args.cmd == "match":
        print(json.dumps(match_media(args.export_dir, records), indent=2, ensure_ascii=False))
        con.close()
        return 0
    # complete
    m = match_media(args.export_dir, records)
    by_key = {r["video_key"]: r for r in records}
    proposals = complete(m["worklist"], by_key, out_dir=args.out_dir)
    # Honest per-field write accounting: a video "completed" ONLY when a substantive field (its
    # transcript) was actually added, so a no-backend item (which can still "fill" null-word retention
    # peaks) is never miscounted as done. Gaps are surfaced in the summary, not swallowed.
    wrote = {"transcript": 0, "chapters": 0, "most_watched": 0}
    videos_completed = 0
    if getattr(args, "write", False):
        for p in proposals:
            rec = by_key.get(p["video_key"])
            if not rec or not p.get("filled"):
                continue
            for field in ("transcript_text", "transcript_ref", "chapters", "most_watched_segments"):
                if field in p:
                    rec[field] = p[field]
            for key, flag in (("transcript", "transcript"), ("chapters", "chapters"),
                              ("most_watched", "most_watched")):
                if flag in p.get("filled", []):
                    wrote[key] += 1
            _vl._upsert(con, rec)
            if "transcript" in p.get("filled", []):
                videos_completed += 1
    gaps = [{"video_key": p["video_key"], "gaps": p["gaps"]} for p in proposals if p.get("gaps")]
    print(json.dumps({"proposals": proposals, "videos_completed": videos_completed, "wrote": wrote,
                      "gaps": gaps, "unmatched_media": m["unmatched_media"], "no_media": m["no_media"]},
                     indent=2, ensure_ascii=False))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
