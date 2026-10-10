#!/usr/bin/env python3
"""Creator OS document intelligence: local, offline, zero-token file classifier.

Identifies a file's type and family from its extension and magic bytes, and reports whether it can be
parsed offline by the bundled local parsers. Runs on the client with no internet and no tokens.

A zip is opened only when its end-of-central-directory record, read from the file's tail, states at
most ZIP_MAX_ENTRIES entries and a directory of at most ZIP_MAX_DIRECTORY_BYTES, so a hostile zip
with a huge directory costs a few reads instead of a full listing (P102).

Usage:
  python3 shared/docintel/classify.py <path> [<path> ...]
  python3 shared/docintel/classify.py --json <path>
  python3 shared/docintel/classify.py --selftest
"""
import json
import struct
import sys
import zipfile
from pathlib import Path

MAGIC = [
    (b"%PDF", "pdf", "pdf"),
    (b"\x89PNG\r\n\x1a\n", "png", "image"),
    (b"\xff\xd8\xff", "jpg", "image"),
    (b"GIF87a", "gif", "image"),
    (b"GIF89a", "gif", "image"),
    (b"ID3", "mp3", "audio"),
    (b"OggS", "ogg", "audio"),
    (b"\x1aE\xdf\xa3", "mkv", "video"),
    (b"PK\x03\x04", "zip", "archive"),
]

EXT_FAMILY = {
    "txt": "document", "md": "document", "rtf": "document", "log": "document",
    "html": "document", "htm": "document", "docx": "document", "doc": "document", "odt": "document",
    "pdf": "pdf",
    "xlsx": "spreadsheet", "xls": "spreadsheet", "csv": "spreadsheet", "tsv": "spreadsheet", "ods": "spreadsheet",
    "pptx": "presentation", "ppt": "presentation", "odp": "presentation",
    "png": "image", "jpg": "image", "jpeg": "image", "gif": "image", "webp": "image",
    "heic": "image", "bmp": "image", "tiff": "image",
    "srt": "transcript", "vtt": "transcript",
    "json": "data", "xml": "data", "yaml": "data", "yml": "data",
    "mp3": "audio", "wav": "audio", "m4a": "audio", "aac": "audio", "flac": "audio", "ogg": "audio",
    "mp4": "video", "mov": "video", "mkv": "video", "webm": "video", "avi": "video",
    "zip": "archive", "tar": "archive", "gz": "archive",
}

OFFLINE_PARSEABLE = {
    "txt", "md", "rtf", "log", "html", "htm", "docx", "xlsx", "csv", "tsv",
    "pptx", "json", "xml", "srt", "vtt", "pdf",
}


ZIP_MAX_ENTRIES = 50_000
ZIP_MAX_DIRECTORY_BYTES = 16 * 1024 * 1024
_EOCD = b"PK\x05\x06"
_ZIP64_LOCATOR = b"PK\x06\x07"
_ZIP64_EOCD = b"PK\x06\x06"


def zip_directory(path):
    """{"entries", "directory_bytes", "zip64"} from a zip's end-of-central-directory record, read
    from the file's last 64 KiB without listing its names, or None when the file has no such
    record. A ZIP64 archive (over 4 GiB or 65,535 entries; Google Takeout writes them for large
    exports) states its totals in a ZIP64 record, which the locator just before the end record
    points to. Never raises."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            span = min(size, 22 + 65535)  # the end record plus the longest comment
            fh.seek(size - span)
            tail = fh.read(span)
            i = tail.rfind(_EOCD)
            if i < 0 or len(tail) - i < 22:
                return None
            entries, dir_bytes = struct.unpack("<HI", tail[i + 10:i + 16])
            loc = i - 20
            if loc >= 0 and tail[loc:loc + 4] == _ZIP64_LOCATOR:
                (rec_at,) = struct.unpack("<Q", tail[loc + 8:loc + 16])
                fh.seek(rec_at)
                rec = fh.read(56)
                if len(rec) < 56 or rec[:4] != _ZIP64_EOCD:
                    return None
                entries, dir_bytes = struct.unpack("<QQ", rec[32:48])
                return {"entries": entries, "directory_bytes": dir_bytes, "zip64": True}
            return {"entries": entries, "directory_bytes": dir_bytes, "zip64": False}
    except (OSError, struct.error, ValueError, OverflowError):
        return None


def zip_refusal(directory):
    """Why a zip's directory is too large to list here, or None (also for None)."""
    if not directory:
        return None
    if directory["entries"] > ZIP_MAX_ENTRIES:
        return f"{directory['entries']} entries, more than {ZIP_MAX_ENTRIES}"
    if directory["directory_bytes"] > ZIP_MAX_DIRECTORY_BYTES:
        return (f"a {directory['directory_bytes'] / 1048576:.1f} MB directory, more than "
                f"{ZIP_MAX_DIRECTORY_BYTES // 1048576} MB")
    return None


def zip_kind(path):
    directory = zip_directory(path)
    if directory is None or zip_refusal(directory):
        return "zip", "archive"  # not a readable zip, or a directory too large to list here
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if any(n.startswith("word/") for n in names):
                return "docx", "document"
            if any(n.startswith("xl/") for n in names):
                return "xlsx", "spreadsheet"
            if any(n.startswith("ppt/") for n in names):
                return "pptx", "presentation"
    except (zipfile.BadZipFile, OSError):
        pass
    return "zip", "archive"


