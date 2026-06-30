#!/usr/bin/env python3
"""Creator OS document intelligence: local, offline, zero-token file classifier.

Identifies a file's type and family from its extension and magic bytes, and reports whether it can be
parsed offline by the bundled local parsers. Runs on the client with no internet and no tokens.

Usage:
  python3 shared/docintel/classify.py <path> [<path> ...]
  python3 shared/docintel/classify.py --json <path>
"""
import json
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


def zip_kind(path):
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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
