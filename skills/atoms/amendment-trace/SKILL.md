---
file: skills/atoms/amendment-trace/SKILL.md
name: amendment-trace
atom: true
description: "traces two or more versions of a brand contract into a NET CURRENT STATE view: for each topic it quotes what the operative agreement says now after all amendments (with its source version), classifies every material difference with exactly one label (unchanged, clarified, expanded, narrowed, added, removed, contradictory, uncertain), applies the engine's source-precedence order, and lists watch_items and conflicts; outputs legal information only (not legal advice); does NOT rule on enforceability, validity, or which version wins as a matter of law, and never drafts binding language."
load:
  - shared/contract-engine.md
  - shared/pipeline-engine.md
  - protocols/safety.md
  - protocols/no-fabrication.md
---

# amendment-trace

Trace a brand-partnership contract across two or more versions and produce a net current state view:
for each topic or clause, what the operative agreement says right now after all amendments, quoted
exactly with its source version; a change_log that classifies every material difference; and the
watch_items and conflicts a human should look at. It aligns versions, applies the document
source-precedence order from `shared/contract-engine.md`, and quotes exactly. It never rules on
enforceability or validity and never drafts binding language. Legal information only, NOT legal advice.

## First line of every output (verbatim)

```
RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.
```

## Purpose

When a deal has gone through redlines, amendments, or side letters, the operative agreement is spread
across several documents and nobody can see the current picture at a glance. This atom reconstructs it.
For each topic it names the governing wording, quotes it verbatim, and says which version it came from;
for each material difference it records the before and after text and tags it with exactly one of the
difference labels defined in the engine's "Amendment and version model" section; and it surfaces the
conflicts and watch_items that deserve human and attorney attention. It organizes and describes the
document record. It does not decide which version legally controls, whether an amendment is valid, or
whether a clause is enforceable. Those are for a licensed attorney.

## Inputs

```json
{
  "contract_id": "string or null -- read the versions[] from the contract record in pipeline/contracts/ (raw text lives only in the gitignored .local.json)",
  "versions": "array or null -- supply directly when not reading from the store; each item { \"version\": string, \"text\": string or null, \"ref\": string or null, \"received_date\": string or null }",
  "focus": "string or null -- optional topic or clause family to prioritize; all topics are still traced"
}
```

- Supply `contract_id` OR `versions`. If neither resolves, return `{ "error": "no_source", "message": "supply contract_id or versions[]" }`.
- Tracing requires at least two versions with resolvable text. If fewer than two resolve, return
  `{ "error": "insufficient_versions", "message": "amendment-trace needs two or more versions with text; found N" }` and never invent a second version.
- Each version item carries either inline `text` or a `ref`. When a `ref` cannot be resolved to text,
  do not guess its contents: set `provisional: true`, list the ref in `retrieval_gaps`, and trace only
  the resolvable versions.
- This atom compares versions against each other, not against the creator's playbook, so it does not
  run in playbook-provisional mode. It reads clause families and difference labels from
  `shared/contract-engine.md`. Reuse `usage-rights-check` for per-version clause extraction rather than
  re-parsing rights, exclusivity, ownership, and FTC language.

## Procedure

1. Resolve inputs. Read `versions[]` from the contract record when `contract_id` is given; otherwise use
   the supplied `versions`. Rank each version by the engine's source-precedence order (final signed or
   latest operative text first, then an explicit amendment or side letter, then an order form or exhibit
   tied by exact reference, then a redline or comparison copy, then conservative structural inference,
   otherwise missing or uncertain).
2. Align topics across versions by section number first, then by exact heading; if numbering differs,
   align by clause topic. When alignment is weak, record `aligned_by: "weak"` and prefer the `uncertain`
   label over forcing a match.
3. For each aligned topic, determine the operative wording from the highest-precedence version that
   addresses it and quote it exactly into `operative_text` with its `source_version` and
   `source_section`. If no version has language on a topic that an earlier version had, that is a
   `removed` change, not a blank.
4. Build the `change_log`: one entry per material difference, with `from_text` and `to_text` quoted
   exactly from their versions and exactly one `label` from `unchanged`, `clarified`, `expanded`,
   `narrowed`, `added`, `removed`, `contradictory`, or `uncertain`. Describe the difference in plain
   language in `why`; never state that a change is or is not enforceable or valid.
5. Record `conflicts` when two versions carry directly contradictory wording on the same topic. State
   which version governs under document source-precedence in `resolved_by_precedence`, or `null` when
   precedence does not resolve it (for example, two undated drafts). This is a document-ordering
   observation, not a legal ruling.
6. Populate `watch_items` with the material changes a human should look at (a narrowed license, an added
   exclusivity window, a removed kill fee, any `contradictory` or `uncertain` topic).
