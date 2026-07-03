#!/usr/bin/env python3
"""Creator OS media probe: silence and scene detection over raw media, with honest degradation.

Backends are OPTIONAL and runtime-detected; nothing here is a required dependency. Each detector
walks a fixed chain and every result records which backend actually ran (`computed_by`) plus the
full audit trail of what was tried (`backend_chain`). When no media backend is available the
chain lands on the stdlib transcript floor shipped in P28 (shared/docintel/transcripts.py), and
when there is no input at all the result carries an honest `gaps[]` entry, never numbers.

Silence chain:  ffmpeg silencedetect  ->  PyAV windowed RMS  ->  transcript gap_metrics
Scene chain:    PySceneDetect ContentDetector  ->  ffmpeg scdet (luma-only; see note)
                ->  transcript suggest_chapters

Usage:
  python3 tools/videoedit/mediaprobe.py status
  python3 tools/videoedit/mediaprobe.py probe <media>
  python3 tools/videoedit/mediaprobe.py silence [--media M] [--transcript T]
      [--noise-db -50] [--min-silence-seconds 2.0] [--backend auto|ffmpeg|pyav|transcript]
  python3 tools/videoedit/mediaprobe.py scenes [--media M] [--transcript T]
      [--threshold 27.0] [--scdet-threshold 10.0] [--backend auto|scenedetect|ffmpeg|transcript]
  python3 tools/videoedit/mediaprobe.py selftest        (or --selftest)
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "shared" / "docintel"))
import transcripts as _t  # noqa: E402

FIXTURES = HERE / "fixtures"
FLOOR_SILENCE = "shared/docintel/transcripts.gap_metrics"
FLOOR_SCENES = "shared/docintel/transcripts.suggest_chapters"
SUBPROCESS_TIMEOUT = 600

SILENCE_END = re.compile(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)")
SCDET = re.compile(r"lavfi\.scd\.score:\s*([0-9.]+),\s*lavfi\.scd\.time:\s*([0-9.]+)")

LUMA_CAVEAT = ("ffmpeg scdet scores luma only (YUV Y-plane); cuts between isoluminant colors "
               "can be missed. PySceneDetect ContentDetector is the recommended detector when "
               "installed. Verified in the P26 evaluation (docs/VIDEO_TOOLING_EVAL.md).")


def _try_import_version(name):
    try:
        mod = __import__(name)
    except Exception:
        return None
    return str(getattr(mod, "__version__", "installed"))


def tool_status():
    """Which optional backends are present on this machine. Detection only; runs nothing."""
    return {
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
        "melt": shutil.which("melt"),
        "auto_editor": shutil.which("auto-editor"),
        "av": _try_import_version("av"),
        "scenedetect": _try_import_version("scenedetect"),
        "moviepy": _try_import_version("moviepy"),
    }


def probe(media_path):
    """ffprobe stream/format summary as JSON. Honest error when ffprobe is absent."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"ok": False, "error": "ffprobe not on PATH", "media": str(media_path)}
    cmd = [ffprobe, "-v", "error", "-show_entries",
           "format=duration,size:stream=codec_name,width,height,r_frame_rate,sample_rate",
           "-of", "json", str(media_path)]
    try:
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": f"ffprobe failed: {exc}", "media": str(media_path)}
    if run.returncode != 0:
        return {"ok": False, "error": run.stderr.strip()[-500:], "media": str(media_path)}
    out = json.loads(run.stdout)
    out["ok"] = True
    return out


def parse_silencedetect(stderr_text):
    """Parse ffmpeg silencedetect stderr into silence spans. Robust to progress-line noise."""
    silences = []
    for m in SILENCE_END.finditer(stderr_text):
        end = float(m.group(1))
        dur = float(m.group(2))
        silences.append({
            "start_seconds": round(end - dur, 3),
            "end_seconds": round(end, 3),
            "duration_seconds": round(dur, 3),
        })
    return silences


