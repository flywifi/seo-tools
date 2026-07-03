#!/usr/bin/env python3
"""Creator OS shorts reframe: crop geometry (pure math, always available) plus an optional
local render behind the shorts_reframe flag.

The geometry half computes the centered (or offset) crop rectangle that turns a source frame
into a target aspect (9:16 for Shorts/Reels/TikTok) and emits it into the shared edit-package
`reframe` block; no tool, flag, or network is needed for that. The render half turns one clip
range into an actual cropped file when the flag is on and a backend exists: MoviePy v2 when
installed, the ffmpeg crop filter as the one-liner fallback, otherwise an honest refusal that
hands the crop parameters to the editor (FCP/Resolve do the crop). Center-crop math only;
subject tracking is out of scope by design.

Usage:
  python3 tools/videoedit/reframe.py geometry --width 1280 --height 720 [--aspect 9:16]
  python3 tools/videoedit/reframe.py package --width W --height H [--aspect 9:16]
  python3 tools/videoedit/reframe.py render --media IN --out OUT --start S --end E
      --width W --height H [--aspect 9:16] [--backend auto|moviepy|ffmpeg]
  python3 tools/videoedit/reframe.py selftest        (or --selftest)
"""
import argparse
import json
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import videoedit_validate as _gate  # noqa: E402

SUBPROCESS_TIMEOUT = 1800


def crop_geometry(source_width, source_height, aspect="9:16", x_center=None, y_center=None):
    """Crop rectangle turning source dimensions into the target aspect. Pure math.

    Returns exact dimensions plus even-rounded ones (H.264 encoders require even sizes).
    x_center/y_center default to frame center; offsets are clamped so the crop stays in frame.
    """
    sw, sh = int(source_width), int(source_height)
    num, den = (int(p) for p in str(aspect).split(":"))
    target = Fraction(num, den)
    source = Fraction(sw, sh)
    if source > target:  # too wide: crop width
        crop_w_exact = sh * num / den
        crop_h_exact = float(sh)
    else:  # too tall or equal: crop height
        crop_w_exact = float(sw)
        crop_h_exact = sw * den / num
    crop_w = min(sw, max(2, int(round(crop_w_exact / 2)) * 2))
    crop_h = min(sh, max(2, int(round(crop_h_exact / 2)) * 2))
    xc = sw / 2 if x_center is None else float(x_center)
    yc = sh / 2 if y_center is None else float(y_center)
    x = int(round(min(max(xc - crop_w / 2, 0), sw - crop_w)))
    y = int(round(min(max(yc - crop_h / 2, 0), sh - crop_h)))
    return {
        "source": {"width": sw, "height": sh},
        "aspect": f"{num}:{den}",
        "crop_exact": {"width": round(crop_w_exact, 3), "height": round(crop_h_exact, 3)},
        "crop": {"width": crop_w, "height": crop_h, "x": x, "y": y},
        "ffmpeg_filter": f"crop={crop_w}:{crop_h}:{x}:{y}",
        "computed_by": "reframe.crop_geometry",
    }


def reframe_package(source_width, source_height, aspect="9:16", title=None):
    """Partial edit-package carrying the reframe directive for otio_core.merge."""
    geo = crop_geometry(source_width, source_height, aspect)
    return {
        "title": title,
        "source": "creator-os",
        "timeline": {"name": title or "shorts reframe"},
        "reframe": {"enabled": True, "aspect": geo["aspect"], "method": "center_crop",
                    "crop": geo["crop"], "ffmpeg_filter": geo["ffmpeg_filter"],
                    "computed_by": geo["computed_by"]},
        "provenance": {"generated_by": "tools/videoedit/reframe.py", "tool_version": "1.0"},
    }


def _moviepy_render(media_path, out_path, start_seconds, end_seconds, crop):
    from moviepy import VideoFileClip
    clip = VideoFileClip(str(media_path)).subclipped(start_seconds, end_seconds)
    cropped = clip.cropped(x1=crop["x"], y1=crop["y"],
                           x2=crop["x"] + crop["width"], y2=crop["y"] + crop["height"])
    cropped.write_videofile(str(out_path), codec="libx264", audio_codec="aac", logger=None)
    clip.close()