7. Set `human_review_required: true`. Default `recommend_counsel: true` whenever anything is
   `contradictory`, `uncertain`, weakly aligned, or a version could not be resolved; it may be `false`
   only when every topic aligns cleanly, no conflicts exist, and every difference is `unchanged` or a
   plainly `clarified` wording change.

## Output

```json
{
  "header": "RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.",
  "tool": "amendment-trace",
  "provisional": false,
  "contract_id": "string or null",
  "versions_compared": [
    {
      "version": "string -- the version label as supplied",
      "received_date": "string or null -- never invented",
      "source_connector": "string or null -- uploaded_file | google_drive | email | manual, when known",
      "precedence_rank": "integer -- 1 is highest per the engine's source-precedence order",
      "text_resolved": true
    }
  ],
  "net_current_state": [
    {
      "topic": "string -- clause family or the contract's own heading",
      "aligned_by": "section_number | heading | topic | weak",
      "operative_text": "string quoted exactly from the governing version, or null if no version addresses it",
      "source_version": "string -- which version the operative text comes from, or null",
      "source_section": "string or null -- section number or heading in that version",
      "superseded_versions": ["string -- versions whose wording on this topic no longer governs"],
      "confidence": "explicit | high | medium | low",
      "notes": "string or null"
    }
  ],
  "change_log": [
    {
      "topic": "string",
      "section_or_heading": "string or null",
      "label": "unchanged | clarified | expanded | narrowed | added | removed | contradictory | uncertain",
      "from_version": "string or null",
      "from_text": "string quoted exactly, or null when the topic was added",
      "to_version": "string or null",
      "to_text": "string quoted exactly, or null when the topic was removed",
      "why": "string -- plain-language description of the difference; never an enforceability or validity claim",
      "confidence": "explicit | high | medium | low"
    }
  ],
  "watch_items": ["string -- material changes that deserve human and attorney attention"],
  "conflicts": [
    {
      "topic": "string",
      "description": "string -- the contradiction between versions, described not resolved",
      "versions_involved": ["string"],
      "resolved_by_precedence": "string or null -- the version that governs under document source-precedence, or null when precedence does not resolve it",
      "evidence_text": {"earlier": "string quoted", "later": "string quoted"}
    }
  ],
  "source_precedence_applied": ["string -- the ordered precedence rules used, from shared/contract-engine.md"],
  "recommend_counsel": true,
  "counsel_reason": "string or null",
  "human_review_required": true,
  "retrieval_gaps": ["string -- version labels or refs whose text could not be resolved"]
}
```

Field rules:
- `operative_text`, `from_text`, `to_text`, and every `evidence_text` value are quoted exactly from a
  source version or are `null`. Never paraphrase into a quote and never invent clause language, dates,
  fees, party names, or version labels.
- `label` is exactly one of the eight difference labels in `shared/contract-engine.md`. Do not coin new
  labels and do not attach two labels to one difference.
- `resolved_by_precedence` reports document ordering only. It never states that a version is legally
  valid, controlling as a matter of law, or that a term is enforceable.
- A topic present in an earlier version and absent from the operative one is a `removed` entry with
  `to_text: null`, not a dropped row.
- When alignment is weak, use `aligned_by: "weak"` and the `uncertain` label rather than forcing a
  match; add the topic to `watch_items` and set `recommend_counsel: true`.
- `provisional` is `true` whenever one or more versions were supplied as a `ref` that could not be
  resolved to text; those refs appear in `retrieval_gaps`.

## Do NOT use for

- Ruling on enforceability, validity, or which version legally controls (that requires a licensed
  attorney; this atom applies document source-precedence to describe the operative wording, nothing
  more).
- Drafting a binding amendment, addendum, or agreement (Phase 2 contract drafting produces a
  plain-language, labeled not-vetted draft; it is not this atom and never emits binding language).
- The single-document clause-by-clause review against the playbook (use `contract-review`) or the fast
  inbound verdict (use `contract-triage`).
- Re-implementing rights, exclusivity, ownership, or FTC extraction (call `usage-rights-check`) or
  cross-deal exclusivity conflict detection (use `exclusivity-check`).
- Writing to `pipeline/contracts/` or `pipeline/deals/` (a CRM write atom does that).
- Releasing output without passing through `govern-artifact`.

## Pipeline note

Reads `versions[]` from the contract record (`pipeline/contracts/contract.template.json`; raw text lives
only in the gitignored `.local.json`) or from supplied `versions`. Uses the amendment and version model,
the eight difference labels, and the source-precedence order defined in `shared/contract-engine.md`, and
the deal linkage in `shared/pipeline-engine.md`. Composes `usage-rights-check` for per-version clause
extraction. Feeds its `conflicts` and `watch_items` into `escalation-brief`. Obeys
`protocols/no-fabrication.md` and `protocols/safety.md`. Pass output to `govern-artifact` before the
spoke surfaces it.
