---
file: skills/atoms/mail-triage/references/artifact-types.md
role: the artifact types this skill produces and the required elements of each.
---

# mail-triage artifact types

- **Triage result** (`tools/mail_triage.py triage`, or the `mail_triage` MCP tool): the boundary
  line, `human_review_required: true`, the counts per pile, and per message the Message-ID, date,
  subject and link (each none when held), sender (its display name none when held), pile, account
  match (resolved, or candidates; masked, account ids as tokens, from the MCP tool unless the
  server was started on stdio, and on the command line with --masked), flags,
  next step, `offline_pattern_scan` and `screen_note`, plus the gaps. Quality-gate dimensions:
  integrity (envelope fields from the connector, matches from the CRM only), safety (boundary
  line, held messages not acted on, nothing written or sent).
