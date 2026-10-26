# 0083. The person may label an Inbox document a receipt, and its entry is recorded after review

- Date: 2026-10-26
- Status: Accepted

## Context

The hub Inbox sorts dropped files in two ways (`shared/docintel/inbox_rules.json`): a category the
offline classifier settles from the format alone (media, transcripts, export bundles), which the
wizard can approve, and a category that needs the content read (contracts, pitches, receipts),
which waits for a Claude session that runs the full injection guard (P61, P62). A receipt or a
payment notice therefore never reached the wizard's approve and work-order screens, although the
income ledger (ADR 0082) and the cost actuals are where it belongs, and the person who dropped it
knows what it is.

## Decision

1. The person may assign the `invoice_receipt` category on the wizard's Inbox screen, in place of a
   session, to a document waiting there (formats in `tools/handoff/inbox.py::PERSON_LABELS`: PDF,
   Word, HTML, text, Markdown and `.eml`). `person_labelled` reads the text `parse_text` extracts on
   this computer and runs the offline pattern tier on it; QUARANTINE or BLOCK leaves the file in the
   Inbox, never routed, and so do a changed file, a file over 2 MB, another format and a missing
   screener. The approved entry carries `category_source: "person"` and `pass2_pending: true`.
2. `.eml` joins the parseable formats: `parse_text` reads it with Python's email module (headers,
   then the text part, else the HTML part; attachments are counted, not read).
3. The work order shows, per labelled file, what `tools/receipt_extract.py` reads from it after the
   approval (never at scan time): money in or out, date, name, amount, confidence and gaps, each
   field editable, with a tick that is off until the person turns it on. A tick writes through
   `tools/books.py`: money received with `add_entry` (an income-ledger entry, `source:
   receipt_extract`, stored as proposed), money paid with the new `add_cost_actual` (a cost-actuals
   entry; the same receipt's sha256 twice is refused). Both gate on `finance_management`.
4. The extractor guesses nothing it cannot read: `payer_type` is always the person's choice, a
   missing field is null with a gap, and text the screen flags gets no proposed record.

## Consequences

- A receipt reaches the books without a Claude session; the semantic pass (pass 2) does not run on
  it before the entry is written. The written fields are short (a name cut at 120 characters, a
  date, an amount), the person reviews each one, and nothing is sent anywhere.
- A PDF with no text layer, or on a computer without a local PDF library, is accepted with no
  screen record and typed in by the person; nothing is read from it.
- The extractor's patterns read at most 200,000 characters, and their repeats are bounded, so a
  hostile file cannot stall the wizard.
- Reading mail from a connected Gmail account is a separate change.
