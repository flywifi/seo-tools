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
    raw = Path(path).read_bytes()
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


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
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for i, row in enumerate(csv.reader(fh, delimiter=delimiter)):
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


def main(argv):
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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
