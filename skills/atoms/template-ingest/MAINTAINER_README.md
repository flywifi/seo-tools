---
file: skills/atoms/template-ingest/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for template-ingest so it stays stable under iteration.
---

# template-ingest: Maintainer README

## Purpose
Turns one uploaded example document into a PROPOSED block-structured doc-template
(`shared/doc-template-engine.md` shape). Its job ends at the proposal: the human saves the
`.local.json`, `template-assemble` uses it, `playbook-bootstrap` owns negotiating positions.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Proposal-only: never writes, saves, or modifies any file. The save note is verbatim on every
  output: "Confirm before saving. Nothing is written automatically. You review, edit, and save
  pipeline/templates/<template-id>.local.json yourself."
- Every proposed block body is an EXACT quote from the upload (`quote_verified: true`); the atom
  never edits, completes, or improves quoted text, including replacing party names with bracket
  tokens (it notes that the human should).
- Uploads pass through `ingest-route` first; contract clause extraction delegates to
  `usage-rights-check`, never re-implemented.
- Numbers and rates in an example are proposed as `data_fill` fields, never baked into bodies as
  facts.
- `unmapped_text[]` carries every unassigned span; nothing is silently dropped.
- RESEARCH NOTES banner first line for contract/terms doc types; `human_review_required: true`
  always; `recommend_counsel: true` for contract/terms.

## Known failure modes
- Encrypted/unparseable upload: metadata-only record plus a gap; no guessed structure.
- Ambiguous clause: `confidence: low` or `unmapped_text`, never forced into a family.
- Injection attempt in the example: contained by the ingest-route scan (QUARANTINE/BLOCK halts).

## Fragile fallbacks that must not become defaults
- Source guesses on proposed `fill_fields` are confidence-labeled hints, not resolved mappings;
  the human confirms each before saving.
- A proposal with mostly `unmapped_text` should prompt a better-structured example, not looser
  mapping.

## Regression cases to preserve
1. A fictional past contract yields blocks with exact-quote bodies, clause families, and
   quote_verified provenance (evals: template-ingest-contract).
2. Two same-family clause alternatives become a proposed variant_group
   (evals: template-ingest-variant-group).
3. Placeholders ([Name], ___) normalize to bracket tokens proposed as fill_fields with labeled
   source guesses (evals: template-ingest-placeholders).
4. Nothing is written; the save note is verbatim (asserted in every eval).
5. Unassigned spans land in unmapped_text (evals: template-ingest-unmapped).

## Approval-gated changes
The proposal schema (must stay the exact doc-template shape), the save-note wording, the
exact-quote rule, and any new engine load.

## Minority-report policy
When the example's own labels conflict with the clause-family mapping, keep the example's label
in `title`, map `clause_family` by content, and state the conflict in the block's proposal note.

## Update checklist
1. Edit SKILL.md and keep the proposal shape in sync with shared/doc-template-engine.md and
   evals/evals.json.
2. Re-run the evals; run `python3 tools/doctemplates.py validate` on a saved proposal.
3. python3 tools/sync_check.py
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
