---
file: skills/atoms/rate-card-fill/SKILL.md
name: rate-card-fill
description: fill a rate card for a brand partnership proposal by populating each requested format with either the creator's actual rates (when provided) or clearly labeled industry benchmark ranges from canonical-sources/rate-benchmarks/benchmarks.json. Use when a spoke is assembling a media kit, partnership proposal, or negotiation brief and needs structured per-format pricing. Do NOT use to invent, guess, or present benchmark ranges as the creator's personal rates.
load:
  - canonical-sources/rate-benchmarks/benchmarks.json
  - protocols/no-fabrication.md
---

# rate-card-fill

Populate a structured rate card for a brand partnership proposal. Each line item is sourced either
from the creator's actual rates (if the caller supplies them) or from the industry benchmark ranges in
`canonical-sources/rate-benchmarks/benchmarks.json`. The two sources are never mixed without
explicit labeling. A benchmark range is always presented as an industry reference point, never as
the creator's personal rate.

## Purpose

Brand partnership proposals require per-format pricing that is honest, defensible, and ready to
negotiate. This atom centralizes rate population so that every spoke that builds proposals, media
kits, or negotiation briefs draws from the same source of truth and applies the same labeling rules.

It handles two scenarios:

1. the creator's actual rates are available: each requested format is filled from `alex_actual_rates`
   when the caller provides them, else from the personal rate actuals file
   rate-card.local.json under pipeline/user-context/ (gitignored; schema:
   `pipeline/user-context/rate-card.template.json`; rows saved by the human from deal-debrief
   proposals). Source is marked `personal_rate`. No benchmark data is surfaced unless a format is missing from the
   provided rates.
2. the creator's rates are not provided (or a format is absent from them): the atom reads
   `canonical-sources/rate-benchmarks/benchmarks.json` and returns the benchmark range for that
   format, labeled `benchmark_range`. A disclaimer is appended to the output stating that the figures
   are industry reference ranges and not the creator's confirmed rates.

The atom never fabricates a number. If neither source covers a requested format, that format is
returned with `rate_or_range: null` and a `notes` value explaining the gap.

## Inputs

```json
{
  "format_list": [
    "long-form-integration",
    "dedicated-video",
    "short-form",
    "instagram-reel",
    "tiktok",
    "pinterest-pin",
    "usage-rights-addon",
    "exclusivity-addon"
  ],
  "alex_actual_rates": {
    "long-form-integration": "number or string or null",
    "dedicated-video": "number or string or null",
    "short-form": "number or string or null",
    "instagram-reel": "number or string or null",
    "tiktok": "number or string or null",
    "pinterest-pin": "number or string or null",
    "usage-rights-addon": "number or string or null",
    "exclusivity-addon": "number or string or null"
  }
}
```

Field rules:
- `format_list` is required. It must contain at least one value from the allowed set above. Unknown
  format identifiers are returned with `rate_or_range: null` and a note flagging the unrecognized key.
- `alex_actual_rates` is optional. If omitted, the personal rate-card local file is checked next;
  only when neither has the format do benchmark ranges apply. Rate benchmark rows carry structured
  `low`/`high`/`unit` fields (P30); metric-benchmark rows with null values are never quoted as ranges.
  If provided but a format key is absent, that format falls back to benchmark ranges and is labeled
  `benchmark_range`. Never infer a missing rate from adjacent formats.

## Output

```json
{
  "tool": "rate-card-fill",
  "rate_card": [
    {
      "format": "string -- the format identifier from format_list",
      "rate_or_range": "string or null -- e.g. '2500' or '500 to 3000 USD' or null if no source covers it",
      "source": "personal_rate | benchmark_range | no_data",
      "notes": "string or null -- gap flag, caveat, or null if clean"
    }
  ],
  "disclaimer": "string or null -- present whenever any line item carries source: benchmark_range; null if every line item is personal_rate",
  "recommended_negotiation_floor": "string or null -- the lowest benchmark floor across all benchmark_range line items in this card, expressed as a plain range string; null if no benchmark lines are present or if benchmark data does not supply a floor"
}
```

Field rules:
- `rate_or_range` for a `personal_rate` line is the value exactly as supplied in `alex_actual_rates`.
  Do not reformat, round, or adjust it.
- `rate_or_range` for a `benchmark_range` line is the range string from
  `canonical-sources/rate-benchmarks/benchmarks.json`. Read the field as-is; do not extrapolate or
  average across entries.
- `source` is `no_data` only when neither `alex_actual_rates` nor `benchmarks.json` covers the
  format. In that case `rate_or_range` is null and `notes` names the gap explicitly.
- `disclaimer` must read: "Rates marked benchmark_range are industry reference ranges sourced from
  canonical-sources/rate-benchmarks/benchmarks.json. They are not the creator's confirmed personal rates.
  Verify against current market data before quoting to a brand." Omit this field (null) only when
  every line item carries `source: personal_rate`.
- `recommended_negotiation_floor` is derived solely from benchmark entries already present in
  `benchmarks.json`. Never compute or infer a floor that does not appear in the file.

## Do NOT use for

- Presenting benchmark ranges as the creator's personal rates, even informally or approximately. Source
  labeling is mandatory on every line item (`protocols/no-fabrication.md`).
- Fabricating rates, inventing ranges, or extrapolating figures for formats not covered by
  `alex_actual_rates` or `benchmarks.json`. Return `no_data` and flag the gap instead.
- Writing proposal copy, email drafts, or negotiation scripts around the rate card (use a document
  spoke for that).
- Computing composite package pricing or applying discounts (that logic belongs in the calling spoke,
  not this atom).
- Storing or writing the rate card to any pipeline record (use the appropriate CRM write atom).
- Releasing the rate card to the user without passing through govern-artifact.

## Protocol note

Obeys `protocols/no-fabrication.md` in full. Every value in the output traces to either
`alex_actual_rates` (caller-supplied) or `canonical-sources/rate-benchmarks/benchmarks.json`
(on-disk reference). If a value cannot be traced, it is null and flagged. Pass output to
govern-artifact before the spoke surfaces it to the user.
