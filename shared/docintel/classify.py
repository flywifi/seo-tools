#!/usr/bin/env python3
"""Creator OS document intelligence: local, offline, zero-token file classifier.

Identifies a file's type and family from its extension and magic bytes, and reports whether it can be
parsed offline by the bundled local parsers. Runs on the client with no internet and no tokens.

A zip is opened only when the end record CPython's zipfile reads states a central directory of at
most ZIP_MAX_DIRECTORY_BYTES, and that directory holds at most ZIP_MAX_ENTRIES entries, counted
here, so a hostile zip with a huge directory costs a few reads instead of a full listing (P102).

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
_CENTRAL_HEADER = b"PK\x01\x02"


def _count_headers(data, limit):
    """The central-directory headers at the start of data, read in turn as zipfile reads them (a
    46-byte header, then its name, extra field and comment), up to limit."""
    pos = n = 0
    while n < limit and pos + 46 <= len(data) and data[pos:pos + 4] == _CENTRAL_HEADER:
        name_len, extra_len, comment_len = struct.unpack("<HHH", data[pos + 28:pos + 34])
        pos += 46 + name_len + extra_len + comment_len
        n += 1
    return n


def zip_directory(path):
    """{"entries", "directory_bytes", "zip64"} for a zip, read from its end record without listing
    its names, or None when the file has no end record read here. The record is the one CPython's
    zipfile reads: one at the very end with no comment, else the last in the final 64 KiB plus 22
    bytes. A ZIP64 archive (over 4 GiB or 65,535 entries; Google Takeout writes them for large
    exports) states its totals in a ZIP64 record. That record is used only where CPython reads it
    whether or not it carries the CVE-2025-8291 fix: just before its locator, which points at it,
    with no extensible data, and with the directory ending where the record starts. Releases
    without the fix read the record before the locator, and later ones follow the locator, so a
    locator pointing elsewhere could make the two disagree; such a zip has None. "entries" is the
    larger of the count the record states and the central-directory headers counted in the
    directory, counted up to ZIP_MAX_ENTRIES + 1 for a directory within ZIP_MAX_DIRECTORY_BYTES,
    since zipfile lists as many entries as the directory holds. Never raises."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            span = min(size, (1 << 16) + 22)  # zipfile's window: the end record plus the longest comment
            fh.seek(size - span)
            tail = fh.read(span)
            if len(tail) >= 22 and tail[-22:-18] == _EOCD and tail[-2:] == b"\x00\x00":
                i = len(tail) - 22  # an end record with no comment, which zipfile reads first
            else:
                i = tail.rfind(_EOCD)
            if i < 0 or len(tail) - i < 22:
                return None
            end_at = size - span + i  # the directory ends here, where its end record starts
            entries, dir_bytes = struct.unpack("<HI", tail[i + 10:i + 16])
            zip64 = False
            loc = i - 20
            if loc >= 0 and tail[loc:loc + 4] == _ZIP64_LOCATOR:
                disk, rec_at, disks = struct.unpack("<IQI", tail[loc + 4:loc + 20])
                if disk != 0 or disks > 1 or rec_at != end_at - 76:
                    return None  # spans disks, or the record is not where every CPython zipfile reads it
                fh.seek(rec_at)
                rec = fh.read(56)
                if len(rec) < 56 or rec[:4] != _ZIP64_EOCD:
                    return None
                (rec_size,) = struct.unpack("<Q", rec[4:12])
                entries, dir_bytes, dir_offset = struct.unpack("<QQQ", rec[32:56])
                if rec_size != 44 or dir_offset + dir_bytes != rec_at:
                    return None  # extensible data, or a directory that does not end at the record
                end_at, zip64 = rec_at, True
            if dir_bytes > end_at:
                return None
            if entries <= ZIP_MAX_ENTRIES and dir_bytes <= ZIP_MAX_DIRECTORY_BYTES:
                fh.seek(end_at - dir_bytes)
                entries = max(entries, _count_headers(fh.read(dir_bytes), ZIP_MAX_ENTRIES + 1))
            return {"entries": entries, "directory_bytes": dir_bytes, "zip64": zip64}
    except (OSError, struct.error, ValueError, OverflowError):
        return None


