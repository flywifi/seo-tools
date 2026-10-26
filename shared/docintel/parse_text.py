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
# The most a zip member or a compressed PDF stream is inflated to: a few-KB file can inflate to
# hundreds of MB, so text past this is not read (P103).
MEMBER_MAX = 16_000_000
# A tag that a "<" with no ">" before the next "<" cannot stretch across, so stripping is linear.
_TAG = re.compile(r"<[^<>]*>")


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
    text = _TAG.sub(" ", markup)
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
            xml = _read_member(z, name).decode("utf-8", "replace")
            xml = xml.replace(para_close, "\n")
            xml = _TAG.sub("", xml)
            chunks.append((name, html.unescape(xml).strip()))
    return chunks


def _read_member(z, name):
    """A zip member's bytes, at most MEMBER_MAX of them."""
    with z.open(name) as fh:
        return fh.read(MEMBER_MAX)


def _docx_xml_text(xml):
    xml = xml.replace("</w:p>", "\n").replace("<w:tab/>", "\t")
    return html.unescape(_TAG.sub("", xml)).strip()


def parse_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = _read_member(z, "word/document.xml").decode("utf-8", "replace")
    return result(path, "docx", "content_ingested", _docx_xml_text(xml))


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


# parse_csv decides the encoding from the file's first part, then reads rows as a stream.
CSV_ENCODING_BYTES = 1 << 20


def parse_csv(path, delimiter):
    """The first rows of a CSV or TSV file, up to the 500 cap. The encoding is the one textdecode
    gives the first CSV_ENCODING_BYTES (1 MiB); the rows are then read as a stream with
    replacement characters, so a large export costs no more memory than the rows kept, and a byte
    past the first MiB that the encoding cannot decode becomes U+FFFD."""
    label = _td.read_text_file(path, max_bytes=CSV_ENCODING_BYTES)[1]
    rows = []
    with open(path, newline="", encoding=_td.CODECS[label], errors="replace") as fh:
        for i, row in enumerate(csv.reader(fh, delimiter=delimiter)):
            rows.append(row)
            if i >= 500:
                break
    text = "\n".join(delimiter.join(r) for r in rows)
    return result(path, "csv", "content_ingested", text, tables=rows[:50],
                  notes=f"{len(rows)} rows parsed (capped at 500)")


def _pdf_streams(data):
    """Each stream's bytes, found by walking the file once: a "stream" keyword followed by a line
    end, up to the next "endstream". A stream with no "endstream" after it ends the walk, so a file
    of repeated "stream" lines is read in linear time (P103)."""
    pos = 0
    while True:
        i = data.find(b"stream", pos)
        if i < 0:
            return
        j = i + 6
        if data[i - 3:i] == b"end" or data[j:j + 1] not in (b"\r", b"\n"):
            pos = j
            continue
        j += 2 if data[j:j + 2] == b"\r\n" else 1
        k = data.find(b"endstream", j)
        if k < 0:
            return
        yield data[j:k].rstrip(b"\r\n")
        pos = k + 9


def parse_pdf(path):
    data = Path(path).read_bytes()
    pieces = []
    for raw in _pdf_streams(data):
        try:
            dec = zlib.decompressobj().decompress(raw, MEMBER_MAX)
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


def parse_eml(path):
    """An email file (.eml) through Python's email module: its From, Subject and Date lines, then
    the text part, else the HTML part with the tags stripped. Attachments are not read (the notes
    say how many there were). A message the module cannot decode degrades to metadata_only."""
    import email
    import email.policy
    try:
        msg = email.message_from_bytes(Path(path).read_bytes(), policy=email.policy.default)
        head = [f"From: {msg.get('from', '')}", f"Subject: {msg.get('subject', '')}",
                f"Date: {msg.get('date', '')}"]
        body = msg.get_body(preferencelist=("plain", "html"))
        text = ""
        if body is not None:
            content = body.get_content()
            text = strip_tags(content) if body.get_content_type() == "text/html" else content
        attached = sum(1 for _ in msg.iter_attachments())
    except (ValueError, LookupError, TypeError, AttributeError) as exc:
        return result(path, "eml", "metadata_only", confidence="low",
                      notes=f"the email could not be decoded ({type(exc).__name__})")
    notes = f"{attached} attachment(s) not read" if attached else ""
    return result(path, "eml", "content_ingested", "\n".join(head) + "\n\n" + text, notes=notes)


