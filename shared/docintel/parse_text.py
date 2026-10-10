#!/usr/bin/env python3
"""Creator OS document intelligence: local, offline, zero-token text extractor.

Extracts text (and simple tables) from common file types using only the Python standard library, on
the client, with no internet and no tokens. Office documents (docx, xlsx, pptx) are zip plus xml, so
they parse directly. PDF is best-effort: it inflates flate streams and reads text show operators; if
the yield is low it returns metadata_only and recommends an optional local library rather than
guessing. The model reads only the compact output this prints.

Usage:
  python3 shared/docintel/parse_text.py <path> [--max-chars 4000] [--json]
"""
import argparse
import csv
import html
import io
import json
import re
import sys
import zipfile
import zlib
from pathlib import Path

try:  # imported as shared.docintel.parse_text
    from . import textdecode as _td
except ImportError:  # run as a script, imported with shared/docintel on sys.path, or loaded from its file
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import textdecode as _td

PDF_MIN_YIELD = 24


def result(path, ftype, status, text="", tables=None, confidence="high", notes="", needs=None):
    text = text or ""
    return {
        "path": str(path),
        "file_type": ftype,
        "ingestion_status": status,
        "char_count": len(text),
        "text": text,
        "tables": tables or [],
        "confidence": confidence,
        "notes": notes,
        "needs_more_info": needs,
        "ran_locally": True,
        "tokens_spent_on_parse": 0,
    }


def read_text(path):
    """The file's text in textdecode's reading order: a byte-order mark, then strict UTF-8, then
    cp1252. UTF-16 without a mark is not tried: any even-length file decodes as UTF-16, so a
    cp1252 file would come back as unrelated characters."""
    return _td.read_text_file(path)[0]


def strip_tags(markup):
    text = re.sub(r"<[^>]+>", " ", markup)
    return re.sub(r"[ \t]+\n", "\n", html.unescape(text)).strip()


def detect(path):
    ext = Path(path).suffix.lower().lstrip(".")
    if ext in ("docx", "xlsx", "pptx", "zip") and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if any(n.startswith("word/") for n in names):
                return "docx"
            if any(n.startswith("xl/") for n in names):
                return "xlsx"
            if any(n.startswith("ppt/") for n in names):
                return "pptx"
    return ext


def parse_office_xml(path, member_glob, para_close, run_tag):
    chunks = []
    with zipfile.ZipFile(path) as z:
        members = sorted(n for n in z.namelist() if re.match(member_glob, n))
        for name in members:
            xml = z.read(name).decode("utf-8", "replace")
            xml = xml.replace(para_close, "\n")
            xml = re.sub(r"<[^>]+>", "", xml)
            chunks.append((name, html.unescape(xml).strip()))
    return chunks


def parse_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = xml.replace("</w:p>", "\n").replace("<w:tab/>", "\t")
    text = html.unescape(re.sub(r"<[^>]+>", "", xml)).strip()
    return result(path, "docx", "content_ingested", text)


def parse_pptx(path):
    parts = parse_office_xml(path, r"ppt/slides/slide\d+\.xml", "</a:p>", "a:t")
    blocks = []
    for i, (_name, txt) in enumerate(parts, 1):
        if txt:
            blocks.append(f"--- slide {i} ---\n{txt}")
    text = "\n\n".join(blocks)
    return result(path, "pptx", "content_ingested", text, notes=f"{len(parts)} slides")


def parse_xlsx(path):
    strings = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if "xl/sharedStrings.xml" in names:
            ss = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
            strings = [html.unescape(t) for t in re.findall(r"<t[^>]*>(.*?)</t>", ss, re.S)]
    text = "\n".join(strings)
    return result(
        path, "xlsx", "content_ingested", text,
        notes="shared-string preview; request the full cell grid if needed",
    )


def parse_csv(path, delimiter):
    rows = []
    for i, row in enumerate(csv.reader(io.StringIO(read_text(path), newline=""), delimiter=delimiter)):
        rows.append(row)
        if i >= 500:
            break
    text = "\n".join(delimiter.join(r) for r in rows)
    return result(path, "csv", "content_ingested", text, tables=rows[:50],
                  notes=f"{len(rows)} rows parsed (capped at 500)")


def parse_pdf(path):
    data = Path(path).read_bytes()
    pieces = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        raw = match.group(1)
        try:
            dec = zlib.decompress(raw)
        except zlib.error:
            continue
        for grp in re.findall(rb"\((?:[^()\\]|\\.)*\)", dec):
            inner = grp[1:-1]
            inner = re.sub(rb"\\([()\\])", rb"\1", inner)
            try:
                pieces.append(inner.decode("latin-1"))
            except Exception:
                continue
    text = re.sub(r"[ \t]{2,}", " ", " ".join(pieces)).strip()
    if len(text) < PDF_MIN_YIELD:
        return result(
            path, "pdf", "metadata_only", text, confidence="low",
            notes="best-effort stdlib extraction yielded little text; likely a scanned or complex PDF",
            needs={
                "reason": "low_text_yield",
                "what_to_provide": "install an optional local PDF library (pypdf or pdfminer.six) or "
                                   "run local OCR, or paste the relevant section as text",
            },
        )
    return result(path, "pdf", "content_ingested", text, confidence="medium",
                  notes="best-effort stdlib extraction; verify critical figures against the source")


