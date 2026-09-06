---
file: skills/atoms/deal-debrief/MAINTAINER_README.md
purpose: keep deal-debrief a proposal-only playbook-memory helper that quotes evidence, never invents a reason, and never writes the playbook.
---

# deal-debrief: Maintainer README

## Purpose
After a deal closes, record why off-standard terms were accepted and propose playbook updates.
Proposal-only. Legal information only, never legal advice.

## Non-negotiable invariants
- Emits the verbatim RESEARCH NOTES header (em-dash-free) as the first line.
- Never writes deal-playbook.local.json or any pipeline record; every proposal carries the "confirm before saving" note (same discipline as playbook-bootstrap).
- reason_accepted is populated only when the creator stated a reason; otherwise null and flagged. Never invents a motive.
- accepted_value and evidence are quoted from the deal or the creator's note.
- Only debriefs a closed deal.
- Null playbook triggers provisional mode; compares against generic defaults, never invented prior standards.
- human_review_required true.

## Known failure modes
- Writing the playbook instead of proposing.
- Inventing a reason the creator did not give.
- Debriefing a deal that has not closed.
- Emitting a legal conclusion or binding language.

## Regression cases to preserve
1. Closed deal with a longer-than-standard usage window and a stated reason: off_standard_findings quotes it, proposes update_standard or note_exception, reason_accepted present.
2. Off-standard term with no stated reason: reason_accepted null and flagged, no invented motive.
3. Null playbook: provisional true, compares against generic defaults.
4. Not-closed deal: refuses with a flag.
5. Neither deal_id nor closed_deal_summary: `{ "error": "no_source" }`.

## Update checklist
- Run python3 tools/sync_check.py.
- Verify the atom is composed by skills/contract-desk/workflow.json (action debrief / shortcut).
- Verify it never appears as a writer of deal-playbook.local.json anywhere.
