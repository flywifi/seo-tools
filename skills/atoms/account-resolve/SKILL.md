---
name: account-resolve
atom: true
standalone: true
description: "resolves a fuzzy brand phrase from a creator ('that lightbulb company', 'the Hearthline people', a nickname) to exactly one account record in pipeline/accounts/, using tiered matching (exact, alias, substring, difflib fuzzy, then a brand-category term map). It NEVER auto-picks past a confident exact or alias match: a category or ambiguous phrase returns resolved:null plus the ranked candidate list with the evidence for each, for the human to choose. Do NOT use to read a contact's name or email (that is contact-lookup, which resolves first then reads), to report a deal's stage (deal-status), or to write or mutate any account record (this atom only reads)."
engines_required:
  - shared/pipeline-engine.md
protocols:
  - protocols/no-fabrication.md
---

# account-resolve

Turn a creator's loose reference to a brand into the one account record it points at, or an
honest "which of these did you mean?" when the phrase is ambiguous.

## When to use this skill
- "which account is the lightbulb company?", "pull up the Hearthline people", "that paint brand
  we talked to in spring" reached through the account-manager `resolve` step, ahead of any read
  that needs an exact account (contact-lookup, deal-status, account-health).

Do NOT use for:
- Reading a contact's name, email, or role (that is `contact-lookup`; it calls this atom first).
- Reporting where a deal stands (use `deal-status`).
- Any write. This atom reads `pipeline/accounts/*.local.json` and proposes; it never edits a
  record.

## Input
```json
{
  "query": "string (required) -- the creator's brand phrase",
  "redacted": "boolean (optional) -- mask brand names for output that leaves the machine"
}
```

## Core procedure
1. Call `tools/accounts.py --resolve "<query>"` (offline, deterministic). The tool normalizes
   the phrase and scores every account by tier: exact brand_name, then `aliases[]`, then
   substring, then `difflib` similarity, then a brand-category term map ("lightbulb" to the
   `lighting` category).
2. Read the result. `resolved` is non-null ONLY for a confident exact or alias match, or a sole
   high-similarity fuzzy match. A category match or two or more close candidates always come
   back as `resolved: null` with the ranked `candidates[]`.
3. If `resolved` is null, present the candidates with their `match_basis` and ask the human which
   brand they mean. Never pick for them; never fabricate an account that is not on the roster.

## Output contract
```json
{
  "query": "",
  "resolved": "the chosen account {account_id, brand_name, confidence, match_basis} or null",
  "resolution": "exact | alias | substring | fuzzy_high | fuzzy_low | category | none",
  "candidates": [{ "account_id": "", "brand_name": "", "confidence": 0.0, "match_basis": "" }],
  "computed_by": "tools/accounts.py.resolve", <!-- verify: tools/accounts.py::resolve -->
  "gaps": []
}
```

## Standalone usability
The resolver output alone tells the caller whether it has a single account to act on or a choice
to put to the human.

## Failure modes
- Ambiguous phrase (two brands share a prefix): `resolved` is null and both appear in
  `candidates`; surface the choice, do not guess.
- Category or nickname only ("the lightbulb company"): resolves to null with the category
  candidates; a category phrase never auto-resolves because more than one brand can share it.
- Empty account store (fresh clone): `resolved` null plus a gap naming the empty store; nothing
  is invented.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
