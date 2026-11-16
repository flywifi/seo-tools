# 0087. A photo of a receipt is read on this computer, or by the chat session, and proposed at probable at most

- Date: 2026-11-12
- Status: Accepted

## Context

The person may label an Inbox document a receipt, and the work order proposes its entry (ADR 0083).
A photo was refused that label, and `tools/receipt_extract.py` read no text from one, so a paper
receipt was typed in by hand. Reading a photo needs a recognition model, which is a dependency the
stdlib-only tools do not have, and text a model read can carry a wrong digit that still adds up.

## Decision

1. **A switch, off by default.** `photo_receipts` in `creator-os-config.json` gates the photo paths
   below. With it off a photo is handled as before.
2. **An optional local reader.** `tools/photo_text.py::read_image` reads a png, jpg, jpeg, webp,
   tif, tiff or bmp file with the `rapidocr` package on `onnxruntime` (`requirements-photo.txt`,
   installed into the repo `.venv` by `tools/setup.py --install-deps` with the other sets). The
   reader's models ship inside its package. It runs in a process of its own under
   `env_paths.app_python()` with a 120 second limit, on files up to 20 MB and pictures up to
   50,000,000 pixels; Pillow opens the picture and turns it upright by its EXIF orientation.
   `lines_from` turns the reader's boxes by their median text angle and groups them into rows,
   and `space_amounts` sets a line's closing amount and the quantity before it apart, which the
   receipt rules need. A missing package, a picture that does not open, a reader that does not
   finish, a photo turned on its side, or no text found, is a gap with no text.
3. **The same screen and rules.** `receipt_extract.extract` hands a photo to the reader while the
   switch is on, and its text goes through the offline injection screen and the receipt rules
   (`_propose`, the body `extract` and `extract_text` share). A QUARANTINE or BLOCK verdict
   withholds the record.
4. **Probable at most.** `extract` on a photo and `extract_text` propose a photo's text at
   probable at most (`_propose` with `from_photo` set, which neither takes as a parameter): an exact
   result becomes probable, and the gap `read from a photo; check each figure against the receipt` is
   added. A lowest reader score under 0.80 adds a gap naming it.
5. **The label.** While the switch is on, `inbox.label_formats` adds the photo formats to the
   receipt label on the wizard's Inbox screen, and `person_labelled` screens the text the reader
   returns before the file is routed. A file with a photo suffix whose opening bytes do not
   match a png, jpeg, webp, tiff or bmp signature (`photo_text.looks_like_photo`) is refused and
   left in the Inbox, and `read_image` returns a gap for it without starting the reader; the
   reader opens a picture with those five Pillow decoders (`_open_photo`), and a file it could not
   decode is refused too. A photo the reader returns no text for otherwise (no reader installed, a
   read that did not finish, a photo on its side or over the pixel limit, or no text found) is
   accepted with no screen record, as a PDF with no readable text is, and the note carries the
   reader's reasons.
6. **The chat session as the other reader.** The read-only MCP tool `receipt_from_text` takes the
   text a session copied from a photo, with the photo's hub path and its fingerprint from the
   inbox ledger, and returns `receipt_extract.extract_text`'s proposal under decisions 3 and 4.
   It reads the config's switch, opens no document and writes nothing.

## Consequences

- A photographed receipt reaches the work order with its fields filled, for the person to check
  against the paper. The photo stays on this computer on the local path; on the session path the
  photo is seen by the AI app the person is using.
- The wizard reads a labelled photo twice in one approval (once to screen it at the label step,
  once for the work order), and the work order screen reads each pending photo again when it is
  opened; each read has the reader's 120 second limit.
- `space_amounts` leaves a line as it is when a run of over 40 blanks sits before its amount,
  between a quantity and the amount, or after the amount.
- `looks_like_photo` reads a file's first 18 bytes. A file that opens with a picture's signature
  and holds something else is refused when the installed reader fails to decode it; with no
  reader installed it is accepted with no screen record, as any photo is then.
- heic and gif are not taken: the reader's decoder was not run on them. A phone that saves HEIC
  photos needs them converted, or the session path.
- A photo turned a quarter is reported and not read; a photo turned upside down gives rows in
  reverse order, which the rules read few fields from, so its gaps ask for the fields.
- The selftests stand in for the reader, so the battery needs no optional package and does not run
  the model. `python3 tools/photo_text.py --engine-check` reads a generated receipt with the
  installed reader and is run by hand. `_rapidocr_reader`, the function that calls the package, is
  covered by that check and by no selftest case.
- The build run of the installed reader (rapidocr 3.10.0, onnxruntime 1.31.1, Python 3.12, Linux
  x64) read a generated receipt's total, date, vendor, card digits and lines from png, jpg, webp,
  tiff and bmp files, from pictures tilted 3 to 30 degrees, blurred, shrunk to a quarter, at low
  contrast, with noise and at JPEG quality 10, from a 12-megapixel and a 48-megapixel JPEG (2.7
  and 3.2 seconds, under 900 MB), and with the network proxy pointed at a closed port. It returned
  no text for heavier blur and a blank page, and the screen flagged an injected line. A phone
  photo of a paper receipt and an install on macOS and Windows were not run there.
- `tools/setup.py --install-deps` installs one more set. rapidocr is 33 MB and onnxruntime 68 MB
  installed; opencv and numpy are already in the video set.
