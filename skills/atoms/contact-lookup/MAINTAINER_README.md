---
file: skills/atoms/contact-lookup/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for contact-lookup so it stays stable under iteration.
---

# contact-lookup: Maintainer README

## Purpose
Resolve a brand phrase to one account and read the contact(s) on it, optionally filtered to a
person hint. The resolution and read are `tools/accounts.py` (offline, deterministic); this atom
is the thin contract around `contacts()`. It reads only.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/pipeline-engine.md`), obeys
  `protocols/no-fabrication.md` (never invent a contact or address) and `protocols/safety.md`
  (contact data is PII; redact anything leaving the machine).
- READ-ONLY. No write path; contact edits are the spoke/SKILL contract's job.
- Resolves the brand first via the shared resolver. If the brand does not resolve to ONE account,
  no contacts are read; the resolver candidates are surfaced instead.
- A person hint that matches no contact returns a gap that NAMES the known contacts; it never
  returns a contact the hint did not match, and never guesses which person "that guy" is.
- Names and emails come verbatim from the record. `--redacted` masks names to initials and emails
  to a stub for any output that leaves the machine.

## Known failure modes
- Ambiguous brand: no contacts, candidates surfaced.
- Unmatched person hint: gap lists the real contacts, no guess.
- Account with no contact row: gap, no fabricated address.

## Fragile fallbacks that must not become defaults
- Returning the primary contact when a person hint did not match "because it's probably them".
- Reading contacts from the top candidate when the brand did not resolve.

## Regression cases to preserve
1. Resolved brand returns all contact rows.
2. Person hint matches exactly one contact and returns it with the verbatim email.
3. Unmatched person hint returns a gap naming the known contacts, zero contacts.
4. Unresolved brand returns no contacts, resolver candidates present.
Mapped to evals/evals.json; the read is pinned by `python3 tools/accounts.py --selftest`.

## Approval-gated changes
The resolve-first rule, the never-guess-the-person rule, the redaction posture, and the output
schema.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/accounts.py --selftest` passes.
3. `python3 tools/sync_check.py` exits 0; `python3 tools/scenario_check.py` stays green.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
