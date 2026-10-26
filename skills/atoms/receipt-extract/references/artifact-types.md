---
file: skills/atoms/receipt-extract/references/artifact-types.md
role: the artifact types this skill produces and the required elements of each.
---

# receipt-extract artifact types

- **Receipt proposal** (`tools/receipt_extract.py <file>`): the boundary line, the file's hub path
  and sha256, the format, direction, counterparty, date, total, subtotal, last four digits, line
  items, whether the lines reconcile, the confidence tier, the injection screen's verdict, the gaps
  and the proposed record. Quality-gate dimensions: integrity (figures from the document only),
  safety (boundary line, screen verdict honored, nothing written).
- **Written entry** (`tools/books.py --add` or `--add-cost`, after the person's yes): the stored
  entry and whether it was written; when refused, the gate's name or the duplicate reason.
