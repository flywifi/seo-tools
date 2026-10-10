# ADR 0080 — Creator OS reads a creator's text files by byte-order mark, then strict UTF-8, then cp1252

- Status: accepted
- Date: 2026-10-10
- Phase: P102

## Context

The transcript parser, the word-error-rate tool, the offline text extractor and the export importer
decoded text files as UTF-8 with replacement characters, or, in the extractor, tried UTF-16 without
a byte-order mark (BOM) before latin-1. Windows tools save text in other encodings. Microsoft's
about_Character_Encoding page says that in Windows PowerShell 5.1 "`Out-File` and the redirection
operators `>` and `>>` create UTF-16LE", and that `Set-Content` uses "the encoding specified by the
active system locale's ANSI legacy code page". A subtitle file written either way came back as an
empty transcript or with every accent replaced, and the run still reported done. A YouTube Studio
CSV saved with a UTF-8 BOM lost its first column name, so the import found no rows. Any
even-length cp1252 file decodes as UTF-16 without an error, so the extractor's guess returned
unrelated characters.

## Decision

One stdlib module, `shared/docintel/textdecode.py`, decodes a creator's text file
<!-- verify: shared/docintel/textdecode.py::decode_text -->, in this order:

1. A BOM decides the encoding: UTF-32 LE or BE, UTF-8, UTF-16 LE or BE.
2. Otherwise strict UTF-8.
3. Otherwise cp1252 with replacement characters, which decodes every byte value.

It returns a label with the text (`utf-32`, `utf-8-sig`, `utf-16`, `utf-8` or `cp1252-fallback`).
`transcripts.parse` and its `--normalize` output carry it as `encoding`. The transcript parser, the
word-error-rate tool, the text extractor and the export importer read through it. UTF-16 without a
BOM is not guessed.

The transcript parser also reads a WebVTT timestamp written without hours (`mm:ss.ttt`), which
the WebVTT format allows beside `hh:mm:ss.ttt`. The files Creator OS writes keep their hours.

## Consequences

- A file saved in a legacy code page other than cp1252 (Cyrillic cp1251, for example) reads as
  Latin characters that look plausible and are wrong. Strict UTF-8 first keeps this rare, and the
  `cp1252-fallback` label in the transcript output makes it visible.
- UTF-16 or UTF-32 text without a BOM reads with NUL characters between its letters. The text
  extractor used to guess UTF-16 and read such a file correctly; the other readers did not. The
  same Microsoft page says that in Windows PowerShell "Using any Unicode encoding, except `UTF7`,
  always creates a BOM".
- The offline injection screen (`tools/injection_scan.py::scan_file`) decodes through the same
  module, so for a file of up to its 2 MB limit it screens the text the transcript parser reads. A
  file that starts with a UTF-16 or UTF-32 BOM is decoded before the binary sniff, which a NUL byte
  trips, and is skipped as binary only when the decoded text holds a NUL character. Its record
  names the encoding.
- A BOM can be put in front of text in another encoding, and a reader that ignores the mark then
  reads that text while the decoded reading does not. Behind a UTF-16 or UTF-32 BOM the screen
  therefore also reads the bytes as UTF-8 and through Python's `utf-16` codec, which takes a UTF-32
  LE mark for a UTF-16 LE one, and keeps the reading with the highest score.

```sources
[
  {"id": "ms-powershell-character-encoding", "name": "about_Character_Encoding (PowerShell, Microsoft Learn)", "url": "https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding", "category": "os-platform", "tier": "T1"},
  {"id": "w3c-webvtt", "name": "WebVTT: The Web Video Text Tracks Format (W3C)", "url": "https://www.w3.org/TR/webvtt1/", "category": "platform-spec", "tier": "T1"}
]
```
