---
file: shared/contract-engine.md
role: Source of truth for contract review, redline, obligations, and legal-requirement checks on
  brand-partnership agreements. Read by the contract-desk spoke and the contract atoms
  (contract-triage, contract-review, legal-requirement-check, escalation-brief, and the Phase 2 and 3
  atoms). The deal lifecycle and CRM record live in shared/pipeline-engine.md; the legal, disclosure,
  and safety boundaries live in protocols/safety.md; non-fabrication rules live in
  protocols/no-fabrication.md.
load: for every contract-desk request and any Pipeline/CRM request that touches contract text
status: authored for P23 from the creator-side deal-review need; adopts the durable patterns from a
  prior commercial-legal review skill (clause taxonomy, obligation rows, difference labels, source
  precedence) and converts them to the solo-creator brand-deal context. US jurisdiction only.
---

# Contract Engine

This engine turns a brand-partnership contract into structured, source-grounded review output for a
solo creator. It never rules on enforceability and never drafts binding language as if vetted. It
organizes, extracts, flags, and explains in plain language so the creator and a qualified attorney
can decide.

## The hard boundary (non-negotiable, identical to protocols/safety.md)

Creator OS is not legal counsel and does not give legal advice. Every contract atom:

- Emits this exact header, verbatim, as the first line of any contract output:

  ```
  RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.
  ```

  (The header uses periods, not dashes, because Creator OS forbids em dashes in user-facing output;
  see protocols/formatting-metadata.md. The meaning is the standard non-lawyer banner.)

- Sets `human_review_required: true` on every output.
- Defaults `recommend_counsel: true` whenever anything is ambiguous, high value, one-sided, or
  structurally incomplete. It may be `false` only when every key field is present, no flags are
  raised, and the terms are unambiguous on their face.
- Summarizes terms in plain language, surfaces the points that deserve attention, and never states
  that a term is or is not enforceable.
- Passes a **consequential-action gate** before anything that leads to signing, sending, or
  committing money: state plainly "this step has legal consequences," attach a one-page brief the
  creator can bring to a lawyer, and do not proceed without an explicit yes from the human. Agents
  never sign, send, or commit; they produce confirmation summaries for human review only.

This is legal information, never legal advice, in every mode, on every path.

## Where a contract sits in the deal lifecycle

The contract-artifact store is `pipeline/contracts/` (schema:
`pipeline/contracts/contract.template.json`; real records are gitignored `.local.json`, and raw
contract text is never committed). A contract record links to its deal by `contract_ref` on the deal
and `deal_id` on the contract.

Contract status maps onto the nine deal stages in `shared/pipeline-engine.md`:

| Contract status | Deal stage | What it means |
|---|---|---|
| `received` | in-discussion or contract-negotiating | an inbound draft has arrived, not yet reviewed |
| `in_review` | contract-negotiating | the atoms have triaged and reviewed it |
| `redlined` | contract-negotiating | review findings and suggested changes exist |
| `negotiating` | contract-negotiating | changes are going back and forth across versions |
| `signed` | signed | an executed agreement exists (every sponsored deliverable has its FTC field) |
| `amended` | signed or in-production | a later version modifies the signed agreement |
| `expired` | closed/fulfilled or archived | the term or usage window has ended |

The Contract Review entry rule (`shared/pipeline-engine.md`) applies at `contract-negotiating`: a deal
cannot advance to `signed` unless every sponsored deliverable has its FTC disclosure field populated.

## Clause taxonomy (creator-side families)

Use these families as stable review buckets. Keep the contract's own labels when they exist.

- **Usage and licensing rights**: where, how long, and by whom the content may be reused; organic vs
  paid; license duration; ownership and copyright.
- **Exclusivity**: category scope, competitor list, platforms, and the duration of any
  no-competing-brand window.
- **Deliverables and revisions**: format and count of deliverables, number of revision rounds, and
  the approval window.
- **Payment and kill fee**: fee, payment timing (for example, net 30 from delivery), deposit, and a
  kill fee if the brand cancels.