def parse_scdet(stderr_text):
    """Parse ffmpeg scdet stderr into scene-change events."""
    return [{"time_seconds": float(t), "score": float(s)}
            for s, t in SCDET.findall(stderr_text)]


def _run_ffmpeg_filter(media_path, args):
    ffmpeg = shutil.which("ffmpeg")
    cmd = [ffmpeg, "-hide_banner", "-i", str(media_path)] + args + ["-f", "null", "-"]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT)
    if run.returncode != 0:
        raise RuntimeError(f"ffmpeg exited {run.returncode}: {run.stderr.strip()[-300:]}")
    return run.stderr


def _pyav_silences(media_path, noise_db, min_silence_seconds, window_seconds=0.1):
    """Windowed RMS silence detection decoded in-process. Needs av; uses numpy when present."""
    import av
    try:
        import numpy as np
    except ImportError:
        np = None
        import audioop  # stdlib through Python 3.12
    threshold = (10 ** (noise_db / 20.0)) * 32768.0
    rate = 48000
    win = int(rate * window_seconds)
    container = av.open(str(media_path))
    astream = next(s for s in container.streams if s.type == "audio")
    resampler = av.AudioResampler(format="s16", layout="mono", rate=rate)
    buf = bytearray()
    rms_windows = []
    for frame in container.decode(astream):
        for rf in resampler.resample(frame):
            buf += bytes(rf.planes[0])[: rf.samples * 2]
            while len(buf) >= win * 2:
                chunk, buf = bytes(buf[: win * 2]), buf[win * 2:]
                if np is not None:
                    arr = np.frombuffer(chunk, dtype=np.int16).astype(np.float64)
                    rms = float(np.sqrt(np.mean(arr * arr)))
                else:
                    rms = float(audioop.rms(chunk, 2))
                rms_windows.append(rms)
    container.close()
    silences = []
    run_start = None
    for i, rms in enumerate(rms_windows + [threshold + 1.0]):
        quiet = rms < threshold
        if quiet and run_start is None:
            run_start = i * window_seconds
        elif not quiet and run_start is not None:
            end = i * window_seconds
            if end - run_start >= min_silence_seconds:
                silences.append({
                    "start_seconds": round(run_start, 3),
                    "end_seconds": round(end, 3),
                    "duration_seconds": round(end - run_start, 3),
                })
            run_start = None
    return silences


def _transcript_silences(transcript_path, min_silence_seconds):
    parsed = _t.parse(str(transcript_path))
    gm = _t.gap_metrics(parsed["segments"], min_silence_seconds)
    return [{
        "start_seconds": round(float(s["from_end"]), 3),
        "end_seconds": round(float(s["to_start"]), 3),
        "duration_seconds": s["gap_seconds"],
        "after_segment": s["after_segment"],
    } for s in gm["silences"]]


def detect_silence(media_path=None, transcript_path=None, noise_db=-50.0,
                   min_silence_seconds=2.0, backend="auto"):
    """Silence spans with provenance. Chain: ffmpeg -> pyav -> transcript floor."""
    params = {"noise_db": noise_db, "min_silence_seconds": min_silence_seconds,
              "media_path": str(media_path) if media_path else None,
              "transcript_path": str(transcript_path) if transcript_path else None}
    order = ["ffmpeg", "pyav", "transcript"] if backend == "auto" else [backend]
    chain = []
    for b in order:
        try:
            if b == "ffmpeg":
                if not media_path:
                    raise LookupError("no media_path")
                if not shutil.which("ffmpeg"):
                    raise LookupError("ffmpeg not on PATH")
                stderr = _run_ffmpeg_filter(
                    media_path, ["-af", f"silencedetect=noise={noise_db}dB:d={min_silence_seconds}"])
                silences, computed_by = parse_silencedetect(stderr), "ffmpeg.silencedetect"
            elif b == "pyav":
                if not media_path:
                    raise LookupError("no media_path")
                if _try_import_version("av") is None:
                    raise LookupError("av not importable")
                silences = _pyav_silences(media_path, noise_db, min_silence_seconds)
                computed_by = "pyav.rms_window"
            elif b == "transcript":
                if not transcript_path:
                    raise LookupError("no transcript_path")
                silences, computed_by = _transcript_silences(
                    transcript_path, min_silence_seconds), FLOOR_SILENCE
            else:
                raise LookupError(f"unknown backend '{b}'")
        except Exception as exc:  # unavailable or failed: record and fall through
            chain.append({"backend": b, "ok": False, "reason": str(exc)})
            continue
        chain.append({"backend": b, "ok": True})
        return {"silences": silences, "computed_by": computed_by,
                "backend_chain": chain, "parameters": params, "gaps": []}
    return {"silences": [], "computed_by": None, "backend_chain": chain, "parameters": params,
            "gaps": [{"gap_type": "no_backend",
                      "description": "no silence backend could run (see backend_chain)",
                      "impact": "no cut candidates computed",
                      "recommended_next_step": "provide media plus ffmpeg or av, or a timecoded transcript"}]}


