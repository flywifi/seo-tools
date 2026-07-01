---
file: skills/partnership-mediakit/SKILL.md
name: partnership-mediakit
description: "Pipeline/CRM spoke that builds brand partnership outreach materials for the creator: pitch paragraph, media kit sections, and rate card. Uses real data when supplied; uses labeled benchmarks when not."
load: always
---

# partnership-mediakit

Pipeline/CRM lane spoke that assembles a complete brand partnership outreach package for the creator's moody-vintage home decor and DIY channel. On a single request it produces the pitch
paragraph, the full set of media kit sections, and a rate card. It never guesses at figures or
invents data: real channel data is used when the caller supplies it; labeled industry benchmark
ranges from `canonical-sources/rate-benchmarks/benchmarks.json` are used when real data is absent;
fields that cannot be filled by either source are returned as explicit placeholders.

## Purpose

Brand partnerships are the primary direct-revenue lane for this channel. partnership-mediakit
exists so that every outreach package the creator sends is accurate, on-brand, legally compliant, and
ready for human review before it leaves the system. It orchestrates four atoms in sequence and
gates the completed package through govern-artifact before surfacing it to the user.

The spoke answers the question: "Given a target brand and whatever channel data I have right now,
what is the strongest, most honest outreach package I can produce?"

It does not make strategic decisions about which brands to pursue, set editorial direction, or
write any copy that could not be defended line-by-line against `protocols/no-fabrication.md`.

Key invariants:

- Benchmark rates are always labeled as industry reference ranges, never as the creator's personal rates.
  This rule is enforced at the atom level (rate-card-fill) and re-checked by govern-artifact.
- Any sponsored content arrangement described in this package must carry an FTC disclosure note per
  `protocols/safety.md`. The spoke flags this in the pitch paragraph's `personalization_notes` and
  in the final package's `compliance_notes` field. The human sender is responsible for including the
  disclosure statement in the final published content.
- No metric, brand name, campaign result, audience demographic, or rate figure is invented. Fields
  that cannot be sourced are returned as null with a `placeholders_to_fill` entry.
- The package is not final until govern-artifact passes and a human reviewer has resolved all
  `placeholders_to_fill` entries.

All voice and identity language comes from `shared/brand-engine.md` (professional outreach mode).
All CRM facts (existing deal stage, brand account history) are read from `shared/pipeline-engine.md`
and the relevant `pipeline/accounts/` and `pipeline/deals/` records when available; they are never
assumed or invented.

## Inputs

```json
{
  "brand_name": "string -- exact brand name as it should appear in the pitch and media kit",
  "brand_product_category": "string -- the product category or specific product line being pitched",
  "proposed_format": "integration | dedicated | short-form -- primary content format to propose",
  "brand_fit_notes": "string or null -- optional: specific aesthetic or audience overlap the caller knows; strengthens the pitch paragraph if provided",
  "alex_pillar": "string or null -- optional: which of the creator's five content pillars this partnership fits",
  "channel_data": {
    "subscribers": "integer or null",
    "avg_views_per_video": "integer or null",
    "engagement_rate_pct": "number or null",
    "avg_monthly_views": "integer or null",
    "top_demographics": "object or null",
    "recent_case_study": "object or null"
  },
  "alex_actual_rates": {
    "long-form-integration": "number or string or null",
    "dedicated-video": "number or string or null",
    "short-form": "number or string or null",
    "instagram-reel": "number or string or null",
    "tiktok": "number or string or null",
    "pinterest-pin": "number or string or null",
    "usage-rights-addon": "number or string or null",
    "exclusivity-addon": "number or string or null"
  },
  "sections_requested": [
    "channel_overview",
    "audience_demo",
    "content_pillars",
    "partnership_formats",
    "case_study",
    "rates_summary"
  ],
  "crm_account_id": "string or null -- pipeline/accounts/ record ID for this brand, if one exists"
}
```

Field rules:

- `brand_name` and `brand_product_category` are required. The spoke cannot produce a grounded pitch
  without them.
- `proposed_format` is required. Choose one of `integration`, `dedicated`, or `short-form`. The
  pitch paragraph and partnership_formats section are built around this choice.
- `channel_data` and `alex_actual_rates` are both optional. Any field within them may be null.
  Missing fields fall through to benchmark ranges or placeholders per the atom-level rules.
- `sections_requested` defaults to all six sections if omitted.
- `crm_account_id` is optional. When provided, the spoke reads the account record via
  `shared/pipeline-engine.md` to incorporate known deal history or contact details into
  `personalization_notes`. When absent, the spoke proceeds without CRM context.

## Primary outputs