def screen_text(path):
    """Every text a screen should read from a file, joined: for an .eml each decoded text part (the
    plain and the HTML ones) and the subject, for a .docx the body, headers, footers, footnotes,
    endnotes and comments, and for anything else parse()'s text. Never raises; "" when nothing
    could be read (P103)."""
    p = Path(path)
    ext = p.suffix.lower().lstrip(".")
    try:
        if ext == "eml":
            import email
            import email.policy
            msg = email.message_from_bytes(p.read_bytes(), policy=email.policy.default)
            texts = [str(msg.get("subject", ""))]
            for part in msg.walk():
                if part.get_content_maintype() == "text" and not part.is_attachment():
                    try:
                        content = part.get_content()
                    except (LookupError, ValueError):
                        content = part.get_payload(decode=True).decode("utf-8", "replace")
                    texts.append(strip_tags(content) if part.get_content_subtype() == "html" else content)
            return "\n".join(t for t in texts if t)
        if ext == "docx" and zipfile.is_zipfile(p):
            with zipfile.ZipFile(p) as z:
                names = [n for n in sorted(z.namelist()) if re.fullmatch(
                    r"word/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml", n)]
                return "\n".join(_docx_xml_text(_read_member(z, n).decode("utf-8", "replace")) for n in names)
        return parse(p).get("text") or ""
    except Exception:  # noqa: BLE001 -- a screen input never raises; the caller sees ""
        return ""


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
        if ftype == "eml":
            return parse_eml(p)
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


