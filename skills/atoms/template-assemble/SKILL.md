---
name: template-assemble
atom: true
standalone: true
description: "assembles a document from a saved creator doc-template by selecting, swapping, or excluding whole blocks per the situation and delegating the mechanical fill to tools/doctemplates.py: bracketed fields resolve from the deal record, creator profile, rate card, or a supplied export, and the creator's vetted text passes through byte-for-byte. Triggers: 'draft the CoolBreeze agreement from my template', 'build my rate card doc', 'assemble the terms sheet without the exclusivity clause'. Do NOT use to create or edit a template (template-ingest proposes; the human saves), to draft plain-language terms with no template (contract-draft), or to author, rephrase, or improve any block text (whole-block swap and bracket fill only)."
engines_required:
  - shared/doc-template-engine.md
protocols:
  - protocols/safety.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# template-assemble

A saved template plus a situation in, an assembled document out. The model's judgment picks which
blocks apply; the code does everything that touches text. No sentence in the output was written
by the system.

## First line of every output (verbatim, for contract and terms_conditions doc types)

```
RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.
```

## When to use this skill
- "draft the agreement from my vetted template for this deal", "assemble my rate card document",
  "build the terms sheet, no exclusivity this time". Contracts arrive via `contract_draft`
  routing when a vetted template exists; other doc types via `document_create`
  (`artifact_type: from_template`).

Do NOT use for:
- Creating or editing a template (use `template-ingest`; the human saves the file).
- Drafting plain-language contract terms when no vetted template exists (use `contract-draft`).
- Authoring, rephrasing, completing, or improving block text. A missing fill stays bracketed and
  gapped; the model never substitutes its own prose into a `vetted_text` block
  (`shared/doc-template-engine.md` authorship boundary).
- Sending or signing anything; `ready_to_sign` is always false for contract and terms documents.

## Inputs

```json
{
  "template_id": "the saved template in pipeline/templates/ (local resolves first)",
  "deal_id": "string or null -- fills deal-sourced fields and informs selection",
  "situation": "what applies this time, in plain language",
  "data": {"analytics_export": "path to a human-saved .local.json, when the template needs it"}
}
```

## Core procedure
Follow `shared/method.md` and the selection semantics in `shared/doc-template-engine.md`.

### Step 1: judge the selection (model)
Read the template's blocks and each block's advisory `applicability.conditions`, the deal record,
and the playbook. Produce the selections object (`include`, `exclude`, `variants`, `reasons`)
with a stated reason for every exclusion and swap. Manual fill values follow the contract-draft
precedence: an explicitly agreed term first, else the playbook standard, labeled; a value with no
source stays unfilled and becomes a gap. Never invent a value.

### Step 2: assemble mechanically (code)
Run `python3 tools/doctemplates.py assemble <template> --select <selections.json>
[--deal <id>] [--data analytics_export=<path>] [--fills <fills.json>]`. The tool resolves the
selection structurally (variant exclusivity, never_with, requires; violations abort with
`selection_errors`), substitutes bracketed fields from the offline sources, and concatenates the
selected bodies. Unfilled fields stay bracketed AND appear in `gaps[]` with a
`recommended_next_step`.

### Step 3: envelope and gate
Present the tool output plus `selection_rationale[]` (one entry per swap or exclusion, from the
`reasons` object). For contract and terms documents: the banner is line 1, `ready_to_sign: false`,
`recommend_counsel: true`, and profile-sourced gaps are mirrored into `profile_gaps[]` with the
contract-draft field names (`legal_name`, `business_address`, `governing_law_state`). Pass the
artifact through `govern-artifact` before the spoke surfaces it.

## Output contract
The `tools/doctemplates.py assemble` result verbatim (`document_text`, `blocks_used` with
per-block provenance tags, `selection_resolved`, `selection_errors`, `gaps`,
`human_review_required: true`) plus `selection_rationale[]` and the contract safety fields above.

## Standalone usability
Given a saved template and a deal id, the assembled document with named gaps is complete decision
support on its own.

## Failure modes
- No saved template: the atom reports it and points at `template-ingest` plus the committed
  starters under `pipeline/templates/`; nothing is assembled from thin air.
- Selection violates the template's structure (two variants of one group, a required group
  emptied, never_with/requires broken): the tool aborts with `selection_errors`; the atom
  surfaces them verbatim and proposes a corrected selection for the human.
- Missing profile, deal, or rate-card values: bracketed tokens remain in the text with named
  gaps; for contracts these mirror into `profile_gaps[]`.
- `document_templates` flag off: assembly still computes read-only; persistence is refused with
  the `_gate` message naming the flag and the wizard /brand-deals route.

## Cross-modality
Inherits its calling spoke's class (Class C); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
