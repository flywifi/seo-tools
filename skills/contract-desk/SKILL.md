---
file: skills/contract-desk/SKILL.md
name: contract-desk
description: "reviews inbound brand-partnership contracts: triage (GREEN/YELLOW/RED), clause-by-clause review against the creator's playbook with dual severity, creator-relevant legal-requirement checks (FTC, usage, exclusivity, payment) with cited sources, and a decision-ready escalation brief; outputs legal information only (not legal advice) per protocols/safety.md; does NOT rule on enforceability, draft binding language, sign, or send anything."
load: for contract-desk requests when the contract_management capability is enabled
---

# contract-desk

contract-desk is the Pipeline/CRM spoke that reviews the contract document itself, complementing
deal-pipeline (which manages the deal's lifecycle and CRM record). It reads an inbound
brand-partnership contract and returns a triage verdict, a clause-by-clause review, legal-requirement
flags with cited sources, and a decision-ready escalation brief. It is legal information only, never
legal advice. It never rules on enforceability, drafts binding language, signs, or sends anything.

## Boundary (verbatim on every artifact)

```
RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.
```

Every output sets `human_review_required: true`, defaults `recommend_counsel: true` when anything is
unclear, and passes the consequential-action gate before any step that leads to signing, sending, or
committing money (see `shared/contract-engine.md` and `protocols/safety.md`).

## Capability gating (all default off)

- `contract_management` (master): activates this spoke. When off, deal-pipeline's existing
  plain-language contract-negotiating behavior is unchanged and this spoke does not run.
- `legal_requirement_checks`: enables the legal-requirement scan step.
- `contract_redline`: enables the full clause-by-clause review and, in Phase 2, version tracing
  (`amendment-trace`): net current state across contract versions.
- `contract_drafting`: enables the Phase 2 plain-language draft assembly (`contract-draft`); the draft
  is always not-vetted, not-binding, and never signed.
- `contract_obligations` (Phase 3): enables `obligation-extract` (pull duties from a signed contract
  into rows) and the offline obligation register. The date math (send-by, weekend and US-holiday
  roll-back, urgency bands) runs in local Python via `tools/obligations.py`, not in tokens; the
  register write is gated by this flag while the read-only scan is always available.
- `playbook-bootstrap` and `deal-debrief` (proposal-only playbook setup and close-out memory) are
  gated by the `contract_management` master and never write the playbook.

## What is delivered

Phase 1 delivers the review path: feed a brand contract (uploaded file or pasted text, reusing the
existing document connectors; no new connector is added) and the spoke produces a triage verdict, a
clause review with dual severity and exact quotes, legal-requirement flags with cited FTC and
reference sources, and an escalation brief of the points worth raising with the brand and an attorney.

Phase 2 adds drafting and version tracking: `contract-draft` assembles a plain-language, not-binding
starting point from the playbook and the deal's agreed terms; `amendment-trace` produces the
net-current-state view across contract versions; and `playbook-bootstrap` proposes (never writes) a
starting playbook from example contracts or nudges an off-standard default from recent deals.

Phase 3 adds obligations and memory: `obligation-extract` pulls the deliverables, deadlines, and
payment terms out of a signed contract into rows; `tools/obligations.py` then computes the dated
register offline (send-by dates, weekend and US-holiday roll-back, urgency bands) so the model spends
no tokens on arithmetic, and the register feeds the content-calendar, production-task, and
deal-resourcing join points through the `import_obligations` handoff. `deal-debrief` closes the loop
after a deal ends by proposing (never writing) playbook memory updates. The register and all real
contract data stay in gitignored `.local` files on the creator's machine.

## Inputs

| Field | Required | Notes |
|---|---|---|
| `contract_text` | one of these | the raw contract or offer text |
| `deal_id` | one of these | read the linked contract from `pipeline/contracts/` and the deal from `pipeline/deals/` |
| `action` | required | one of: `triage`, `review`, `trace`, `legal_check`, `escalate`, `draft`, `obligations`, `debrief`, `full`, `playbook_setup` |
| `deal_context` | optional | fee, category, sponsorship type, brand name; never invented |

Supply `contract_text` or `deal_id`. The spoke reads the creator's positions from the deal-playbook
(`pipeline/user-context/deal-playbook.template.json`, real values gitignored); when it is still the
null template the atoms run in a labeled provisional mode against the generic defaults in
`shared/contract-engine.md`.

## Atoms composed

Phase 1:
- `contract-triage` -- GREEN/YELLOW/RED verdict; hidden-obligation and deal-breaker scan.
- `contract-review` -- clause-by-clause findings with dual severity and plain-language redline
  suggestions.
- `legal-requirement-check` -- FTC disclosure, usage-rights, exclusivity, and payment flags with
  cited sources.
- `escalation-brief` -- decision-ready accept/counter/walk brief; draft only, never sent.

Phase 2:
- `contract-draft` -- assembles a plain-language, not-vetted, not-binding starting point from the
  playbook standards and the deal's agreed terms; nulls unknowns; never emits operative legalese.
- `amendment-trace` -- net current state across contract versions with the difference labels and
  source precedence from `shared/contract-engine.md`; quotes exactly, flags conflicts.
- `playbook-bootstrap` -- proposal-only: bootstrap a starting playbook from example contracts, or
  nudge an off-standard default from recent deals; never writes the playbook (the human confirms).

Phase 3:
- `obligation-extract` -- pulls deliverables, deadlines, and payment terms from a signed contract into
  obligation rows (one per duty, quoted evidence); hands them to `tools/obligations.py` for the offline
  date math; never computes dates or writes the register itself.
- `deal-debrief` -- proposal-only close-out memory: records why off-standard terms were accepted and
  proposes playbook updates; never writes the playbook.

Reused and governance:
- `usage-rights-check` and `exclusivity-check` -- the extraction and conflict-detection core.
- `govern-artifact` -- runs the quality gate before any output is surfaced.

## Workflow

For `action: full`: `contract-triage` then, unless triage is a clear walk-away RED, `contract-review`,
`amendment-trace` (when two or more versions exist), and `legal-requirement-check`, then
`escalation-brief` on the flagged items, then `govern-artifact`. `contract-draft` (`action: draft`)
and `playbook-bootstrap` (`action: playbook_setup`) run outside the review chain and still pass through
`govern-artifact`. Each atom is also directly callable via `shortcut_atoms`.

## Engines required

- `shared/contract-engine.md` -- clause taxonomy, four-tier playbook model, dual severity, confidence
  labels, amendment model, deadline math, curated sources, and the non-advisory boundary.
- `shared/pipeline-engine.md` -- deal lifecycle, the Contract Review entry rule, and the contract
  record's link to the deal.

## References

- `protocols/safety.md` -- the legal boundary and FTC disclosure rules.
- `protocols/no-fabrication.md` -- never invent clause language, dates, fees, or citations; null and
  flag.
- `protocols/quality-gates.md` -- every output passes the quality gate via `govern-artifact`.
- `pipeline/contracts/contract.template.json` -- the contract-artifact store schema.
- `canonical-sources/source-registry.json` -- the FTC and reference sources cited by
  `legal-requirement-check`.

## Do NOT use for

- Ruling on enforceability, validity, or which party would prevail (that requires a licensed attorney).
- Drafting binding contract language, signing, or sending anything to a brand.
- Managing the deal's stage transitions or CRM record (use `deal-pipeline`).
- Media kits or outreach copy (use `partnership-mediakit`).
- Any output that bypasses the RESEARCH NOTES boundary, the human-review requirement, or
  `govern-artifact`.

## Cross-modality
Class: C.
Runs on: Claude Desktop/Code (native, MCP + the tool module); claude.ai via a hosted remote-MCP connector; Custom GPT / Gemini only when the tool is hosted behind a remote MCP or an Action; Gems: no.
Mechanism: tools/obligations.py deterministic date math (send-by dates with weekend/US-federal-holiday roll-backward, urgency bands, register compute) exposed via MCP tools obligation_scan / obligation_build / import_obligations; contract-engine.md reasoning atoms for triage/review/legal checks; FTC citations from canonical-sources/source-registry.json.
Fallback: No runtime or hosted seam: run the reasoning atoms (triage, review, legal-requirement-check, escalation-brief) over shared/contract-engine.md against pasted contract text; state that the obligation register date math (tools/obligations.py send-by/holiday-roll/urgency compute) is unavailable, present raw contract deadlines quoted verbatim without computed dates, flag them unverified, and never fabricate a date or obligation.
See `shared/cross-modality-engine.md`.