```json
{
  "skill": "partnership-mediakit",
  "brand_name": "echo of input",
  "proposed_format": "echo of input",
  "pitch_paragraph": {
    "body": "string -- 150 to 250 words; professional, warm, specific; ready to paste into an outreach email draft",
    "subject_line_options": [
      "string -- direct value proposition angle",
      "string -- aesthetic or niche angle",
      "string -- question or curiosity angle"
    ],
    "personalization_notes": [
      "string -- items the sender must verify or customize before use, including mandatory FTC disclosure reminder"
    ],
    "fabrication_check": "PASS | FLAG:<reason>"
  },
  "media_kit_sections": [
    {
      "section_name": "string -- one of the six section names",
      "section_title": "string -- display heading",
      "section_body": "string -- markdown-formatted section body",
      "data_source": "real | benchmark | placeholder | mixed",
      "benchmark_label": "string or null -- present when data_source is benchmark or mixed",
      "placeholders_to_fill": ["list of fields requiring real data before publishing"],
      "fabrication_check": "PASS | FLAG:<reason>"
    }
  ],
  "rate_card": {
    "line_items": [
      {
        "format": "string",
        "rate_or_range": "string or null",
        "source": "personal_rate | benchmark_range | no_data",
        "notes": "string or null"
      }
    ],
    "disclaimer": "string or null -- present whenever any line item carries source: benchmark_range",
    "recommended_negotiation_floor": "string or null"
  },
  "compliance_notes": [
    "FTC disclosure: any sponsored content produced under this partnership must include a clear and conspicuous disclosure statement per protocols/safety.md. The sender is responsible for including the disclosure in the final published content.",
    "All benchmark rates are industry reference ranges only; verify against current market data before quoting to a brand."
  ],
  "placeholders_to_fill": ["aggregate list of all unresolved placeholders across pitch, sections, and rate card"],
  "govern_artifact_result": "PASS | HOLD:<reason>",
  "human_review_required": true
}
```

Output guarantees:

- `human_review_required` is always `true`. No package is final until a human reviewer has
  resolved every entry in `placeholders_to_fill` and the sender has confirmed `compliance_notes`.
- `govern_artifact_result` is `PASS` only when govern-artifact clears the full package through
  `protocols/quality-gates.md`. A `HOLD` result surfaces the blocking reason; the spoke does not
  suppress or soften it.
- `disclaimer` in the rate card is null only when every line item carries `source: personal_rate`.
  Whenever any benchmark range appears, the full disclaimer text from rate-card-fill is present.
- `compliance_notes` always includes the FTC disclosure reminder regardless of whether
  `proposed_format` is a dedicated video, integration, or short-form piece.

## Atoms composed

1. pitch-paragraph: writes the personalized pitch paragraph, three subject line options, and
   personalization notes for the brand. Called first. Receives `brand_name`,
   `brand_product_category`, `proposed_format`, `brand_fit_notes`, and `alex_pillar`.
2. mediakit-section (called once per requested section): writes one self-contained media kit
   section per invocation, using `channel_data` and `brand_name` as inputs. The spoke sequences
   these calls across all entries in `sections_requested`.
3. rate-card-fill: populates the rate card from `alex_actual_rates` when supplied, falling back to
   `canonical-sources/rate-benchmarks/benchmarks.json` benchmark ranges with mandatory labeling.
4. govern-artifact: gates the assembled package through `protocols/quality-gates.md` before the
   spoke returns output to the user. Any quality gate failure is surfaced as `HOLD` in
   `govern_artifact_result`; the spoke never silently passes a failing package.

## Engines required

- `shared/brand-engine.md`: channel identity, aesthetic description, content pillars, voice modes
  (professional outreach mode for pitch and media kit copy).
- `shared/pipeline-engine.md`: CRM record access and deal-stage context; used when
  `crm_account_id` is provided to pull existing account history into `personalization_notes`.

## References

- `shared/brand-engine.md`
- `shared/pipeline-engine.md`
- `protocols/safety.md`
- `protocols/no-fabrication.md`
- `protocols/quality-gates.md`
- `canonical-sources/rate-benchmarks/benchmarks.json`

## Do NOT use for

- Deciding which brands to pitch or evaluating brand fit as a strategy. This spoke builds materials
  for a brand the caller has already selected. Use content-strategy or deal-pipeline for brand
  prospecting and prioritization.
- Sending outreach emails, posting to any external platform, or writing any content to any CRM
  record. This spoke produces text only; all external actions require a human.
- Producing final publishable materials without human review. `human_review_required` is always
  `true`; every `placeholders_to_fill` entry must be resolved and `compliance_notes` confirmed
  before the package goes out.
- Presenting benchmark rate ranges as the creator's personal rates in any context. Benchmark figures are
  always labeled as industry reference ranges. Presenting them otherwise violates
  `protocols/no-fabrication.md`.
- Fabricating subscriber counts, engagement rates, audience demographics, case study outcomes, or
  brand endorsements. If real data is not supplied and no benchmark applies, the field is null and
  flagged, never filled with an invented figure.
- Outreach for product categories outside moody-vintage home decor, DIY, thrifting, seasonal decor,
  or outdoor living. Pitches for out-of-niche products misrepresent the creator's audience and brand.
- Creating or updating `pipeline/` CRM records. Read access to an existing account record is
  permitted when `crm_account_id` is supplied; write operations belong to deal-pipeline or
  account-manager.