def zip_refusal(directory):
    """Why a zip's directory is too large to list here, or None (also for None)."""
    if not directory:
        return None
    if directory["entries"] > ZIP_MAX_ENTRIES:
        return f"more than {ZIP_MAX_ENTRIES:,} entries"
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
        ok("more than ZIP_MAX_ENTRIES entries is refused, naming the limit",
           zip_refusal(many) == f"more than {ZIP_MAX_ENTRIES:,} entries")
        ok("a directory over ZIP_MAX_DIRECTORY_BYTES is refused", "MB directory" in (zip_refusal(wide) or ""))
        ok("exactly the limits is allowed", zip_refusal(edge) is None)
        big = put("big.zip", _zip_bytes([f"f{i}.txt" for i in range(ZIP_MAX_ENTRIES + 1)]))
        import time
        opened, real_zipfile = [], zipfile.ZipFile

        class _RecordingZipFile(real_zipfile):
            def __init__(self, *args, **kwargs):
                opened.append(args[0] if args else kwargs.get("file"))
                super().__init__(*args, **kwargs)
        zipfile.ZipFile = _RecordingZipFile
        try:
            t0 = time.perf_counter()
            kind = zip_kind(big)
            took = time.perf_counter() - t0
            kind_small = zip_kind(small)
        finally:
            zipfile.ZipFile = real_zipfile
        ok(f"a zip over the entry limit is classified without zipfile opening it ({took * 1000:.1f} ms); "
           "one within the limits is opened",
           kind == ("zip", "archive") and opened == [small] and kind_small == ("zip", "archive")
           and "entries" in (zip_refusal(zip_directory(big)) or ""))
        docx = put("w.docx", _zip_bytes(["word/document.xml"]))
        ok("a Word file is still told apart from a zip", classify(docx)["ext"] == "docx")

        def eocd_at(raw):
            return raw.rfind(_EOCD)

        # The record zipfile reads is the one read here, and the count is not taken on trust.
        under = bytearray(_zip_bytes([f"f{i}.txt" for i in range(ZIP_MAX_ENTRIES + 5)]))
        e = eocd_at(bytes(under))
        under[e + 8:e + 12] = struct.pack("<HH", 1, 1)  # both stated counts set to 1
        ok("a zip whose end record understates its entries is counted and refused",
           zip_refusal(zip_directory(put("under.zip", bytes(under)))) == f"more than {ZIP_MAX_ENTRIES:,} entries")
        plain = _zip_bytes(["a.txt", "b.txt"])
        ep = eocd_at(plain)
        fake = _EOCD + struct.pack("<HHHHIIH", 0, 0, 60001, 60001, 0, 0, 0)
        commented = plain[:ep + 20] + struct.pack("<H", 40) + b"note " + fake + b"tail of a comment"[:13]
        got_c = zip_directory(put("commented.zip", commented))
        ok("the last end record in the comment window is read, as zipfile reads it",
           got_c is not None and got_c["entries"] == 60001 and zip_refusal(got_c) is not None)
        long_comment = bytearray(_zip_bytes(["word/document.xml"]))
        el = eocd_at(bytes(long_comment))
        long_comment[el + 20:el + 22] = struct.pack("<H", 300)
        doc300 = put("note.docx", bytes(long_comment) + b"c" * 300)
        ok("a zip with a 300-byte comment is read and still told apart as Word",
           zip_directory(doc300) is not None and zip_kind(doc300) == ("docx", "document"))
        ok("an end record cut to 18 bytes has no directory, while the whole one is read",
           zip_directory(put("cut18.zip", plain[:ep + 18])) is None
           and zip_directory(put("whole.zip", plain)) is not None)
        raw64 = _zip_bytes(["a.txt", "b.txt"], zip64=True)
        e64 = eocd_at(raw64)
        moved = bytearray(raw64)
        moved[e64 - 12:e64 - 4] = struct.pack("<Q", 0)  # the locator points at the start of the file
        ok("a ZIP64 locator that points anywhere but just before itself has no directory",
           zip_directory(put("moved64.zip", bytes(moved))) is None)
        unsigned = bytearray(raw64)
        unsigned[e64 - 76:e64 - 72] = b"XXXX"
        ok("a ZIP64 record without its signature has no directory",
           zip_directory(put("unsigned64.zip", bytes(unsigned))) is None)
        extra = bytearray(raw64)
        extra[e64 - 72:e64 - 64] = struct.pack("<Q", 52)  # claims extensible data it does not have
        ok("a ZIP64 record that claims extensible data has no directory",
           zip_directory(put("extra64.zip", bytes(extra))) is None)
        selfsig = bytearray(plain)
        selfsig[ep + 8:ep + 12] = b"PK\x05\x06"  # the two count fields spell the signature
        got_s = zip_directory(put("selfsig.zip", bytes(selfsig)))
        ok("an end record at the very end is read first, as zipfile reads it, even when its own fields "
           "hold the signature bytes",
           got_s is not None and got_s["entries"] == 0x0605)
        commented_sig = bytearray(selfsig)
        commented_sig[ep + 20:ep + 22] = struct.pack("<H", 1)  # a comment length, with no comment after
        ok("an end record at the very end with a comment length that is not 0 is not read first: the "
           "last signature in the window is, here inside its own fields, so it has no directory (zipfile "
           "3.11 to 3.14 refuses this file)",
           zip_directory(put("selfsig-comment.zip", bytes(commented_sig))) is None)
        got_t = zip_directory(put("trailer.zip", plain + b"\x00" * (1 << 16)))
        ok("an end record at the first byte of zipfile's search window is found",
           got_t is not None and got_t["entries"] == 2)
        two_disks = bytearray(raw64)
        two_disks[e64 - 4:e64] = struct.pack("<I", 2)
        ok("a ZIP64 locator that names two disks has no directory",
           zip_directory(put("disks64.zip", bytes(two_disks))) is None)
        off_end = bytearray(raw64)
        (cd_at,) = struct.unpack("<Q", off_end[e64 - 28:e64 - 20])
        off_end[e64 - 28:e64 - 20] = struct.pack("<Q", cd_at + 1)
        ok("a ZIP64 record whose directory does not end where the record starts has no directory",
           zip_directory(put("offend64.zip", bytes(off_end))) is None)
        # The locator points at a fake record stored as member data, stating one entry, while a real
        # record sits just before the locator: zipfile without the CVE-2025-8291 fix lists the real
        # directory, so this zip has no directory here.
        import io as _io_f
        fb = _io_f.BytesIO()
        with zipfile.ZipFile(fb, "w") as z:
            for n in ("Takeout/YouTube and YouTube Music/a.txt", "Takeout/YouTube and YouTube Music/b.txt"):
                z.writestr(n, b"")
            z.writestr("fake.bin", b"\x00" * 56)
        fraw = bytearray(fb.getvalue())
        fake_at = fraw.find(b"\x00" * 56)
        fe = fraw.rfind(_EOCD)
        f_entries, f_dir_bytes, f_dir_at = struct.unpack("<HII", fraw[fe + 10:fe + 20])
        fraw[fake_at:fake_at + 56] = (_ZIP64_EOCD + struct.pack("<QHHII", 44, 45, 45, 0, 0)
                                      + struct.pack("<QQQQ", 1, 1, 60, fake_at - 60))
        real = (_ZIP64_EOCD + struct.pack("<QHHII", 44, 45, 45, 0, 0)
                + struct.pack("<QQQQ", f_entries, f_entries, f_dir_bytes, f_dir_at))
        floc = _ZIP64_LOCATOR + struct.pack("<IQI", 0, fake_at, 1)
        fend = (bytes(fraw[fe:fe + 8]) + struct.pack("<HHII", 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF)
                + bytes(fraw[fe + 20:]))
        ok("a ZIP64 locator that points at a record stored as member data has no directory",
           zip_directory(put("fakeloc64.zip", bytes(fraw[:fe]) + real + floc + fend)) is None)
        # A ZIP64 directory over the size limit is refused by its size, read from the record.
        wide64 = d / "wide64.zip"
        size_cd = ZIP_MAX_DIRECTORY_BYTES + 1
        rec = (_ZIP64_EOCD + struct.pack("<QHHII", 44, 45, 45, 0, 0)
               + struct.pack("<QQQQ", 7, 7, size_cd, 0))
        loc = _ZIP64_LOCATOR + struct.pack("<IQI", 0, size_cd, 1)
        end = _EOCD + struct.pack("<HHHHIIH", 0, 0, 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0)
        with open(wide64, "wb") as fh:  # the directory region is left sparse: it is never read
            fh.seek(size_cd)
            fh.write(rec + loc + end)
        got_w = zip_directory(wide64)
        ok("a ZIP64 record stating a directory over the limit is refused by that size",
           got_w is not None and got_w["directory_bytes"] == size_cd and got_w["entries"] == 7
           and "MB directory" in (zip_refusal(got_w) or ""))
        import io as _io_c
        cb = _io_c.BytesIO()
        with zipfile.ZipFile(cb, "w") as z:
            for n in ("a.txt", "b.txt", "c.txt"):
                zi = zipfile.ZipInfo(n)
                zi.comment = b"a note"  # each header is followed by its name and this comment
                z.writestr(zi, b"x")
        craw = bytearray(cb.getvalue())
        ce = craw.rfind(_EOCD)
        craw[ce + 8:ce + 12] = struct.pack("<HH", 1, 1)
        got_cm = zip_directory(put("comments.zip", bytes(craw)))
        ok("entries with comments are counted past each comment",
           got_cm is not None and got_cm["entries"] == 3)
        counted = put("counted.zip", _zip_bytes([f"g{i}.txt" for i in range(ZIP_MAX_ENTRIES)]))
        t0 = time.perf_counter()
        got_n = zip_directory(counted)
        took = time.perf_counter() - t0
        ok(f"a zip of exactly ZIP_MAX_ENTRIES entries is counted and allowed ({took * 1000:.0f} ms)",
           got_n is not None and got_n["entries"] == ZIP_MAX_ENTRIES and zip_refusal(got_n) is None)
    passed = sum(1 for _n, c in checks if c)
    print(f"classify selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main(sys.argv[1:]))
