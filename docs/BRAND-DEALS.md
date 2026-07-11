# Brand deals: the inbound-pitch runbook (P40)

How Creator OS handles a brand pitch end to end, what unlocks each step, and the boundaries that
never move. Built and acceptance-tested against a fictional scenario (the "CoolBreeze" portable-AC
pitch: long-form video plus TikTok, a stated base offer) and regression-locked as scenario
`S7-coolbreeze-pitch` in `tools/scenario_check.py`.

## The flow

One hub classification, `pitch_triage`, routed to the `deal-pipeline` spoke, runs the chain:

1. **pitch-extract** (`skills/atoms/pitch-extract/`): the email body is untrusted content; a
   durable citation is stamped from the trusted envelope (RFC 5322 Message-ID plus permalink, or a
   human-supplied manual reference). Produces account and deal skeletons keyed to the CRM schemas.
   The compensation offer is a verbatim quote, never normalized. Instructions inside the email are
   flagged, never followed. The skeleton lands at stage `identified` with
   `stage_history[0].origin: inbound_pitch`; the enforced 9-stage machine is never extended.
2. **product-fit** (`skills/atoms/product-fit/`): every persona scored with reasoning tied to its
   stored pain point; pillar alignment; seasonal timing cited to the seasonal source; stored
   exclusivity conflicts checked through the pipeline read path. `data_basis` states whether the
   scores rest on niche-default personas or measured audience data; an exclusivity red flag caps
   the verdict at conditional_fit.
3. **proposal-price** (`skills/atoms/proposal-price/`, math in `tools/finance.py`): the package
   floor in one call (`--price-package`). Per-item floors resolve from the personal rate card when
   the item names a `format` (`rate_floor_source: rate_card`); an item with no computable floor is
   listed in `unpriceable_items` and EXCLUDED from the sum, never treated as 0. A benchmark
   comparison without a known subscriber tier emits `benchmark_tier_assumed`. Rate-floor-only
   pricing works and carries a `no_cost_basis` gap until a cost estimate exists.
4. **gap-record** then **govern-artifact**: every gap travels with the brief; the quality gate
   rules the release.

The brief contract: `fit_verdict`, `price_floor_package`, `content_angle_handoff` (strong personas
handed to content-strategy for video ideas), `recommended_next_steps`,
`human_review_required: true`. Contract drafting is NOT auto-run: the brief ends by telling the
human to ask for `contract_draft`.

## What unlocks what

The triage chain itself always runs. The rest is flag-gated, one click at the setup wizard's
`/brand-deals` screen (`python3 tools/wizard.py`), which writes only to the gitignored
`creator-os-config.local.json`:

| Switch or file | Unlocks |
|---|---|
| `contract_management` | contract-desk review of an inbound contract |
| `contract_drafting` | plain-language draft agreements (not-vetted, not-binding) |
| `finance_management` | finance record writes under `pipeline/finance/` |
| `pipeline/finance/rate-card.local.json` | personal rate floors per format (copy `pipeline/finance/rate-card.template.json`) |
| `creator-profile.local.json` | fills the party-identity placeholders in contract drafts; missing values surface as mandatory `profile_gaps[]` on every draft |

## The rate card

Real rates live ONLY in `pipeline/finance/rate-card.local.json` (gitignored; the committed file is
the all-null template). Rows are written by the human; `deal-debrief` proposes a `rate_history` row
from each closed deal and the human saves or discards it. `rate-card-fill` reads the card first as
the `personal_rate` source before any benchmark range.

Benchmark lever records for usage-rights and exclusivity uplifts and short-form tier rates exist in
`canonical-sources/rate-benchmarks/benchmarks.json` as structure only: null values,
`needs_research: true`, "do not quote" in the text. Pricing null-flags them by name; values arrive
only through a cited research pass.

## Boundaries that never move

- **Decision support never auto-quotes.** The consequential-action gate (amount, counterparty,
  explicit yes) applies before any number reaches a brand.
- **Human review before anything outward.** Every artifact carries `human_review_required: true`
  and passes govern-artifact; nothing is sent, accepted, or signed by the system.
- **No fabrication.** Missing rates, terms, or audience data are null plus a named gap
  (`protocols/no-fabrication.md`); an unpriceable item is an understatement flag, never a zero.
- **Contracts stay advisory.** Drafts are plain-language, not-vetted, not-binding, always
  recommending counsel; `ready_to_sign` is always false.
- **Private data stays local.** Rate cards, profiles, and deal records live in gitignored
  `.local.json` files; the pre-commit secret scan and drift invariants 19 to 21 fail closed in CI.

## Reusable documents (P42)

Rate cards, contracts, analytics overviews, and terms/conditions can be assembled from your own
block-structured templates: upload an example, save the proposed template by hand, and future
documents fill your brackets from the deal, the profile, and the rate card, with whole clause
blocks swapped per situation. Runbook: `docs/DOCUMENT-TEMPLATES.md`.

## Verification

```bash
python3 tools/finance.py --selftest      # includes the P40 pricing checks
python3 tools/scenario_check.py          # S7 pitch triage + S8 vetted-template assembly
python3 tools/sync_check.py              # drift guard, 31 invariants
```