def _ffmpeg_render(media_path, out_path, start_seconds, end_seconds, crop):
    cmd = [shutil.which("ffmpeg"), "-hide_banner", "-y",
           "-ss", str(start_seconds), "-to", str(end_seconds), "-i", str(media_path),
           "-vf", f"crop={crop['width']}:{crop['height']}:{crop['x']}:{crop['y']}",
           "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(out_path)]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT)
    if run.returncode != 0:
        raise RuntimeError(f"ffmpeg exited {run.returncode}: {run.stderr.strip()[-300:]}")
    return cmd


def render(media_path, out_path, start_seconds, end_seconds, crop, config=None, backend="auto"):
    """Render one cropped clip. Gated on the shorts_reframe flag; degrades to a refusal that
    hands the crop parameters onward (the editor does the crop). Never a required dependency."""
    allowed, reason = _gate.realization_allowed("shorts_reframe", config)
    result = {"rendered": False, "renderer": None, "out_path": None, "backend_chain": [], "gaps": []}
    if not allowed:
        result["gaps"].append({
            "gap_type": "flag_off",
            "description": reason,
            "impact": "no local render; crop parameters still valid",
            "recommended_next_step": "enable shorts_reframe, or apply the crop in the editor"})
        return result
    order = ["moviepy", "ffmpeg"] if backend == "auto" else [backend]
    for b in order:
        try:
            if b == "moviepy":
                try:
                    import moviepy  # noqa: F401
                except ImportError:
                    raise LookupError("moviepy not importable")
                _moviepy_render(media_path, out_path, start_seconds, end_seconds, crop)
            elif b == "ffmpeg":
                if not shutil.which("ffmpeg"):
                    raise LookupError("ffmpeg not on PATH")
                _ffmpeg_render(media_path, out_path, start_seconds, end_seconds, crop)
            else:
                raise LookupError(f"unknown backend '{b}'")
        except Exception as exc:
            result["backend_chain"].append({"backend": b, "ok": False, "reason": str(exc)})
            continue
        result["backend_chain"].append({"backend": b, "ok": True})
        result.update({"rendered": True, "renderer": f"{b}.crop", "out_path": str(out_path)})
        return result
    result["gaps"].append({
        "gap_type": "no_backend",
        "description": "no render backend could run (see backend_chain)",
        "impact": "no local render; crop parameters still valid",
        "recommended_next_step": "pip install moviepy or put ffmpeg on PATH, or apply the crop in the editor"})
    return result


def _check(label, cond, failures):
    print(f"  [{'ok' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)


def selftest():
    failures = []
    g = crop_geometry(1280, 720, "9:16")
    _check("1280x720 to 9:16 exact width is 405.0 (P26 S-5 golden)",
           g["crop_exact"]["width"] == 405.0, failures)
    _check("even-rounded crop is 404x720 centered at x=438",
           g["crop"] == {"width": 404, "height": 720, "x": 438, "y": 0}, failures)
    _check("ffmpeg filter string matches crop", g["ffmpeg_filter"] == "crop=404:720:438:0", failures)

    g = crop_geometry(1080, 1920, "9:16")
    _check("already 9:16 source is untouched",
           g["crop"] == {"width": 1080, "height": 1920, "x": 0, "y": 0}, failures)
    g = crop_geometry(1920, 1080, "1:1")
    _check("1:1 from 16:9 crops width to 1080",
           g["crop"]["width"] == 1080 and g["crop"]["height"] == 1080, failures)
    g = crop_geometry(720, 1280, "16:9")
    _check("16:9 from tall source crops height (720x404)",
           g["crop"]["width"] == 720 and g["crop"]["height"] == 404, failures)
    g = crop_geometry(1280, 720, "9:16", x_center=100)
    _check("off-center x is clamped in frame", g["crop"]["x"] == 0, failures)
    g = crop_geometry(1280, 720, "9:16", x_center=1280)
    _check("off-center x clamps at right edge", g["crop"]["x"] == 1280 - 404, failures)

    pkg = reframe_package(1280, 720)
    _check("reframe package carries enabled directive with provenance",
           pkg["reframe"]["enabled"] and pkg["reframe"]["computed_by"] == "reframe.crop_geometry",
           failures)
    sys.path.insert(0, str(HERE))
    import otio_core
    merged = otio_core.merge(otio_core.normalize({}), pkg)
    _check("merge adopts the enabled reframe directive (no-clobber)",
           merged["reframe"]["enabled"] is True
           and merged["reframe"]["crop"] == {"width": 404, "height": 720, "x": 438, "y": 0},
           failures)

    r = render("in.mp4", "out.mp4", 0, 5, crop_geometry(1280, 720)["crop"],
               config={"capabilities": {"shorts_reframe": {"enabled": False}}})
    _check("render refuses with flag off and keeps crop params valid",
           not r["rendered"] and r["gaps"][0]["gap_type"] == "flag_off", failures)
    r = render("in.mp4", "out.mp4", 0, 5, crop_geometry(1280, 720)["crop"],
               config={"capabilities": {"shorts_reframe": {"enabled": True}}},
               backend="pyav")
    _check("unknown render backend refused honestly",
           not r["rendered"] and r["gaps"][0]["gap_type"] == "no_backend", failures)

    n = 12
    print(f"selftest: {'PASS' if not failures else 'FAIL'} ({n - len(failures)} of {n} checks)")
    return 0 if not failures else 1


def main(argv):
    if argv and argv[0] == "--selftest":
        argv = ["selftest"]
    ap = argparse.ArgumentParser(description="Creator OS shorts reframe (geometry + optional render)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("geometry", "package"):
        p = sub.add_parser(name)
        p.add_argument("--width", type=int, required=True)
        p.add_argument("--height", type=int, required=True)
        p.add_argument("--aspect", default="9:16")
        p.add_argument("--x-center", type=float, default=None)
        p.add_argument("--y-center", type=float, default=None)
    p = sub.add_parser("render")
    p.add_argument("--media", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--start", type=float, required=True)
    p.add_argument("--end", type=float, required=True)
    p.add_argument("--width", type=int, required=True)
    p.add_argument("--height", type=int, required=True)
    p.add_argument("--aspect", default="9:16")
    p.add_argument("--backend", default="auto")
    sub.add_parser("selftest")
    args = ap.parse_args(argv)
    if args.cmd == "geometry":
        print(json.dumps(crop_geometry(args.width, args.height, args.aspect,
                                       args.x_center, args.y_center), indent=2))
    elif args.cmd == "package":
        print(json.dumps(reframe_package(args.width, args.height, args.aspect), indent=2))
    elif args.cmd == "render":
        crop = crop_geometry(args.width, args.height, args.aspect)["crop"]
        print(json.dumps(render(args.media, args.out, args.start, args.end, crop,
                                backend=args.backend), indent=2))
    elif args.cmd == "selftest":
        return selftest()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
