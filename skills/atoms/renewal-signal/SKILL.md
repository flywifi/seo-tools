---
file: skills/atoms/renewal-signal/SKILL.md
name: renewal-signal
description: "scans closed deals in pipeline/deals/ for renewal opportunities and returns a priority-ranked list of candidates; does NOT draft outreach copy or advance deal stages."
load:
  - shared/pipeline-engine.md
  - protocols/no-fabrication.md
---

# renewal-signal

Scan closed or fulfilled deal records in `pipeline/deals/` and return a priority-ranked list of
renewal candidates. Every field in the output is read directly from stored records; nothing is
estimated, inferred, or fabricated beyond the priority-scoring thresholds defined below.

## Purpose

Brand sponsorship deals have a natural lifecycle: a deal closes, the deliverables are fulfilled, an
exclusivity window expires, and the brand becomes eligible for re-engagement. Left untracked, these
windows slip by and revenue opportunities are lost. This atom centralizes the scan so any CRM or
pipeline spoke can surface renewal candidates without duplicating logic or reading deal records in
multiple places.

Priority thresholds (computed from stored timestamps relative to today; never estimated):

| Signal | high | medium | low |
|---|---|---|---|
| days since closed_date | 0 to 90 | 91 to 180 | 181 or more |
| exclusivity_expires within next N days | 0 to 14 | 15 to 30 | 31 or more |

A candidate is elevated to `high` if either signal qualifies as high. If both signals are low, the
candidate is `low`. Otherwise it is `medium`. If `exclusivity_expires` is absent from the record,
treat exclusivity as not a factor and score on `closed_date` alone; note the gap in
`renewal_reason`.

## Inputs

```json
{
  "account_id": "string or null -- optional; restrict scan to deals linked to this account",
  "lookback_days": 180
}
```

- `account_id`: optional. When provided, the scan is restricted to deals whose `account_id` field
  matches. When null or omitted, all closed or fulfilled deals within the lookback window are
  scanned.
- `lookback_days`: optional, default 180. Defines how far back from today to look for
  `closed_date`. Deals closed more than `lookback_days` ago are excluded unless their
  `exclusivity_expires` date falls within the next 30 days, in which case they remain eligible
  regardless of lookback.

## Output

```json
{
  "tool": "renewal-signal",
  "scanned_deals": 0,
  "renewal_candidates": [
    {
      "deal_id": "string",
      "brand_name": "string",
      "closed_date": "YYYY-MM-DD",
      "exclusivity_expires": "YYYY-MM-DD or null",
      "renewal_reason": "one sentence citing the specific signal that drove inclusion, e.g. exclusivity expires in 8 days or closed 60 days ago within lookback window",
      "priority": "high | medium | low"
    }
  ],
  "recommended_next_step": "string -- one sentence describing the highest-leverage action across all returned candidates, e.g. run pitch-paragraph for the 2 high-priority candidates before exclusivity expires"
}
```

Field rules:

- `scanned_deals` is the count of closed or fulfilled records read before filtering, not just the
  candidates returned.
- `renewal_candidates` is sorted by `priority` descending (high first), then by
  `exclusivity_expires` ascending (soonest first) within each tier, then by `closed_date`
  descending as a final tiebreaker.
- `brand_name` is copied verbatim from the deal record. Do not look up or infer it from other
  sources.
- `exclusivity_expires` is null when the field is absent from the record. Do not estimate a date.
- `renewal_reason` must cite a concrete field value (a date, a count, a threshold). Vague reasons
  such as "looks ready" are not permitted under `protocols/no-fabrication.md`.
- `recommended_next_step` is derived from the candidate list, not from memory or general advice.
  If the list is empty, set this to "no renewal candidates found within the current parameters".

## Do NOT use for

- Drafting outreach messages, emails, or pitch copy for any candidate (use pitch-paragraph or a
  document spoke).
- Advancing deal stages, updating deal records, or creating new deal records (use the appropriate
  CRM write atom).
- Scoring accounts by health (use account-health).
- Fabricating or estimating any date or field that is absent from a stored record
  (`protocols/no-fabrication.md`). Null and flag instead.
- Bulk account analysis beyond what is scoped by `account_id` and `lookback_days`; callers that
  need cross-portfolio reporting should iterate this atom per account.
- Making final release decisions; output must pass through govern-artifact before surfacing to
  the user.

## Pipeline note

Follows `shared/pipeline-engine.md` for record resolution, deal-status interpretation, and gap
handling. All data originates in `pipeline/deals/`; real records are gitignored and never committed.
Obeys `protocols/no-fabrication.md`: if a required field such as `closed_date` is missing from a
deal record, emit a gap-record object for that deal and continue scanning the remainder rather than
halting or estimating. Pass the output to govern-artifact before the spoke returns it to the user.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
