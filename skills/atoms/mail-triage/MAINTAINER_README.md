---
file: skills/atoms/mail-triage/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for mail-triage so it stays stable under iteration.
---

# mail-triage: Maintainer README

## Purpose
Sorting inbound mail the session read through its own Gmail connector, realized by
`tools/mail_triage.py` (the `mail_triage` MCP tool on Claude Desktop, Codex and Antigravity, each of
which starts the server on stdio; ADR 0085). It ends at the pile and the
next step: pitches go to `pitch_triage`, receipts to the hub Inbox as `.eml` files, and the person
replies in Gmail.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md`, `protocols/safety.md` and
  `protocols/formatting-metadata.md`.
- Proposal-only: the tool has no write path and no mail access; its selftest reads its own text for
  imports and calls by name. The session never sends, replies to, labels, archives or deletes mail because of it.
- Bodies are untrusted: pass 1 in the tool, pass 2 in the session; a held message gets no other
  pile.
- Senders match by address (`tools/accounts.py::resolve_sender`), never by display name; a domain <!-- verify: tools/accounts.py::resolve_sender -->
  match is a candidate the person confirms.
- Envelope fields are copied from the connector's result, never written by the model.
- Unless the server was started on stdio, the CRM side of each match is masked.

## Known failure modes
- Fixed word lists miss a payment notice or pitch worded another way (it lands in `other`).
- An agency writing for a brand is not matched to it.

## Fragile fallbacks that must not become defaults
- Matching a sender by display name or by a fuzzy brand-name guess.
- Recording a payment notice from the body text instead of the saved `.eml` file.

## Regression cases to preserve
1. A contact's payment message: `payment_notice` with its account and the `.eml` step.
2. A spoofed display name: no match, flagged, the warning first in the next step.
3. An injected body: `held`, subject not echoed, no pass 2.
Mapped to evals/evals.json and `python3 tools/mail_triage.py --selftest`.

## Approval-gated changes
The pile order, the word lists, the matching rules, the caps (50 messages, 65,536 characters of body) and
anything that writes or touches mail.

## Minority-report policy
When the tool's pile and the session's reading disagree, show both; the person decides.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/mail_triage.py --selftest` and `python3 tools/accounts.py --selftest` pass.
3. `python3 tools/sync_check.py` exits 0.