def _pyscenedetect_cuts(media_path, threshold):
    from scenedetect import ContentDetector, detect
    scene_list = detect(str(media_path), ContentDetector(threshold=threshold))
    # scenedetect 0.7 renamed get_seconds() to the `seconds` property; support both.
    def _secs(tc):
        return tc.seconds if hasattr(tc, "seconds") else tc.get_seconds()
    return [{"time_seconds": round(_secs(scene[0]), 3), "score": None}
            for scene in scene_list[1:]]


def _transcript_chapters(transcript_path, min_gap_seconds=8.0):
    parsed = _t.parse(str(transcript_path))
    return _t.suggest_chapters(parsed["segments"], min_gap_seconds)


def detect_scenes(media_path=None, transcript_path=None, threshold=27.0,
                  scdet_threshold=10.0, backend="auto"):
    """Scene cuts and chapter candidates with provenance.
    Chain: pyscenedetect -> ffmpeg scdet (luma caveat) -> transcript floor.
    Titles are never invented: proposed_chapters carry suggested_title null."""
    params = {"threshold": threshold, "scdet_threshold": scdet_threshold,
              "media_path": str(media_path) if media_path else None,
              "transcript_path": str(transcript_path) if transcript_path else None}
    order = (["scenedetect", "ffmpeg", "transcript"] if backend == "auto"
             else [backend])
    chain, notes = [], []
    for b in order:
        try:
            if b == "scenedetect":
                if not media_path:
                    raise LookupError("no media_path")
                if _try_import_version("scenedetect") is None:
                    raise LookupError("scenedetect not importable")
                cuts, computed_by = _pyscenedetect_cuts(media_path, threshold), "pyscenedetect.ContentDetector"
            elif b == "ffmpeg":
                if not media_path:
                    raise LookupError("no media_path")
                if not shutil.which("ffmpeg"):
                    raise LookupError("ffmpeg not on PATH")
                stderr = _run_ffmpeg_filter(
                    media_path, ["-vf", f"scdet=threshold={scdet_threshold}", "-an"])
                cuts, computed_by = parse_scdet(stderr), "ffmpeg.scdet"
                notes.append(LUMA_CAVEAT)
            elif b == "transcript":
                if not transcript_path:
                    raise LookupError("no transcript_path")
                proposed = _transcript_chapters(transcript_path)
                chain.append({"backend": b, "ok": True})
                return {"scene_cuts": [], "proposed_chapters": proposed,
                        "computed_by": FLOOR_SCENES, "backend_chain": chain,
                        "parameters": params, "notes": notes, "gaps": []}
            else:
                raise LookupError(f"unknown backend '{b}'")
        except Exception as exc:
            chain.append({"backend": b, "ok": False, "reason": str(exc)})
            continue
        chain.append({"backend": b, "ok": True})
        proposed = [{"start_seconds": 0.0, "basis": "scene_start", "suggested_title": None}]
        proposed += [{"start_seconds": c["time_seconds"], "basis": "scene_cut",
                      "suggested_title": None} for c in cuts]
        return {"scene_cuts": cuts, "proposed_chapters": proposed, "computed_by": computed_by,
                "backend_chain": chain, "parameters": params, "notes": notes, "gaps": []}
    return {"scene_cuts": [], "proposed_chapters": [], "computed_by": None,
            "backend_chain": chain, "parameters": params, "notes": notes,
            "gaps": [{"gap_type": "no_backend",
                      "description": "no scene backend could run (see backend_chain)",
                      "impact": "no chapter candidates computed",
                      "recommended_next_step": "provide media plus scenedetect or ffmpeg, or a timecoded transcript"}]}