def _zip_one(path, name, text):
    """A zip holding one deflated member (selftest helper)."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, text)


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

        em = d / "m.eml"
        em.write_bytes(b"From: Shop <s@shop.example>\nSubject: Your receipt\nDate: Tue, 07 Jul 2026 10:00:00 -0400\n"
                       b"MIME-Version: 1.0\nContent-Type: multipart/mixed; boundary=b1\n\n--b1\n"
                       b"Content-Type: text/html; charset=utf-8\n\n<p>Total <b>$4.00</b></p>\n--b1\n"
                       b"Content-Type: application/pdf\nContent-Disposition: attachment; filename=r.pdf\n\n"
                       b"%PDF-1.4\n--b1--\n")
        r5 = parse(str(em))
        ok("an .eml is read through the email module: headers, the HTML part stripped, attachments counted",
           r5["file_type"] == "eml" and r5["ingestion_status"] == "content_ingested"
           and r5["text"].startswith("From: Shop <s@shop.example>\nSubject: Your receipt")
           and " ".join(r5["text"].split()).endswith("Total $4.00") and "%PDF" not in r5["text"]
           and "1 attachment" in r5["notes"])
        em.write_bytes(b"From: a@b.example\nContent-Type: text/plain; charset=\"no-such-codec\"\n\nhi\n")
        r6 = parse(str(em))
        ok("an .eml whose charset Python lacks degrades to metadata_only, no traceback",
           r6["file_type"] == "eml" and r6["ingestion_status"] == "metadata_only" and r6["text"] == "")

        import time as _time
        mixed = d / "mixed.eml"
        mixed.write_bytes(b"From: s@shop.example\nSubject: Receipt\nMIME-Version: 1.0\n"
                          b"Content-Type: multipart/alternative; boundary=b2\n\n--b2\n"
                          b"Content-Type: text/plain; charset=utf-8\n\nTotal $9.00\n--b2\n"
                          b"Content-Type: text/html; charset=utf-8\nContent-Transfer-Encoding: base64\n\n"
                          + __import__("base64").b64encode(b"<p>Total $90.00</p><p style='display:none'>hidden note</p>")
                          + b"\n--b2--\n")
        r7, s7 = parse(str(mixed)), screen_text(str(mixed))
        ok("an .eml with plain and HTML parts: parse reads the plain part, screen_text reads both",
           "$9.00" in r7["text"] and "$90.00" not in r7["text"] and "$90.00" in s7 and "hidden note" in s7
           and "$9.00" in s7)
        with zipfile.ZipFile(d / "parts.docx", "w") as z:
            z.writestr("word/document.xml", "<w:p><w:t>body text</w:t></w:p>")
            z.writestr("word/footer1.xml", "<w:p><w:t>footer note</w:t></w:p>")
            z.writestr("word/comments.xml", "<w:p><w:t>comment note</w:t></w:p>")
        s8 = screen_text(str(d / "parts.docx"))
        ok("screen_text reads a docx's body, footers and comments",
           all(t in s8 for t in ("body text", "footer note", "comment note")))
        slow = []
        for name, build in (("streams.pdf", lambda f: f.write_bytes(b"%PDF-1.4\n" + b"stream\n" * 20000)),
                            ("lt.docx", lambda f: _zip_one(f, "word/document.xml", "<" * 100000)),
                            ("bomb.docx", lambda f: _zip_one(f, "word/document.xml", "a" * 40_000_000))):
            f = d / name
            build(f)
            t0 = _time.monotonic()
            parse(str(f))
            screen_text(str(f))
            slow.append((name, _time.monotonic() - t0))
        ok(f"repeated stream keywords, a run of '<' and an inflating docx are read in bounded time ({slow}), "
           "and an inflating docx is read only up to MEMBER_MAX",
           all(t < 5 for _n, t in slow) and len(parse(str(d / "bomb.docx"))["text"]) == MEMBER_MAX)

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
        for name, raw in (("utf-16", codecs.BOM_UTF16_LE + "item\tnote\nlamp\tcaf\u00e9\n".encode("utf-16-le")),
                          ("utf-8-sig", codecs.BOM_UTF8 + "item\tnote\nlamp\tcaf\u00e9\n".encode("utf-8"))):
            tp = d / f"rates-{name}.tsv"
            tp.write_bytes(raw)
            ok(f"a {name} tsv keeps its first column name and accents",
               parse(str(tp))["tables"] == [["item", "note"], ["lamp", "caf\u00e9"]])
        markup = "<html><body><p>Caf\u00e9 cr\u00e8me</p></body></html>"
        for name, raw in (("cp1252", markup.encode("cp1252")),
                          ("utf-16", codecs.BOM_UTF16_LE + markup.encode("utf-16-le"))):
            hp = d / f"page-{name}.html"
            hp.write_bytes(raw)
            ok(f"a {name} html file reads as written", parse(str(hp))["text"] == "Caf\u00e9 cr\u00e8me")
        doc = {"title": "Caf\u00e9 cr\u00e8me", "n": 2}
        for name, raw in (("cp1252", json.dumps(doc, ensure_ascii=False).encode("cp1252")),
                          ("utf-16", codecs.BOM_UTF16_LE + json.dumps(doc, ensure_ascii=False).encode("utf-16-le"))):
            jp = d / f"doc-{name}.json"
            jp.write_bytes(raw)
            got = parse(str(jp))
            ok(f"a {name} json file is parsed as written",
               got["ingestion_status"] == "content_ingested" and json.loads(got["text"]) == doc)
        # A large CSV is streamed: memory follows the rows kept, not the file's size.
        import tracemalloc
        bigc = d / "big.csv"
        with open(bigc, "w", encoding="utf-8", newline="") as fh:
            fh.write("video,title,views\n")
            for i in range(160_000):
                fh.write(f"v{i},A fictional title number {i} for the stream check,{i}\n")
        tracemalloc.start()
        try:
            got_big = parse(str(bigc))
            _cur, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        ok(f"a csv of {bigc.stat().st_size // 1048576} MB is read as a stream, its 501 rows in under "
           f"6 MB of memory ({peak / 1048576:.1f} MB)",
           bigc.stat().st_size > 8 * 1048576 and peak < 6 * 1048576
           and len(got_big["tables"]) == 50 and got_big["notes"].startswith("501 rows"))
        # A byte the encoding cannot decode past the first MiB (here 0xFF in UTF-8, in row 450 of
        # rows 3 KB long) becomes U+FFFD in its row; the file is still read.
        latec = d / "late-byte.csv"
        with open(latec, "wb") as fh:
            fh.write(b"video,notes\n")
            for i in range(480):
                fh.write(f"v{i},".encode("ascii") + (b"\xff" if i == 450 else b"") + b"n" * 3000 + b"\n")
        got_late = parse(str(latec))
        ok("a byte past the first MiB that the encoding cannot decode becomes U+FFFD in its row",
           got_late["ingestion_status"] == "content_ingested" and "v450,�n" in got_late["text"]
           and got_late["notes"].startswith("481 rows"))

    print(f"parse_text selftest: {'PASS' if not failures else 'FAIL'} ({len(failures)} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main(sys.argv[1:]))
