---
file: skills/atoms/income-ledger/references/artifact-types.md
role: the artifact types this skill produces and the required elements of each.
---

# income-ledger artifact types

- **Ledger entry** (`tools/books.py --add`): the validated, normalized entry with `entry_id`,
  `status`, `confidence`, `gaps[]`; `written` and, when refused, the gate's name. Quality-gate
  dimensions: integrity (figures from the input only), safety (boundary line, gate honored).
- **Payer summary** (`--summary`): per-payer cash and product value, unpriced item count,
  entries awaiting confirmation, cash by month, year totals. Dimensions: accuracy (exact decimal),
  integrity (void entries excluded, other years excluded).
- **Gift register** (`--gifts`): each product entry with price, price source, page, disposition
  and content references; unpriced first. Dimensions: integrity (no value without a source).
- **Form check** (`--form-check`): per form, the ledger cash, the difference and a match flag;
  payers with cash and no form. Dimensions: accuracy; the difference is never explained.
- **Set-aside** (`--set-aside --percent P`): income, this year's cost actuals, net, and net times
  the creator's percentage. Dimensions: safety (boundary line; no default rate).
- **Export** (`--export`): `<year>-income.local.csv` and `<year>-gifts.local.csv` under
  `pipeline/finance/exports/`, boundary line first. Dimensions: safety (`.local.` path rule).
