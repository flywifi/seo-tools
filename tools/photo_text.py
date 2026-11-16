#!/usr/bin/env python3
"""Text from a photo of a receipt, read on this computer (P103, ADR 0087).

read_image(path) hands a photo (png, jpg, jpeg, webp, tif, tiff, bmp) to the optional local reader
(the rapidocr package on onnxruntime, from requirements-photo.txt) and returns the text it found as
lines in reading order, with the reader's lowest confidence score and the gaps to show the person.
The reader runs in a process of its own, under the interpreter that holds the optional packages
(env_paths.app_python), with a time limit: a photo it stalls on, or a reader that is not installed,
comes back as a gap and no text. The photo stays on this computer; the reader's models ship inside
its package and nothing is downloaded when it runs.

The text is what a recognition model read, so a digit can be wrong: tools/receipt_extract.py caps
what it proposes from a photo at "probable" and asks the person to check the figures. Nothing is
written here.

CLI:
  python3 tools/photo_text.py <photo>          # JSON: text, engine, lowest_score, gaps
  python3 tools/photo_text.py --engine-check   # reads a generated receipt with the installed reader
  python3 tools/photo_text.py --selftest
"""
from __future__ import annotations

import json
import math
import re
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import env_paths  # noqa: E402

TOOL = "tools/photo_text.py"
PHOTO_SUFFIXES = frozenset({"png", "jpg", "jpeg", "webp", "tif", "tiff", "bmp"})
MAX_BYTES = 20_000_000    # a 12-megapixel phone JPEG is about 5 MB
MAX_PIXELS = 50_000_000   # width times height; a larger picture is refused before it is decoded
READ_TIMEOUT = 120        # seconds the reader's process gets
LOW_SCORE = 0.80          # a lowest score under this adds a gap that names it
TEXT_MAX = 200_000        # characters kept of what the reader returns
PHOTO_FORMATS = ("PNG", "JPEG", "WEBP", "TIFF", "BMP")  # the decoders Pillow may use for a photo
SETUP_HINT = ("the photo reader is not installed; run python3 tools/setup.py --install-deps, or ask a chat "
              "session to read the photo")


class PhotoRefused(Exception):
    """A photo the reader does not take; its message is the gap shown to the person."""


def looks_like_photo(path):
    """True when the file's opening bytes are those of a png, jpeg, webp, tiff or bmp picture. The
    suffix is a name; this is the content. A file that cannot be opened is not a photo."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(12)
    except OSError:
        return False
    return (head.startswith(b"\x89PNG\r\n\x1a\n") or head.startswith(b"\xff\xd8\xff")
            or (head[:4] == b"RIFF" and head[8:12] == b"WEBP") or head[:4] in (b"II*\x00", b"MM\x00*")
            or (head[:2] == b"BM" and head[6:10] == b"\x00\x00\x00\x00"))


def _blank():
    return {"text": "", "engine": None, "lowest_score": None, "gaps": []}


def lines_from(boxes, txts, scores):
    """(text, lowest score, sideways) from the reader's boxes. Each box is four (x, y) corners
    starting at the text's top left. The boxes are turned by their median text angle, so a tilted
    photo still groups into rows; boxes whose vertical centres lie within 0.6 of a box height share
    a row, and a row's cells are joined left to right with two spaces. sideways is True when most
    boxes holding three or more characters are taller than they are wide: the photo is turned a
    quarter, and the rows cannot be rebuilt."""
    boxes = [[(float(x), float(y)) for x, y in box] for box in boxes]
    if not boxes:
        return "", 0.0, False
    theta = statistics.median(math.atan2(b[1][1] - b[0][1], b[1][0] - b[0][0]) for b in boxes)
    cos_t, sin_t = math.cos(-theta), math.sin(-theta)
    turned = [[(x * cos_t - y * sin_t, x * sin_t + y * cos_t) for x, y in b] for b in boxes]
    tall = wide = 0
    for box, txt in zip(turned, txts):
        if len(str(txt).strip()) < 3:
            continue
        width = max(p[0] for p in box) - min(p[0] for p in box)
        height = max(p[1] for p in box) - min(p[1] for p in box)
        if height > width:
            tall += 1
        else:
            wide += 1
    rows = []
    for box, txt, score in sorted(zip(turned, txts, scores),
                                  key=lambda t: (min(p[1] for p in t[0]), min(p[0] for p in t[0]))):
        top, bottom = min(p[1] for p in box), max(p[1] for p in box)
        mid = (top + bottom) / 2
        if rows and abs(rows[-1]["mid"] - mid) <= (bottom - top) * 0.6:
            rows[-1]["cells"].append((min(p[0] for p in box), str(txt)))
        else:
            rows.append({"mid": mid, "cells": [(min(p[0] for p in box), str(txt))]})
    text = "\n".join("  ".join(t for _x, t in sorted(r["cells"])) for r in rows) + "\n"
    return text, min(float(s) for s in scores), tall > wide


# Every run of blanks is bounded and starts at the run's first blank, so the pattern is linear in the
# text (a run of over 40 blanks is left as it is: it is two columns apart already).
_TAIL = re.compile(r"(?<![ \t])[ \t]{1,40}(?:(\d{1,3})[ \t]{0,40})?((?:\$|USD ?)\d[\d,]*\.\d{2})[ \t]{0,40}$", re.M)


def space_amounts(text):
    """The text with a line's closing amount, and a quantity before it, set off by two spaces. The
    reader returns a receipt's quantity and amount columns as one cell ("2 $12.50", "2$12.50"), and
    receipt_extract's line rule needs two spaces between columns."""
    return _TAIL.sub(lambda m: ("  " + m.group(1) if m.group(1) else "") + "  " + m.group(2), text)