def to_edit_package(silence_result=None, scene_result=None, title=None):
    """Partial edit-package for otio_core.merge. Marker names are data-derived, never invented;
    chapter titles stay pending (recorded in gaps[]) until a human or the model names them."""
    markers = []
    gaps = []
    provenance = []
    if silence_result:
        for s in silence_result.get("silences", []):
            markers.append({"start_seconds": round(float(s["start_seconds"]), 3),
                            "name": f"silence {s['duration_seconds']}s",
                            "note": "cut candidate (dead air)",
                            "type": "to-do", "color": None})
        if silence_result.get("computed_by"):
            provenance.append(f"silences: {silence_result['computed_by']}")
    if scene_result:
        for c in scene_result.get("proposed_chapters", []):
            markers.append({"start_seconds": round(float(c["start_seconds"]), 3),
                            "name": f"chapter candidate ({c['basis']})",
                            "note": "title pending; name from transcript or footage",
                            "type": "chapter", "color": None})
        if scene_result.get("proposed_chapters"):
            gaps.append({"gap_type": "chapter_titles_pending",
                         "description": "chapter candidates carry no titles by design",
                         "impact": "chapters[] not populated until titles are named",
                         "recommended_next_step": "name each candidate from the transcript, then chapter-map"})
        if scene_result.get("computed_by"):
            provenance.append(f"scenes: {scene_result['computed_by']}")
    return {
        "title": title,
        "source": "creator-os",
        "timeline": {"name": title or "media probe", "markers": markers},
        "gaps": gaps,
        "provenance": {"generated_by": "tools/videoedit/mediaprobe.py; " + "; ".join(provenance),
                       "tool_version": "1.0"},
    }


