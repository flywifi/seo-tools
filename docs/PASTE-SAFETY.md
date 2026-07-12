# Paste safety: what belongs in a third-party AI chat, and what does not (P43)

Creator OS protects your private data on your computer with layered guarantees: gitignored local
files, a pre-commit secret scan, drift invariants that fail closed in CI, capability flags, and a
local redaction layer. **None of that travels with you.** The moment you paste something into
ChatGPT, a custom GPT, a Project, or a Gem, it lives on that provider's servers under their terms.
This page is the decision guide the wizard's transition screens summarize.

## Safe to paste

- The committed knowledge packs and packaging files (custom instructions, exported GPT
  instruction and knowledge files, Gem instructions). They are built from public repo content and
  carry no personal data by design.
- The all-null committed templates and schemas (rate-card template, contract starters, profile
  template). Shapes, not data.
- Fictional examples and anything already published on your channel.

## Paste with care (decide deliberately)

- Your niche strategy, content calendar themes, and audience observations. Not secret, but they
  are your competitive thinking.
- Dated data export files (freshness and task exports). They are designed for this flow, but scan
  each one before uploading: exports can accumulate brand names and figures over time.
- Brand names of prospects you are negotiating with (a leak can burn a deal).

## Do not paste without a deliberate, informed decision

- **Rate card numbers** (`pipeline/finance/rate-card.local.json`). Your negotiating floor is
  leverage; treat it like a password.
- **Contract text**, including attorney-provided template bodies
  (`pipeline/templates/*.local.json`, `pipeline/contracts/*.local.json`). Confidentiality clauses
  may forbid sharing it at all; and off your computer the P42 authorship guarantees no longer
  hold (see docs/DOCUMENT-TEMPLATES.md).
- **Personal identity details**: legal name, business address, contact lists, anything from
  `creator-profile.local.json` beyond your public display name.
- **Finance records**: invoices, actuals, bank or PayPal exports, reconciliation files. The local
  redaction layer (banded amounts, initialed brands) exists precisely because raw figures should
  not leave the machine; pasting raw records bypasses it.
- Credentials of any kind, ever.

## Two facts to remember

1. **The redaction layer is local.** `finance-desk` redacts figures before they leave your
   machine only when the tools run; on a paste surface YOU are the redaction layer.
2. **Consent gates are local.** Live lookups on your computer ask first (for example the
   jurisdiction geocoder). A custom GPT Action calls the same public endpoints from OpenAI's side
   with no ask-first step: what you type into the GPT goes to OpenAI and to the endpoint. Decide
   what you type accordingly.

When in doubt: keep the real number or name at home, paste a placeholder, and let the local tools
fill the real value when the work comes back to your computer.

## Related
Updating a pasted pack (and why a live connector avoids the paste entirely): docs/UPDATING.md and
docs/TRANSITIONS.md ("Updating by ChatGPT surface").