def _rapidocr_reader(path):
    """(boxes, txts, scores, engine name) from the installed reader. ImportError when a package is
    missing; PhotoRefused for a picture over MAX_PIXELS. The picture is opened by Pillow with the
    PHOTO_FORMATS decoders, turned upright by its EXIF orientation, and handed over as a BGR array."""
    from importlib import metadata
    import numpy as np
    from PIL import Image, ImageOps
    from rapidocr import RapidOCR
    with Image.open(path, formats=PHOTO_FORMATS) as im:
        width, height = im.size
        if width * height > MAX_PIXELS:
            raise PhotoRefused(f"the photo is {width} by {height} pixels, over the {MAX_PIXELS} the reader takes; "
                               "type the entry in")
        arr = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))[:, :, ::-1].copy()
    res = RapidOCR()(arr)
    if res.txts is None or len(res.txts) == 0:
        return [], [], [], f"rapidocr {metadata.version('rapidocr')}"
    return ([[(float(x), float(y)) for x, y in box] for box in res.boxes], [str(t) for t in res.txts],
            [float(s) for s in res.scores], f"rapidocr {metadata.version('rapidocr')}")


def read_here(path, reader=None):
    """The result for one photo, read in this process (the reader's own process runs this). Every
    failure is a gap: a missing package names the setup step, and the text stays empty."""
    out = _blank()
    reader = _rapidocr_reader if reader is None else reader
    try:
        boxes, txts, scores, engine = reader(path)
    except ImportError as exc:
        out["gaps"].append(f"{SETUP_HINT} ({type(exc).__name__})")
        return out
    except PhotoRefused as exc:
        out["gaps"].append(str(exc))
        return out
    except Exception as exc:  # noqa: BLE001 - a picture the reader cannot open or read is a gap
        out["gaps"].append(f"the photo could not be read as a picture ({type(exc).__name__}); type the entry in")
        return out
    out["engine"] = engine
    if not txts:
        out["gaps"].append("no text was found in the photo; type the entry in")
        return out
    text, lowest, sideways = lines_from(boxes, txts, scores)
    out["lowest_score"] = round(lowest, 2)
    if sideways:
        out["gaps"].append("the photo looks turned on its side, so its lines cannot be put in order; turn it "
                           "upright and drop it in again, or type the entry in")
        return out
    out["text"] = space_amounts(text)[:TEXT_MAX]
    if lowest < LOW_SCORE:
        out["gaps"].append(f"part of the photo was hard to read (lowest score {lowest:.2f}); check each figure "
                           "against the receipt")
    return out