def classify(path):
    p = Path(path)
    ext = p.suffix.lower().lstrip(".")
    family = EXT_FAMILY.get(ext, "unknown")
    magic = None
    if p.exists() and p.is_file():
        with open(p, "rb") as fh:
            head = fh.read(16)
        for sig, name, _fam in MAGIC:
            if head.startswith(sig):
                magic = name
                break
        if magic == "zip" or ext in ("docx", "xlsx", "pptx"):
            kind, fam = zip_kind(p)
            if kind != "zip":
                ext, family = kind, fam
    parser = None
    if family == "transcript":
        parser = "transcripts.py"
    elif ext in OFFLINE_PARSEABLE:
        parser = "parse_text.py"
    return {
        "path": str(p),
        "ext": ext,
        "family": family,
        "magic": magic,
        "parseable_offline": ext in OFFLINE_PARSEABLE or family == "transcript",
        "recommended_parser": parser,
        "trust_hint": "trusted_upload",
        "exists": p.exists(),
    }


def main(argv):
    as_json = "--json" in argv
    paths = [a for a in argv if a != "--json"]
    if not paths:
        print(__doc__)
        return 2
    out = [classify(p) for p in paths]
    print(json.dumps(out if len(out) > 1 else out[0], indent=2))
    return 0


def _zip_bytes(names, zip64=False):
    """A zip built in memory holding the named empty members; with zip64, its end records are the
    ZIP64 forms (zipfile writes them when told the archive may be large)."""
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", allowZip64=True) as z:
        for n in names:
            if zip64:
                with z.open(n, "w", force_zip64=True) as fh:
                    fh.write(b"")
            else:
                z.writestr(n, b"")
    raw = buf.getvalue()
    if zip64 and _ZIP64_LOCATOR not in raw[-200:]:
        # zipfile adds the ZIP64 end records only past its limits; write them by hand for the test
        i = raw.rfind(_EOCD)
        entries, dir_bytes, dir_at = struct.unpack("<HII", raw[i + 10:i + 20])
        rec = (_ZIP64_EOCD + struct.pack("<QHHII", 44, 45, 45, 0, 0)
               + struct.pack("<QQQQ", entries, entries, dir_bytes, dir_at))
        loc = _ZIP64_LOCATOR + struct.pack("<IQI", 0, i, 1)
        end = raw[i:i + 8] + struct.pack("<HHII", 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF) + raw[i + 20:]
        raw = raw[:i] + rec + loc + end
    return raw


def selftest() -> int:
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)

        def put(name, raw):
            (d / name).write_bytes(raw)
            return d / name

        small = put("small.zip", _zip_bytes(["a.txt", "b/c.txt"]))
        info = zip_directory(small)
        ok("the end record of a small zip states its entries and directory size",
           info is not None and info["entries"] == 2 and info["directory_bytes"] > 0
           and info["zip64"] is False and zip_refusal(info) is None)
        z64 = put("z64.zip", _zip_bytes(["a.txt", "b.txt", "c.txt"], zip64=True))
        info64 = zip_directory(z64)
        ok("a ZIP64 zip is read through its ZIP64 record (3 entries, not 65,535)",
           info64 is not None and info64["zip64"] is True and info64["entries"] == 3
           and zip_refusal(info64) is None)
        try:
            with zipfile.ZipFile(z64) as z:
                listed = z.namelist()
        except (zipfile.BadZipFile, OSError):
            listed = None
        ok("the hand-written ZIP64 test zip is a valid zip", listed == ["a.txt", "b.txt", "c.txt"])
        ok("a file with no end record has no directory", zip_directory(put("x.zip", b"PK\x03\x04 not a zip")) is None)
        trunc = _zip_bytes(["a.txt"])
        ok("a zip whose end record is cut short has no directory",
           zip_directory(put("t.zip", trunc[:-10])) is None)
        ok("a ZIP64 locator that points past the file has no directory",
           zip_directory(put("bad64.zip", _zip_bytes(["a.txt"], zip64=True)[:30]
                             + _zip_bytes(["a.txt"], zip64=True)[-42:])) is None)
        many = {"entries": ZIP_MAX_ENTRIES + 1, "directory_bytes": 10, "zip64": False}
        edge = {"entries": ZIP_MAX_ENTRIES, "directory_bytes": ZIP_MAX_DIRECTORY_BYTES, "zip64": True}
        wide = {"entries": 10, "directory_bytes": ZIP_MAX_DIRECTORY_BYTES + 1, "zip64": False}
        ok("more than ZIP_MAX_ENTRIES entries is refused, with the count",
           str(ZIP_MAX_ENTRIES + 1) in (zip_refusal(many) or ""))
        ok("a directory over ZIP_MAX_DIRECTORY_BYTES is refused", "MB directory" in (zip_refusal(wide) or ""))
        ok("exactly the limits is allowed", zip_refusal(edge) is None)
        big = put("big.zip", _zip_bytes([f"f{i}.txt" for i in range(ZIP_MAX_ENTRIES + 1)]))
        import time
        t0 = time.perf_counter()
        kind = zip_kind(big)
        took = time.perf_counter() - t0
        ok(f"a zip over the entry limit is classified without listing it ({took * 1000:.1f} ms)",
           kind == ("zip", "archive") and took < 0.05 and "entries" in (zip_refusal(zip_directory(big)) or ""))
        docx = put("w.docx", _zip_bytes(["word/document.xml"]))
        ok("a Word file is still told apart from a zip", classify(docx)["ext"] == "docx")
    passed = sum(1 for _n, c in checks if c)
    print(f"classify selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main(sys.argv[1:]))