- **FTC and disclosure**: who is responsible for the paid-partnership disclosure; confirmation the
  contract does not try to waive it (a contract cannot waive the FTC obligation).
- **Content approval and veto**: brand review and approval rights, veto scope, and the approval
  turnaround window.
- **Whitelisting and paid boosting**: whether the brand may run the creator's content as paid ads,
  and on what terms.
- **Morality**: conduct clauses that let the brand terminate; scope and mutuality.
- **Territory**: geographic scope of the license and the exclusivity.

## The four-tier playbook model

The creator's own negotiating positions live in `pipeline/user-context/deal-playbook.template.json`
(real values in the gitignored `.local.json`). For each clause the playbook records four tiers:

- **standard**: the position the creator opens with.
- **fallbacks**: ordered concessions the creator can live with.
- **never**: lines the creator will not cross.
- **the_one_thing**: the single point that matters most on this clause.

Every contract atom reads the playbook first. If the playbook is still the null template, the atom
runs in a clearly labeled provisional mode (prefix `[PROVISIONAL: no playbook configured]`) against
the generic creator-side defaults below, and never against invented positions. Generic defaults
(guidance, not the creator's committed positions):

- Usage rights default to organic social use for a bounded window (commonly 6 to 12 months); paid
  amplification and perpetual or white-label use are worth flagging and pricing separately.
- Exclusivity should name a specific category and a bounded window; open-ended or whole-niche
  exclusivity for a single-post fee is worth flagging.
- Payment should state a fee and a timing (for example, net 30 from delivery) and, on larger scopes,
  a kill fee; "payment on brand's discretion" or no timing is worth flagging.
- The FTC disclosure obligation cannot be contracted away and is required on every sponsored,
  gifted, or affiliate deliverable (protocols/safety.md).

## Plain-language draft assembly (contract-draft)

`contract-draft` (P23 Phase 2) assembles a plain-language starting point from terms that are already
known. It never parses raw contract text (that is `usage-rights-check`) and never emits operative
legalese, indemnity, or warranty language. For each clause family it fills one plain-language term by
this source precedence, and tags the term with the source it used:

1. `deal_agreed`: a term explicitly agreed in the deal record or the supplied agreed_terms object.
   Agreed terms always win. Quote the source field exactly.
2. `playbook_standard`: where the deal is silent and a real playbook is configured, the creator's
   `standard` tier for that clause (the opening position, never a `fallback` or `never` line). Labeled,
   because a standard opening position is not the same as an agreed term.
3. `generic_default`: provisional mode only (null-template playbook). The generic creator-side defaults
   in this engine, offered as guidance and never presented as the creator's committed position.
4. `MISSING`: no source provides the term. The term is null, the family is flagged and listed in
   `missing_terms`, and nothing is invented to fill it.

The output is always labeled not-vetted, not-binding, and a starting point to formalize with a qualified
professional. It passes the consequential-action gate above (turning these terms into a signed agreement
is a consequential action), sets `ready_to_sign: false`, and never emits anything meant to be signed
as-is. `amendment-trace` uses the separate version source precedence in "Amendment and version model";
this section governs draft assembly only.

## Bootstrapping and nudging the playbook (proposal only)

The playbook is the creator's own document. No atom ever writes it. `playbook-bootstrap` (P23 Phase 2)
proposes to it in two modes, and the human confirms, edits, and saves the local playbook file by hand:

- bootstrap: from example past contracts or terms the creator supplies, propose a starting four-tier
  position per clause family, each proposed value tagged with the example that supports it (an exact
  quote) and a confidence label. Omit any clause family the examples do not address; never invent a
  position to fill a tier.
- nudge: from a set of recent deals, detect a term the creator has repeatedly accepted off the current
  standard (the same off-standard value in at least two of the provided deals) and propose updating
  that default, quoting the supporting deals. Never fabricate the frequency; count only observed deals.

Both modes are proposal-only, carry the RESEARCH NOTES boundary, set `human_review_required: true`,
and state plainly that nothing is written to the playbook automatically. Neither mode rules on
enforceability or drafts binding clause language; proposed positions are plain-language negotiating
preferences, not vetted contract text.

## Dual severity (rank deal-breakers first)

Every review finding carries two independent severities, each `none | low | medium | high`:

- **legal_risk**: how exposed the creator is if the clause operates as written (for example, granting
  perpetual worldwide rights, or an uncapped indemnity).
- **business_friction**: how much the clause costs the creator in practice (for example, a 5-round
  approval loop, or exclusivity that blocks likely future deals).

Order findings deal-breakers first: any finding with `high` on either axis leads, then `medium`, then
the rest. A clause can be low legal risk but high business friction, or the reverse. Never collapse
the two into one score.

## Confidence labels (quote before you infer)

Tag every extracted field and finding with one of:

- `explicit`: directly supported by quoted or clearly visible contract wording.
- `high`: simple structural inference (for example, carrying a section heading to the paragraph
  directly under it).
- `medium` or `low`: best-effort interpretation, used only when the creator asked for it and the
  field cannot be left blank.

Separate three states in every output: **explicitly stated**, **reasonably inferred**, and
**missing or not found**. Never smooth over a gap. A missing clause is a finding, not a blank.

## Obligation-row schema (one row per distinct duty)

When extracting obligations (contract-review surfaces them; the Phase 3 obligation-extract atom writes
them to the register), keep one row per distinct obligation and preserve the direction of the duty.
Columns:

`document`, `section`, `clause_family`, `obligation_type`, `obligated_party`,
`beneficiary_or_counterparty`, `required_action`, `trigger`, `timing_or_deadline`,
`consequence_if_stated`, `evidence_text`, `confidence`, `notes`.

Do not merge unrelated duties into one row. Quote `evidence_text` from the source.

## Amendment and version model (net current state)

When more than one version exists, produce a net-current-state view: for each topic, what the
operative agreement says right now after all amendments, with the exact quote and its source version.

Classify each material difference with exactly one label: `unchanged`, `clarified`, `expanded`,
`narrowed`, `added`, `removed`, `contradictory`, or `uncertain`. Align by section number or exact
heading; if numbering differs, align by clause topic. Preserve both versions' wording for material
differences. Call out when a later document overrides an earlier one. If alignment is weak, mark
`uncertain` rather than forcing a match.

Source precedence when versions conflict:

1. Final signed or latest operative agreement text
2. Amendment or side letter that explicitly modifies the agreement
3. Order form or exhibit tied by exact reference to the agreement
4. Redline or comparison copy
5. Conservative inference from document structure
6. Otherwise mark as missing or uncertain

(Version tracing is implemented in P23 Phase 2 as the `amendment-trace` atom, which uses this model.)

## Deadline date math (obligations to timeline)

For deadlines pulled from a contract (Phase 3 obligation register), store both the raw date and an
effective date with a provenance tag, and:

- **Alert off the send-by date**, not the due date. If an invoice is due net 30 from delivery, the
  action the creator controls is delivering and invoicing on time; surface the send-by date.
- **Roll backward over weekends and holidays**: if a computed action date lands on a weekend or a US
  federal holiday, move it earlier to the prior business day, never later.
- **Urgency bands** (half-open, in days until the action date): red is 0 to 13, orange is 14 to 44,
  yellow is 45 to 89, and beyond 89 is out of band. Feed these to the existing join points
  (content-calendar, production-task) rather than a parallel calendar.

## Obligation register (P23 Phase 3)

`obligation-extract` reads a signed contract and emits obligation rows (the schema above). The rows
are the input to the offline compute lane; the register itself is the dated result. Record shape
(`pipeline/user-context/obligation-register.template.json`; real data in the gitignored `.local.json`):
`obligations[]` each carrying the extracted row plus the computed `raw_date`, `effective_date`,
`send_by_date`, `urgency_band`, `provenance`, and `gaps`; plus `contract_ref`/`deal_id`,
`computed_as_of`, `lead_days`, `band_counts`, and `last_computed`. The register feeds the existing
join points, never a parallel calendar: content-calendar (`entries[].publish_target_date`,
`posts[].ftc_disclosure` via `linked_deal_id`), production-task (D-minus-N offsets from `send_by_date`),
and deal-resourcing plus invoice-status (payment triggers).

## Offline compute lane (deterministic, token-saving)

The date math above is pure arithmetic, so it runs in code, not in tokens. `tools/obligations.py`
(pure stdlib, no network) takes the extracted rows and computes send-by dates, weekend and
US-federal-holiday roll-backward, and urgency bands, then writes the register. It mirrors the P22
scoop handoff: a `--scan` read-only mode (always available), a flag-gated `--build --write` (the write
needs `contract_obligations`), and a sha256 bucket manifest (`--manifest` / `--verify`) so an offline
machine's register can be verified before the online side trusts it. The MCP tools `obligation_build`,
`obligation_scan`, and `import_obligations` are the online-to-offline bridge: the model calls them, the
local tool returns the computed register or scan as JSON, and the model never does the arithmetic. The
general rule: deterministic tasks (date math, rollups, register builds, deadline scans, hash
verification) run locally over gitignored `.local` artifacts; the LLM orchestrates and interprets;
results cross back through an import adapter with a hash-verified manifest.

## Playbook memory (deal-debrief)

`deal-debrief` closes the loop after a deal ends: it records why any off-standard term was accepted and
PROPOSES a playbook update (`update_standard` or `note_exception`), backed by evidence from the deal.
Like `playbook-bootstrap`, it is proposal-only and never writes `deal-playbook.local.json`; the human
confirms and saves. It never invents a reason the creator did not give.

## Inbound triage (GREEN, YELLOW, RED)

`contract-triage` gives an inbound offer a fast verdict before a full review:

- **GREEN**: standard, low-risk terms; nothing hidden; proceed to normal review.
- **YELLOW**: something needs attention before signing (an ambiguous clause, a missing standard term,
  or a hidden obligation such as a non-disclosure or non-compete tucked into a sponsorship offer).
  Any hidden obligation auto-sets YELLOW at minimum.
- **RED**: a likely deal-breaker on the creator's `never` list, or a term with high legal risk (for
  example, perpetual worldwide rights for a flat fee, or an uncapped indemnity).