def read_image(path, python=None, run=None, timeout=READ_TIMEOUT):
    """{"text", "engine", "lowest_score", "gaps"} for a photo. The reader runs as
    `<python> -B tools/photo_text.py --read <path>` (python defaults to env_paths.app_python(), run to
    subprocess.run) and gets timeout seconds. A suffix outside PHOTO_SUFFIXES, a file over
    MAX_BYTES, a file whose opening bytes are not a picture's (looks_like_photo), a reader that does
    not finish, or a reply that is not the result object, comes back as a gap with no text."""
    p = Path(path)
    out = _blank()
    ext = p.suffix.lower().lstrip(".")
    if ext not in PHOTO_SUFFIXES:
        out["gaps"].append(f"a .{ext} file is not read as a photo; type the entry in")
        return out
    try:
        size = p.stat().st_size
    except OSError as exc:
        out["gaps"].append(f"the photo could not be opened ({type(exc).__name__}); type the entry in")
        return out
    if size > MAX_BYTES:
        out["gaps"].append(f"the photo is over {MAX_BYTES} bytes; type the entry in")
        return out
    if not looks_like_photo(p):
        out["gaps"].append("the file is not a png, jpg, webp, tiff or bmp picture; type the entry in")
        return out
    run = subprocess.run if run is None else run
    python = python or env_paths.app_python()
    try:
        done = run([str(python), "-B", str(HERE / "photo_text.py"), "--read", str(p)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        out["gaps"].append(f"the photo reader did not finish in {timeout} seconds; type the entry in")
        return out
    except OSError as exc:
        out["gaps"].append(f"the photo reader could not be started ({type(exc).__name__}); type the entry in")
        return out
    lines = (done.stdout or "").strip().splitlines()
    try:
        reply = json.loads(lines[-1]) if lines else None
    except ValueError:
        reply = None
    if (not isinstance(reply, dict) or not isinstance(reply.get("text"), str)
            or not isinstance(reply.get("gaps"), list) or not all(isinstance(g, str) for g in reply["gaps"])):
        out["gaps"].append(f"the photo reader stopped without a result (exit code {done.returncode}); "
                           "type the entry in")
        return out
    score = reply.get("lowest_score")
    out.update(text=reply["text"][:TEXT_MAX], gaps=list(reply["gaps"]),
               engine=reply["engine"] if isinstance(reply.get("engine"), str) else None,
               lowest_score=float(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else None)
    return out


# ── selftest ─────────────────────────────────────────────────────────────────


def _box(x, y, w, h, deg=0.0):
    """Four corners of a w by h box whose top left is (x, y), turned deg about the origin."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [(px * c - py * s, px * s + py * c) for px, py in ((x, y), (x + w, y), (x + w, y + h), (x, y + h))]


def _grid(deg=0.0):
    """A receipt's boxes as the reader returns them: three rows, the amounts in a right column."""
    cells = [("Northstar Tools", 30, 40, 220), ("Brad nails 18ga 2in", 30, 120, 280), ("2 $12.50", 600, 122, 110),
             ("Order total", 30, 200, 160), ("$239.61", 610, 198, 100)]
    return ([_box(x, y, w, 30, deg) for _t, x, y, w in cells], [t for t, _x, _y, _w in cells],
            [0.99, 0.97, 0.95, 0.98, 0.91])


def selftest():
    results = []

    def ok(name, cond):
        results.append((name, bool(cond)))

    want = "Northstar Tools\nBrad nails 18ga 2in  2 $12.50\nOrder total  $239.61\n"
    text, lowest, sideways = lines_from(*_grid())
    ok("boxes on one line share a row, cells run left to right, and the lowest score is returned",
       text == want and lowest == 0.91 and sideways is False)
    ok("a photo tilted 8, 30 or minus 12 degrees rebuilds the same rows",
       all(lines_from(*_grid(d))[0] == want and lines_from(*_grid(d))[2] is False for d in (8, 30, -12)))
    boxes, txts, scores = _grid()
    shuffled = list(zip(boxes, txts, scores))[::-1]
    ok("the rows do not depend on the order the reader returned the boxes in",
       lines_from([b for b, _t, _s in shuffled], [t for _b, t, _s in shuffled], [s for _b, _t, s in shuffled])[0] == want)
    ok("boxes half a line apart are two rows",
       lines_from([_box(0, 0, 100, 30), _box(200, 20, 100, 30)], ["left", "right"], [0.9, 0.9])[0] == "left\nright\n"
       and lines_from([_box(0, 0, 100, 30), _box(200, 17, 100, 30)], ["left", "right"], [0.9, 0.9])[0] == "left  right\n")
    tall = [_box(40 * i, 0, 30, 200) for i in range(3)]
    ok("boxes taller than wide read as a photo on its side; a two-character box does not count",
       lines_from(tall, ["Order total", "Subtotal", "Shipping"], [0.9] * 3)[2] is True
       and lines_from(tall + [_box(0, 300, 200, 30)], ["ab", "cd", "ef", "Order total"], [0.9] * 4)[2] is False
       and lines_from([_box(0, 0, 30, 200)], ["ab"], [0.9])[2] is False
       and lines_from([], [], []) == ("", 0.0, False))
    ok("a closing amount and the quantity before it are set off by two spaces",
       space_amounts("Brad nails  2 $12.50\nKit 1$199.99\nTotal $5.00 \nUSD 7.25 due\nSize 5\n")
       == "Brad nails  2  $12.50\nKit  1  $199.99\nTotal  $5.00\nUSD 7.25 due\nSize 5\n"
       and space_amounts(space_amounts("a 2 $1.00\n")) == space_amounts("a 2 $1.00\n")
       and space_amounts("a 1234 $1.00\n") == "a 1234  $1.00\n")

    ok("an amount written with USD at a line's end is set off too, and a run of over 40 blanks is left alone",
       space_amounts("Kit 1 USD 7.25\nFee USD7.25\n") == "Kit  1  USD 7.25\nFee  USD7.25\n"
       and space_amounts("Kit" + " " * 41 + "$5.00\n") == "Kit" + " " * 41 + "$5.00\n"
       and space_amounts("Kit" + " " * 40 + "$5.00\n") == "Kit  $5.00\n")
    import time
    t0 = time.monotonic()
    blanks = space_amounts("Order total" + " " * TEXT_MAX + "x\n" + "\t" * TEXT_MAX + "$1.00\n")
    took = time.monotonic() - t0
    # 10 s is a tripwire for a pattern that stops being linear: the case takes well under a second.
    ok(f"TEXT_MAX blanks in a row are passed through within 10 s ({took:.2f} s)",
       took < 10 and len(blanks) == 2 * TEXT_MAX + 19)
    skew = [_box(0, 0, 100, 30), _box(0, 100, 100, 30), _box(0, 200, 100, 30, 80)]
    ok("the turn is the median box angle, so one box at another angle does not tilt the rest",
       lines_from(skew[:2] + [_box(300, 0, 100, 30)] + skew[2:], ["a", "c", "b", "d"], [0.9] * 4)[0].startswith("a  b\n"))
    ok("a box counts as tall once it is higher than it is wide",
       lines_from([_box(0, 0, 100, 150)], ["Order total"], [0.9])[2] is True
       and lines_from([_box(0, 0, 100, 100)], ["Order total"], [0.9])[2] is False)
    ok("the limits are the documented ones",
       READ_TIMEOUT == 120 and MAX_PIXELS == 50_000_000 and MAX_BYTES == 20_000_000 and TEXT_MAX == 200_000)

    def reader_of(value):
        def reader(_path):
            if isinstance(value, BaseException):
                raise value
            return value
        return reader

    got = read_here("x.jpg", reader_of((*_grid(), "stub 1.0")))
    ok("a read returns the spaced text, the engine's name and the lowest score, with no gap",
       got == {"text": space_amounts(want), "engine": "stub 1.0", "lowest_score": 0.91, "gaps": []})
    low = read_here("x.jpg", reader_of((boxes, txts, [0.99, 0.97, 0.79, 0.98, 0.91], "stub 1.0")))
    edge = read_here("x.jpg", reader_of((boxes, txts, [0.99, 0.97, 0.80, 0.98, 0.91], "stub 1.0")))
    ok("a lowest score under 0.80 adds a gap that names it, and 0.80 does not",
       low["text"] == space_amounts(want) and low["gaps"] and "0.79" in low["gaps"][0] and edge["gaps"] == [])
    side = read_here("x.jpg", reader_of((tall, ["Order total", "Subtotal", "Shipping"], [0.9] * 3, "stub 1.0")))
    ok("a photo on its side returns no text and says so",
       side["text"] == "" and len(side["gaps"]) == 1 and "on its side" in side["gaps"][0] and side["engine"] == "stub 1.0")
    none = read_here("x.jpg", reader_of(([], [], [], "stub 1.0")))
    missing = read_here("x.jpg", reader_of(ImportError("no module")))
    refused = read_here("x.jpg", reader_of(PhotoRefused("the photo is too large")))
    broken = read_here("x.jpg", reader_of(OSError("cannot identify image file")))
    ok("no text found, a missing package, a refused picture and a picture that does not open are each a gap "
       "with no text",
       [r["text"] for r in (none, missing, refused, broken)] == [""] * 4
       and "no text was found" in none["gaps"][0] and none["engine"] == "stub 1.0"
       and missing["gaps"] == [f"{SETUP_HINT} (ImportError)"] and missing["engine"] is None
       and refused["gaps"] == ["the photo is too large"]
       and "could not be read as a picture (OSError)" in broken["gaps"][0])
    long_text = read_here("x.jpg", reader_of(([_box(0, 0, 9000, 30)], ["x" * (TEXT_MAX + 50)], [0.9], "stub 1.0")))
    ok("the text kept is cut at TEXT_MAX characters", len(long_text["text"]) == TEXT_MAX)

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        photo = Path(td) / "receipt.JPG"
        photo.write_bytes(b"\xff\xd8\xff" + b"0" * 64)
        calls = []

        def run_of(stdout="", returncode=0, raises=None):
            def run(argv, **kwargs):
                calls.append((argv, kwargs))
                if raises is not None:
                    raise raises
                return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr="noise")
            return run

        reply = {"text": "Order total  $239.61\n", "engine": "stub 1.0", "lowest_score": 0.93, "gaps": ["check it"]}
        got = read_image(photo, python="py-x", run=run_of("a log line\n" + json.dumps(reply) + "\n"))
        ok("read_image runs this file's --read under the interpreter it was given, with the time limit, and "
           "returns the reply's last line",
           got == reply and len(calls) == 1
           and calls[0][0] == ["py-x", "-B", str(HERE / "photo_text.py"), "--read", str(photo)]
           and calls[0][1].get("timeout") == READ_TIMEOUT and calls[0][1].get("capture_output") is True)
        ok("a reply that is not the result object, or none, is a gap that names the exit code",
           all(r["text"] == "" and r["engine"] is None and "exit code 3" in r["gaps"][0] for r in (
               read_image(photo, python="py-x", run=run_of("", 3)),
               read_image(photo, python="py-x", run=run_of("not json", 3)),
               read_image(photo, python="py-x", run=run_of("[1, 2]", 3)),
               read_image(photo, python="py-x", run=run_of(json.dumps({"text": 5, "gaps": []}), 3)),
               read_image(photo, python="py-x", run=run_of(json.dumps({"text": "t", "gaps": "g"}), 3)),
               read_image(photo, python="py-x", run=run_of(json.dumps({"text": "t", "gaps": [1]}), 3)))))
        odd = read_image(photo, python="py-x", run=run_of(json.dumps(
            {"text": "y" * (TEXT_MAX + 9), "engine": 7, "lowest_score": True, "gaps": []})))
        ok("a reply's text is cut at TEXT_MAX, and an engine or score of another type reads as none",
           len(odd["text"]) == TEXT_MAX and odd["engine"] is None and odd["lowest_score"] is None)
        slow = read_image(photo, python="py-x", run=run_of(raises=subprocess.TimeoutExpired("x", 5)), timeout=5)
        gone = read_image(photo, python="py-x", run=run_of(raises=FileNotFoundError("py-x")))
        ok("a reader that does not finish, or cannot be started, is a gap with no text",
           slow["text"] == "" and "did not finish in 5 seconds" in slow["gaps"][0]
           and gone["text"] == "" and "could not be started (FileNotFoundError)" in gone["gaps"][0])
        n = len(calls)
        heic = Path(td) / "receipt.heic"
        heic.write_bytes(b"0")
        big = Path(td) / "big.png"
        with open(big, "wb") as fh:
            fh.truncate(MAX_BYTES + 1)
        at_cap = Path(td) / "cap.png"
        with open(at_cap, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
            fh.truncate(MAX_BYTES)
        refusals = [read_image(heic, python="py-x", run=run_of()), read_image(big, python="py-x", run=run_of()),
                    read_image(Path(td) / "absent.png", python="py-x", run=run_of())]
        ok("a suffix outside the list, a file over MAX_BYTES and a file that is not there are refused "
           "without the reader being started",
           len(calls) == n and all(r["text"] == "" and len(r["gaps"]) == 1 for r in refusals)
           and "a .heic file is not read as a photo" in refusals[0]["gaps"][0]
           and f"over {MAX_BYTES} bytes" in refusals[1]["gaps"][0]
           and "could not be opened (FileNotFoundError)" in refusals[2]["gaps"][0])
        read_image(at_cap, python="py-x", run=run_of(json.dumps(reply)))
        ok("a file of exactly MAX_BYTES reaches the reader", len(calls) == n + 1)
        n = len(calls)
        heads = {"a.png": b"\x89PNG\r\n\x1a\n", "b.jpg": b"\xff\xd8\xff\xe0", "c.webp": b"RIFF\x10\x00\x00\x00WEBP",
                 "d.tif": b"II*\x00", "e.tiff": b"MM\x00*", "f.bmp": b"BM\x10\x00\x00\x00\x00\x00\x00\x00"}
        fakes = {"g.jpg": b"Order total $5.00\n", "h.jpg": b"%!PS-Adobe-3.0 EPSF-3.0\n", "i.png": b"",
                 "j.webp": b"RIFF\x10\x00\x00\x00WAVE", "k.bmp": b"BMW sells cars\n", "l.png": b"\x89PNG"}
        for name, head in {**heads, **fakes}.items():
            (Path(td) / name).write_bytes(head)
        not_pictures = [read_image(Path(td) / name, python="py-x", run=run_of()) for name in fakes]
        ok("a file with a photo suffix whose opening bytes are not a picture's is a gap, and the reader is not "
           "started; the five formats' opening bytes are taken",
           len(calls) == n and all(r["text"] == "" and r["gaps"] == [
               "the file is not a png, jpg, webp, tiff or bmp picture; type the entry in"] for r in not_pictures)
           and all(looks_like_photo(Path(td) / name) for name in heads)
           and not any(looks_like_photo(Path(td) / name) for name in fakes)
           and looks_like_photo(Path(td) / "absent.png") is False
           and PHOTO_FORMATS == ("PNG", "JPEG", "WEBP", "TIFF", "BMP"))
        saved = env_paths.app_python
        try:
            env_paths.app_python = lambda *a, **k: "py-app"
            read_image(photo, run=run_of(json.dumps(reply)))
        finally:
            env_paths.app_python = saved
        ok("with no interpreter given the reader runs under env_paths.app_python()", calls[-1][0][0] == "py-app")
        out_lines = []
        code = main(["--read", str(heic)], reader=reader_of((*_grid(), "stub 1.0")), emit=out_lines.append)
        ok("--read prints the result as one line of JSON",
           code == 0 and len(out_lines) == 1 and "\n" not in out_lines[0]
           and json.loads(out_lines[0])["text"] == space_amounts(want))
    printed = []
    lone = main(["--read"], reader=reader_of((*_grid(), "stub 1.0")), emit=printed.append, usage=printed.append)
    ok("--read with no file after it reads nothing and prints the usage", printed == [__doc__] and lone == 2)
    ok("the photo suffixes are the seven the reader was run on, and the creator-facing gaps carry no em dash",
       PHOTO_SUFFIXES == {"png", "jpg", "jpeg", "webp", "tif", "tiff", "bmp"}
       and "—" not in SETUP_HINT + json.dumps([none, side, low, broken, refusals, slow, gone]))

    failed = [name for name, passed in results if not passed]
    for name, passed in results:
        print(("ok   " if passed else "FAIL ") + name)
    print(f"photo_text selftest: {len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


def engine_check():
    """Read a receipt image generated here with the installed reader, and say what came back. Run by
    hand after setup; the battery does not run it (it needs the optional packages)."""
    import tempfile
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print(json.dumps({"ok": False, "gaps": [f"{SETUP_HINT} (ImportError)"]}))
        return 1
    lines = ["Northstar Tools", "Order confirmation", "Date: 2026-05-02", "Sold by: Northstar Tools Co",
             "Brad nails 18ga 2in                 2       $12.50", "Order total                                 $25.00"]
    img = Image.new("RGB", (900, 40 * (len(lines) + 2)), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((30, 40 * (i + 1)), line, fill="black", font=ImageFont.load_default(size=28))
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "engine-check.png"
        img.save(path)
        got = read_image(path)
    good = "Order total  $25.00" in got["text"] and "2026-05-02" in got["text"] and "Brad nails 18ga 2in  2  $12.50" in got["text"]
    print(json.dumps({"ok": good, **got}, indent=2))
    return 0 if good else 1


def main(argv=None, reader=None, emit=print, usage=print):
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        return selftest()
    if "--engine-check" in argv:
        return engine_check()
    if "--read" in argv and argv.index("--read") + 1 < len(argv):
        emit(json.dumps(read_here(argv[argv.index("--read") + 1], reader=reader)))
        return 0
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        usage(__doc__)
        return 2
    print(json.dumps(read_image(files[0]), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
