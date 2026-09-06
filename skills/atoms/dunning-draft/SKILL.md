---
name: dunning-draft
atom: true
standalone: true
description: "drafts an escalating payment-reminder message for one overdue invoice, tone keyed to the aging bucket (gentle for current and 1 to 30 days, firm for 31 to 60, final for 61 and beyond), with every figure and date taken from the ar-review row and the invoice's frozen terms_snapshot late-penalty clause; NEVER sends anything (the human reviews and sends behind the consequential-action gate). Drafts are written to gitignored .local files only. Do NOT use to compute what is owed (ar-review does the math), to match payments (payment-reconcile), or to write audience-voice content (this is professional business correspondence)."
engines_required:
  - shared/finance-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/safety.md
  - protocols/formatting-metadata.md
---

# dunning-draft

The polite, firm, or final "please pay this invoice" message, drafted from the record and
handed to the human to send.

## When to use this skill
- "draft a reminder for the Hearthline invoice", "they are 45 days late, write the follow-up",
  "send the final notice" (which means: DRAFT the final notice), reached through the
  finance-desk `dun` action off an `ar-review` row.

Do NOT use for:
- Computing what is owed, days late, or accrued penalties (that is `ar-review` /
  `tools/finance.py`; this atom only restates the row).
- Matching deposits to invoices (use `payment-reconcile`).
- Audience-voice writing. This is professional business correspondence: courteous, specific,
  and unembellished. No em dashes, ranges with "to" (`protocols/formatting-metadata.md`).

## Input
```json
{
  "invoice_id": "string (required)",
  "recipient_name": "string or null (from the account record's contact)",
  "extra_context": "string or null (anything the human wants mentioned)"
}
```

## Core procedure
1. Pull the invoice's ar-review row (`tools/finance.py --ar-scan`): amount, due date, days past
   due, accrued penalty, chase-by date, and the `terms_snapshot` late-penalty clause. Every
   figure in the draft comes from that row; the model never computes or adjusts a number.
2. Pick the tone from the aging bucket:
   - `current` or `1_to_30`: GENTLE. Friendly nudge; assume oversight; restate invoice number,
     amount, and due date; offer to resend the invoice.
   - `31_to_60`: FIRM. Direct; state days past due; reference the agreed net terms verbatim
     from the snapshot; if the terms carry a late penalty, note that it applies per the
     agreement (quote the clause, state the accrued figure from the row).
   - `61_to_90` and `over_90`: FINAL. Formal; full history (invoice date, due date, days past
     due, accrued penalty per the snapshot); state the next step plainly (escalation to the
     contract's remedies, per `contract-desk` if one exists) without threats the contract does
     not support.
3. Structure: subject line, greeting, one short paragraph of facts, the ask (amount and how to
   pay, from the record), a courteous close. No invented history, no legal language beyond
   quoting the contract's own terms, no apology theater.
4. Write the draft to a gitignored local file (`pipeline/finance/dunning-<invoice_id>.local.md`)
   and present it. NOTHING IS SENT: the consequential-action gate restates amount,
   counterparty, and tone, and the human sends from their own mail client.

## Output contract
```json
{
  "invoice_id": "",
  "tone": "gentle | firm | final",
  "subject": "",
  "draft": "the full message text",
  "figures_from": "tools/finance.py ar_scan row (verbatim)",
  "penalty_clause_quoted": "the terms_snapshot text, or null when no penalty exists",
  "saved_to": "pipeline/finance/dunning-<invoice_id>.local.md",
  "human_review_required": true,
  "sent": false
}
```
EXPOSURE NOTE: the draft necessarily contains the real amount and counterparty (it is a letter
to them). It lives only in a gitignored `.local.md` file and in the human's outbox; it is never
committed, posted, or quoted into shared text unredacted.

## Standalone usability
The draft alone is a complete, send-ready message; the human can copy it into any mail client.

## Failure modes
- Invoice not overdue: the atom says so and drafts nothing harsher than a gentle heads-up on
  request; escalation tone is never applied early.
- No late-penalty clause in the snapshot: the firm/final drafts say the terms are net-N with no
  penalty stated; a penalty is never implied that the agreement does not contain.
- Disputed invoice: refused with a pointer to resolve the dispute first (chasing a disputed
  invoice is a human judgment call).

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
