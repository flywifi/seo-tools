---
name: contact-lookup
atom: true
standalone: true
description: "answers 'what's the email for that guy from my Hearthline account?' by resolving the brand phrase to one account (via account-resolve) and then reading the contact rows on that record, optionally filtered to a person hint (a name or role). It returns the contact's name, role, and email VERBATIM from pipeline/accounts/; a person hint that matches nobody returns a gap naming the known contacts, never the wrong person. Contact data is PII: output that leaves the machine is masked. Do NOT use to resolve which brand is meant when that itself is ambiguous (that is account-resolve, which this calls), to score account health (account-health), or to write or change a contact (this atom only reads)."
engines_required:
  - shared/pipeline-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/safety.md
---

# contact-lookup

The "who do I email at this brand" answer: resolve the brand, then read the contact off the
record. It never guesses a person and never invents an address.

## When to use this skill
- "what's the email for that guy from my Hearthline account?", "who's my contact at the lighting
  brand?", "pull the creative director for Hearthline" reached through the account-manager
  `contact_lookup` action.

Do NOT use for:
- Deciding which brand an ambiguous phrase means (that is `account-resolve`; this atom calls it
  and stops if the brand does not resolve to one account).
- Account health, renewals, or deal status (use `account-health`, `renewal-signal`,
  `deal-status`).
- Any write. This atom reads `pipeline/accounts/*.local.json`; it never edits a contact.

## Input
```json
{
  "query": "string (required) -- the brand phrase",
  "person": "string or null -- a name or role hint ('that guy', 'Marcus', 'creative director')",
  "redacted": "boolean (optional) -- mask names and emails for output that leaves the machine"
}
```

## Core procedure
1. Call `tools/accounts.py --contacts "<query>" [--person "<hint>"]`. It resolves the brand
   through the same tiered resolver as `account-resolve`, then reads the `primary_contact` and
   `secondary_contacts` on the resolved record.
2. If the brand does not resolve to one account, stop and surface the resolver's candidates: ask
   the human which brand, do not read contacts from a guess.
3. If a `person` hint matches no contact, return the gap the tool produces, which names the known
   contacts on the account. Never return a contact the hint did not match, and never invent an
   address for a person who is not on the record.
4. The contact's email and name are PII. When the answer leaves the machine (a screenshot, shared
   text), pass `redacted: true` so names become initials and emails are masked.

## Output contract
```json
{
  "query": "",
  "person_hint": "the hint, or null",
  "account": "{account_id, brand_name} or null when the brand did not resolve",
  "contacts": [{ "name": "", "role": "", "email": "", "kind": "primary | secondary" }],
  "candidates": "the resolver candidates, present when the brand did not resolve",
  "computed_by": "tools/accounts.py.contacts",
  "gaps": []
}
```
EXPOSURE NOTE: contacts carry a real name and email. The raw result is for the human operator on
this machine; anything quoted into shared or external text uses the redacted form.

## Standalone usability
Given a brand the roster can resolve, the atom returns a send-ready contact row on its own.

## Failure modes
- Brand does not resolve (ambiguous or unknown): no contacts returned, the resolver candidates are
  surfaced for the human to choose.
- Person hint matches nobody: a gap lists the contacts that ARE on the account; the atom does not
  guess which one was meant.
- Account has no contact on record: a gap says so; no address is fabricated.