def parse(path):
    p = Path(path)
    if not p.exists():
        return result(p, "unknown", "referenced", notes="file not found",
                      needs={"reason": "missing_file", "what_to_provide": "a valid path or the file itself"})
    ftype = detect(p)
    try:
        if ftype == "docx":
            return parse_docx(p)
        if ftype == "pptx":
            return parse_pptx(p)
        if ftype == "xlsx":
            return parse_xlsx(p)
        if ftype == "pdf":
            return parse_pdf(p)
        if ftype in ("csv",):
            return parse_csv(p, ",")
        if ftype in ("tsv",):
            return parse_csv(p, "\t")
        if ftype in ("html", "htm"):
            return result(p, "html", "content_ingested", strip_tags(read_text(p)))
        if ftype in ("json",):
            obj = json.loads(read_text(p))
            return result(p, "json", "content_ingested", json.dumps(obj, indent=2)[:200000])
        if ftype in ("xml",):
            return result(p, "xml", "content_ingested", strip_tags(read_text(p)))
        if ftype in ("txt", "md", "log", "rtf", "yaml", "yml", "vtt", "srt", ""):
            return result(p, ftype or "txt", "content_ingested", read_text(p))
        return result(p, ftype, "metadata_only", confidence="low",
                      notes=f"no offline parser for .{ftype}",
                      needs={"reason": "unsupported_type",
                             "what_to_provide": "paste the text, or convert to a supported format"})
    except Exception as exc:
        return result(p, ftype, "metadata_only", confidence="low",
                      notes=f"parse error: {exc}",
                      needs={"reason": "parse_error", "what_to_provide": "a non-corrupt copy or the text"})


def _main(argv):
    ap = argparse.ArgumentParser(description="Creator OS offline text extractor")
    ap.add_argument("path")
    ap.add_argument("--max-chars", type=int, default=4000)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    out = parse(args.path)
    if args.max_chars and out.get("text") and len(out["text"]) > args.max_chars:
        out["text"] = out["text"][: args.max_chars]
        out["truncated"] = True
    print(json.dumps(out, indent=2) if args.json else
          f"{out['file_type']} | {out['ingestion_status']} | {out['char_count']} chars | {out['notes']}\n\n{out['text'][:args.max_chars]}")
    return 0


def main(argv):
    """Thin CLI boundary (P66): an unhandled filesystem error from a user-supplied path (for
    example a >255-byte component raising ENAMETOOLONG, which Path.exists() does not suppress)
    becomes the clean {"error","next_step"} envelope instead of a raw traceback."""
    try:
        return _main(argv)
    except OSError as exc:
        print(json.dumps({"error": str(exc),
                          "next_step": "pass a readable file path (this one could not be opened)"}))
        return 1


def selftest() -> int:
    """Offline proof over synthetic documents built in a temp dir. No network, no real user files.

    This is the offline, zero-token extractor the document lane depends on, and its honest-
    degradation contract (never a traceback, never a fabricated value) is the load-bearing part
    (P74 WP4)."""
    import tempfile, zipfile
    failures = []

    def ok(name, cond):
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    ok("strip_tags removes markup and keeps the text", "Hello" in strip_tags("<p>Hello</p>"))
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        csv_p = d / "a.csv"
        csv_p.write_text("name,qty\nlamp,2\n", encoding="utf-8")
        r = parse(str(csv_p))
        ok("csv is ingested", r["ingestion_status"] == "content_ingested")
        ok("csv rows become a table", r["tables"] == [["name", "qty"], ["lamp", "2"]])
        ok("parsing spends zero tokens and runs locally (the offline guarantee)",
           r["tokens_spent_on_parse"] == 0 and r["ran_locally"] is True)

        dx = d / "b.docx"
        with zipfile.ZipFile(dx, "w") as z:
            z.writestr("word/document.xml",
                       '<?xml version="1.0"?><w:document xmlns:w="x"><w:body><w:p><w:r>'
                       '<w:t>Invoice total</w:t></w:r></w:p></w:body></w:document>')
        r2 = parse(str(dx))
        ok("docx is ingested and its run text extracted",
           r2["ingestion_status"] == "content_ingested" and "Invoice total" in r2["text"])

        r3 = parse(str(d / "missing.csv"))
        ok("an absent file is 'referenced', never an exception",
           r3["ingestion_status"] == "referenced")
        ok("an absent file names what to provide instead of inventing content",
           isinstance(r3["needs_more_info"], dict)
           and r3["needs_more_info"].get("reason") == "missing_file")

        bad = d / "c.docx"
        bad.write_bytes(b"not a zip at all")
        r4 = parse(str(bad))
        ok("a corrupt docx degrades to metadata_only with empty text, no traceback",
           r4["ingestion_status"] == "metadata_only" and r4["text"] == "")

        # P102: Windows encodings read as written. A cp1252 file of even length decoded as
        # UTF-16 before the shared decoder.
        import codecs
        note = "Caf\u00e9 \u2014 na\u00efve"
        for name, raw in (("cp1252", note.encode("cp1252")),
                          ("utf-16", codecs.BOM_UTF16_LE + note.encode("utf-16-le")),
                          ("utf-8-sig", codecs.BOM_UTF8 + note.encode("utf-8"))):
            fp = d / f"note-{name}.txt"
            fp.write_bytes(raw)
            ok(f"a {name} text file ({len(raw)} bytes) reads as written", parse(str(fp))["text"] == note)
        ok("the cp1252 sample has an even length, the case UTF-16 guessing misread",
           len(note.encode("cp1252")) % 2 == 0)
        cp = d / "rates.csv"
        cp.write_bytes("item,note\r\nlamp,caf\u00e9\r\n".encode("cp1252"))
        ok("a cp1252 csv keeps its accents in the table",
           parse(str(cp))["tables"] == [["item", "note"], ["lamp", "caf\u00e9"]])

    print(f"parse_text selftest: {'PASS' if not failures else 'FAIL'} ({len(failures)} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main(sys.argv[1:]))
