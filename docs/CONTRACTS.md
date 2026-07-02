# Contract Desk (P23)

Plain-English guide to the contract-review capability. Full engine spec: `shared/contract-engine.md`.

## The one rule that shapes everything

This is legal **information**, never legal **advice**. Every contract output starts with this line,
word for word:

```
RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.
```

The system organizes, extracts, flags, and explains a contract in plain language. It never rules on
whether a term is enforceable, never drafts binding language as if a lawyer vetted it, and never
signs or sends anything. It recommends a qualified attorney whenever anything is unclear, and it
stops for an explicit human yes before any step that leads to signing, sending, or committing money.

## What it does

Feed it a brand-partnership contract (paste the text, or point at an uploaded file or a Drive
document) and it gives you four things:

1. **Triage** (GREEN / YELLOW / RED): a fast verdict so you know whether to relax, slow down, or
   stop. It looks hard for two things that hide in friendly-looking offers: an obligation buried
   where you would not look (a non-disclosure or non-compete tucked into a sponsorship), and a clause
   on your "never" list. Any hidden obligation is at least YELLOW; a likely deal-breaker is RED.
2. **Clause-by-clause review**: for each part of the contract, what your playbook wants, what the
   contract actually says (quoted exactly), the gap, and two separate severity scores: **legal risk**
   (how exposed you are) and **business friction** (how much it costs you in practice). A clause can
   be low risk but high friction, or the reverse, so they are never merged. Each finding comes with a
   plain-language change you could ask for.
3. **Legal-requirement check**: a fixed checklist of the rules that matter to a US creator, each with
   a cited source. FTC disclosure (a contract cannot waive it), usage-rights that go too far,
   perpetual usage paired with a flat fee, exclusivity that overlaps another deal, and missing
   payment or kill-fee terms.
4. **Escalation brief**: the flagged points turned into a one-page, decision-ready list. For each
   issue: the exact quote, your three options (accept, counter, walk) with the trade-off of each, and
   a decide-by date. This is a draft for you and your attorney. It is never sent, and producing it
   never commits you to anything.

## Your playbook makes it yours

The review is only as sharp as your own positions. `pipeline/user-context/deal-playbook.template.json`
holds a four-tier library for each clause: your **standard** opening position, the **fallbacks** you
can live with, the **never** lines you will not cross, and the **one thing** that matters most. Copy
it to `deal-playbook.local.json` (gitignored, never committed) and fill it in. Until you do, the
review still runs, but it is clearly labeled `[PROVISIONAL: no playbook configured]` and compares
against generic creator-side defaults instead of your real positions.

You do not have to start from scratch. `playbook-bootstrap` can read a few of your past contracts and
**propose** a starting playbook, each proposed position backed by a quote from the example, and it can
watch your recent deals and nudge you ("you accepted this off-standard term in your last few deals,
update your default?"). It is proposal-only: it never writes your playbook. You confirm, edit, and
save `deal-playbook.local.json` yourself.

## Where contracts live

The contract itself is stored in `pipeline/contracts/` as a record linked to its deal. Only the
schema (`pipeline/contracts/contract.template.json`) is committed; the real contract, including its
raw text, lives in a gitignored `.local.json` file and never enters git. On the deal side, the deal
record now carries a `contract_ref` that links to the contract, and a `contract_text` field the
review can read from.

## The switches (all off by default)

Contract Desk is one master switch plus four features, set in `creator-os-config.json`:

- `contract_management` (master): turns on the contract-desk spoke. With it off, nothing changes:
  your deals still get the plain-language term summary and attention flags at the
  contract-negotiating stage, exactly as before.
- `contract_redline`: the full clause-by-clause review, and (Phase 2) version tracing across
  amendments (the net-current-state view of what the agreement says now).
- `legal_requirement_checks`: the FTC and usage/exclusivity/payment checklist.
- `contract_drafting` (Phase 2): assemble a plain-language starting point from your playbook and the
  deal's agreed terms. It is always labeled not-vetted and not-binding, never operative legalese, and
  never signed. When off, asking to draft degrades to a summary plus a recommendation to work with a
  professional.
- `contract_obligations` (Phase 3): pull the deliverables, deadlines, and payment terms out of a
  signed contract into a dated obligation register, and feed those deadlines to your calendar and
  production tasks. The date math runs on your computer in Python (no tokens); the register is written
  only when this flag is on, but the read-only deadline scan always works. See `docs/LOCAL_CONTEXT.md`.

## What runs where

The review is knowledge work (reading and organizing text), so it works on every AI engine and
offline. There is no new connector: reading an uploaded contract reuses the document connectors you
already have. Nothing here calls a platform API or sends anything.

## How it fits the deal pipeline

`deal-pipeline` still owns the deal record, the nine-stage lifecycle, and the rule that every
sponsored deliverable must have its FTC disclosure field filled before a deal can reach `signed`.
When `contract_management` is on, the review of the contract document is handled by contract-desk;
when it is off, deal-pipeline handles contract-negotiating the way it always has.

## Try it

- "Triage this contract: [paste text]" gives the GREEN / YELLOW / RED verdict.
- "Review this brand contract against my playbook" runs the clause-by-clause review.
- "Check this contract for FTC and usage-rights issues" runs the legal-requirement checklist.
- "Draft the points I should raise with the brand" produces the escalation brief (draft only).
- "Draft a plain-language agreement from the terms we agreed" produces the not-binding starting point.
- "What does the contract say now after all the amendments?" runs the net-current-state version trace.
- "Bootstrap a playbook from these past contracts" proposes a starting playbook for you to confirm.
- "Pull the deadlines out of this signed contract" extracts obligations; the register's dates are then
  computed on your computer (`tools/obligations.py`), never in the model.
- "What do I need to act on in the next two weeks?" runs the read-only deadline scan.

## Status

Phase 1 delivered the review path: the contract-artifact store, the contract engine, the deal-playbook
template, the five flags, the curated FTC and reference sources, and four atoms (contract-triage,
contract-review, legal-requirement-check, escalation-brief).

Phase 2 delivered drafting and version tracking: `contract-draft` (a plain-language, not-binding
starting point assembled from the playbook and the deal's agreed terms), `amendment-trace` (net current
state across contract versions, with exact quotes and the difference labels), and `playbook-bootstrap`
(propose a starting playbook from example contracts, or nudge an off-standard default from recent
deals; proposal-only, never writes your playbook). All three are composed by the contract-desk spoke
and pass the same non-advisory boundary and quality gate.

Phase 3 delivered obligations, timelines, and memory: `obligation-extract` pulls the duties from a
signed contract into rows; `tools/obligations.py` computes the dated register offline (send-by dates,
weekend and US-holiday roll-back, urgency bands) so the model spends no tokens on the math, gated by
`contract_obligations` for the write; `import_obligations` feeds the deadlines to the content calendar,
production tasks, and invoicing; and `deal-debrief` proposes (never writes) playbook memory after a
deal closes. All of the creator's real data (contracts, the register, the playbook) stays in gitignored
`.local` files on the creator's machine, enforced by drift-guard invariant 19 and reported by
`tools/local_privacy.py`. See `docs/LOCAL_CONTEXT.md`.