def _check(label, cond, failures):
    print(f"  [{'ok' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)


def selftest():
    failures = []
    srt = HERE.parent.parent / "skills" / "creator-core" / "evals" / "fixtures" / "workshop-footage.srt"

    sd_fixture = (FIXTURES / "silencedetect-ffmpeg-7.0.2.stderr.txt").read_text(encoding="utf-8")
    silences = parse_silencedetect(sd_fixture)
    _check("silencedetect fixture parses 3 silences", len(silences) == 3, failures)
    authored = [(92.0, 104.5), (210.0, 218.5), (300.0, 320.0)]
    close = all(abs(s["start_seconds"] - a[0]) <= 0.05 and abs(s["end_seconds"] - a[1]) <= 0.05
                for s, a in zip(silences, authored))
    _check("silencedetect spans within 0.05s of authored ground truth", close, failures)

    sc_fixture = (FIXTURES / "scdet-ffmpeg-7.0.2.stderr.txt").read_text(encoding="utf-8")
    cuts = parse_scdet(sc_fixture)
    _check("scdet fixture parses 3 cuts", len(cuts) == 3, failures)
    _check("scdet cut times are 150/240/330",
           [c["time_seconds"] for c in cuts] == [150.0, 240.0, 330.0], failures)
    _check("scdet misses the 60s isoluminant cut (documented luma caveat)",
           60.0 not in [c["time_seconds"] for c in cuts], failures)

    r = detect_silence(transcript_path=srt, min_silence_seconds=8.0, backend="transcript")
    _check("transcript floor finds the 3 authored gaps", len(r["silences"]) == 3, failures)
    _check("transcript floor computed_by is the P28 product function",
           r["computed_by"] == FLOOR_SILENCE, failures)
    _check("transcript floor durations are 12.5/8.5/20.0",
           [s["duration_seconds"] for s in r["silences"]] == [12.5, 8.5, 20.0], failures)

    r = detect_silence(media_path="/nonexistent-p29.mp4", transcript_path=srt,
                       min_silence_seconds=8.0)
    _check("auto chain falls through to transcript on unusable media",
           r["computed_by"] == FLOOR_SILENCE, failures)
    tried = [c["backend"] for c in r["backend_chain"]]
    _check("backend_chain records ffmpeg and pyav attempts in order",
           tried == ["ffmpeg", "pyav", "transcript"], failures)
    _check("failed links carry reasons",
           all(c.get("reason") for c in r["backend_chain"] if not c["ok"]), failures)

    r = detect_scenes(transcript_path=srt, backend="transcript")
    _check("scene floor proposes 3 chapter boundaries", len(r["proposed_chapters"]) == 3, failures)
    _check("scene floor computed_by is the P28 product function",
           r["computed_by"] == FLOOR_SCENES, failures)
    _check("scene floor invents no titles",
           all(c["suggested_title"] is None for c in r["proposed_chapters"]), failures)

    r = detect_silence()
    _check("no input yields empty silences plus a gaps entry",
           r["silences"] == [] and r["computed_by"] is None and len(r["gaps"]) == 1, failures)
    r = detect_scenes(backend="pyav")
    _check("unknown scene backend is refused honestly",
           r["computed_by"] is None and not r["proposed_chapters"], failures)

    sil = detect_silence(transcript_path=srt, min_silence_seconds=8.0, backend="transcript")
    sc = detect_scenes(transcript_path=srt, backend="transcript")
    pkg = to_edit_package(sil, sc, title="selftest")
    sys.path.insert(0, str(HERE))
    import otio_core
    merged = otio_core.merge(otio_core.normalize({}), pkg)
    _check("edit-package merges through otio_core (3 silence + 3 chapter markers)",
           len(merged["timeline"]["markers"]) == 6, failures)
    _check("merge is idempotent (no duplicate markers)",
           len(otio_core.merge(merged, pkg)["timeline"]["markers"]) == 6, failures)
    _check("chapter titles recorded as pending in gaps[]",
           any(g["gap_type"] == "chapter_titles_pending" for g in merged["gaps"]), failures)

    n = 17
    print(f"selftest: {'PASS' if not failures else 'FAIL'} "
          f"({n - len(failures)} of {n} checks)")
    return 0 if not failures else 1


def main(argv):
    if argv and argv[0] == "--selftest":
        argv = ["selftest"]
    ap = argparse.ArgumentParser(description="Creator OS media probe (silence and scenes)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("probe")
    p.add_argument("media")
    for name in ("silence", "scenes"):
        p = sub.add_parser(name)
        p.add_argument("--media")
        p.add_argument("--transcript")
        p.add_argument("--backend", default="auto")
        if name == "silence":
            p.add_argument("--noise-db", type=float, default=-50.0)
            p.add_argument("--min-silence-seconds", type=float, default=2.0)
        else:
            p.add_argument("--threshold", type=float, default=27.0)
            p.add_argument("--scdet-threshold", type=float, default=10.0)
    sub.add_parser("selftest")
    args = ap.parse_args(argv)
    if args.cmd == "status":
        print(json.dumps(tool_status(), indent=2))
    elif args.cmd == "probe":
        print(json.dumps(probe(args.media), indent=2))
    elif args.cmd == "silence":
        print(json.dumps(detect_silence(args.media, args.transcript, args.noise_db,
                                        args.min_silence_seconds, args.backend), indent=2))
    elif args.cmd == "scenes":
        print(json.dumps(detect_scenes(args.media, args.transcript, args.threshold,
                                       args.scdet_threshold, args.backend), indent=2))
    elif args.cmd == "selftest":
        return selftest()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
