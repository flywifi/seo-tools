#!/usr/bin/env python3
"""Creator OS document intelligence: read a creator's text file in the encoding it was saved in.

Text files reach Creator OS in more than one encoding. Windows PowerShell 5.1's Out-File and its
`>` redirection write UTF-16 LE with a byte-order mark (BOM), its Set-Content writes the computer's
ANSI code page (cp1252 on a Western European Windows), and most editors write UTF-8, with or
without a BOM. Decoding everything as UTF-8 with replacement characters turns a UTF-16 subtitle
into an empty transcript and every accent in a cp1252 file into U+FFFD.

decode_text() reads, in order: a BOM (UTF-32 LE or BE, UTF-8, UTF-16 LE or BE), then strict UTF-8,
then cp1252 with replacement characters, which never fails. It returns the text and a label
naming the rule that decided, so a cp1252 reading of a file saved in another legacy code page
(Cyrillic cp1251, say) is visible in the output rather than silent.

Usage:
  python3 shared/docintel/textdecode.py <file>        # print the label and the first characters
  python3 shared/docintel/textdecode.py --selftest
"""
import codecs
import json
import sys
from pathlib import Path

# Longest BOM first: the UTF-32 LE BOM begins with the UTF-16 LE one.
_BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32", "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32", "utf-32"),
    (codecs.BOM_UTF8, "utf-8-sig", "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16", "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16", "utf-16"),
)
LABELS = ("utf-32", "utf-8-sig", "utf-16", "utf-8", "cp1252-fallback")
# The codec each label stands for, for a caller that decides from a file's first part and then
# streams the rest (parse_text.parse_csv): open(path, encoding=CODECS[label], errors="replace").
CODECS = {"utf-32": "utf-32", "utf-8-sig": "utf-8-sig", "utf-16": "utf-16", "utf-8": "utf-8",
          "cp1252-fallback": "cp1252"}


def decode_text(raw, complete=True):
    """(text, label) for raw bytes. complete=False says the bytes are the first part of a longer
    file, so a UTF-8 sequence cut at the end does not count against strict UTF-8. Never raises."""
    raw = bytes(raw)
    for bom, codec, label in _BOMS:
        if raw.startswith(bom):
            return raw.decode(codec, errors="replace"), label
    try:
        if complete:
            return raw.decode("utf-8"), "utf-8"
        return codecs.getincrementaldecoder("utf-8")().decode(raw, final=False), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace"), "cp1252-fallback"


def read_text_file(path, max_bytes=None):
    """(text, label) for the file at path, read whole or, with max_bytes, its first max_bytes.
    An unreadable path raises OSError, as Path.read_text does."""
    with open(path, "rb") as fh:
        if max_bytes is None:
            return decode_text(fh.read())
        raw = fh.read(max_bytes + 1)
    return decode_text(raw[:max_bytes], complete=len(raw) <= max_bytes)