Triage scores relevance and importance separately from the verdict and records the reasons; it never
resolves the issue, it routes it.

## Curated legal sources (US only)

`legal-requirement-check` cites these. They are registered in
`canonical-sources/source-registry.json` (seeded from `canonical-sources/legal-sources-seed.json` via
`tools/source_currency.py`, the only writer). Creator OS deliberately avoids case-law, court-docket,
and statute corpora; this is a small curated set of primary FTC and plain-language contract-hygiene
references, not a legal database.

- FTC Endorsement Guides (16 CFR Part 255)
- FTC Disclosures 101 for Social Media Influencers
- FTC Endorsements FAQ (The Dos and Don'ts)
- FTC Endorsements and influencers hub
- U.S. Copyright Office (copyright basics and ownership)
- Cornell LII Wex: contract, and Wex: license

Jurisdiction is US only, matching these sources. A non-US contract would need different sources; flag
that rather than applying US guidance to a foreign agreement.

## Reuse map (compose, do not duplicate)

- `usage-rights-check` is the raw-`contract_text` clause extractor (usage rights, exclusivity,
  ownership, FTC, flags, recommend_counsel). contract-triage and contract-review call it rather than
  re-parsing.
- `exclusivity-check` cross-references active deals for category and timing conflicts.
- `invoice-status`, `production-task`, and `calendar-slot` are reused for the obligations and timeline
  work (Phase 3).
- `govern-artifact` runs the quality gate on every contract output before the spoke surfaces it.

## Non-fabrication rules for contracts

Inherited from protocols/no-fabrication.md and non-negotiable here:

- Never invent clause language, party names, dates, fees, or terms. Quote or paraphrase conservatively
  from the source; if a term is absent, the field is null and a flag is raised.
- Never present an interpretation as a legal conclusion.
- Every finding points to `evidence_text` quoted from the contract, or is labeled as inferred or
  missing.
- When a document is ambiguous, conflicting, or incomplete, say so directly.
