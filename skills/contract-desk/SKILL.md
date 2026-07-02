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
- `contract_redline`: enables the full clause-by-clause review; version tracing (amendment-trace) is
  Phase 2.
- `contract_drafting` (Phase 2) and `contract_obligations` (Phase 3): drafting and the obligation
  register are not built in Phase 1. Requests for them degrade honestly to a plain-language summary
  plus a recommendation to proceed with a qualified professional (see `creator-os-config.json`
  degraded_behavior).

## What Phase 1 delivers

Feed a brand contract (uploaded file or pasted text, reusing the existing document connectors; no new
connector is added) and the spoke produces: a triage verdict, a clause review with dual severity and
exact quotes, legal-requirement flags with cited FTC and reference sources, and an escalation brief of
the points worth raising with the brand and an attorney.

## Inputs

| Field | Required | Notes |
|---|---|---|
| `contract_text` | one of these | the raw contract or offer text |
| `deal_id` | one of these | read the linked contract from `pipeline/contracts/` and the deal from `pipeline/deals/` |
| `action` | required | one of: `triage`, `review`, `legal_check`, `escalate`, `full` |
| `deal_context` | optional | fee, category, sponsorship type, brand name; never invented |

Supply `contract_text` or `deal_id`. The spoke reads the creator's positions from the deal-playbook
(`pipeline/user-context/deal-playbook.template.json`, real values gitignored); when it is still the
null template the atoms run in a labeled provisional mode against the generic defaults in
`shared/contract-engine.md`.

## Atoms composed (Phase 1)

- `contract-triage` -- GREEN/YELLOW/RED verdict; hidden-obligation and deal-breaker scan.
- `contract-review` -- clause-by-clause findings with dual severity and plain-language redline
  suggestions.
- `legal-requirement-check` -- FTC disclosure, usage-rights, exclusivity, and payment flags with
  cited sources.
- `escalation-brief` -- decision-ready accept/counter/walk brief; draft only, never sent.
- `usage-rights-check` and `exclusivity-check` -- reused as the extraction and conflict-detection core.
- `govern-artifact` -- runs the quality gate before any output is surfaced.

## Workflow

For `action: full`: `contract-triage` then, unless triage is a clear walk-away RED, `contract-review`
and `legal-requirement-check`, then `escalation-brief` on the flagged items, then `govern-artifact`.
Each atom is also directly callable via `shortcut_atoms`.

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