def selftest() -> int:
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    text = "Café crème — naïve résumé\r\n"
    cases = {
        "utf-8": (text.encode("utf-8"), "utf-8"),
        "utf-8 with a BOM": (codecs.BOM_UTF8 + text.encode("utf-8"), "utf-8-sig"),
        "UTF-16 LE with a BOM": (codecs.BOM_UTF16_LE + text.encode("utf-16-le"), "utf-16"),
        "UTF-16 BE with a BOM": (codecs.BOM_UTF16_BE + text.encode("utf-16-be"), "utf-16"),
        "UTF-32 LE with a BOM": (codecs.BOM_UTF32_LE + text.encode("utf-32-le"), "utf-32"),
        "UTF-32 BE with a BOM": (codecs.BOM_UTF32_BE + text.encode("utf-32-be"), "utf-32"),
        "cp1252": (text.encode("cp1252"), "cp1252-fallback"),
    }
    for name, (raw, want) in cases.items():
        got, label = decode_text(raw)
        ok(f"{name} decodes to the text with label {want}", got == text and label == want)
    ok("an empty file is utf-8 and empty", decode_text(b"") == ("", "utf-8"))
    broken = {"utf-8-sig": codecs.BOM_UTF8 + b"ok \xff\xfe",
              "utf-16": codecs.BOM_UTF16_LE + "ok".encode("utf-16-le") + b"\x00",  # cut at an odd byte
              "utf-32": codecs.BOM_UTF32_BE + b"\x00\x11\x00\x00"}  # past the last code point
    try:
        got_broken = {label: decode_text(raw) for label, raw in broken.items()}
        raised = False
    except UnicodeDecodeError:
        got_broken, raised = {}, True
    ok("a byte-order mark followed by bytes its encoding cannot decode gives replacement characters, "
       "never an error",
       not raised and all(got_broken[lbl][1] == lbl and got_broken[lbl][0].endswith("\ufffd")
                          for lbl in broken))
    ok("cp1252 never raises: every byte value decodes",
       decode_text(bytes(range(256)))[1] == "cp1252-fallback")
    ok("the labels are the documented set", {lbl for _r, lbl in cases.values()} <= set(LABELS))
    ok("each label's codec in CODECS decodes its sample to the same text",
       set(CODECS) == set(LABELS)
       and all(raw.decode(CODECS[lbl], errors="replace") == text for raw, lbl in cases.values()))
    cut = "été".encode("utf-8")[:-1]  # the final two-byte character is cut in half
    ok("a UTF-8 file cut mid-character stays utf-8 when complete=False",
       decode_text(cut, complete=False) == ("ét", "utf-8"))
    ok("the same bytes as a whole file are not valid UTF-8", decode_text(cut)[1] == "cp1252-fallback")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.srt"
        p.write_bytes(codecs.BOM_UTF16_LE + text.encode("utf-16-le"))
        ok("read_text_file reads a UTF-16 file whole", read_text_file(p) == (text, "utf-16"))
        long_utf8 = Path(td) / "long.txt"
        long_utf8.write_bytes(("é" * 10).encode("utf-8"))
        part = read_text_file(long_utf8, max_bytes=5)
        ok("read_text_file with max_bytes reads the first part, cut mid-character, as utf-8",
           part == ("éé", "utf-8"))
        ok("read_text_file with max_bytes at least the size reads the whole file",
           read_text_file(long_utf8, max_bytes=20) == ("é" * 10, "utf-8"))
        cut_file, longer = Path(td) / "cut.txt", Path(td) / "longer.txt"
        cut_file.write_bytes(cut)  # the whole file ends inside a character
        longer.write_bytes(cut + "\u00e9!".encode("utf-8")[1:])  # the same first bytes, then more
        ok("a file exactly max_bytes long is read as a whole file, so a cut final character counts; "
           "the same bytes at the start of a longer file are a cut first part",
           read_text_file(cut_file, max_bytes=len(cut))[1] == "cp1252-fallback"
           and read_text_file(longer, max_bytes=len(cut)) == ("ét", "utf-8"))
        try:
            read_text_file(Path(td) / "missing.txt")
            raised = False
        except OSError:
            raised = True
        ok("a missing file raises OSError", raised)
    passed = sum(1 for _n, c in checks if c)
    print(f"textdecode selftest: {'PASS' if passed == len(checks) else 'FAIL'} "
          f"({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


def _main(argv):
    if not argv:
        print(__doc__)
        return 2
    text, label = read_text_file(argv[0])
    print(json.dumps({"encoding": label, "chars": len(text), "start": text[:200]}, ensure_ascii=False))
    return 0


def main(argv):
    """Thin CLI boundary: an unreadable path becomes a clean {"error","next_step"} envelope."""
    try:
        return _main(argv)
    except OSError as exc:
        print(json.dumps({"error": str(exc),
                          "next_step": "pass a readable file path (this one could not be opened)"}))
        return 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main(sys.argv[1:]))
