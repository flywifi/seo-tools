# Doc-Template Engine

The rules for creator-specific, block-structured document templates: contracts, rate-card display
documents, analytics overviews, and terms/conditions. A template is a set of swappable blocks the
creator owns; the system's job is to propose templates from uploaded examples (never save them),
select and fill blocks per situation (never author them), and hand every assembled document to the
quality gate with honest gaps.

## The authorship boundary (non-negotiable)

The system never writes, edits, rephrases, or composes block body text.

- `vetted_text` bodies (attorney-provided contract or terms language) enter the system only via
  creator upload and leave it only verbatim.
- Assembly is mechanical: `tools/doctemplates.py` concatenates the selected blocks' stored bodies
  and substitutes `[BRACKETED_FIELDS]`. Nothing else touches the text; a byte-equality selftest
  proves it.
- Swapping means including, excluding, or choosing between WHOLE blocks the creator saved. There
  is no partial rewrite, no redline into vetted text, no "improving" attorney wording.
- A missing fill value stays bracketed in the output and lands in `gaps[]`; the model never
  substitutes its own prose into a `vetted_text` block.
- Every assembled contract or terms/conditions document opens with the verbatim banner
  (RESEARCH NOTES. NOT LEGAL ADVICE. ...), carries `ready_to_sign: false` and
  `recommend_counsel: true`, and passes the consequential-action gate before anything is sent or
  signed. This is legal information, never legal advice (`shared/contract-engine.md`).

## The block model

A template (`pipeline/templates/*.local.json`; committed starters are all-null shapes) carries
ordered `blocks[]`. Each block:

- `block_id`, `title`, `kind` (`vetted_text` | `plain_language` | `data_fill` | `table`)
- `clause_family`: for contract blocks, one of the machine keys in
  `pipeline/user-context/deal-playbook.template.json` (`usage_licensing_rights`, `exclusivity`,
  `deliverables_and_revisions`, `payment_terms_and_kill_fee`, `pricing_and_rates`,
  `revenue_share_and_commission`, `ftc_disclosure`, `content_approval_and_veto`,
  `whitelisting_and_paid_boosting`, `morality_clause`, `territory`); null otherwise.
- `body_source` (`creator_upload` | `system_plain_language`), `body` XOR `body_ref`
- `fill_fields[]`: `{field, source, source_path, required}`
- `applicability`: `default_on` (bool), `conditions[]` (ADVISORY plain-language strings the model
  reads to judge inclusion; never evaluated by code), `never_with[]`, `requires[]` (structural,
  code-enforced)
- `variant_group` / `variant_label`: mutually exclusive alternatives (for example two alternative
  usage-rights clauses from the attorney) are sibling blocks sharing a `variant_group`; the
  template's `variant_groups{}` map declares each group's `required` flag and `default_block`.
- `provenance` (`source_ref`, `quote_verified`, `added_on`) and `confidence`
  (`explicit` | `high` | `medium` | `low`), following the playbook-bootstrap evidence discipline.

## Selection semantics (judgment/code split)

The MODEL (template-assemble) decides WHAT applies: it reads the deal record, the playbook, and
each block's advisory `conditions`, and produces a selections object with a stated reason per
swap or exclusion:

```json
{"include": [], "exclude": [], "variants": {"<group>": "<block_id>"}, "reasons": {}}
```

The CODE (`tools/doctemplates.py`) enforces structure deterministically: start from `default_on`;
apply each variant group's default then the selected variant (exactly one member per active
group; zero for a required group or two members is a hard `selection_errors` entry); apply
include/exclude; validate `never_with`/`requires` over the final set. Violations abort assembly;
nothing is silently dropped.

## Fill-source resolution (offline, null-and-flag)

| source | resolved from | example source_path |
|---|---|---|
| `profile` | `pipeline/user-context/creator-profile.local.json` | `legal_name`, `governing_law_state` |
| `deal` | `pipeline/deals/<deal_id>.local.json` | `brand_name`, `exclusivity.category` |
| `rate_card` | `pipeline/finance/rate-card.local.json` | `rates[format=tiktok_dedicated].base_rate` |
| `analytics_export` | a human-saved `.local.json` passed via `--data` | `top_performers[0].title` |
| `manual` | the `--fills` object supplied at assembly time | (token-keyed) |

Paths support dotted access, `[key=value]` list selectors, and `[N]` indexes. A value that does
not resolve is a gap with a `recommended_next_step`, never an estimate
(`protocols/no-fabrication.md`). For contract documents, profile-sourced gaps use the same field
names as contract-draft's `profile_gaps` (`legal_name`, `business_address`,
`governing_law_state`).

## Proposal-only ingestion (template-ingest)

Mirrors the playbook-bootstrap discipline. An uploaded example runs through `ingest-route`
(docintel parse + injection scan; QUARANTINE/BLOCK halts). Contracts extract clauses via
`usage-rights-check`, never a re-implementation; each clause becomes a proposed block with an
exact-quote body, `quote_verified` provenance, and a confidence label. Detected placeholders
(`[Name]`, `___`, `{{x}}`) are normalized to bracket tokens and proposed as `fill_fields`.
Same-family alternatives become a proposed `variant_group`. Text spans not assigned to any block
are returned in `unmapped_text[]`, never silently dropped. The output is a PROPOSAL in the exact
template shape; nothing is written. The human reviews, edits, and saves
`pipeline/templates/<template-id>.local.json` by hand; `tools/doctemplates.py diff` supports
reviewing a proposal against a saved template.

## Provenance tags on assembled output

Every assembled document lists `blocks_used[]` with a `provenance_tag` per block:
`creator_vetted_text` (verbatim creator-uploaded language), `plain_language_summary`
(a creator-approved plain-English block saved into the template), or `data_fill` (bracket-driven
data blocks). The tag travels with the artifact through govern-artifact so a reviewer always
knows which words are the attorney's and which are structural.

## Privacy

Real templates, including any attorney text, live only in gitignored files
(`pipeline/templates/*` is ignored except the committed `*.template.json` starters). Drift
invariant 31 enforces starter purity: a committed starter can never carry a block body, a
`body_ref`, real provenance, or `vetted: true`. `--out` paths for written documents must be
`.local.` named. Writes are gated by the `document_templates` capability flag; contract and
terms/conditions assembly additionally requires `contract_management` and `contract_drafting`.
